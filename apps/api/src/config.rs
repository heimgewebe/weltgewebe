use std::{env, fs, path::Path};

use anyhow::{Context, Result};
use serde::Deserialize;

macro_rules! apply_env_override {
    ($self:ident, $field:ident, $env_var:literal) => {
        if let Ok(value) = env::var($env_var) {
            match value.trim().parse() {
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

macro_rules! apply_env_override_option {
    ($self:ident, $field:ident, $type:ty, $env_var:literal) => {
        if let Ok(value) = env::var($env_var) {
            if !value.trim().is_empty() {
                match value.trim().parse::<$type>() {
                    Ok(parsed) => {
                        $self.$field = Some(parsed);
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

    // Entry Policy Configuration
    #[serde(default)]
    pub auth_allow_emails: Option<Vec<String>>,
    #[serde(default)]
    pub auth_allow_email_domains: Option<Vec<String>>,
    #[serde(default)]
    pub auth_auto_provision: bool,

    // Rate Limiting Configuration
    #[serde(default)]
    pub auth_rl_ip_per_min: Option<u32>,
    #[serde(default)]
    pub auth_rl_ip_per_hour: Option<u32>,
    #[serde(default)]
    pub auth_rl_email_per_min: Option<u32>,
    #[serde(default)]
    pub auth_rl_email_per_hour: Option<u32>,

    // SMTP Configuration
    #[serde(default)]
    pub smtp_host: Option<String>,
    #[serde(default)]
    pub smtp_port: Option<u16>,
    #[serde(default)]
    pub smtp_user: Option<String>,
    #[serde(default)]
    pub smtp_pass: Option<String>,
    #[serde(default)]
    pub smtp_from: Option<String>,

    // Dev/Ops Configuration
    #[serde(default)]
    pub auth_log_magic_token: bool,
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
            let val = val.trim();
            self.auth_public_login = val == "1" || val.eq_ignore_ascii_case("true");
        }
        if let Ok(val) = env::var("APP_BASE_URL") {
            let val = val.trim();
            if !val.is_empty() {
                self.app_base_url = Some(val.to_string());
            }
        }
        if let Ok(val) = env::var("AUTH_TRUSTED_PROXIES") {
            let val = val.trim();
            if !val.is_empty() {
                self.auth_trusted_proxies = Some(val.to_string());
            }
        }

        // Entry Policy Overrides
        if let Ok(val) = env::var("AUTH_ALLOW_EMAILS") {
            let entries: Vec<String> = val
                .split(',')
                .map(|s| s.trim().to_ascii_lowercase())
                .filter(|s| !s.is_empty())
                .collect();
            if !entries.is_empty() {
                self.auth_allow_emails = Some(entries);
            }
        }
        if let Ok(val) = env::var("AUTH_ALLOW_EMAIL_DOMAINS") {
            let entries: Vec<String> = val
                .split(',')
                .map(|s| s.trim().to_ascii_lowercase())
                .filter(|s| !s.is_empty())
                .collect();
            if !entries.is_empty() {
                self.auth_allow_email_domains = Some(entries);
            }
        }
        if let Ok(val) = env::var("AUTH_AUTO_PROVISION") {
            let val = val.trim();
            self.auth_auto_provision = val == "1" || val.eq_ignore_ascii_case("true");
        }

        // Rate Limit Overrides
        apply_env_override_option!(self, auth_rl_ip_per_min, u32, "AUTH_RL_IP_PER_MIN");
        apply_env_override_option!(self, auth_rl_ip_per_hour, u32, "AUTH_RL_IP_PER_HOUR");
        apply_env_override_option!(self, auth_rl_email_per_min, u32, "AUTH_RL_EMAIL_PER_MIN");
        apply_env_override_option!(self, auth_rl_email_per_hour, u32, "AUTH_RL_EMAIL_PER_HOUR");

        // SMTP Overrides
        if let Ok(val) = env::var("SMTP_HOST") {
            if !val.trim().is_empty() {
                self.smtp_host = Some(val.trim().to_string());
            }
        }
        apply_env_override_option!(self, smtp_port, u16, "SMTP_PORT");
        if let Ok(val) = env::var("SMTP_USER") {
            if !val.trim().is_empty() {
                self.smtp_user = Some(val.trim().to_string());
            }
        }
        if let Ok(val) = env::var("SMTP_PASS") {
            if !val.trim().is_empty() {
                self.smtp_pass = Some(val.trim().to_string());
            }
        }
        if let Ok(val) = env::var("SMTP_FROM") {
            if !val.trim().is_empty() {
                self.smtp_from = Some(val.trim().to_string());
            }
        }

        // Dev/Ops Overrides
        if let Ok(val) = env::var("AUTH_LOG_MAGIC_TOKEN") {
            let val = val.trim();
            self.auth_log_magic_token = val == "1" || val.eq_ignore_ascii_case("true");
        }

        self.normalize().validate()
    }

    fn normalize(mut self) -> Self {
        if let Some(emails) = self.auth_allow_emails {
            let normalized: Vec<String> = emails
                .into_iter()
                .map(|s| s.trim().to_ascii_lowercase())
                .filter(|s| !s.is_empty())
                .collect();
            self.auth_allow_emails = if normalized.is_empty() {
                None
            } else {
                Some(normalized)
            };
        }

        if let Some(domains) = self.auth_allow_email_domains {
            let normalized: Vec<String> = domains
                .into_iter()
                .map(|s| s.trim().to_ascii_lowercase())
                .filter(|s| !s.is_empty())
                .collect();
            self.auth_allow_email_domains = if normalized.is_empty() {
                None
            } else {
                Some(normalized)
            };
        }

        self
    }

    fn validate(self) -> Result<Self> {
        if self.auth_public_login && self.app_base_url.is_none() {
            anyhow::bail!("AUTH_PUBLIC_LOGIN is enabled but APP_BASE_URL is not set. Please set APP_BASE_URL (e.g. https://mein-weltgewebe.de)");
        }

        if self.auth_auto_provision {
            let has_email_allowlist = self
                .auth_allow_emails
                .as_ref()
                .map(|v| !v.is_empty())
                .unwrap_or(false);
            let has_domain_allowlist = self
                .auth_allow_email_domains
                .as_ref()
                .map(|v| !v.is_empty())
                .unwrap_or(false);

            if !has_email_allowlist && !has_domain_allowlist {
                anyhow::bail!("AUTH_AUTO_PROVISION is enabled but no allowlist is configured. Set AUTH_ALLOW_EMAILS or AUTH_ALLOW_EMAIL_DOMAINS to prevent open registration spam.");
            }
        }

        if self.auth_public_login {
            // Check for valid SMTP configuration
            let smtp_valid = self.smtp_host.is_some()
                && self.smtp_user.is_some()
                && self.smtp_pass.is_some()
                && self.smtp_from.is_some();

            // Check if dev logging fallback is enabled
            let dev_logging = self.auth_log_magic_token;

            if !smtp_valid && !dev_logging {
                anyhow::bail!("AUTH_PUBLIC_LOGIN is enabled but no delivery mechanism is configured. Configure SMTP_* or set AUTH_LOG_MAGIC_TOKEN=1 for dev.");
            }
        } else if self.smtp_host.is_some() && self.smtp_from.is_none() {
            // Only check this consistency if we didn't already bail above,
            // though the above check implies strictness when public login is on.
            // This clause catches "SMTP partially configured but Public Login OFF" edge cases.
            anyhow::bail!(
                "SMTP_HOST is set but SMTP_FROM is missing. Please set SMTP_FROM (e.g. noreply@example.com)."
            );
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
        // Enable token logging to satisfy delivery requirement for this test
        let _log = EnvGuard::set("AUTH_LOG_MAGIC_TOKEN", "1");

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
        let _emails = EnvGuard::unset("AUTH_ALLOW_EMAILS");
        let _domains = EnvGuard::unset("AUTH_ALLOW_EMAIL_DOMAINS");
        let _auto = EnvGuard::unset("AUTH_AUTO_PROVISION");

        let cfg = AppConfig::load_from_path(file.path())?;
        assert!(!cfg.auth_public_login);
        assert!(cfg.app_base_url.is_none());
        assert!(cfg.auth_trusted_proxies.is_none());
        assert!(cfg.auth_allow_emails.is_none());
        assert!(cfg.auth_allow_email_domains.is_none());
        assert!(!cfg.auth_auto_provision);

        Ok(())
    }

    #[test]
    #[serial]
    fn validation_fails_if_auto_provision_enabled_without_allowlist() -> Result<()> {
        let file = NamedTempFile::new()?;
        std::fs::write(file.path(), YAML)?;

        let _auto = EnvGuard::set("AUTH_AUTO_PROVISION", "1");
        let _emails = EnvGuard::unset("AUTH_ALLOW_EMAILS");
        let _domains = EnvGuard::unset("AUTH_ALLOW_EMAIL_DOMAINS");

        let res = AppConfig::load_from_path(file.path());
        assert!(res.is_err());
        assert!(res
            .unwrap_err()
            .to_string()
            .contains("AUTH_AUTO_PROVISION is enabled but no allowlist is configured"));

        Ok(())
    }

    #[test]
    #[serial]
    fn validation_succeeds_with_auto_provision_and_email_allowlist() -> Result<()> {
        let file = NamedTempFile::new()?;
        std::fs::write(file.path(), YAML)?;

        let _auto = EnvGuard::set("AUTH_AUTO_PROVISION", "1");
        let _emails = EnvGuard::set("AUTH_ALLOW_EMAILS", "test@example.com, foo@bar.com");
        let _domains = EnvGuard::unset("AUTH_ALLOW_EMAIL_DOMAINS");

        let cfg = AppConfig::load_from_path(file.path())?;
        assert!(cfg.auth_auto_provision);
        assert_eq!(cfg.auth_allow_emails.unwrap().len(), 2);

        Ok(())
    }

    #[test]
    #[serial]
    fn validation_succeeds_with_auto_provision_and_domain_allowlist() -> Result<()> {
        let file = NamedTempFile::new()?;
        std::fs::write(file.path(), YAML)?;

        let _auto = EnvGuard::set("AUTH_AUTO_PROVISION", "1");
        let _emails = EnvGuard::unset("AUTH_ALLOW_EMAILS");
        let _domains = EnvGuard::set("AUTH_ALLOW_EMAIL_DOMAINS", "example.com");

        let cfg = AppConfig::load_from_path(file.path())?;
        assert!(cfg.auth_auto_provision);
        assert_eq!(cfg.auth_allow_email_domains.unwrap().len(), 1);

        Ok(())
    }

    #[test]
    #[serial]
    fn validation_normalizes_mixed_case_inputs() -> Result<()> {
        let file = NamedTempFile::new()?;
        // Simulate YAML input with mixed case
        let yaml_content = format!(
            "{}\nauth_allow_email_domains: [\"Example.COM\", \"  Space.net \"]\n",
            YAML
        );
        std::fs::write(file.path(), yaml_content)?;

        // Ensure env doesn't override
        let _domains = EnvGuard::unset("AUTH_ALLOW_EMAIL_DOMAINS");

        let cfg = AppConfig::load_from_path(file.path())?;
        let domains = cfg.auth_allow_email_domains.expect("domains set");

        assert_eq!(domains.len(), 2);
        assert!(domains.contains(&"example.com".to_string()));
        assert!(domains.contains(&"space.net".to_string()));

        Ok(())
    }

    #[test]
    #[serial]
    fn validation_fails_if_public_login_without_delivery() -> Result<()> {
        let file = NamedTempFile::new()?;
        std::fs::write(file.path(), YAML)?;

        let _public = EnvGuard::set("AUTH_PUBLIC_LOGIN", "1");
        let _url = EnvGuard::set("APP_BASE_URL", "http://localhost");
        // Ensure no SMTP and no dev logging
        let _smtp_host = EnvGuard::unset("SMTP_HOST");
        let _smtp_user = EnvGuard::unset("SMTP_USER");
        let _smtp_pass = EnvGuard::unset("SMTP_PASS");
        let _smtp_from = EnvGuard::unset("SMTP_FROM");
        let _smtp_port = EnvGuard::unset("SMTP_PORT");
        let _log_token = EnvGuard::unset("AUTH_LOG_MAGIC_TOKEN");

        let res = AppConfig::load_from_path(file.path());
        assert!(res.is_err());
        assert!(res
            .unwrap_err()
            .to_string()
            .contains("no delivery mechanism is configured"));

        Ok(())
    }

    #[test]
    #[serial]
    fn validation_succeeds_if_public_login_with_auth_log_magic_token() -> Result<()> {
        let file = NamedTempFile::new()?;
        std::fs::write(file.path(), YAML)?;

        let _public = EnvGuard::set("AUTH_PUBLIC_LOGIN", "1");
        let _url = EnvGuard::set("APP_BASE_URL", "http://localhost");
        // No SMTP but enable dev logging
        let _smtp_host = EnvGuard::unset("SMTP_HOST");
        let _smtp_user = EnvGuard::unset("SMTP_USER");
        let _smtp_pass = EnvGuard::unset("SMTP_PASS");
        let _smtp_from = EnvGuard::unset("SMTP_FROM");
        let _smtp_port = EnvGuard::unset("SMTP_PORT");
        let _log_token = EnvGuard::set("AUTH_LOG_MAGIC_TOKEN", "1");

        let cfg = AppConfig::load_from_path(file.path())?;
        assert!(cfg.auth_public_login);
        assert!(cfg.auth_log_magic_token);

        Ok(())
    }
}
