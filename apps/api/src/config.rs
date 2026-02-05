use std::{env, fs, path::Path};

use anyhow::{Context, Result};
use serde::Deserialize;

macro_rules! apply_env_override {
    ($self:ident, $field:ident, $env_var:literal) => {
        if let Ok(value) = env::var($env_var) {
            match value.parse() {
                Ok(parsed) => {
                    $self.$field = parsed;
                }
                Err(e) => {
                    tracing::warn!(
                        env_var = $env_var,
                        value = %value,
                        error = %e,
                        "failed to parse environment override; keeping configured value"
                    );
                }
            }
        }
    };
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
pub struct AppConfig {
    pub fade_days: u32,
    pub ron_days: u32,
    pub anonymize_opt_in: bool,
    pub delegation_expire_days: u32,

    // Public Login Configuration
    #[serde(default)]
    pub auth_public_login: bool,
    #[serde(default)]
    pub app_base_url: Option<String>,
    #[serde(default)]
    pub auth_trusted_proxies: Option<String>,
}

impl AppConfig {
    const DEFAULT_CONFIG: &'static str = include_str!("../../../configs/app.defaults.yml");

    pub fn load() -> Result<Self> {
        let config = match env::var("APP_CONFIG_PATH") {
            Ok(path) => {
                if !Path::new(&path).is_file() {
                    tracing::warn!(
                        path,
                        "configuration file specified but not found or is not a regular file; falling back to defaults"
                    );
                    serde_yaml::from_str(Self::DEFAULT_CONFIG)
                        .context("failed to parse embedded default configuration")?
                } else {
                    match Self::load_from_path(&path) {
                        Ok(cfg) => cfg,
                        Err(e) => {
                            tracing::warn!(
                                path,
                                error = %e,
                                "failed to load configuration file; falling back to defaults"
                            );
                            serde_yaml::from_str(Self::DEFAULT_CONFIG)
                                .context("failed to parse embedded default configuration")?
                        }
                    }
                }
            }
            Err(_) => serde_yaml::from_str(Self::DEFAULT_CONFIG)
                .context("failed to parse embedded default configuration")?,
        };

        config.apply_env_overrides()
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

        // Auth Overrides
        if let Ok(val) = env::var("AUTH_PUBLIC_LOGIN") {
            self.auth_public_login = val == "1" || val.eq_ignore_ascii_case("true");
        }
        if let Ok(val) = env::var("APP_BASE_URL") {
            if !val.is_empty() {
                self.app_base_url = Some(val);
            }
        }
        if let Ok(val) = env::var("AUTH_TRUSTED_PROXIES") {
            if !val.is_empty() {
                self.auth_trusted_proxies = Some(val);
            }
        }

        self.validate()
    }

    fn validate(self) -> Result<Self> {
        if self.auth_public_login && self.app_base_url.is_none() {
            anyhow::bail!("AUTH_PUBLIC_LOGIN is enabled but APP_BASE_URL is not set. Please set APP_BASE_URL (e.g. https://mein-weltgewebe.de)");
        }
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

    #[test]
    #[serial]
    fn load_falls_back_to_defaults_when_config_path_is_invalid() -> Result<()> {
        let temp_dir = tempdir()?;
        let invalid_path = temp_dir.path().join("does-not-exist.yml");

        let _config_path = EnvGuard::set(
            "APP_CONFIG_PATH",
            invalid_path.to_str().expect("path is valid utf-8"),
        );
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

    #[test]
    #[serial]
    fn validation_fails_if_public_login_enabled_without_base_url() -> Result<()> {
        let file = NamedTempFile::new()?;
        std::fs::write(file.path(), YAML)?;

        let _public = EnvGuard::set("AUTH_PUBLIC_LOGIN", "1");
        let _url = EnvGuard::unset("APP_BASE_URL");

        let res = AppConfig::load_from_path(file.path());
        assert!(res.is_err());
        assert!(res
            .unwrap_err()
            .to_string()
            .contains("APP_BASE_URL is not set"));

        Ok(())
    }

    #[test]
    #[serial]
    fn validation_succeeds_with_public_login_and_base_url() -> Result<()> {
        let file = NamedTempFile::new()?;
        std::fs::write(file.path(), YAML)?;

        let _public = EnvGuard::set("AUTH_PUBLIC_LOGIN", "1");
        let _url = EnvGuard::set("APP_BASE_URL", "https://example.com");

        let cfg = AppConfig::load_from_path(file.path())?;
        assert!(cfg.auth_public_login);
        assert_eq!(cfg.app_base_url.unwrap(), "https://example.com");

        Ok(())
    }

    #[test]
    #[serial]
    fn auth_fields_default_correctly() -> Result<()> {
        let file = NamedTempFile::new()?;
        std::fs::write(file.path(), YAML)?;

        // Ensure envs are unset
        let _public = EnvGuard::unset("AUTH_PUBLIC_LOGIN");
        let _url = EnvGuard::unset("APP_BASE_URL");
        let _proxies = EnvGuard::unset("AUTH_TRUSTED_PROXIES");

        let cfg = AppConfig::load_from_path(file.path())?;
        assert!(!cfg.auth_public_login);
        assert!(cfg.app_base_url.is_none());
        assert!(cfg.auth_trusted_proxies.is_none());

        Ok(())
    }
}
