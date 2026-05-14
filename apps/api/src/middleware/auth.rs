use axum::{body::Body, extract::State, http::Request, middleware::Next, response::Response};
use axum_extra::extract::cookie::CookieJar;

use crate::{auth::role::Role, routes::auth::SESSION_COOKIE_NAME, state::ApiState};

#[derive(Clone, Debug)]
pub struct AuthContext {
    pub authenticated: bool,
    pub account_id: Option<String>,
    pub device_id: Option<String>,
    pub role: Role,
    pub expires_at: Option<chrono::DateTime<chrono::Utc>>,
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
        device_id: None,
        role: Role::Gast,
        expires_at: None,
    };
    let mut session_id_to_touch = None;

    if let Some(cookie) = jar.get(SESSION_COOKIE_NAME) {
        if let Some(session) = state.sessions.get(cookie.value()).await {
            {
                let accounts = state.accounts.read().await;
                if let Some(internal) = accounts.get(&session.account_id) {
                    ctx.authenticated = true;
                    ctx.account_id = Some(session.account_id.clone());
                    ctx.device_id = Some(session.device_id.clone());
                    ctx.role = internal.role.clone();
                    ctx.expires_at = Some(session.expires_at);
                    session_id_to_touch = Some(session.id.clone());
                }
            }

            if let Some(session_id) = session_id_to_touch {
                state.sessions.touch(&session_id).await;
            }
        }
    }

    request.extensions_mut().insert(ctx);
    next.run(request).await
}
