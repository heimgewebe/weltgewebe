with open("apps/api/src/routes/auth.rs", "r") as f:
    content = f.read()

content = content.replace(
"""pub async fn session(Extension(ctx): Extension<AuthContext>) -> impl IntoResponse {
    Json(SessionStatus {
        authenticated: ctx.authenticated,
        expires_at: ctx.expires_at,
        // TODO: Map to actual device ID once Device Management is implemented (Roadmap Phase 2, Step 3)
        device_id: if ctx.authenticated {
            Some("current-device-placeholder".to_string())
        } else {
            None
        },
    })
}""",
"""pub async fn session(Extension(ctx): Extension<AuthContext>) -> impl IntoResponse {
    Json(SessionStatus {
        authenticated: ctx.authenticated,
        expires_at: ctx.expires_at,
        // TODO: Map to actual device ID once Device Management is implemented (Roadmap Phase 2, Step 3)
        device_id: None,
    })
}"""
)

with open("apps/api/src/routes/auth.rs", "w") as f:
    f.write(content)
