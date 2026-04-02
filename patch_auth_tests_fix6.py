import sys

with open("apps/api/tests/api_auth.rs", "r", encoding="utf-8") as f:
    content = f.read()

target = """    let app = api_router().with_state(state.clone());"""
replacement = """    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());"""

if target in content:
    content = content.replace(target, replacement)
    with open("apps/api/tests/api_auth.rs", "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched apps/api/tests/api_auth.rs with auth_middleware router successfully.")
else:
    print("Target string not found.")
    sys.exit(1)
