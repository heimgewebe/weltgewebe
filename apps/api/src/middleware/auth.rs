use axum::{
    body::Body,
    extract::State,
    http::{header::SET_COOKIE, HeaderValue, Request, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
};
use axum_extra::extract::cookie::{Cookie, CookieJar, SameSite};
use chrono::{DateTime, Utc};
use time::{Duration as CookieDuration, OffsetDateTime};

use crate::{
    auth::{role::Role, session::Session},
    routes::auth::SESSION_COOKIE_NAME,
    state::ApiState,
};

#[derive(Clone, Debug)]
pub struct AuthContext {
    pub authenticated: bool,
    pub account_id: Option<String>,
    pub device_id: Option<String>,
    pub role: Role,
    pub expires_at: Option<DateTime<Utc>>,
}

fn secure_session_cookies() -> bool {
    std::env::var("AUTH_COOKIE_SECURE")
        .map(|value| value != "0" && !value.eq_ignore_ascii_case("false"))
        .unwrap_or(true)
}

fn persistent_session_cookie(session: &Session, secure: bool) -> Cookie<'static> {
    let now = Utc::now();
    let remaining_seconds = session
        .expires_at
        .signed_duration_since(now)
        .num_seconds()
        .max(0);
    let expires = OffsetDateTime::from_unix_timestamp(session.expires_at.timestamp())
        .expect("chrono session expiry must fit into cookie timestamp range");

    Cookie::build((SESSION_COOKIE_NAME, session.id.clone()))
        .path("/")
        .http_only(true)
        .same_site(SameSite::Lax)
        .secure(secure)
        .max_age(CookieDuration::seconds(remaining_seconds))
        .expires(expires)
        .build()
}

fn removal_session_cookie(secure: bool) -> Cookie<'static> {
    Cookie::build((SESSION_COOKIE_NAME, ""))
        .path("/")
        .http_only(true)
        .same_site(SameSite::Lax)
        .secure(secure)
        .max_age(CookieDuration::ZERO)
        .expires(OffsetDateTime::UNIX_EPOCH)
        .build()
}

fn append_cookie(response: &mut Response, cookie: Cookie<'static>) {
    let value = HeaderValue::try_from(cookie.to_string())
        .expect("session cookie must always form a valid Set-Cookie header");
    response.headers_mut().append(SET_COOKIE, value);
}

fn is_removal_cookie(cookie: &Cookie<'_>) -> bool {
    cookie
        .max_age()
        .map(|age| age.whole_seconds() <= 0)
        .unwrap_or(false)
}

async fn normalize_session_cookie_headers(
    state: &ApiState,
    response: &mut Response,
) -> Result<bool, crate::auth::session::SessionBackendError> {
    let existing = response
        .headers()
        .get_all(SET_COOKIE)
        .iter()
        .cloned()
        .collect::<Vec<_>>();
    if existing.is_empty() {
        return Ok(false);
    }

    response.headers_mut().remove(SET_COOKIE);
    let secure = secure_session_cookies();
    let mut saw_session_cookie = false;

    for header in existing {
        let parsed = header
            .to_str()
            .ok()
            .and_then(|value| Cookie::parse(value.to_owned()).ok())
            .map(|cookie| cookie.into_owned());

        let Some(cookie) = parsed else {
            response.headers_mut().append(SET_COOKIE, header);
            continue;
        };

        if cookie.name() != SESSION_COOKIE_NAME {
            response.headers_mut().append(SET_COOKIE, header);
            continue;
        }

        saw_session_cookie = true;
        if is_removal_cookie(&cookie) || cookie.value().is_empty() {
            append_cookie(response, removal_session_cookie(secure));
            continue;
        }

        match state.sessions.get(cookie.value()).await? {
            Some(session) => append_cookie(response, persistent_session_cookie(&session, secure)),
            None => {
                tracing::error!(
                    event = "auth.middleware.session_cookie_without_session",
                    session_id = %cookie.value(),
                    "Refusing to emit a session cookie without a matching server session"
                );
                append_cookie(response, removal_session_cookie(secure));
                return Err(crate::auth::session::SessionBackendError::Unavailable);
            }
        }
    }

    Ok(saw_session_cookie)
}

