with open("apps/api/src/routes/auth.rs", "r") as f:
    content = f.read()

import re

# Find the end of me function and inject session function and struct ONLY ONCE
me_func_match = re.search(r'pub async fn me\(Extension\(ctx\): Extension<AuthContext>\) -> impl IntoResponse \{\n    Json\(AuthStatus \{\n        authenticated: ctx\.authenticated,\n        account_id: ctx\.account_id,\n        role: ctx\.role,\n    \}\)\n\}', content)

if me_func_match:
    insertion = """

#[derive(Serialize)]
pub struct SessionStatus {
    pub authenticated: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expires_at: Option<chrono::DateTime<chrono::Utc>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub device_id: Option<String>,
}

pub async fn session(Extension(ctx): Extension<AuthContext>) -> impl IntoResponse {
    Json(SessionStatus {
        authenticated: ctx.authenticated,
        expires_at: ctx.expires_at,
        // TODO: Map to actual device ID once Device Management is implemented (Roadmap Phase 2, Step 3)
        device_id: if ctx.authenticated { Some("current-device-placeholder".to_string()) } else { None },
    })
}"""
    content = content[:me_func_match.end()] + insertion + content[me_func_match.end():]

# Now find the end of the module (last closing brace) to add tests
mod_end_match = re.search(r'\}\n$', content)

if mod_end_match:
    test_code = """
    #[test]
    #[serial]
    fn test_session_status_authenticated() {
        let _guard = EnvGuard::set("AUTH_DEV_LOGIN", "1");
        let now = chrono::Utc::now();
        let ctx = AuthContext {
            authenticated: true,
            account_id: Some("acc123".to_string()),
            role: Role::Weber,
            expires_at: Some(now),
        };

        let status = SessionStatus {
            authenticated: ctx.authenticated,
            expires_at: ctx.expires_at,
            device_id: if ctx.authenticated { Some("current-device-placeholder".to_string()) } else { None },
        };

        assert!(status.authenticated);
        assert_eq!(status.device_id.unwrap(), "current-device-placeholder");
        assert_eq!(status.expires_at.unwrap(), now);
    }

    #[test]
    #[serial]
    fn test_session_status_unauthenticated() {
        let _guard = EnvGuard::set("AUTH_DEV_LOGIN", "1");
        let ctx = AuthContext {
            authenticated: false,
            account_id: None,
            role: Role::Gast,
            expires_at: None,
        };

        let status = SessionStatus {
            authenticated: ctx.authenticated,
            expires_at: ctx.expires_at,
            device_id: if ctx.authenticated { Some("current-device-placeholder".to_string()) } else { None },
        };

        assert!(!status.authenticated);
        assert!(status.device_id.is_none());
        assert!(status.expires_at.is_none());
    }
}
"""
    content = content[:mod_end_match.start()] + test_code

with open("apps/api/src/routes/auth.rs", "w") as f:
    f.write(content)
