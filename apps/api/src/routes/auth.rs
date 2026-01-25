use axum::{
    extract::{ConnectInfo, Json, State},
    http::StatusCode,
    response::IntoResponse,
    Extension,
};
use axum_extra::extract::cookie::{Cookie, CookieJar, SameSite};
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
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

/// Checks if dev-login is enabled and if the request is from an allowed source.
/// Returns Ok(()) if the request should be allowed, or Err(StatusCode) otherwise.
fn check_dev_login_guard(addr: SocketAddr) -> Result<(), StatusCode> {
    let dev_login_enabled = std::env::var("AUTH_DEV_LOGIN")
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false);

    if !dev_login_enabled {
        return Err(StatusCode::NOT_FOUND);
    }

    let allow_remote = std::env::var("AUTH_DEV_LOGIN_ALLOW_REMOTE")
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false);

    // Check if the client address is localhost (IPv4 or IPv6)
    let is_localhost = match addr.ip() {
        std::net::IpAddr::V4(ip) => ip.is_loopback(),
        std::net::IpAddr::V6(ip) => ip.is_loopback(),
    };

    if !is_localhost && !allow_remote {
        return Err(StatusCode::FORBIDDEN);
    }

    Ok(())
}

pub async fn list_dev_accounts(
    State(state): State<ApiState>,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
) -> Result<Json<Vec<DevAccount>>, StatusCode> {
    check_dev_login_guard(addr)?;

    // Check if the client address is localhost (IPv4 or IPv6)
    let is_localhost = match addr.ip() {
        std::net::IpAddr::V4(ip) => ip.is_loopback(),
        std::net::IpAddr::V6(ip) => ip.is_loopback(),
    };

    let allow_remote = std::env::var("AUTH_DEV_LOGIN_ALLOW_REMOTE")
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false);

    tracing::warn!(
        client_addr = %addr,
        is_localhost = is_localhost,
        allow_remote = allow_remote,
        "dev-login endpoint accessed"
    );

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
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    jar: CookieJar,
    Json(payload): Json<LoginRequest>,
) -> impl IntoResponse {
    // Check dev-login guard (enabled + localhost/remote check)
    if let Err(status) = check_dev_login_guard(addr) {
        if status == StatusCode::NOT_FOUND {
            tracing::warn!("Login attempt refused: AUTH_DEV_LOGIN is not enabled");
        } else if status == StatusCode::FORBIDDEN {
            tracing::warn!(
                client_addr = %addr,
                account_id = %payload.account_id,
                "Login attempt refused: remote access not allowed"
            );
        }
        return (jar, status);
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
