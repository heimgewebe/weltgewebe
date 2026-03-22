with open("apps/api/src/middleware/auth.rs", "r") as f:
    content = f.read()

content = content.replace(
"""pub struct AuthContext {
    pub authenticated: bool,
    pub account_id: Option<String>,
    pub role: Role,
}""",
"""pub struct AuthContext {
    pub authenticated: bool,
    pub account_id: Option<String>,
    pub role: Role,
    pub expires_at: Option<chrono::DateTime<chrono::Utc>>,
}"""
)

content = content.replace(
"""    let mut ctx = AuthContext {
        authenticated: false,
        account_id: None,
        role: Role::Gast,
    };""",
"""    let mut ctx = AuthContext {
        authenticated: false,
        account_id: None,
        role: Role::Gast,
        expires_at: None,
    };"""
)

content = content.replace(
"""            if let Some(internal) = accounts_map.get(&session.account_id) {
                ctx.authenticated = true;
                ctx.account_id = Some(session.account_id);
                ctx.role = internal.role.clone();
            }""",
"""            if let Some(internal) = accounts_map.get(&session.account_id) {
                ctx.authenticated = true;
                ctx.account_id = Some(session.account_id);
                ctx.role = internal.role.clone();
                ctx.expires_at = Some(session.expires_at);
            }"""
)

with open("apps/api/src/middleware/auth.rs", "w") as f:
    f.write(content)
