use axum::{
    extract::{Json, State},
    http::StatusCode,
    response::IntoResponse,
    Extension,
};
use axum_extra::extract::cookie::{Cookie, CookieJar, SameSite};
use serde::{Deserialize, Serialize};
use time::Duration;

use crate::{auth::role::Role, middleware::auth::AuthContext, state::ApiState};

pub const SESSION_COOKIE_NAME: &str = "gewebe_session";

fn build_session_cookie(value: String, max_age: Option<Duration>) -> Cookie<'static> {
    // Default to secure, but allow override via env for local dev (http)
    let secure_cookies = std::env::var("AUTH_COOKIE_SECURE")
        .map(|v| v != "0" && !v.eq_ignore_ascii_case("false"))
        .unwrap_or(true);

    let mut builder = Cookie::build((SESSION_COOKIE_NAME, value))
        .path("/")
        .http_only(true)
        .same_site(SameSite::Strict)
        .secure(secure_cookies);

    if let Some(age) = max_age {
        builder = builder.max_age(age);
    }

    builder.build()
}

#[derive(Deserialize)]
pub struct LoginRequest {
    pub account_id: String,
}

#[derive(Serialize)]
pub struct AuthStatus {
    pub authenticated: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub account_id: Option<String>,
    pub role: Role,
}

#[derive(Serialize)]
pub struct DevAccount {
    pub id: String,
    pub title: String,
    pub summary: Option<String>,
    pub role: Role,
}

pub async fn list_dev_accounts(
    State(state): State<ApiState>,
    headers: axum::http::HeaderMap,
) -> Result<Json<Vec<DevAccount>>, StatusCode> {
    let dev_login_enabled = std::env::var("AUTH_DEV_LOGIN")
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false);

    if !dev_login_enabled {
        return Err(StatusCode::NOT_FOUND);
    }

    let allow_remote = std::env::var("AUTH_DEV_LOGIN_ALLOW_REMOTE")
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false);

    let host = headers
        .get(axum::http::header::HOST)
        .and_then(|h| h.to_str().ok())
        .unwrap_or("");

    // Simple localhost detection (stripping ports and brackets)
    let hostname = if host.starts_with('[') {
        // IPv6 literal, e.g. [::1] or [::1]:8080
        if let Some(end) = host.rfind(']') {
            &host[1..end] // Strip brackets to get pure ::1
        } else {
            host
        }
    } else {
        // IPv4 or domain, strip port
        host.split(':').next().unwrap_or(host)
    };

    let is_localhost = matches!(hostname, "localhost" | "127.0.0.1" | "::1");

    tracing::warn!(
        host = host,
        remote = !is_localhost,
        allow_remote = allow_remote,
        "dev-login endpoint accessed"
    );

    if !is_localhost && !allow_remote {
        return Err(StatusCode::FORBIDDEN);
    }

    let mut accounts: Vec<DevAccount> = state
        .accounts
        .values()
        .map(|acc| DevAccount {
            id: acc.public.id.clone(),
            title: acc.public.title.clone(),
            summary: acc.public.summary.clone(),
            role: acc.role.clone(),
        })
        .collect();

    // Sort by ID for deterministic order
    accounts.sort_by(|a, b| a.id.cmp(&b.id));

    Ok(Json(accounts))
}

pub async fn login(
    State(state): State<ApiState>,
    jar: CookieJar,
    Json(payload): Json<LoginRequest>,
) -> impl IntoResponse {
    // SECURITY: Dev-Login only active if explicitly enabled via feature flag
    let dev_login_enabled = std::env::var("AUTH_DEV_LOGIN")
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false);

    if !dev_login_enabled {
        tracing::warn!("Login attempt refused: AUTH_DEV_LOGIN is not enabled");
        return (jar, StatusCode::NOT_FOUND);
    }

    if !state.accounts.contains_key(&payload.account_id) {
        tracing::warn!(?payload.account_id, "Login attempt refused: Account not found");
        return (jar, StatusCode::BAD_REQUEST);
    }

    let session = state.sessions.create(payload.account_id);

    let cookie = build_session_cookie(session.id, None);

    (jar.add(cookie), StatusCode::OK)
}

pub async fn logout(State(state): State<ApiState>, jar: CookieJar) -> impl IntoResponse {
    if let Some(cookie) = jar.get(SESSION_COOKIE_NAME) {
        state.sessions.delete(cookie.value());
    }

    let cookie = build_session_cookie("".to_string(), Some(Duration::seconds(0)));

    (jar.add(cookie), StatusCode::OK)
}

pub async fn me(Extension(ctx): Extension<AuthContext>) -> impl IntoResponse {
    Json(AuthStatus {
        authenticated: ctx.authenticated,
        account_id: ctx.account_id,
        role: ctx.role,
    })
}
