use std::path::Path;

use weltgewebe_api::test_helpers::EnvGuard;

pub fn set_gewebe_in_dir(dir: &Path) -> EnvGuard {
    EnvGuard::set(
        "GEWEBE_IN_DIR",
        dir.to_str()
            .expect("GEWEBE_IN_DIR must be valid UTF-8 for tests"),
    )
}
