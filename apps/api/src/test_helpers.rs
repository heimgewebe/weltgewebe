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
