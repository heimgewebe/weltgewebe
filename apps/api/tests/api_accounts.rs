use anyhow::{Context, Result};
use axum::{
    body,
    http::{Request, StatusCode},
    Router,
};
mod helpers;

use helpers::{assert_account_has_single_node_relation, read_account_details, test_node};
use std::sync::Arc;
use tokio::sync::RwLock;
use tower::ServiceExt;
use weltgewebe_api::{
    auth::{
        accounts::AccountStore, rate_limit::AuthRateLimiter, role::Role, session::SessionBackend,
    },
    config::AppConfig,
    routes::{
        accounts::{AccountInternal, AccountPublic},
        api_router,
        edges::Edge,
    },
    state::{ApiState, OrderedCache},
    telemetry::{BuildInfo, Metrics},
};

async fn test_state() -> Result<ApiState> {
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
        domain_read_source: weltgewebe_api::config::DomainReadSource::Jsonl,
        domain_account_write_source: weltgewebe_api::config::DomainAccountWriteSource::Jsonl,
        domain_node_write_source: weltgewebe_api::config::DomainNodeWriteSource::Jsonl,
        domain_edge_write_source: weltgewebe_api::config::DomainEdgeWriteSource::Jsonl,
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
        accounts: Arc::new(RwLock::new(AccountStore::new())),
        nodes: Arc::new(tokio::sync::RwLock::new(
            weltgewebe_api::state::OrderedCache::new(),
        )),
        nodes_persist: Arc::new(tokio::sync::Mutex::new(())),
        accounts_persist: Arc::new(tokio::sync::Mutex::new(())),
        edges: Arc::new(tokio::sync::RwLock::new(
            weltgewebe_api::state::OrderedCache::new(),
        )),
        rate_limiter,
        mailer: None,
        webauthn: None,
        passkey_registrations: Default::default(),
        passkey_registration_grants: Default::default(),
        passkey_authentications: Default::default(),
        passkeys: Default::default(),
    })
}