fn unavailable_response() -> Response {
    StatusCode::SERVICE_UNAVAILABLE.into_response()
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
    let mut clear_session_cookie = false;

    if let Some(cookie) = jar.get(SESSION_COOKIE_NAME) {
        let session = match state.sessions.get(cookie.value()).await {
            Ok(session) => session,
            Err(error) => {
                tracing::error!(
                    event = "auth.middleware.session_backend_failed",
                    operation = "get",
                    error = %error,
                    "Session backend operation failed during auth middleware"
                );
                return unavailable_response();
            }
        };

        if let Some(session) = session {
            let account = {
                let accounts = state.accounts.read().await;
                accounts.get(&session.account_id).cloned()
            };

            match account {
                Some(internal) if !internal.public.disabled => {
                    ctx.authenticated = true;
                    ctx.account_id = Some(session.account_id.clone());
                    ctx.device_id = Some(session.device_id.clone());
                    ctx.role = internal.role;
                    ctx.expires_at = Some(session.expires_at);
                    session_id_to_touch = Some(session.id);
                }
                Some(_) | None => {
                    clear_session_cookie = true;
                    if let Err(error) = state.sessions.delete(&session.id).await {
                        tracing::error!(
                            event = "auth.middleware.session_backend_failed",
                            operation = "delete_inactive_account_session",
                            error = %error,
                            "Failed to delete a session for a missing or disabled account"
                        );
                        return unavailable_response();
                    }
                }
            }
        } else {
            clear_session_cookie = true;
        }
    }

    if let Some(session_id) = session_id_to_touch {
        if let Err(error) = state.sessions.touch(&session_id).await {
            tracing::error!(
                event = "auth.middleware.session_backend_failed",
                operation = "touch",
                error = %error,
                "Session backend operation failed during auth middleware"
            );
            return unavailable_response();
        }
    }

    request.extensions_mut().insert(ctx);
    let mut response = next.run(request).await;
    let saw_session_cookie = match normalize_session_cookie_headers(&state, &mut response).await {
        Ok(saw_session_cookie) => saw_session_cookie,
        Err(error) => {
            tracing::error!(
                event = "auth.middleware.session_cookie_normalization_failed",
                error = %error,
                "Failed to align browser cookie expiry with the server session"
            );
            let mut response = unavailable_response();
            append_cookie(
                &mut response,
                removal_session_cookie(secure_session_cookies()),
            );
            return response;
        }
    };

    if clear_session_cookie && !saw_session_cookie {
        append_cookie(
            &mut response,
            removal_session_cookie(secure_session_cookies()),
        );
    }

    response
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Duration;

    fn session(expiry: DateTime<Utc>) -> Session {
        Session {
            id: "session-id".to_string(),
            account_id: "account-id".to_string(),
            device_id: "device-id".to_string(),
            created_at: Utc::now(),
            last_active: Utc::now(),
            expires_at: expiry,
        }
    }

    #[test]
    fn persistent_cookie_matches_server_expiry_and_security_contract() {
        let expiry = Utc::now() + Duration::days(30);
        let cookie = persistent_session_cookie(&session(expiry), true);

        assert_eq!(cookie.name(), SESSION_COOKIE_NAME);
        assert_eq!(cookie.value(), "session-id");
        assert_eq!(cookie.path(), Some("/"));
        assert_eq!(cookie.http_only(), Some(true));
        assert_eq!(cookie.secure(), Some(true));
        assert_eq!(cookie.same_site(), Some(SameSite::Lax));
        assert!(cookie.max_age().unwrap().whole_seconds() > 0);
        assert_eq!(
            cookie.expires_datetime().unwrap().unix_timestamp(),
            expiry.timestamp()
        );
    }

    #[test]
    fn removal_cookie_is_immediately_expired_with_same_scope() {
        let cookie = removal_session_cookie(false);

        assert_eq!(cookie.name(), SESSION_COOKIE_NAME);
        assert_eq!(cookie.value(), "");
        assert_eq!(cookie.path(), Some("/"));
        assert_eq!(cookie.http_only(), Some(true));
        assert_eq!(cookie.secure(), Some(false));
        assert_eq!(cookie.same_site(), Some(SameSite::Lax));
        assert_eq!(cookie.max_age().unwrap().whole_seconds(), 0);
        assert_eq!(
            cookie.expires_datetime().unwrap().unix_timestamp(),
            OffsetDateTime::UNIX_EPOCH.unix_timestamp()
        );
    }
}
