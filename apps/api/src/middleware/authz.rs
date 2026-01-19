use axum::http::Method;
use axum::{body::Body, http::Request, middleware::Next, response::Response};
use axum::{http::StatusCode, response::IntoResponse};

use crate::auth::role::Role;
use crate::middleware::auth::AuthContext;

/// Gate for write endpoints:
/// - Safe methods (GET, HEAD, OPTIONS) pass through.
/// - Others:
///   - no valid session -> 401
///   - authenticated as Gast -> 403
pub async fn require_write(req: Request<Body>, next: Next) -> Response {
    if req.method() == Method::GET || req.method() == Method::HEAD || req.method() == Method::OPTIONS
    {
        return next.run(req).await;
    }

    let ctx = req
        .extensions()
        .get::<AuthContext>()
        .cloned()
        .unwrap_or(AuthContext {
            authenticated: false,
            account_id: None,
            role: Role::Gast,
        });

    if !ctx.authenticated {
        return StatusCode::UNAUTHORIZED.into_response();
    }
    if ctx.role == Role::Gast {
        return StatusCode::FORBIDDEN.into_response();
    }

    next.run(req).await
}
