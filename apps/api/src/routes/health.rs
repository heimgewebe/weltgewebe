use std::{
    env,
    future::Future,
    path::{Path, PathBuf},
    time::Duration,
};
use tokio::{fs, io::AsyncReadExt, time::timeout};

use axum::{
    extract::State,
    http::{header, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    routing::get,
    Json, Router,
};
use serde::Deserialize;
use serde_json::{json, Map};
use sqlx::query_scalar;

#[cfg(test)]
use crate::auth::accounts::AccountStore;
use crate::{
    state::ApiState,
    telemetry::health::{readiness_check_failed, readiness_checks_succeeded},
};

pub fn health_routes() -> Router<ApiState> {
    Router::new()
        .route("/health/live", get(live))
        .route("/health/ready", get(ready))
}

async fn live() -> Response {
    let body = Json(json!({ "status": "ok" }));
    let mut response = body.into_response();
    response
        .headers_mut()
        .insert(header::CACHE_CONTROL, HeaderValue::from_static("no-store"));
    response
}

#[derive(Debug, Default, Clone, Copy)]
enum CheckStatus {
    #[default]
    Ready,
    Skipped,
    Failed,
}

#[derive(Debug, Default)]
struct CheckResult {
    status: CheckStatus,
    errors: Vec<String>,
}

impl CheckResult {
    fn ready() -> Self {
        Self {
            status: CheckStatus::Ready,
            errors: Vec::new(),
        }
    }

    fn skipped() -> Self {
        Self {
            status: CheckStatus::Skipped,
            errors: Vec::new(),
        }
    }

    fn failure(errors: Vec<String>) -> Self {
        Self {
            status: CheckStatus::Failed,
            errors,
        }
    }

    fn failure_with_message(message: String) -> Self {
        Self::failure(vec![message])
    }
}

fn readiness_verbose() -> bool {
    env::var("READINESS_VERBOSE")
        .map(|value| {
            let trimmed = value.trim();
            trimmed == "1" || trimmed.eq_ignore_ascii_case("true")
        })
        .unwrap_or(false)
}

const MAX_POLICY_FILE_BYTES: u64 = 64 * 1024;
const READINESS_CHECK_TIMEOUT_MS: u64 = 750;
const READINESS_TOTAL_TIMEOUT_MS: u64 = 1_000;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct PolicyLimits {
    max_nodes_jsonl_mb: u64,
    max_edges_jsonl_mb: u64,
}

impl PolicyLimits {
    fn validate(self) -> Result<(), String> {
        if self.max_nodes_jsonl_mb == 0 {
            return Err("max_nodes_jsonl_mb must be greater than zero".to_string());
        }
        if self.max_edges_jsonl_mb == 0 {
            return Err("max_edges_jsonl_mb must be greater than zero".to_string());
        }
        Ok(())
    }
}

async fn read_policy_bytes(
    file: fs::File,
    path: &Path,
    expected_len: u64,
) -> Result<Vec<u8>, String> {
    let capacity = usize::try_from(expected_len.min(MAX_POLICY_FILE_BYTES))
        .expect("policy size limit fits usize");
    let mut limited = file.take(MAX_POLICY_FILE_BYTES + 1);
    let mut raw = Vec::with_capacity(capacity);
    limited.read_to_end(&mut raw).await.map_err(|error| {
        format!(
            "failed to read policy file at {}: {}",
            path.display(),
            error
        )
    })?;
    if raw.is_empty() || raw.len() as u64 > MAX_POLICY_FILE_BYTES {
        return Err(format!(
            "policy file at {} must contain between 1 and {} bytes",
            path.display(),
            MAX_POLICY_FILE_BYTES
        ));
    }
    Ok(raw)
}

async fn check_policy_file(path: &Path) -> Result<(), String> {
    let mut options = fs::OpenOptions::new();
    options.read(true);
    #[cfg(unix)]
    options.custom_flags(libc::O_NONBLOCK);
    let file = options.open(path).await.map_err(|error| {
        format!(
            "failed to open policy file at {}: {}",
            path.display(),
            error
        )
    })?;
    let metadata = file.metadata().await.map_err(|error| {
        format!(
            "failed to inspect policy file at {}: {}",
            path.display(),
            error
        )
    })?;

    if !metadata.is_file() {
        return Err(format!(
            "policy file at {} is not a regular file",
            path.display()
        ));
    }
    if metadata.len() == 0 || metadata.len() > MAX_POLICY_FILE_BYTES {
        return Err(format!(
            "policy file at {} must contain between 1 and {} bytes",
            path.display(),
            MAX_POLICY_FILE_BYTES
        ));
    }

    let raw = read_policy_bytes(file, path, metadata.len()).await?;
    let raw = std::str::from_utf8(&raw).map_err(|error| {
        format!(
            "policy file at {} is not valid UTF-8: {}",
            path.display(),
            error
        )
    })?;
    let policy: PolicyLimits = serde_yaml::from_str(raw).map_err(|error| {
        format!(
            "failed to parse policy file at {}: {}",
            path.display(),
            error
        )
    })?;
    policy
        .validate()
        .map_err(|error| format!("invalid policy file at {}: {}", path.display(), error))
}

async fn check_policy_fallbacks(paths: &[PathBuf]) -> CheckResult {
    let mut errors = Vec::new();
    for path in paths {
        match fs::metadata(path).await {
            Ok(_) => match check_policy_file(path).await {
                Ok(()) => return CheckResult::ready(),
                Err(message) => {
                    readiness_check_failed("policy", &message);
                    return CheckResult::failure_with_message(message);
                }
            },
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
                errors.push(format!(
                    "failed to access policy file at {}: {}",
                    path.display(),
                    error
                ));
            }
            Err(error) => {
                let message = format!(
                    "failed to access policy file at {}: {}",
                    path.display(),
                    error
                );
                readiness_check_failed("policy", &message);
                return CheckResult::failure_with_message(message);
            }
        }
    }

    for error in &errors {
        readiness_check_failed("policy", error);
    }

    let message = format!(
        "no policy file found in fallback locations: {}",
        paths
            .iter()
            .map(|path| path.display().to_string())
            .collect::<Vec<_>>()
            .join(", ")
    );
    readiness_check_failed("policy", &message);
    errors.push(message);

    CheckResult::failure(errors)
}

