import sys

with open("apps/api/src/routes/auth.rs", "r", encoding="utf-8") as f:
    content = f.read()

target = """        ChallengeIntent::RemoveDevice { target_device_id } => {
            tracing::info!(
                event = "auth.step_up.consume.remove_device",
                request_id = %request_id,
                account_id = %account_id,
                target_device_id = %target_device_id,
                "Step-up consume: executing RemoveDevice intent"
            );
            state
                .sessions
                .delete_by_device(&account_id, &target_device_id);
            StatusCode::NO_CONTENT.into_response()
        }
    }
}"""

replacement = """        ChallengeIntent::RemoveDevice { target_device_id } => {
            tracing::info!(
                event = "auth.step_up.consume.remove_device",
                request_id = %request_id,
                account_id = %account_id,
                target_device_id = %target_device_id,
                "Step-up consume: executing RemoveDevice intent"
            );
            state
                .sessions
                .delete_by_device(&account_id, &target_device_id);
            StatusCode::NO_CONTENT.into_response()
        }
        ChallengeIntent::UpdateEmail { new_email } => {
            tracing::info!(
                event = "auth.step_up.consume.update_email",
                request_id = %request_id,
                account_id = %account_id,
                "Step-up consume: executing UpdateEmail intent"
            );
            let mut accounts = state.accounts.write().await;
            if let Some(account) = accounts.get_mut(&account_id) {
                account.email = Some(new_email.to_lowercase());
            }
            StatusCode::NO_CONTENT.into_response()
        }
    }
}"""

if target in content:
    content = content.replace(target, replacement)
    with open("apps/api/src/routes/auth.rs", "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched apps/api/src/routes/auth.rs successfully.")
else:
    print("Target string not found in apps/api/src/routes/auth.rs.")
    sys.exit(1)
