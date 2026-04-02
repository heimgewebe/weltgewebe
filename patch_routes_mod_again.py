import sys

with open("apps/api/src/routes/mod.rs", "r", encoding="utf-8") as f:
    content = f.read()

target = """        .route("/auth/me", get(me))
        .route("/auth/session", get(session))"""

replacement = """        .route("/auth/me", get(me))
        .route("/auth/me/email", axum::routing::put(update_email))
        .route("/auth/session", get(session))"""

target2 = """session, session_refresh,"""
replacement2 = """session, session_refresh, update_email,"""

if target in content and target2 in content:
    content = content.replace(target, replacement)
    content = content.replace(target2, replacement2)
    with open("apps/api/src/routes/mod.rs", "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched apps/api/src/routes/mod.rs successfully.")
else:
    print("Target string not found in apps/api/src/routes/mod.rs.")
    sys.exit(1)