async fn check_nats(state: &ApiState) -> CheckResult {
    if !state.nats_configured {
        return CheckResult::skipped();
    }

    match state.nats_client.as_ref() {
        Some(client) => match client.flush().await {
            Ok(_) => CheckResult::ready(),
            Err(error) => {
                let message = error.to_string();
                readiness_check_failed("nats", &message);
                CheckResult::failure_with_message(message)
            }
        },
        None => {
            let message = "client not initialised".to_string();
            readiness_check_failed("nats", &message);
            CheckResult::failure_with_message(message)
        }
    }
}

async fn check_database(state: &ApiState) -> CheckResult {
    if !state.db_pool_configured {
        return CheckResult::skipped();
    }

    match state.db_pool.as_ref() {
        Some(pool) => match query_scalar::<_, i32>("SELECT 1")
            .fetch_optional(pool)
            .await
        {
            Ok(_) => CheckResult::ready(),
            Err(error) => {
                let message = error.to_string();
                readiness_check_failed("database", &message);
                CheckResult::failure_with_message(message)
            }
        },
        None => {
            let message = "connection pool not initialised".to_string();
            readiness_check_failed("database", &message);
            CheckResult::failure_with_message(message)
        }
    }
}

async fn check_policy() -> CheckResult {
    // Prefer an explicit configuration via env var to avoid hard-coded path assumptions.
    // Fallbacks stay for dev/CI convenience.
    let env_path = env::var_os("POLICY_LIMITS_PATH").map(PathBuf::from);
    let fallback_paths = [
        Path::new("policies/limits.yaml").to_path_buf(),
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies/limits.yaml"),
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../policies/limits.yaml"),
    ];

    if let Some(path) = env_path {
        match check_policy_file(&path).await {
            Ok(()) => CheckResult::ready(),
            Err(message) => {
                readiness_check_failed("policy", &message);
                CheckResult::failure_with_message(message)
            }
        }
    } else {
        check_policy_fallbacks(&fallback_paths).await
    }
}

