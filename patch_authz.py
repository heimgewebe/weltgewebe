with open("apps/api/src/middleware/authz.rs", "r") as f:
    content = f.read()

content = content.replace(
"""        .unwrap_or(AuthContext {
            authenticated: false,
            account_id: None,
            role: Role::Gast,
        });""",
"""        .unwrap_or(AuthContext {
            authenticated: false,
            account_id: None,
            role: Role::Gast,
            expires_at: None,
        });"""
)

with open("apps/api/src/middleware/authz.rs", "w") as f:
    f.write(content)
