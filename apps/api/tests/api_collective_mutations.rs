use anyhow::Result;
use axum::{
    body,
    http::{Request, StatusCode},
    middleware::from_fn_with_state,
    Router,
};
use serial_test::serial;
use std::{fs, path::Path, sync::Arc};
use tokio::sync::RwLock;
use tower::ServiceExt;

mod helpers;

use helpers::set_gewebe_in_dir;
use weltgewebe_api::{
    auth::{
        accounts::AccountStore, rate_limit::AuthRateLimiter, role::Role, session::SessionBackend,
    },
    config::{
        AppConfig, DomainAccountWriteSource, DomainEdgeWriteSource, DomainNodeWriteSource,
        DomainReadSource,
    },
    middleware::{auth::auth_middleware, csrf::require_csrf},
    routes::{
        accounts::{AccountInternal, AccountPublic},
        api_router,
        edges::Edge,
    },
    state::{ApiState, OrderedCache},
    telemetry::{BuildInfo, Metrics},
};

async fn state_for_role(role: Role) -> Result<ApiState> {
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
        domain_read_source: DomainReadSource::Jsonl,
        domain_account_write_source: DomainAccountWriteSource::Jsonl,
        domain_node_write_source: DomainNodeWriteSource::Jsonl,
        domain_edge_write_source: DomainEdgeWriteSource::Jsonl,
        passkey_credential_source: weltgewebe_api::config::PasskeyCredentialSource::InMemory,
        auth_public_login: false,
        auth_cookie_secure: weltgewebe_api::config::auth_cookie_secure_env_override()
            .unwrap_or(true),
        app_base_url: None,
        auth_trusted_proxies: None,
        auth_allow_emails: None,
        auth_allow_email_domains: None,
        auth_auto_provision: false,
        auth_auto_provision_role: weltgewebe_api::config::AutoProvisionRole::Gast,
        auth_rl_ip_per_min: None,
        auth_rl_ip_per_hour: None,
        auth_rl_email_per_min: None,
        auth_rl_email_per_hour: None,
        smtp_host: None,
        smtp_port: None,
        smtp_user: None,
        smtp_pass: None,
        smtp_from: None,
        auth_log_magic_token: false,
        webauthn_rp_id: None,
        webauthn_rp_origin: None,
        webauthn_rp_name: None,
    };

    let mut accounts = AccountStore::new();
    accounts.insert(AccountInternal {
        public: AccountPublic {
            id: "actor".to_string(),
            kind: "garnrolle".to_string(),
            title: "Testgarnrolle".to_string(),
            summary: None,
            public_pos: None,
            map_state: weltgewebe_api::routes::accounts::GarnrolleMapState::NotOnMap,
            radius_m: 0,
            disabled: false,
            tags: vec![],
        },
        role,
        email: Some("actor@example.test".to_string()),
        webauthn_user_id: uuid::Uuid::new_v4(),
    });

    let rate_limiter = Arc::new(AuthRateLimiter::new(&config));
    Ok(ApiState {
        db_pool: None,
        db_pool_configured: false,
        nats_client: None,
        nats_configured: false,
        config,
        metrics,
        sessions: SessionBackend::new_in_memory(),
        challenges: Default::default(),
        tokens: weltgewebe_api::auth::tokens::TokenStore::new(),
        step_up_tokens: weltgewebe_api::auth::step_up_tokens::StepUpTokenStore::new(),
        accounts: Arc::new(RwLock::new(accounts)),
        nodes: Arc::new(RwLock::new(
            weltgewebe_api::routes::nodes::load_nodes().await,
        )),
        nodes_persist: Arc::new(tokio::sync::Mutex::new(())),
        accounts_persist: Arc::new(tokio::sync::Mutex::new(())),
        domain_projection_gate: std::sync::Arc::new(tokio::sync::RwLock::new(())),
        domain_projection_version: std::sync::Arc::new(std::sync::atomic::AtomicI64::new(0)),
        edges: Arc::new(RwLock::new(OrderedCache::new())),
        rate_limiter,
        mailer: None,
        webauthn: None,
        passkey_registrations: Default::default(),
        passkey_registration_grants: Default::default(),
        passkey_authentications: Default::default(),
        passkeys: Default::default(),
    })
}

