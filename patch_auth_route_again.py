import sys

with open("apps/api/src/routes/auth.rs", "r", encoding="utf-8") as f:
    content = f.read()

target = """pub async fn me(Extension(ctx): Extension<AuthContext>) -> impl IntoResponse {
    Json(AuthStatus {
        authenticated: ctx.authenticated,
        account_id: ctx.account_id,
        role: ctx.role,
    })
}"""

replacement = """pub async fn me(Extension(ctx): Extension<AuthContext>) -> impl IntoResponse {
    Json(AuthStatus {
        authenticated: ctx.authenticated,
        account_id: ctx.account_id,
        role: ctx.role,
    })
}

#[derive(Deserialize)]
pub struct UpdateEmailPayload {
    pub new_email: String,
}

pub async fn update_email(
    State(state): State<ApiState>,
    Extension(ctx): Extension<AuthContext>,
    Json(payload): Json<UpdateEmailPayload>,
) -> impl IntoResponse {
    if !ctx.authenticated {
        let err = serde_json::json!({"error": "UNAUTHORIZED"});
        return (StatusCode::UNAUTHORIZED, Json(err)).into_response();
    }
    let account_id = match ctx.account_id {
        Some(id) => id,
        None => return (StatusCode::UNAUTHORIZED, Json(serde_json::json!({"error": "UNAUTHORIZED"}))).into_response(),
    };
    let device_id = match ctx.device_id {
        Some(id) => id,
        None => return (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({"error": "SESSION_INVALID"}))).into_response(),
    };
    let challenge = state.challenges.create(
        account_id,
        device_id,
        ChallengeIntent::UpdateEmail {
            new_email: payload.new_email,
        },
    );
    let err_payload = serde_json::json!({
        "error": "STEP_UP_REQUIRED",
        "challenge_id": challenge.id
    });
    (StatusCode::FORBIDDEN, Json(err_payload)).into_response()
}"""

if target in content:
    content = content.replace(target, replacement)
    with open("apps/api/src/routes/auth.rs", "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched apps/api/src/routes/auth.rs successfully.")
else:
    print("Target string not found in apps/api/src/routes/auth.rs.")
    sys.exit(1)
