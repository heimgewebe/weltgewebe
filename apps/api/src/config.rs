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
        if let Ok(value) = env::var("HA_FADE_DAYS") {
            self.fade_days = value
                .parse()
                .with_context(|| format!("failed to parse HA_FADE_DAYS override: {value}"))?;
        }

        if let Ok(value) = env::var("HA_RON_DAYS") {
            self.ron_days = value
                .parse()
                .with_context(|| format!("failed to parse HA_RON_DAYS override: {value}"))?;
        }

        if let Ok(value) = env::var("HA_ANONYMIZE_OPT_IN") {
            self.anonymize_opt_in = value.parse().with_context(|| {
                format!("failed to parse HA_ANONYMIZE_OPT_IN override: {value}")
            })?;
        }

        if let Ok(value) = env::var("HA_DELEGATION_EXPIRE_DAYS") {
            self.delegation_expire_days = value.parse().with_context(|| {
                format!("failed to parse HA_DELEGATION_EXPIRE_DAYS override: {value}")
            })?;
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
    use std::io::Write;
    use tempfile::{tempdir, NamedTempFile};

    const YAML: &str = r#"fade_days: 7
ron_days: 84
anonymize_opt_in: true
delegation_expire_days: 28
"#;

    #[test]
    #[serial]
    fn load_from_path_reads_defaults() -> Result<()> {
        let mut file = NamedTempFile::new()?;
        write!(file, "{YAML}")?;

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
        let mut file = NamedTempFile::new()?;
        write!(file, "{YAML}")?;

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
