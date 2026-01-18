use axum::{
    extract::{Json, State},
    http::StatusCode,
    response::IntoResponse,
};
use axum_extra::extract::cookie::{Cookie, CookieJar, SameSite};
use serde::{Deserialize, Serialize};
use time::Duration;

use crate::state::ApiState;

pub const SESSION_COOKIE_NAME: &str = "gewebe_session";

#[derive(Deserialize)]
pub struct LoginRequest {
    pub account_id: String,
}

#[derive(Serialize)]
pub struct AuthStatus {
    pub authenticated: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub account_id: Option<String>,
    pub role: String,
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

    let session = state.sessions.create(payload.account_id);

    let cookie = Cookie::build((SESSION_COOKIE_NAME, session.id))
        .path("/")
        .http_only(true)
        .same_site(SameSite::Strict)
        .build();

    (jar.add(cookie), StatusCode::OK)
}

pub async fn logout(State(state): State<ApiState>, jar: CookieJar) -> impl IntoResponse {
    if let Some(cookie) = jar.get(SESSION_COOKIE_NAME) {
        state.sessions.delete(cookie.value());
    }

    let cookie = Cookie::build((SESSION_COOKIE_NAME, ""))
        .path("/")
        .http_only(true)
        .same_site(SameSite::Strict)
        .max_age(Duration::seconds(0))
        .build();

    (jar.add(cookie), StatusCode::OK)
}

pub async fn me(State(state): State<ApiState>, jar: CookieJar) -> impl IntoResponse {
    let mut authenticated = false;
    let mut account_id = None;
    let mut role = "gast".to_string();

    if let Some(cookie) = jar.get(SESSION_COOKIE_NAME) {
        if let Some(session) = state.sessions.get(cookie.value()) {
            authenticated = true;
            account_id = Some(session.account_id);
            role = "weber".to_string();
        }
    }

    Json(AuthStatus {
        authenticated,
        account_id,
        role,
    })
}