#[tokio::test]
async fn accounts_list_is_sorted_and_limited() -> Result<()> {
    let mut state = test_state().await?;
    let mut accounts = AccountStore::new();

    // Insert accounts in unsorted order: u2, a1, u1
    // Expected sort order (lexicographical by ID): a1, u1, u2
    let ids = vec!["u2", "a1", "u1"];

    for id in ids {
        accounts.insert(AccountInternal {
            public: AccountPublic {
                id: id.to_string(),
                kind: "garnrolle".to_string(),
                title: format!("Title {}", id),
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
    }

    state.accounts = Arc::new(RwLock::new(accounts));

    let app = Router::new().merge(api_router()).with_state(state);

    // Request limit=2. Expect "a1", "u1".
    let req = Request::get("/accounts?limit=2").body(body::Body::empty())?;
    let res = app.oneshot(req).await?;

    assert_eq!(res.status(), StatusCode::OK);

    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let arr = v.as_array().context("must be array")?;

    assert_eq!(arr.len(), 2, "Should return exactly 2 accounts");
    assert_eq!(arr[0]["id"], "a1", "First account should be a1");
    assert_eq!(arr[1]["id"], "u1", "Second account should be u1");

    Ok(())
}

#[tokio::test]
async fn accounts_offset_pagination() -> Result<()> {
    let mut state = test_state().await?;
    let mut accounts = AccountStore::new();

    // Insert in unsorted order; BTreeMap sorts lexicographically: a1, b2, c3
    for id in &["b2", "a1", "c3"] {
        accounts.insert(AccountInternal {
            public: AccountPublic {
                id: id.to_string(),
                kind: "garnrolle".to_string(),
                title: format!("Title {}", id),
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
    }

    state.accounts = Arc::new(RwLock::new(accounts));
    let app = Router::new().merge(api_router()).with_state(state);

    // limit=1&offset=0 liefert erstes Element (a1 — BTreeMap sort)
    let req = Request::get("/accounts?limit=1&offset=0").body(body::Body::empty())?;
    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let arr = v.as_array().context("must be array")?;
    assert_eq!(arr.len(), 1);
    assert_eq!(arr[0]["id"], "a1");

    // limit=1&offset=1 liefert zweites Element (b2)
    let req = Request::get("/accounts?limit=1&offset=1").body(body::Body::empty())?;
    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let arr = v.as_array().context("must be array")?;
    assert_eq!(arr.len(), 1);
    assert_eq!(arr[0]["id"], "b2");

    // Offset außerhalb der Ergebnislänge liefert leere Liste
    let req = Request::get("/accounts?limit=10&offset=100").body(body::Body::empty())?;
    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let arr = v.as_array().context("must be array")?;
    assert_eq!(arr.len(), 0);

    // Ungültiger Offset (negativ) -> 400
    let req = Request::get("/accounts?offset=-1").body(body::Body::empty())?;
    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    // Ungültiger Offset (kein Integer) -> 400
    let req = Request::get("/accounts?offset=abc").body(body::Body::empty())?;
    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    Ok(())
}

#[tokio::test]
async fn accounts_invalid_limit() -> Result<()> {
    let mut state = test_state().await?;
    let mut accounts = AccountStore::new();

    accounts.insert(AccountInternal {
        public: AccountPublic {
            id: "a1".to_string(),
            kind: "garnrolle".to_string(),
            title: "Title a1".to_string(),
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

    state.accounts = Arc::new(RwLock::new(accounts));
    let app = Router::new().merge(api_router()).with_state(state);

    // limit=abc -> 400
    let req = Request::get("/accounts?limit=abc").body(body::Body::empty())?;
    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    // limit=-1 -> 400
    let req = Request::get("/accounts?limit=-1").body(body::Body::empty())?;
    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    Ok(())
}

#[tokio::test]
async fn accounts_limit_is_clamped_to_max_page_size() -> Result<()> {
    let mut state = test_state().await?;
    let mut accounts = AccountStore::new();

    // Seed more accounts than the page-size cap so the clamp is observable.
    for i in 0..1100 {
        accounts.insert(AccountInternal {
            public: AccountPublic {
                id: format!("a{i:04}"),
                kind: "garnrolle".to_string(),
                title: format!("Title {i}"),
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
    }

    state.accounts = Arc::new(RwLock::new(accounts));
    let app = Router::new().merge(api_router()).with_state(state);

    // A limit above MAX_PAGE_SIZE (1000) must be clamped, mirroring /edges.
    let req = Request::get("/accounts?limit=5000").body(body::Body::empty())?;
    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    assert_eq!(v.as_array().context("must be array")?.len(), 1000);

    Ok(())
}

fn seed_account(id: &str) -> AccountInternal {
    AccountInternal {
        public: AccountPublic {
            id: id.to_string(),
            kind: "garnrolle".to_string(),
            title: format!("Title {id}"),
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
    }
}

#[tokio::test]
async fn accounts_cursor_pagination_envelope_and_walk() -> Result<()> {
    let mut state = test_state().await?;
    let mut accounts = AccountStore::new();

    // Insert unsorted; BTreeMap + cursor_page both yield id-ascending order.
    for id in &["a3", "a1", "a5", "a2", "a4"] {
        accounts.insert(seed_account(id));
    }
    state.accounts = Arc::new(RwLock::new(accounts));
    let app = Router::new().merge(api_router()).with_state(state);

    // Page 1: envelope with the first two ids.
    let req = Request::get("/accounts?pagination=cursor&limit=2").body(body::Body::empty())?;
    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let items = v["items"].as_array().context("items must be array")?;
    assert_eq!(items.len(), 2);
    assert_eq!(items[0]["id"], "a1");
    assert_eq!(items[1]["id"], "a2");
    assert_eq!(v["page"]["has_more"], true);
    let cursor1 = v["page"]["next_cursor"]
        .as_str()
        .context("next_cursor must be present on page 1")?
        .to_string();

    // Page 2: next id-ordered slice, no duplicates from page 1.
    let uri = format!("/accounts?cursor={cursor1}&limit=2");
    let res = app
        .clone()
        .oneshot(Request::get(uri.as_str()).body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let items = v["items"].as_array().context("items must be array")?;
    assert_eq!(items.len(), 2);
    assert_eq!(items[0]["id"], "a3");
    assert_eq!(items[1]["id"], "a4");
    let cursor2 = v["page"]["next_cursor"]
        .as_str()
        .context("next_cursor must be present on page 2")?
        .to_string();

    // Page 3 (last): single remaining id, has_more false, next_cursor null.
    let uri = format!("/accounts?cursor={cursor2}&limit=2");
    let res = app
        .oneshot(Request::get(uri.as_str()).body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let items = v["items"].as_array().context("items must be array")?;
    assert_eq!(items.len(), 1);
    assert_eq!(items[0]["id"], "a5");
    assert_eq!(v["page"]["has_more"], false);
    assert!(v["page"]["next_cursor"].is_null());

    Ok(())
}

#[tokio::test]
async fn accounts_cursor_invalid_is_bad_request() -> Result<()> {
    let mut state = test_state().await?;
    let mut accounts = AccountStore::new();
    accounts.insert(seed_account("a1"));
    state.accounts = Arc::new(RwLock::new(accounts));
    let app = Router::new().merge(api_router()).with_state(state);

    // Odd-length / non-hex cursor token -> deterministic 400.
    let req = Request::get("/accounts?cursor=zzz").body(body::Body::empty())?;
    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    Ok(())
}

#[tokio::test]
async fn accounts_cursor_limit_is_clamped_to_max_page_size() -> Result<()> {
    let mut state = test_state().await?;
    let mut accounts = AccountStore::new();
    for i in 0..1100 {
        accounts.insert(seed_account(&format!("a{i:04}")));
    }
    state.accounts = Arc::new(RwLock::new(accounts));
    let app = Router::new().merge(api_router()).with_state(state);

    let req = Request::get("/accounts?pagination=cursor&limit=5000").body(body::Body::empty())?;
    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let items = v["items"].as_array().context("items must be array")?;
    assert_eq!(items.len(), 1000);
    assert_eq!(v["page"]["limit"], 1000);
    assert_eq!(v["page"]["has_more"], true);

    Ok(())
}

#[tokio::test]
async fn accounts_cursor_limit_zero_is_bad_request() -> Result<()> {
    let state = test_state().await?;
    let app = Router::new().merge(api_router()).with_state(state);

    let req = Request::get("/accounts?pagination=cursor&limit=0").body(body::Body::empty())?;
    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    Ok(())
}

#[tokio::test]
async fn account_details_project_outgoing_relation_without_public_note() -> Result<()> {
    const ACCOUNT_ID: &str = "account-1";
    const NODE_ID: &str = "node-1";
    const CREATED_AT: &str = "2026-07-11T11:11:50.322307+00:00";

    let mut state = test_state().await?;
    let mut accounts = AccountStore::new();
    let mut account = seed_account(ACCOUNT_ID);
    account.public.title = "Alexander Mohr".to_string();
    account.public.summary = Some("schaunmermal".to_string());
    accounts.insert(account);
    state.accounts = Arc::new(RwLock::new(accounts));

    let mut nodes = OrderedCache::new();
    nodes.insert(
        NODE_ID.to_string(),
        test_node(NODE_ID, "fairschenkbox", Some("sharing is caring")),
    );
    state.nodes = Arc::new(RwLock::new(nodes));

    let mut edges = OrderedCache::new();
    edges.insert(
        "edge-1".to_string(),
        Edge {
            id: "edge-1".to_string(),
            source_id: ACCOUNT_ID.to_string(),
            source_type: Some("account".to_string()),
            target_id: NODE_ID.to_string(),
            target_type: Some("node".to_string()),
            edge_kind: "reference".to_string(),
            note: Some("nicht öffentlich".to_string()),
            created_at: Some(CREATED_AT.to_string()),
        },
    );
    state.edges = Arc::new(RwLock::new(edges));

    let app = Router::new().merge(api_router()).with_state(state);
    let value = read_account_details(&app, ACCOUNT_ID).await?;

    assert_eq!(value["title"], "Alexander Mohr");
    let projected_at = assert_account_has_single_node_relation(
        &value,
        ACCOUNT_ID,
        NODE_ID,
        "fairschenkbox",
        "reference",
        "Hat den Knoten \"fairschenkbox\" geknüpft.",
    );
    assert_eq!(projected_at, CREATED_AT);

    Ok(())
}

#[tokio::test]
async fn account_details_attribute_incoming_admin_relation_neutrally() -> Result<()> {
    const ACCOUNT_ID: &str = "account-incoming";
    const NODE_ID: &str = "node-incoming";
    const CREATED_AT: &str = "2026-07-12T12:00:00+00:00";

    let mut state = test_state().await?;
    let mut accounts = AccountStore::new();
    accounts.insert(seed_account(ACCOUNT_ID));
    state.accounts = Arc::new(RwLock::new(accounts));

    let mut nodes = OrderedCache::new();
    nodes.insert(
        NODE_ID.to_string(),
        test_node(NODE_ID, "Importknoten", None),
    );
    state.nodes = Arc::new(RwLock::new(nodes));

    let mut edges = OrderedCache::new();
    edges.insert(
        "edge-incoming".to_string(),
        Edge {
            id: "edge-incoming".to_string(),
            source_id: NODE_ID.to_string(),
            source_type: Some("node".to_string()),
            target_id: ACCOUNT_ID.to_string(),
            target_type: Some("account".to_string()),
            edge_kind: "reference".to_string(),
            note: Some("interne Importnotiz".to_string()),
            created_at: Some(CREATED_AT.to_string()),
        },
    );
    state.edges = Arc::new(RwLock::new(edges));

    let app = Router::new().merge(api_router()).with_state(state);
    let value = read_account_details(&app, ACCOUNT_ID).await?;
    let projected_at = assert_account_has_single_node_relation(
        &value,
        ACCOUNT_ID,
        NODE_ID,
        "Importknoten",
        "reference",
        "Wurde über einen Faden mit dem Knoten \"Importknoten\" verknüpft.",
    );
    assert_eq!(projected_at, CREATED_AT);

    Ok(())
}

#[tokio::test]
async fn account_details_ignore_node_typed_account_id_collision() -> Result<()> {
    const ACCOUNT_ID: &str = "account-mistyped";
    const NODE_ID: &str = "node-real";

    let mut state = test_state().await?;
    let mut accounts = AccountStore::new();
    accounts.insert(seed_account(ACCOUNT_ID));
    state.accounts = Arc::new(RwLock::new(accounts));

    let mut nodes = OrderedCache::new();
    nodes.insert(
        NODE_ID.to_string(),
        test_node(NODE_ID, "Echter Knoten", None),
    );
    state.nodes = Arc::new(RwLock::new(nodes));

    let mut edges = OrderedCache::new();
    edges.insert(
        "edge-type-confused".to_string(),
        Edge {
            id: "edge-type-confused".to_string(),
            source_id: ACCOUNT_ID.to_string(),
            source_type: Some("node".to_string()),
            target_id: NODE_ID.to_string(),
            target_type: Some("node".to_string()),
            edge_kind: "reference".to_string(),
            note: None,
            created_at: Some("2026-07-13T05:55:00+00:00".to_string()),
        },
    );
    state.edges = Arc::new(RwLock::new(edges));

    let app = Router::new().merge(api_router()).with_state(state);
    let value = read_account_details(&app, ACCOUNT_ID).await?;
    assert_eq!(value["nodes"].as_array().map(Vec::len), Some(0));
    assert_eq!(value["activity"].as_array().map(Vec::len), Some(0));

    Ok(())
}

#[tokio::test]
async fn guest_identity_is_not_a_public_garnrolle() -> Result<()> {
    let mut state = test_state().await?;
    let mut accounts = AccountStore::new();
    let mut guest = seed_account("guest-hidden");
    guest.role = Role::Gast;
    accounts.insert(guest);
    accounts.insert(seed_account("weber-visible"));
    state.accounts = Arc::new(RwLock::new(accounts));

    let app = Router::new().merge(api_router()).with_state(state);

    let list = app
        .clone()
        .oneshot(Request::get("/accounts").body(body::Body::empty())?)
        .await?;
    assert_eq!(list.status(), StatusCode::OK);
    let bytes = body::to_bytes(list.into_body(), usize::MAX).await?;
    let accounts: serde_json::Value = serde_json::from_slice(&bytes)?;
    assert_eq!(accounts.as_array().map(Vec::len), Some(1));
    assert_eq!(accounts[0]["id"], "weber-visible");

    let detail = app
        .oneshot(Request::get("/accounts/guest-hidden").body(body::Body::empty())?)
        .await?;
    assert_eq!(detail.status(), StatusCode::NOT_FOUND);

    Ok(())
}
