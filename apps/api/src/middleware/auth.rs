use axum::{body::Body, extract::State, http::Request, middleware::Next, response::Response};
use axum_extra::extract::cookie::CookieJar;

use crate::{routes::auth::SESSION_COOKIE_NAME, state::ApiState};

#[derive(Clone, Debug)]
pub struct AuthContext {
    pub authenticated: bool,
    pub account_id: Option<String>,
    pub role: String,
}

pub async fn auth_middleware(
    State(state): State<ApiState>,
    jar: CookieJar,
    mut request: Request<Body>,
    next: Next,
) -> Response {
    let mut ctx = AuthContext {
        authenticated: false,
        account_id: None,
        role: "gast".to_string(),
    };

    if let Some(cookie) = jar.get(SESSION_COOKIE_NAME) {
        if let Some(session) = state.sessions.get(cookie.value()) {
            ctx.authenticated = true;
            ctx.account_id = Some(session.account_id);
            ctx.role = "weber".to_string();
        }
    }

    request.extensions_mut().insert(ctx);
    next.run(request).await
}
