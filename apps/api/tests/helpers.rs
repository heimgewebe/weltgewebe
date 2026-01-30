use std::collections::HashMap;
use std::path::Path;
use std::sync::Arc;

use weltgewebe_api::routes::accounts::AccountInternal;
use weltgewebe_api::state::ApiState;
use weltgewebe_api::test_helpers::EnvGuard;

pub fn set_accounts(state: &mut ApiState, accounts: HashMap<String, AccountInternal>) {
    let mut ids: Vec<_> = accounts.keys().cloned().collect();
    ids.sort();
    state.sorted_account_ids = Arc::new(ids);
    state.accounts = Arc::new(accounts);
}

pub fn set_gewebe_in_dir(dir: &Path) -> EnvGuard {
    EnvGuard::set(
        "GEWEBE_IN_DIR",
        dir.to_str()
            .expect("GEWEBE_IN_DIR must be valid UTF-8 for tests"),
    )
}