#[derive(Debug)]
struct ReadinessResults {
    nats: CheckResult,
    database: CheckResult,
    policy: CheckResult,
}

async fn bounded_check<F>(name: &'static str, budget: Duration, check: F) -> CheckResult
where
    F: Future<Output = CheckResult>,
{
    match timeout(budget, check).await {
        Ok(result) => result,
        Err(_) => {
            let message = format!("readiness check timed out after {} ms", budget.as_millis());
            readiness_check_failed(name, &message);
            CheckResult::failure_with_message(message)
        }
    }
}

async fn run_readiness_checks_with_budgets<N, D, P>(
    nats: N,
    database: D,
    policy: P,
    check_budget: Duration,
    total_budget: Duration,
) -> ReadinessResults
where
    N: Future<Output = CheckResult>,
    D: Future<Output = CheckResult>,
    P: Future<Output = CheckResult>,
{
    let checks = async {
        let (nats, database, policy) = tokio::join!(
            bounded_check("nats", check_budget, nats),
            bounded_check("database", check_budget, database),
            bounded_check("policy", check_budget, policy),
        );
        ReadinessResults {
            nats,
            database,
            policy,
        }
    };

    match timeout(total_budget, checks).await {
        Ok(results) => results,
        Err(_) => {
            let message = format!(
                "readiness checks exceeded total budget of {} ms",
                total_budget.as_millis()
            );
            for name in ["nats", "database", "policy"] {
                readiness_check_failed(name, &message);
            }
            ReadinessResults {
                nats: CheckResult::failure_with_message(message.clone()),
                database: CheckResult::failure_with_message(message.clone()),
                policy: CheckResult::failure_with_message(message),
            }
        }
    }
}

async fn run_readiness_checks(state: &ApiState) -> ReadinessResults {
    run_readiness_checks_with_budgets(
        check_nats(state),
        check_database(state),
        check_policy(),
        Duration::from_millis(READINESS_CHECK_TIMEOUT_MS),
        Duration::from_millis(READINESS_TOTAL_TIMEOUT_MS),
    )
    .await
}

async fn ready(State(state): State<ApiState>) -> Response {
    readiness_response(run_readiness_checks(&state).await)
}

fn readiness_response(
    ReadinessResults {
        nats,
        database,
        policy,
    }: ReadinessResults,
) -> Response {
    let status = if matches!(database.status, CheckStatus::Failed)
        || matches!(nats.status, CheckStatus::Failed)
        || matches!(policy.status, CheckStatus::Failed)
    {
        StatusCode::SERVICE_UNAVAILABLE
    } else {
        StatusCode::OK
    };

    if status == StatusCode::OK {
        readiness_checks_succeeded();
    }

    let verbose = readiness_verbose();

    let body = Json(json!({
        "status": if status == StatusCode::OK { "ok" } else { "error" },
        "checks": {
            "database": matches!(database.status, CheckStatus::Ready),
            "nats": matches!(nats.status, CheckStatus::Ready),
            "policy": matches!(policy.status, CheckStatus::Ready),
        }
    }));

    let mut value = body.0;

    if verbose {
        let mut errors = Map::new();

        if !database.errors.is_empty() {
            errors.insert("database".to_string(), json!(database.errors));
        }

        if !nats.errors.is_empty() {
            errors.insert("nats".to_string(), json!(nats.errors));
        }

        if !policy.errors.is_empty() {
            errors.insert("policy".to_string(), json!(policy.errors));
        }

        if !errors.is_empty() {
            if let Some(object) = value.as_object_mut() {
                object.insert("errors".to_string(), json!(errors));
            }
        }
    }

    let mut response = Json(value).into_response();
    *response.status_mut() = status;
    response
        .headers_mut()
        .insert(header::CACHE_CONTROL, HeaderValue::from_static("no-store"));
    response
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::OrderedCache;
    use crate::{
        auth::{rate_limit::AuthRateLimiter, session::SessionBackend},
        config::AppConfig,
        telemetry::{BuildInfo, Metrics},
        test_helpers::EnvGuard,
    };
    use anyhow::Result;
    use axum::{body, extract::State, http::header};
    use serde_json::Value;
    use serial_test::serial;
    #[cfg(unix)]
    use std::{ffi::CString, os::unix::ffi::OsStrExt};
    use std::{future::pending, io::Write, sync::Arc, time::Duration};
    use tempfile::NamedTempFile;
    use tokio::sync::RwLock;

    fn test_state() -> Result<ApiState> {
        let metrics = Metrics::try_new(BuildInfo {
            version: "test",
            commit: "test",
            build_timestamp: "test",
        })?;

        let config = AppConfig {
            anonymize_opt_in: true,
            delegation_expire_days: 28,
            max_guest_owned_nodes: 1_000,
            domain_read_source: crate::config::DomainReadSource::Jsonl,
            domain_account_write_source: crate::config::DomainAccountWriteSource::Jsonl,
            domain_node_write_source: crate::config::DomainNodeWriteSource::Jsonl,
            domain_edge_write_source: crate::config::DomainEdgeWriteSource::Jsonl,
            passkey_credential_source: crate::config::PasskeyCredentialSource::InMemory,
            auth_public_login: false,
            auth_cookie_secure: crate::config::auth_cookie_secure_env_override().unwrap_or(true),
            app_base_url: None,
            auth_trusted_proxies: None,
            auth_allow_emails: None,
            auth_allow_email_domains: None,
            auth_auto_provision: false,
            auth_auto_provision_role: crate::config::AutoProvisionRole::Gast,
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
            tokens: crate::auth::tokens::TokenStore::new(),
            step_up_tokens: crate::auth::step_up_tokens::StepUpTokenStore::new(),
            accounts: Arc::new(RwLock::new(AccountStore::new())),
            nodes: Arc::new(RwLock::new(OrderedCache::new())),
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

    #[tokio::test]
    #[serial]
    async fn live_returns_ok_status_and_no_store_header() -> Result<()> {
        let response = live().await;
        let status = response.status();
        let cache_control = response.headers().get(header::CACHE_CONTROL).cloned();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::OK);
        assert_eq!(
            cache_control.as_ref().and_then(|value| value.to_str().ok()),
            Some("no-store")
        );
        assert_eq!(body["status"], "ok");

        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_succeeds_when_optional_dependencies_are_disabled() -> Result<()> {
        let state = test_state()?;

        let response = ready(State(state)).await;
        let status = response.status();
        let cache_control = response.headers().get(header::CACHE_CONTROL).cloned();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::OK);
        assert_eq!(
            cache_control.as_ref().and_then(|value| value.to_str().ok()),
            Some("no-store")
        );
        assert_eq!(body["status"], "ok");
        assert_eq!(body["checks"]["database"], false);
        assert_eq!(body["checks"]["nats"], false);
        assert_eq!(body["checks"]["policy"], true);

        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_fails_when_policy_path_is_invalid() -> Result<()> {
        let _policy = EnvGuard::set("POLICY_LIMITS_PATH", "/does/not/exist");
        let state = test_state()?;

        let response = ready(State(state)).await;
        let status = response.status();
        let cache_control = response.headers().get(header::CACHE_CONTROL).cloned();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(
            cache_control.as_ref().and_then(|value| value.to_str().ok()),
            Some("no-store")
        );
        assert_eq!(body["status"], "error");
        assert_eq!(body["checks"]["database"], false);
        assert_eq!(body["checks"]["nats"], false);
        assert_eq!(body["checks"]["policy"], false);

        Ok(())
    }

    #[tokio::test(start_paused = true)]
    async fn readiness_marks_only_the_stalled_dependency_failed() -> Result<()> {
        let results = tokio::time::timeout(
            Duration::from_millis(500),
            run_readiness_checks_with_budgets(
                async { CheckResult::ready() },
                pending::<CheckResult>(),
                async { CheckResult::ready() },
                Duration::from_millis(10),
                Duration::from_millis(100),
            ),
        )
        .await
        .expect("stalled readiness dependency must be bounded");

        assert!(matches!(results.nats.status, CheckStatus::Ready));
        assert!(matches!(results.database.status, CheckStatus::Failed));
        assert!(matches!(results.policy.status, CheckStatus::Ready));
        assert!(results
            .database
            .errors
            .iter()
            .any(|message| message.contains("timed out after 10 ms")));

        let response = readiness_response(results);
        assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;
        assert_eq!(body["status"], "error");
        assert_eq!(body["checks"]["database"], false);
        assert_eq!(body["checks"]["nats"], true);
        assert_eq!(body["checks"]["policy"], true);

        Ok(())
    }

    #[tokio::test(start_paused = true)]
    async fn readiness_total_budget_is_a_hard_fallback() -> Result<()> {
        let results = tokio::time::timeout(
            Duration::from_millis(500),
            run_readiness_checks_with_budgets(
                pending::<CheckResult>(),
                pending::<CheckResult>(),
                pending::<CheckResult>(),
                Duration::from_millis(100),
                Duration::from_millis(10),
            ),
        )
        .await
        .expect("readiness total budget must bound every check");

        for result in [&results.nats, &results.database, &results.policy] {
            assert!(matches!(result.status, CheckStatus::Failed));
            assert!(result
                .errors
                .iter()
                .any(|message| message.contains("exceeded total budget of 10 ms")));
        }

        Ok(())
    }

    fn policy_file(content: &str) -> Result<NamedTempFile> {
        let mut file = NamedTempFile::new()?;
        file.write_all(content.as_bytes())?;
        file.flush()?;
        Ok(file)
    }

    #[tokio::test]
    async fn policy_check_accepts_valid_contract() -> Result<()> {
        let file = policy_file("max_nodes_jsonl_mb: 10\nmax_edges_jsonl_mb: 10\n")?;
        assert!(check_policy_file(file.path()).await.is_ok());
        Ok(())
    }

    #[tokio::test]
    async fn policy_check_rejects_malformed_yaml() -> Result<()> {
        let file = policy_file("max_nodes_jsonl_mb: [\n")?;
        let error = check_policy_file(file.path())
            .await
            .expect_err("malformed YAML");
        assert!(error.contains("failed to parse policy file"));
        Ok(())
    }

    #[tokio::test]
    async fn policy_check_rejects_missing_or_unknown_fields() -> Result<()> {
        let missing = policy_file("max_nodes_jsonl_mb: 10\n")?;
        assert!(check_policy_file(missing.path()).await.is_err());

        let unknown =
            policy_file("max_nodes_jsonl_mb: 10\nmax_edges_jsonl_mb: 10\nunwired_limit: 1\n")?;
        assert!(check_policy_file(unknown.path()).await.is_err());
        Ok(())
    }

    #[tokio::test]
    async fn policy_fallbacks_fail_closed_on_first_existing_invalid_file() -> Result<()> {
        let invalid = policy_file("max_nodes_jsonl_mb: [\n")?;
        let valid = policy_file("max_nodes_jsonl_mb: 10\nmax_edges_jsonl_mb: 10\n")?;
        let paths = [invalid.path().to_path_buf(), valid.path().to_path_buf()];

        let result = check_policy_fallbacks(&paths).await;
        assert!(matches!(result.status, CheckStatus::Failed));
        Ok(())
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn policy_check_rejects_fifo_without_blocking() -> Result<()> {
        let directory = tempfile::tempdir()?;
        let path = directory.path().join("limits.yaml");
        let c_path = CString::new(path.as_os_str().as_bytes())?;
        let created = unsafe { libc::mkfifo(c_path.as_ptr(), 0o600) };
        assert_eq!(created, 0, "mkfifo must succeed");

        let result = tokio::time::timeout(Duration::from_millis(500), check_policy_file(&path))
            .await
            .expect("FIFO policy check must not block");
        let error = result.expect_err("FIFO is not a regular policy file");
        assert!(error.contains("is not a regular file"));
        Ok(())
    }

    #[tokio::test]
    async fn policy_check_rejects_growth_after_metadata_snapshot() -> Result<()> {
        let file = policy_file("max_nodes_jsonl_mb: 10\nmax_edges_jsonl_mb: 10\n")?;
        let reader = fs::File::open(file.path()).await?;
        let initial_len = reader.metadata().await?.len();

        let mut writer = std::fs::OpenOptions::new().append(true).open(file.path())?;
        writer.write_all(&vec![b' '; MAX_POLICY_FILE_BYTES as usize])?;
        writer.flush()?;

        let error = read_policy_bytes(reader, file.path(), initial_len)
            .await
            .expect_err("grown policy must exceed the bounded read");
        assert!(error.contains("must contain between 1 and"));
        Ok(())
    }

    #[tokio::test]
    async fn policy_check_rejects_non_utf8_content() -> Result<()> {
        let mut file = NamedTempFile::new()?;
        file.write_all(&[0xff, 0xfe])?;
        file.flush()?;

        let error = check_policy_file(file.path())
            .await
            .expect_err("non-UTF-8 policy");
        assert!(error.contains("is not valid UTF-8"));
        Ok(())
    }

    #[tokio::test]
    async fn policy_check_rejects_oversized_files_before_parsing() -> Result<()> {
        let mut file = NamedTempFile::new()?;
        file.write_all(&vec![b'a'; MAX_POLICY_FILE_BYTES as usize + 1])?;
        file.flush()?;

        let error = check_policy_file(file.path())
            .await
            .expect_err("oversized policy");
        assert!(error.contains("must contain between 1 and"));
        Ok(())
    }

    #[tokio::test]
    async fn policy_check_rejects_zero_limits() -> Result<()> {
        let file = policy_file("max_nodes_jsonl_mb: 0\nmax_edges_jsonl_mb: 10\n")?;
        let error = check_policy_file(file.path())
            .await
            .expect_err("zero limit");
        assert!(error.contains("max_nodes_jsonl_mb must be greater than zero"));
        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_fails_when_policy_yaml_is_invalid() -> Result<()> {
        let file = policy_file("max_nodes_jsonl_mb: [\n")?;
        let _policy = EnvGuard::set(
            "POLICY_LIMITS_PATH",
            file.path().to_str().expect("temporary path is valid UTF-8"),
        );
        let state = test_state()?;

        let response = ready(State(state)).await;
        let status = response.status();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(body["status"], "error");
        assert_eq!(body["checks"]["policy"], false);
        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_fails_when_database_pool_missing() -> Result<()> {
        let mut state = test_state()?;
        state.db_pool_configured = true;

        let response = ready(State(state)).await;
        let status = response.status();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(body["checks"]["database"], false);
        assert_eq!(body["checks"]["nats"], false);
        assert_eq!(body["checks"]["policy"], true);

        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_fails_when_nats_client_missing() -> Result<()> {
        let mut state = test_state()?;
        state.nats_configured = true;

        let response = ready(State(state)).await;
        let status = response.status();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(body["checks"]["database"], false);
        assert_eq!(body["checks"]["nats"], false);
        assert_eq!(body["checks"]["policy"], true);

        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_includes_error_details_when_verbose_enabled() -> Result<()> {
        let _policy = EnvGuard::set("POLICY_LIMITS_PATH", "/does/not/exist");
        let _verbose = EnvGuard::set("READINESS_VERBOSE", "1");
        let state = test_state()?;

        let response = ready(State(state)).await;
        let status = response.status();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(body["checks"]["policy"], false);

        let errors = body["errors"]["policy"].as_array().expect("policy errors");
        assert!(!errors.is_empty());
        assert!(errors
            .iter()
            .filter_map(|value| value.as_str())
            .any(|message| message.contains("failed to open policy file")));

        Ok(())
    }
}
