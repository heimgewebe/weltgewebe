import sys

with open("apps/api/tests/api_auth.rs", "r", encoding="utf-8") as f:
    content = f.read()

tests = """
#[tokio::test]
#[serial]
async fn test_update_email_requires_step_up() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;

    let session = state.sessions.create("u1".to_string(), Some("dev1".to_string()));
    let cookie = format!("{}={}", SESSION_COOKIE_NAME, session.id);

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    let req = Request::builder()
        .method("PUT")
        .uri("/auth/me/email")
        .header("Cookie", cookie.clone())
        .header("Origin", "http://localhost")
        .header("Content-Type", "application/json")
        .header("X-Forwarded-For", "127.0.0.1")
        .body(body::Body::from(
            r#"{"new_email": "new@example.com"}"#,
        ))?;

    let res = app.oneshot(req).await?;

    let status = res.status();
    let body_bytes = axum::body::to_bytes(res.into_body(), usize::MAX).await?;
    let body_str = String::from_utf8_lossy(&body_bytes);
    println!("Response status: {}", status);
    println!("Response body: {}", body_str);

    assert_eq!(status, StatusCode::FORBIDDEN);

    let body_json: serde_json::Value = serde_json::from_str(&body_str)?;
    assert_eq!(body_json["error"], "STEP_UP_REQUIRED");
    assert!(body_json.get("challenge_id").is_some());
    Ok(())
}

#[tokio::test]
#[serial]
async fn test_update_email_success_via_step_up_consume() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;

    let session = state.sessions.create("u1".to_string(), Some("dev1".to_string()));
    let cookie = format!("{}={}", SESSION_COOKIE_NAME, session.id);

    use weltgewebe_api::auth::challenges::ChallengeIntent;

    let challenge = state.challenges.create(
        session.account_id.clone(),
        session.device_id.clone(),
        ChallengeIntent::UpdateEmail { new_email: "new@example.com".to_string() }
    );

    let token = state.step_up_tokens.create(challenge.id.clone(), session.account_id.clone(), session.device_id.clone());

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    let req = Request::builder()
        .method("POST")
        .uri("/auth/step-up/magic-link/consume")
        .header("Cookie", cookie)
        .header("Content-Type", "application/json")
        .header("Origin", "http://localhost")
        .header("X-Forwarded-For", "127.0.0.1")
        .body(body::Body::from(
            serde_json::json!({
                "token": token,
                "challenge_id": challenge.id
            }).to_string(),
        ))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::NO_CONTENT);

    let accounts = state.accounts.read().await;
    let acc = accounts.get("u1").unwrap();
    assert_eq!(acc.email, Some("new@example.com".to_string()));

    Ok(())
}
"""

if "test_update_email_requires_step_up" not in content:
    with open("apps/api/tests/api_auth.rs", "a", encoding="utf-8") as f:
        f.write(tests)
    print("Added tests to apps/api/tests/api_auth.rs")
else:
    print("Tests already exist.")
