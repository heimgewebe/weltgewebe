use std::{env, fs, path::Path};

use anyhow::{anyhow, bail, Context, Result};
use serde::Deserialize;

#[derive(Debug, Clone, Deserialize, PartialEq)]
pub struct AppConfig {
    pub fade_days: u32,
    pub ron_days: u32,
    pub anonymize_opt_in: bool,
    pub delegation_expire_days: u32,
}

impl AppConfig {
    pub const DEFAULT_PATH: &'static str = "configs/app.defaults.yml";

    pub fn load() -> Result<Self> {
        let path = env::var("APP_CONFIG_PATH").unwrap_or_else(|_| Self::DEFAULT_PATH.to_string());
        Self::load_from_path(path)
    }

    pub fn load_from_path(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();
        let raw = fs::read_to_string(path)
            .with_context(|| format!("failed to read configuration file at {}", path.display()))?;
        let config = Self::parse_config(&raw)
            .with_context(|| format!("failed to parse configuration file at {}", path.display()))?;

        config.apply_env_overrides()
    }

    fn parse_config(raw: &str) -> Result<Self> {
        let mut fade_days = None;
        let mut ron_days = None;
        let mut anonymize_opt_in = None;
        let mut delegation_expire_days = None;

        for (index, line) in raw.lines().enumerate() {
            let line_number = index + 1;
            let line = line.split('#').next().unwrap_or("").trim();

            if line.is_empty() {
                continue;
            }

            let (key, value) = line
                .split_once(':')
                .map(|(k, v)| (k.trim(), v.trim()))
                .ok_or_else(|| {
                    anyhow!(
                        "invalid configuration entry on line {}: {}",
                        line_number,
                        line
                    )
                })?;

            match key {
                "fade_days" => {
                    fade_days = Some(parse_u32(value, "fade_days", line_number)?);
                }
                "ron_days" => {
                    ron_days = Some(parse_u32(value, "ron_days", line_number)?);
                }
                "anonymize_opt_in" => {
                    anonymize_opt_in = Some(parse_bool(value, "anonymize_opt_in", line_number)?);
                }
                "delegation_expire_days" => {
                    delegation_expire_days =
                        Some(parse_u32(value, "delegation_expire_days", line_number)?);
                }
                other => {
                    bail!(
                        "unknown configuration key '{}' on line {}",
                        other,
                        line_number
                    );
                }
            }
        }

        Ok(Self {
            fade_days: fade_days
                .ok_or_else(|| anyhow!("missing configuration value for fade_days"))?,
            ron_days: ron_days
                .ok_or_else(|| anyhow!("missing configuration value for ron_days"))?,
            anonymize_opt_in: anonymize_opt_in
                .ok_or_else(|| anyhow!("missing configuration value for anonymize_opt_in"))?,
            delegation_expire_days: delegation_expire_days
                .ok_or_else(|| anyhow!("missing configuration value for delegation_expire_days"))?,
        })
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

fn parse_u32(value: &str, field: &str, line: usize) -> Result<u32> {
    value.parse().with_context(|| {
        format!(
            "failed to parse '{}' as an integer on line {}: {}",
            field, line, value
        )
    })
}

fn parse_bool(value: &str, field: &str, line: usize) -> Result<bool> {
    value.parse().with_context(|| {
        format!(
            "failed to parse '{}' as a boolean on line {}: {}",
            field, line, value
        )
    })
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
        write!(file, "{}", YAML)?;

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

    /// Kleiner Env-Helper, der Variablen für die Testdauer setzt/entfernt und danach zurücksetzt.
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
            if let Some(ref val) = self.original {
                env::set_var(self.key, val);
            } else {
                env::remove_var(self.key);
            }
        }
    }
}
