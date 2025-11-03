### 📄 apps/api/src/config.rs

**Größe:** 4 KB | **md5:** `ee70ae7586941cbd2747fca6b264117b`

```rust
use std::{env, fs, path::Path};

use anyhow::{Context, Result};
use serde::Deserialize;

macro_rules! apply_env_override {
    ($self:ident, $field:ident, $env_var:literal) => {
        if let Ok(value) = env::var($env_var) {
            $self.$field = value
                .parse()
                .with_context(|| format!("failed to parse {} override: {value}", $env_var))?;
        }
    };
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
pub struct AppConfig {
    pub fade_days: u32,
    pub ron_days: u32,
    pub anonymize_opt_in: bool,
    pub delegation_expire_days: u32,
}

impl AppConfig {
    const DEFAULT_CONFIG: &'static str = include_str!("../../../configs/app.defaults.yml");

    pub fn load() -> Result<Self> {
        match env::var("APP_CONFIG_PATH") {
            Ok(path) => Self::load_from_path(path),
            Err(_) => {
                let config: Self = serde_yaml::from_str(Self::DEFAULT_CONFIG)
                    .context("failed to parse embedded default configuration")?;
                config.apply_env_overrides()
            }
        }
    }

    pub fn load_from_path(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();
        let raw = fs::read_to_string(path)
            .with_context(|| format!("failed to read configuration file at {}", path.display()))?;
        let config: Self = serde_yaml::from_str(&raw)
            .with_context(|| format!("failed to parse configuration file at {}", path.display()))?;
        config.apply_env_overrides()
    }

    fn apply_env_overrides(mut self) -> Result<Self> {
        apply_env_override!(self, fade_days, "HA_FADE_DAYS");
        apply_env_override!(self, ron_days, "HA_RON_DAYS");
        apply_env_override!(self, anonymize_opt_in, "HA_ANONYMIZE_OPT_IN");
        apply_env_override!(self, delegation_expire_days, "HA_DELEGATION_EXPIRE_DAYS");

        Ok(self)
    }
}

#[cfg(test)]
mod tests {
    use super::AppConfig;
    use crate::test_helpers::{DirGuard, EnvGuard};
    use anyhow::Result;
    use serial_test::serial;
    use tempfile::{tempdir, NamedTempFile};

    const YAML: &str = r#"fade_days: 7
ron_days: 84
anonymize_opt_in: true
delegation_expire_days: 28
"#;

    #[test]
    #[serial]
    fn load_from_path_reads_defaults() -> Result<()> {
        let file = NamedTempFile::new()?;
        std::fs::write(file.path(), YAML)?;

        let _config_path = EnvGuard::unset("APP_CONFIG_PATH");
        let _fade = EnvGuard::unset("HA_FADE_DAYS");
        let _ron = EnvGuard::unset("HA_RON_DAYS");
        let _anonymize = EnvGuard::unset("HA_ANONYMIZE_OPT_IN");
        let _delegation = EnvGuard::unset("HA_DELEGATION_EXPIRE_DAYS");

        let cfg = AppConfig::load_from_path(file.path())?;
        assert_eq!(cfg.fade_days, 7);
        assert_eq!(cfg.ron_days, 84);
        assert!(cfg.anonymize_opt_in);
        assert_eq!(cfg.delegation_expire_days, 28);

        Ok(())
    }

    #[test]
    #[serial]
    fn load_from_path_applies_env_overrides() -> Result<()> {
        let file = NamedTempFile::new()?;
        std::fs::write(file.path(), YAML)?;

        let _config_path = EnvGuard::unset("APP_CONFIG_PATH");
        let _fade = EnvGuard::set("HA_FADE_DAYS", "10");
        let _ron = EnvGuard::set("HA_RON_DAYS", "90");
        let _anonymize = EnvGuard::set("HA_ANONYMIZE_OPT_IN", "false");
        let _delegation = EnvGuard::set("HA_DELEGATION_EXPIRE_DAYS", "14");

        let cfg = AppConfig::load_from_path(file.path())?;
        assert_eq!(cfg.fade_days, 10);
        assert_eq!(cfg.ron_days, 90);
        assert!(!cfg.anonymize_opt_in);
        assert_eq!(cfg.delegation_expire_days, 14);

        Ok(())
    }

    #[test]
    #[serial]
    fn load_uses_embedded_defaults_when_config_file_missing() -> Result<()> {
        let temp_dir = tempdir()?;
        let _dir = DirGuard::change_to(temp_dir.path())?;

        let _config_path = EnvGuard::unset("APP_CONFIG_PATH");
        let _fade = EnvGuard::unset("HA_FADE_DAYS");
        let _ron = EnvGuard::unset("HA_RON_DAYS");
        let _anonymize = EnvGuard::unset("HA_ANONYMIZE_OPT_IN");
        let _delegation = EnvGuard::unset("HA_DELEGATION_EXPIRE_DAYS");

        let cfg = AppConfig::load()?;
        assert_eq!(cfg.fade_days, 7);
        assert_eq!(cfg.ron_days, 84);
        assert!(cfg.anonymize_opt_in);
        assert_eq!(cfg.delegation_expire_days, 28);

        Ok(())
    }
}
```

### 📄 apps/api/src/main.rs

**Größe:** 4 KB | **md5:** `dc30b3c8002563c00cfe2ad07f824889`