async fn authenticated_app(state: ApiState) -> (Router, String) {
    let session = state
        .sessions
        .create("actor".to_string(), None)
        .await
        .expect("in-memory session must be created");
    let cookie = format!("gewebe_session={}", session.id);
    let app = Router::new()
        .merge(api_router())
        .layer(from_fn_with_state(state.clone(), auth_middleware))
        .layer(axum::middleware::from_fn(require_csrf))
        .with_state(state);
    (app, cookie)
}

fn write_fixture(path: &Path, content: &str) {
    fs::create_dir_all(path.parent().expect("fixture parent")).expect("create fixture dir");
    fs::write(path, content).expect("write fixture");
}

fn mutation_request(method: &str, uri: &str, cookie: &str, payload: &str) -> Request<body::Body> {
    Request::builder()
        .method(method)
        .uri(uri)
        .header("Content-Type", "application/json")
        .header("Cookie", cookie)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::from(payload.to_string()))
        .expect("valid request")
}

#[tokio::test]
#[serial]
async fn weber_can_replace_shared_node_and_delete_node_cascade() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    let nodes_path = in_dir.join("demo.nodes.jsonl");
    let edges_path = in_dir.join("demo.edges.jsonl");
    write_fixture(
        &nodes_path,
        concat!(
            r#"{"id":"n1","kind":"Werkstatt","title":"Alt","address":"Alt 1","location":{"lat":53.5,"lon":10.0},"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}"#,
            "\n",
            r#"{"id":"n2","kind":"Ort","title":"Ziel","address":"Ziel 2","location":{"lat":53.6,"lon":10.1},"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}"#,
            "\n",
        ),
    );
    write_fixture(
        &edges_path,
        concat!(
            r#"{"id":"e1","source_id":"n1","source_type":"node","target_id":"n2","target_type":"node","edge_kind":"reference","created_at":"2026-01-01T00:00:00Z"}"#,
            "\n",
        ),
    );
    let _env = set_gewebe_in_dir(&in_dir);
    let state = state_for_role(Role::Weber).await?;
    state.edges.write().await.insert(
        "e1".to_string(),
        Edge {
            id: "e1".to_string(),
            source_id: "n1".to_string(),
            source_type: Some("node".to_string()),
            target_id: "n2".to_string(),
            target_type: Some("node".to_string()),
            edge_kind: "reference".to_string(),
            note: None,
            created_at: Some("2026-01-01T00:00:00Z".to_string().into()),
            expires_at: None,
        },
    );
    let (app, cookie) = authenticated_app(state.clone()).await;

    let replace = mutation_request(
        "PUT",
        "/nodes/n1",
        &cookie,
        r#"{"title":"Gemeinsam gepflegt","kind":"Werkstatt","address":"Neu 1","location":{"lat":53.55,"lon":10.05},"summary":"Gemeinsamer Knoten","info":"Pflegbar durch alle Weber","tags":["commons"]}"#,
    );
    let response = app.clone().oneshot(replace).await?;
    assert_eq!(response.status(), StatusCode::OK);
    let bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
    let node: serde_json::Value = serde_json::from_slice(&bytes)?;
    assert_eq!(node["title"], "Gemeinsam gepflegt");
    assert_eq!(node["created_at"], "2026-01-01T00:00:00Z");

    // PUT intentionally shares the create contract: coordinates are nested
    // under `location`. Flat `lat`/`lon` fields must fail rather than silently
    // drifting away from the TypeScript client contract.
    let flat_location = mutation_request(
        "PUT",
        "/nodes/n1",
        &cookie,
        r#"{"title":"Falscher Vertrag","kind":"Werkstatt","address":"Neu 1","lat":53.55,"lon":10.05,"tags":[]}"#,
    );
    let response = app.clone().oneshot(flat_location).await?;
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    assert_eq!(
        state
            .nodes
            .read()
            .await
            .get("n1")
            .map(|node| node.title.as_str()),
        Some("Gemeinsam gepflegt")
    );

    let delete_node = mutation_request("DELETE", "/nodes/n1", &cookie, "");
    let response = app.clone().oneshot(delete_node).await?;
    assert_eq!(response.status(), StatusCode::NO_CONTENT);
    assert!(state.nodes.read().await.get("n1").is_none());
    assert!(state.edges.read().await.get("e1").is_none());
    assert!(!fs::read_to_string(&nodes_path)?.contains(r#""id":"n1""#));
    assert!(!fs::read_to_string(&edges_path)?.contains(r#""id":"e1""#));

    let response = app
        .clone()
        .oneshot(Request::get("/nodes/n1").body(body::Body::empty())?)
        .await?;
    assert_eq!(response.status(), StatusCode::NOT_FOUND);
    let response = app
        .oneshot(Request::get("/edges/e1").body(body::Body::empty())?)
        .await?;
    assert_eq!(response.status(), StatusCode::NOT_FOUND);

    Ok(())
}

#[tokio::test]
#[serial]
async fn node_delete_rejects_mixed_node_and_edge_write_sources() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    let nodes_path = in_dir.join("demo.nodes.jsonl");
    let original = concat!(
        r#"{"id":"n1","kind":"Werkstatt","title":"Alt","address":"Alt 1","location":{"lat":53.5,"lon":10.0},"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}"#,
        "\n",
    );
    write_fixture(&nodes_path, original);
    let _env = set_gewebe_in_dir(&in_dir);
    let mut state = state_for_role(Role::Weber).await?;
    state.config.domain_edge_write_source = DomainEdgeWriteSource::Postgres;
    let (app, cookie) = authenticated_app(state).await;

    let delete = mutation_request("DELETE", "/nodes/n1", &cookie, "");
    let response = app.oneshot(delete).await?;
    assert_eq!(response.status(), StatusCode::CONFLICT);
    assert_eq!(fs::read_to_string(&nodes_path)?, original);

    Ok(())
}

#[tokio::test]
#[serial]
async fn node_delete_jsonl_keeps_account_and_role_endpoint_collisions() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    let nodes_path = in_dir.join("demo.nodes.jsonl");
    let edges_path = in_dir.join("demo.edges.jsonl");
    write_fixture(
        &nodes_path,
        concat!(
            r#"{"id":"n1","kind":"Werkstatt","title":"Alt","address":"Alt 1","location":{"lat":53.5,"lon":10.0},"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}"#,
            "\n",
            r#"{"id":"n2","kind":"Ort","title":"Ziel","address":"Ziel 2","location":{"lat":53.6,"lon":10.1},"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}"#,
            "\n",
        ),
    );
    write_fixture(
        &edges_path,
        concat!(
            r#"{"id":"e-node","source_id":"n1","source_type":"node","target_id":"n2","target_type":"node","edge_kind":"reference","created_at":"2026-01-01T00:00:00Z"}"#,
            "\n",
            r#"{"id":"e-account-collision","source_id":"n1","source_type":"account","target_id":"n2","target_type":"node","edge_kind":"reference","created_at":"2026-01-01T00:00:00Z"}"#,
            "\n",
            r#"{"id":"e-role-collision","source_id":"n2","source_type":"node","target_id":"n1","target_type":"role","edge_kind":"reference","created_at":"2026-01-01T00:00:00Z"}"#,
            "\n",
        ),
    );
    let _env = set_gewebe_in_dir(&in_dir);
    let state = state_for_role(Role::Weber).await?;
    {
        let mut edges = state.edges.write().await;
        for (id, source_id, source_type, target_id, target_type) in [
            ("e-node", "n1", "node", "n2", "node"),
            ("e-account-collision", "n1", "account", "n2", "node"),
            ("e-role-collision", "n2", "node", "n1", "role"),
        ] {
            edges.insert(
                id.to_string(),
                Edge {
                    id: id.to_string(),
                    source_id: source_id.to_string(),
                    source_type: Some(source_type.to_string()),
                    target_id: target_id.to_string(),
                    target_type: Some(target_type.to_string()),
                    edge_kind: "reference".to_string(),
                    note: None,
                    created_at: Some("2026-01-01T00:00:00Z".to_string().into()),
                    expires_at: None,
                },
            );
        }
    }
    let (app, cookie) = authenticated_app(state.clone()).await;

    let delete = mutation_request("DELETE", "/nodes/n1", &cookie, "");
    let response = app.oneshot(delete).await?;
    let status = response.status();
    let bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
    assert_eq!(
        status,
        StatusCode::NO_CONTENT,
        "unexpected delete response: {}",
        String::from_utf8_lossy(&bytes)
    );

    assert!(state.nodes.read().await.get("n1").is_none());
    let edges = state.edges.read().await;
    assert!(edges.get("e-node").is_none());
    assert!(edges.get("e-account-collision").is_some());
    assert!(edges.get("e-role-collision").is_some());
    drop(edges);

    let edge_file = fs::read_to_string(&edges_path)?;
    assert!(!edge_file.contains(r#""id":"e-node""#));
    assert!(edge_file.contains(r#""id":"e-account-collision""#));
    assert!(edge_file.contains(r#""id":"e-role-collision""#));
    assert!(!fs::read_to_string(&nodes_path)?.contains(r#""id":"n1""#));

    Ok(())
}

#[tokio::test]
#[serial]
async fn node_delete_jsonl_deletes_unique_untyped_legacy_edge() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    let nodes_path = in_dir.join("demo.nodes.jsonl");
    let edges_path = in_dir.join("demo.edges.jsonl");
    write_fixture(
        &nodes_path,
        concat!(
            r#"{"id":"n1","kind":"Werkstatt","title":"Alt","address":"Alt 1","location":{"lat":53.5,"lon":10.0},"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}"#,
            "\n",
            r#"{"id":"n2","kind":"Ort","title":"Ziel","address":"Ziel 2","location":{"lat":53.6,"lon":10.1},"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}"#,
            "\n",
        ),
    );
    write_fixture(
        &edges_path,
        concat!(
            r#"{"id":"e-untyped-legacy","source_id":"n1","target_id":"n2","target_type":"node","edge_kind":"reference","created_at":"2026-01-01T00:00:00Z"}"#,
            "\n",
            r#"{"id":"e-kept","source_id":"n2","source_type":"node","target_id":"n3","target_type":"node","edge_kind":"reference","created_at":"2026-01-01T00:00:00Z"}"#,
            "\n",
        ),
    );
    let _env = set_gewebe_in_dir(&in_dir);
    let state = state_for_role(Role::Weber).await?;
    state.edges.write().await.insert(
        "e-untyped-legacy".to_string(),
        Edge {
            id: "e-untyped-legacy".to_string(),
            source_id: "n1".to_string(),
            source_type: None,
            target_id: "n2".to_string(),
            target_type: Some("node".to_string()),
            edge_kind: "reference".to_string(),
            note: None,
            created_at: Some("2026-01-01T00:00:00Z".to_string().into()),
            expires_at: None,
        },
    );
    let (app, cookie) = authenticated_app(state.clone()).await;

    let delete = mutation_request("DELETE", "/nodes/n1", &cookie, "");
    let response = app.oneshot(delete).await?;
    let status = response.status();
    let bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
    assert_eq!(
        status,
        StatusCode::NO_CONTENT,
        "unexpected delete response: {}",
        String::from_utf8_lossy(&bytes)
    );

    assert!(state.nodes.read().await.get("n1").is_none());
    assert!(state.edges.read().await.get("e-untyped-legacy").is_none());
    let edge_file = fs::read_to_string(&edges_path)?;
    assert!(!edge_file.contains(r#""id":"e-untyped-legacy""#));
    assert!(edge_file.contains(r#""id":"e-kept""#));
    assert!(!fs::read_to_string(&nodes_path)?.contains(r#""id":"n1""#));

    Ok(())
}

#[tokio::test]
#[serial]
async fn node_delete_jsonl_rejects_untyped_account_collision_without_partial_mutation() -> Result<()>
{
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    let nodes_path = in_dir.join("demo.nodes.jsonl");
    let edges_path = in_dir.join("demo.edges.jsonl");
    let nodes_original = concat!(
        r#"{"id":"n1","kind":"Werkstatt","title":"Alt","address":"Alt 1","location":{"lat":53.5,"lon":10.0},"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}"#,
        "\n",
    );
    let edges_original = concat!(
        r#"{"id":"e-untyped-account-collision","source_id":"n1","target_id":"n2","target_type":"node","edge_kind":"reference","created_at":"2026-01-01T00:00:00Z"}"#,
        "\n",
    );
    write_fixture(&nodes_path, nodes_original);
    write_fixture(&edges_path, edges_original);
    let _env = set_gewebe_in_dir(&in_dir);
    let state = state_for_role(Role::Weber).await?;
    state.accounts.write().await.insert(AccountInternal {
        public: AccountPublic {
            id: "n1".to_string(),
            kind: "garnrolle".to_string(),
            title: "Kollidierende Garnrolle".to_string(),
            summary: None,
            public_pos: None,
            map_state: weltgewebe_api::routes::accounts::GarnrolleMapState::NotOnMap,
            radius_m: 0,
            disabled: false,
            tags: vec![],
        },
        role: Role::Weber,
        email: None,
        webauthn_user_id: uuid::Uuid::new_v4(),
    });
    state.edges.write().await.insert(
        "e-untyped-account-collision".to_string(),
        Edge {
            id: "e-untyped-account-collision".to_string(),
            source_id: "n1".to_string(),
            source_type: None,
            target_id: "n2".to_string(),
            target_type: Some("node".to_string()),
            edge_kind: "reference".to_string(),
            note: None,
            created_at: Some("2026-01-01T00:00:00Z".to_string().into()),
            expires_at: None,
        },
    );
    let (app, cookie) = authenticated_app(state.clone()).await;

    let delete = mutation_request("DELETE", "/nodes/n1", &cookie, "");
    let response = app.oneshot(delete).await?;
    assert_eq!(response.status(), StatusCode::CONFLICT);

    assert!(state.nodes.read().await.get("n1").is_some());
    assert!(state
        .edges
        .read()
        .await
        .get("e-untyped-account-collision")
        .is_some());
    assert_eq!(fs::read_to_string(&nodes_path)?, nodes_original);
    assert_eq!(fs::read_to_string(&edges_path)?, edges_original);

    Ok(())
}

#[tokio::test]
#[serial]
async fn node_delete_jsonl_rejects_untyped_role_collision_without_partial_mutation() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    let nodes_path = in_dir.join("demo.nodes.jsonl");
    let edges_path = in_dir.join("demo.edges.jsonl");
    let nodes_original = concat!(
        r#"{"id":"n1","kind":"Werkstatt","title":"Alt","address":"Alt 1","location":{"lat":53.5,"lon":10.0},"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}"#,
        "\n",
        r#"{"id":"n2","kind":"Ort","title":"Ziel","address":"Ziel 2","location":{"lat":53.6,"lon":10.1},"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}"#,
        "\n",
    );
    let edges_original = concat!(
        r#"{"id":"e-role-evidence","source_id":"n2","source_type":"node","target_id":"n1","target_type":"role","edge_kind":"reference","created_at":"2026-01-01T00:00:00Z"}"#,
        "\n",
        r#"{"id":"e-untyped-role-collision","source_id":"n1","target_id":"n2","target_type":"node","edge_kind":"reference","created_at":"2026-01-01T00:00:00Z"}"#,
        "\n",
    );
    write_fixture(&nodes_path, nodes_original);
    write_fixture(&edges_path, edges_original);
    let _env = set_gewebe_in_dir(&in_dir);
    let state = state_for_role(Role::Weber).await?;
    {
        let mut edges = state.edges.write().await;
        edges.insert(
            "e-role-evidence".to_string(),
            Edge {
                id: "e-role-evidence".to_string(),
                source_id: "n2".to_string(),
                source_type: Some("node".to_string()),
                target_id: "n1".to_string(),
                target_type: Some("role".to_string()),
                edge_kind: "reference".to_string(),
                note: None,
                created_at: Some("2026-01-01T00:00:00Z".to_string().into()),
                expires_at: None,
            },
        );
        edges.insert(
            "e-untyped-role-collision".to_string(),
            Edge {
                id: "e-untyped-role-collision".to_string(),
                source_id: "n1".to_string(),
                source_type: None,
                target_id: "n2".to_string(),
                target_type: Some("node".to_string()),
                edge_kind: "reference".to_string(),
                note: None,
                created_at: Some("2026-01-01T00:00:00Z".to_string().into()),
                expires_at: None,
            },
        );
    }
    let (app, cookie) = authenticated_app(state.clone()).await;

    let delete = mutation_request("DELETE", "/nodes/n1", &cookie, "");
    let response = app.oneshot(delete).await?;
    assert_eq!(response.status(), StatusCode::CONFLICT);

    assert!(state.nodes.read().await.get("n1").is_some());
    assert!(state.edges.read().await.get("e-role-evidence").is_some());
    assert!(state
        .edges
        .read()
        .await
        .get("e-untyped-role-collision")
        .is_some());
    assert_eq!(fs::read_to_string(&nodes_path)?, nodes_original);
    assert_eq!(fs::read_to_string(&edges_path)?, edges_original);

    Ok(())
}

#[tokio::test]
#[serial]
async fn node_delete_jsonl_rejects_invalid_endpoint_type_without_partial_mutation() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    let nodes_path = in_dir.join("demo.nodes.jsonl");
    let edges_path = in_dir.join("demo.edges.jsonl");
    let nodes_original = concat!(
        r#"{"id":"n1","kind":"Werkstatt","title":"Alt","address":"Alt 1","location":{"lat":53.5,"lon":10.0},"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}"#,
        "\n",
        r#"{"id":"n2","kind":"Ort","title":"Ziel","address":"Ziel 2","location":{"lat":53.6,"lon":10.1},"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}"#,
        "\n",
    );
    let edges_original = concat!(
        r#"{"id":"e-node","source_id":"n1","source_type":"node","target_id":"n2","target_type":"node","edge_kind":"reference","created_at":"2026-01-01T00:00:00Z"}"#,
        "\n",
        r#"{"id":"e-invalid-collision","source_id":"n2","source_type":"node","target_id":"n1","target_type":"group","edge_kind":"reference","created_at":"2026-01-01T00:00:00Z"}"#,
        "\n",
    );
    write_fixture(&nodes_path, nodes_original);
    write_fixture(&edges_path, edges_original);
    let _env = set_gewebe_in_dir(&in_dir);
    let state = state_for_role(Role::Weber).await?;
    state.edges.write().await.insert(
        "e-node".to_string(),
        Edge {
            id: "e-node".to_string(),
            source_id: "n1".to_string(),
            source_type: Some("node".to_string()),
            target_id: "n2".to_string(),
            target_type: Some("node".to_string()),
            edge_kind: "reference".to_string(),
            note: None,
            created_at: Some("2026-01-01T00:00:00Z".to_string().into()),
            expires_at: None,
        },
    );
    let (app, cookie) = authenticated_app(state.clone()).await;

    let delete = mutation_request("DELETE", "/nodes/n1", &cookie, "");
    let response = app.oneshot(delete).await?;
    assert_eq!(response.status(), StatusCode::CONFLICT);

    assert!(state.nodes.read().await.get("n1").is_some());
    assert!(state.edges.read().await.get("e-node").is_some());
    assert_eq!(fs::read_to_string(&nodes_path)?, nodes_original);
    assert_eq!(fs::read_to_string(&edges_path)?, edges_original);

    Ok(())
}

#[tokio::test]
#[serial]
async fn concurrent_replace_and_delete_leave_one_coherent_jsonl_result() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    let nodes_path = in_dir.join("demo.nodes.jsonl");
    let edges_path = in_dir.join("demo.edges.jsonl");
    write_fixture(
        &nodes_path,
        concat!(
            r#"{"id":"n1","kind":"Werkstatt","title":"Alt","address":"Alt 1","location":{"lat":53.5,"lon":10.0},"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}"#,
            "\n",
            r#"{"id":"n2","kind":"Ort","title":"Ziel","address":"Ziel 2","location":{"lat":53.6,"lon":10.1},"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}"#,
            "\n",
        ),
    );
    write_fixture(
        &edges_path,
        concat!(
            r#"{"id":"e1","source_id":"n1","source_type":"node","target_id":"n2","target_type":"node","edge_kind":"reference","created_at":"2026-01-01T00:00:00Z"}"#,
            "\n",
        ),
    );
    let _env = set_gewebe_in_dir(&in_dir);
    let state = state_for_role(Role::Weber).await?;
    state.edges.write().await.insert(
        "e1".to_string(),
        Edge {
            id: "e1".to_string(),
            source_id: "n1".to_string(),
            source_type: Some("node".to_string()),
            target_id: "n2".to_string(),
            target_type: Some("node".to_string()),
            edge_kind: "reference".to_string(),
            note: None,
            created_at: Some("2026-01-01T00:00:00Z".to_string().into()),
            expires_at: None,
        },
    );
    let (app, cookie) = authenticated_app(state.clone()).await;

    let replace = mutation_request(
        "PUT",
        "/nodes/n1",
        &cookie,
        r#"{"title":"Parallel gepflegt","kind":"Werkstatt","address":"Neu 1","location":{"lat":53.55,"lon":10.05},"tags":[]}"#,
    );
    let delete = mutation_request("DELETE", "/nodes/n1", &cookie, "");
    let (replace_response, delete_response) =
        tokio::join!(app.clone().oneshot(replace), app.clone().oneshot(delete),);
    let replace_status = replace_response?.status();
    let delete_status = delete_response?.status();

    assert_eq!(delete_status, StatusCode::NO_CONTENT);
    assert!(matches!(
        replace_status,
        StatusCode::OK | StatusCode::NOT_FOUND
    ));
    assert!(state.nodes.read().await.get("n1").is_none());
    assert!(state.edges.read().await.get("e1").is_none());
    assert!(!fs::read_to_string(&nodes_path)?.contains(r#""id":"n1""#));
    assert!(!fs::read_to_string(&edges_path)?.contains(r#""id":"e1""#));

    Ok(())
}

#[tokio::test]
#[serial]
async fn guest_cannot_mutate_shared_elements() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    let nodes_path = in_dir.join("demo.nodes.jsonl");
    let original = concat!(
        r#"{"id":"n1","kind":"Werkstatt","title":"Alt","address":"Alt 1","location":{"lat":53.5,"lon":10.0},"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}"#,
        "\n",
    );
    write_fixture(&nodes_path, original);
    let _env = set_gewebe_in_dir(&in_dir);
    let state = state_for_role(Role::Gast).await?;
    let (app, cookie) = authenticated_app(state).await;

    let replace = mutation_request(
        "PUT",
        "/nodes/n1",
        &cookie,
        r#"{"title":"Verboten","kind":"Werkstatt","address":"Neu 1","location":{"lat":53.55,"lon":10.05}}"#,
    );
    assert_eq!(
        app.clone().oneshot(replace).await?.status(),
        StatusCode::FORBIDDEN
    );
    let delete = mutation_request("DELETE", "/nodes/n1", &cookie, "");
    assert_eq!(
        app.clone().oneshot(delete).await?.status(),
        StatusCode::FORBIDDEN
    );
    assert_eq!(fs::read_to_string(&nodes_path)?, original);

    Ok(())
}
