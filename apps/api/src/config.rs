use std::{env, fs, path::Path};

use anyhow::{Context, Result};
use serde::Deserialize;

#[derive(Debug, Clone, Deserialize, PartialEq)]
pub struct AppConfig {
    pub fade_days: u32,
    pub ron_days: u32,
    pub anonymize_opt_in: bool,
    pub delegation_expire_days: u32,
}

impl AppConfig {
    pub const DEFAULT_PATH = "configs/app.defaults.yml";

    pub fn load() -> Result<Self> {
        let path = env::var("APP_CONFIG_PATH").unwrap_or_else(|_| Self::DEFAULT_PATH.to_string());
        Self::load_from_path(path)
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
        if let Ok(value) = env::var("HA_FADE_DAYS") {
            self.fade_days = value
                .parse()
                .with_context(|| format!("failed to parse HA_FADE_DAYS override: {}", value))?;
        }

        if let Ok(value) = env::var("HA_RON_DAYS") {
            self.ron_days = value
                .parse()
                .with_context(|| format!("failed to parse HA_RON_DAYS override: {}", value))?;
        }

        if let Ok(value) = env::var("HA_ANONYMIZE_OPT_IN") {
            self.anonymize_opt_in = value.parse().with_context(|| {
                format!("failed to parse HA_ANONYMIZE_OPT_IN override: {}", value)
            })?;
        }

        if let Ok(value) = env::var("HA_DELEGATION_EXPIRE_DAYS") {
            self.delegation_expire_days = value.parse().with_context(|| {
                format!(
                    "failed to parse HA_DELEGATION_EXPIRE_DAYS override: {}",
                    value
                )
            })?;
        }

        Ok(self)
    }
}

#[cfg(test)]
mod tests {
    use super::AppConfig;
    use anyhow::Result;
    use serial_test::serial;
    use std::{env, io::Write};
    use tempfile::NamedTempFile;

    const YAML: &str = r#"fade_days: 7
ron_days: 84
anonymize_opt_in: true
delegation_expire_days: 28
"#;

    #[test]
    #[serial]
    fn load_from_path_reads_defaults() -> Result<()> {
        let mut file = NamedTempFile::new()?;
        write!(file, "{}", YAML)?;

        let _fade = EnvGuard::unset("HA_FADE_DAYS");
        let _ron = EnvGuard::unset("HA_RON_DAYS");
        let _anonymize = EnvGuard::unset("HA_ANONYMIZE_OPT_IN");
        let _delegation = EnvGuard::unset("HA_DELEGATION_EXPIRE_DAYS");

        let config = AppConfig::load_from_path(file.path())?;

        assert_eq!(
            config,
            AppConfig {
                fade_days: 7,
                ron_days: 84,
                anonymize_opt_in: true,
                delegation_expire_days: 28,
            }
        );

        Ok(())
    }

    #[test]
    #[serial]
    fn load_from_path_applies_overrides() -> Result<()> {
        let mut file = NamedTempFile::new()?;
        write!(file, "{}", YAML)?;

        let _fade = EnvGuard::set("HA_FADE_DAYS", "10");
        let _ron = EnvGuard::set("HA_RON_DAYS", "90");
        let _anonymize = EnvGuard::set("HA_ANONYMIZE_OPT_IN", "false");
        let _delegation = EnvGuard::set("HA_DELEGATION_EXPIRE_DAYS", "14");

        let config = AppConfig::load_from_path(file.path())?;

        assert_eq!(
            config,
            AppConfig {
                fade_days: 10,
                ron_days: 90,
                anonymize_opt_in: false,
                delegation_expire_days: 14,
            }
        );

        Ok(())
    }

    struct EnvGuard {
        key: &'static str,
        original: Option<String>,
    }

    impl EnvGuard {
        fn set(key: &'static str, value: &str) -> Self {
            let original = env::var(key).ok();
            env::set_var(key, value);
            Self { key, original }
        }

        fn unset(key: &'static str) -> Self {
            let original = env::var(key).ok();
            env::remove_var(key);
            Self { key, original }
        }
    }

    impl Drop for EnvGuard {
        fn drop(&mut self) {
            if let Some(value) = &self.original {
                env::set_var(self.key, value);
            } else {
                env::remove_var(self.key);
            }
        }
    }
}
