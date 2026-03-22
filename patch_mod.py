with open("apps/api/src/routes/mod.rs", "r") as f:
    content = f.read()

content = content.replace(
"""    auth::{
        consume_login_get, consume_login_post, dev_login, list_dev_accounts, logout, me,
        request_login,
    },""",
"""    auth::{
        consume_login_get, consume_login_post, dev_login, list_dev_accounts, logout, me,
        request_login, session,
    },"""
)

content = content.replace(
"""        .route("/auth/logout", post(logout))
        .route("/auth/me", get(me))
}""",
"""        .route("/auth/logout", post(logout))
        .route("/auth/me", get(me))
        .route("/auth/session", get(session))
}"""
)

with open("apps/api/src/routes/mod.rs", "w") as f:
    f.write(content)
