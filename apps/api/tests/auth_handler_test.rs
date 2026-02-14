#[cfg(test)]
mod tests {
    use anyhow::Result;
    use axum::{
        body,
        extract::connect_info::MockConnectInfo,
        http::{Request, StatusCode},
        Router,
    };
    use serial_test::serial;
    use std::{collections::BTreeMap, net::SocketAddr, sync::Arc};
    use tokio::sync::RwLock;
    use tower::ServiceExt;
    use weltgewebe_api::{
        auth::{rate_limit::AuthRateLimiter, role::Role, session::SessionStore},
        config::AppConfig,
        routes::{
            accounts::{AccountInternal, AccountPublic, Visibility},
            api_router,
        },
        state::ApiState,
        telemetry::{BuildInfo, Metrics},
    };

    fn test_state_undeliverable() -> Result<ApiState> {
        let metrics = Metrics::try_new(BuildInfo {
            version: "test",
            commit: "test",
            build_timestamp: "test",
        })?;

        let config = AppConfig {
            fade_days: 7,
            ron_days: 84,
            anonymize_opt_in: true,
            delegation_expire_days: 28,
            auth_public_login: true, // Enabled
            app_base_url: Some("http://localhost".to_string()),
            auth_trusted_proxies: None,
            auth_allow_emails: None,
            auth_allow_email_domains: None,
            auth_auto_provision: false,
            auth_rl_ip_per_min: None,
            auth_rl_ip_per_hour: None,
            auth_rl_email_per_min: None,
            auth_rl_email_per_hour: None,
            smtp_host: None, // No SMTP
            smtp_port: None,
            smtp_user: None,
            smtp_pass: None,
            smtp_from: None,
            auth_log_magic_token: false, // No Dev Logging
        };

        let rate_limiter = Arc::new(AuthRateLimiter::new(&config));

        let mut account_map = BTreeMap::new();
        let account = AccountInternal {
            public: AccountPublic {
                id: "u1".to_string(),
                kind: "garnrolle".to_string(),
                title: "User".to_string(),
                summary: None,
                public_pos: None,
                visibility: Visibility::Public,
                radius_m: 0,
                ron_flag: false,
                disabled: false,
                tags: vec![],
            },
            role: Role::Gast,
            email: Some("u1@example.com".to_string()),
        };
        account_map.insert(account.public.id.clone(), account);

        Ok(ApiState {
            db_pool: None,
            db_pool_configured: false,
            nats_client: None,
            nats_configured: false,
            config,
            metrics,
            sessions: SessionStore::new(),
            tokens: weltgewebe_api::auth::tokens::TokenStore::new(),
            accounts: Arc::new(RwLock::new(account_map)),
            nodes: Arc::new(tokio::sync::RwLock::new(Vec::new())),
            edges: Arc::new(tokio::sync::RwLock::new(Vec::new())),
            rate_limiter,
            mailer: None, // No Mailer instance
        })
    }

    fn app(state: ApiState) -> Router {
        Router::new()
            .merge(api_router())
            .layer(MockConnectInfo(SocketAddr::from(([127, 0, 0, 1], 8080))))
            .with_state(state)
    }

    #[tokio::test]
    #[serial]
    async fn request_login_fails_503_if_undeliverable() -> Result<()> {
        let state = test_state_undeliverable()?;
        let app = app(state);

        let req = Request::post("/auth/login/request")
            .header("Content-Type", "application/json")
            .body(body::Body::from(r#"{"email":"u1@example.com"}"#))?;

        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::SERVICE_UNAVAILABLE);

        Ok(())
    }
}