```rust
mod config;
mod routes;
mod state;
mod telemetry;

#[cfg(test)]
mod test_helpers;

use std::{env, io::ErrorKind, net::SocketAddr};

use anyhow::{anyhow, Context};
use async_nats::Client as NatsClient;
use axum::{routing::get, Router};
use config::AppConfig;
use routes::health::health_routes;
use routes::meta::meta_routes;
use sqlx::postgres::PgPoolOptions;
use state::ApiState;
use telemetry::{metrics_handler, BuildInfo, Metrics, MetricsLayer};
use tokio::net::TcpListener;
use tracing_subscriber::{fmt, EnvFilter};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let dotenv = dotenvy::dotenv();
    if let Ok(path) = &dotenv {
        tracing::debug!(?path, "loaded environment variables from .env file");
    }

    if let Err(error) = dotenv {
        match &error {
            dotenvy::Error::Io(io_error) if io_error.kind() == ErrorKind::NotFound => {}
            _ => tracing::warn!(%error, "failed to load environment from .env file"),
        }
    }
    init_tracing()?;

    let app_config = AppConfig::load().context("failed to load API configuration")?;
    let (db_pool, db_pool_configured) = initialise_database_pool().await;
    let (nats_client, nats_configured) = initialise_nats_client().await;

    let metrics = Metrics::try_new(BuildInfo::collect())?;
    let state = ApiState {
        db_pool,
        db_pool_configured,
        nats_client,
        nats_configured,
        config: app_config.clone(),
        metrics: metrics.clone(),
    };

    let app = Router::new()
        .merge(health_routes())
        .merge(meta_routes())
        .route("/metrics", get(metrics_handler))
        .layer(MetricsLayer::new(metrics))
        .with_state(state);

    let bind_addr: SocketAddr = env::var("API_BIND")
        .unwrap_or_else(|_| "0.0.0.0:8080".to_string())
        .parse()
        .context("failed to parse API_BIND address")?;

    tracing::info!(%bind_addr, "starting API server");

    let listener = TcpListener::bind(bind_addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

fn init_tracing() -> anyhow::Result<()> {
    if tracing::dispatcher::has_been_set() {
        return Ok(());
    }

    let env_filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info"));
    fmt()
        .with_env_filter(env_filter)
        .try_init()
        .map_err(|error| anyhow!(error))?;

    Ok(())
}

async fn initialise_database_pool() -> (Option<sqlx::PgPool>, bool) {
    let database_url = match env::var("DATABASE_URL") {
        Ok(url) => url,
        Err(_) => return (None, false),
    };

    let pool = match PgPoolOptions::new()
        .max_connections(5)
        .connect_lazy(&database_url)
    {
        Ok(pool) => pool,
        Err(error) => {
            tracing::warn!(error = %error, "failed to configure database pool");
            return (None, true);
        }
    };

    match pool.acquire().await {
        Ok(connection) => drop(connection),
        Err(error) => {
            tracing::warn!(
                error = %error,
                "database connection unavailable at startup; readiness will keep retrying",
            );
        }
    }

    (Some(pool), true)
}

async fn initialise_nats_client() -> (Option<NatsClient>, bool) {
    let nats_url = match env::var("NATS_URL") {
        Ok(url) => url,
        Err(_) => return (None, false),
    };

    match async_nats::connect(&nats_url).await {
        Ok(client) => (Some(client), true),
        Err(error) => {
            tracing::warn!(error = %error, "failed to connect to NATS");
            (None, true)
        }
    }
}
```

### 📄 apps/api/src/state.rs

**Größe:** 615 B | **md5:** `a8b5db0d3a261fbc705eaf927aa0d82a`

```rust
use crate::{config::AppConfig, telemetry::Metrics};
use async_nats::Client as NatsClient;
use sqlx::PgPool;

// ApiState is constructed for future expansion of the API server state. It is
// currently unused by the binary, so we explicitly allow dead code here to keep
// the CI pipeline green while maintaining the transparent intent of the state
// container.
#[allow(dead_code)]
#[derive(Clone)]
pub struct ApiState {
    pub db_pool: Option<PgPool>,
    pub db_pool_configured: bool,
    pub nats_client: Option<NatsClient>,
    pub nats_configured: bool,
    pub config: AppConfig,
    pub metrics: Metrics,
}
```

### 📄 apps/api/src/test_helpers.rs

**Größe:** 1 KB | **md5:** `d67155af27b660b18cae353260709fdc`

```rust
use std::{
    env,
    path::{Path, PathBuf},
};

pub struct EnvGuard {
    key: &'static str,
    original: Option<String>,
}

impl EnvGuard {
    pub fn set(key: &'static str, value: &str) -> Self {
        let original = env::var(key).ok();
        env::set_var(key, value);
        Self { key, original }
    }

    pub fn unset(key: &'static str) -> Self {
        let original = env::var(key).ok();
        env::remove_var(key);
        Self { key, original }
    }
}

impl Drop for EnvGuard {
    fn drop(&mut self) {
        if let Some(ref val) = self.original {
            env::set_var(self.key, val);
        } else {
            env::remove_var(self.key);
        }
    }
}

pub struct DirGuard {
    original: PathBuf,
}

impl DirGuard {
    pub fn change_to(path: impl AsRef<Path>) -> anyhow::Result<Self> {
        let original = env::current_dir()?;
        env::set_current_dir(path.as_ref())?;
        Ok(Self { original })
    }
}

impl Drop for DirGuard {
    fn drop(&mut self) {
        let _ = env::set_current_dir(&self.original);
    }
}
```

