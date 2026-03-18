import re

with open('apps/api/src/routes/accounts.rs', 'r') as f:
    code = f.read()

# Make sure test_guard_private_hides_public_pos tests the new private -> Ron migration
code = re.sub(
    r'fn test_guard_private_hides_public_pos\(\) \{[\s\S]*?assert!\(account\.public_pos\.is_none\(\)\);\s*\}',
    r'''fn test_guard_private_hides_public_pos() {
        let input = serde_json::json!({
            "id": "test-private",
            "type": "garnrolle",
            "title": "Private Test",
            "location": { "lat": 53.5, "lon": 10.0 },
            "visibility": "private" // Legacy field
        });

        let account = map_json_to_public_account(&input).expect("Mapping failed");

        // GUARD: Legacy private accounts are safely mapped to Ron (no public location)
        assert_eq!(account.mode, AccountMode::Ron);
        assert!(account.public_pos.is_none());
    }''', code
)

# test_guard_verortet_without_location_fails
code += r'''

#[cfg(test)]
mod additional_tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_verortet_without_location_fails() {
        let input = json!({
            "id": "test-verortet-no-loc",
            "type": "garnrolle",
            "title": "No Loc",
            "mode": "verortet",
        });

        let account = map_json_to_public_account(&input);
        assert!(account.is_none(), "Verortet account without location must fail mapping");
    }

    #[test]
    fn test_ron_without_location_succeeds() {
        let input = json!({
            "id": "test-ron-no-loc",
            "type": "ron",
            "title": "No Loc Ron",
            "mode": "ron",
        });

        let account = map_json_to_public_account(&input).expect("Ron without location should succeed");
        assert_eq!(account.mode, AccountMode::Ron);
        assert!(account.public_pos.is_none());
    }
}
'''

with open('apps/api/src/routes/accounts.rs', 'w') as f:
    f.write(code)
