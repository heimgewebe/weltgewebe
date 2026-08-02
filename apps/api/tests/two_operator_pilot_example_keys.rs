use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use ed25519_dalek::VerifyingKey;
use serde_json::Value;
use sha2::{Digest, Sha256};

const EXAMPLE: &str = include_str!("../../../platform/cell-pilot/two-operator-pilot.example.invalid.json");
const RFC8032_PUBLIC_KEYS: [&str; 2] = [
    "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo",
    "PUAXw-hDiVqStwqnTRt-vJyYLM8uxJaMwM1V8Sr0Zgw",
];
const FORMER_PUBLIC_TEMPLATE_KEYS: [&str; 2] = [
    "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8",
    "ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3ODk6Ozw9Pj8",
];
const KNOWN_WEAK_KEY: &str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";

fn decode_runtime_key(encoded: &str) -> Option<([u8; 32], VerifyingKey)> {
    let bytes: [u8; 32] = URL_SAFE_NO_PAD.decode(encoded).ok()?.try_into().ok()?;
    let key = VerifyingKey::from_bytes(&bytes).ok()?;
    if key.is_weak() { return None; }
    Some((bytes, key))
}

#[test]
fn public_example_keys_are_runtime_valid_digest_bound_and_reciprocal() {
    let document: Value = serde_json::from_str(EXAMPLE).expect("example JSON must parse");
    let cells = document["cells"].as_array().expect("cells must be an array");
    assert_eq!(cells.len(), 2);
    for (index, cell) in cells.iter().enumerate() {
        let active = cell["identity"]["active_public_key"].as_str().expect("active public key must be a string");
        assert_eq!(active, RFC8032_PUBLIC_KEYS[index]);
        let (bytes, _) = decode_runtime_key(active).expect("example key must pass runtime checks");
        let digest = Sha256::digest(bytes)
            .iter()
            .map(|byte| format!("{byte:02x}"))
            .collect::<String>();
        assert_eq!(cell["identity"]["public_key_sha256"].as_str(), Some(digest.as_str()));
        assert_eq!(cell["peer"]["expected_public_key"].as_str(), Some(RFC8032_PUBLIC_KEYS[1-index]));
    }
}

#[test]
fn weak_key_is_rejected_and_former_template_keys_are_absent() {
    assert!(
        decode_runtime_key(KNOWN_WEAK_KEY).is_none(),
        "known weak Ed25519 point unexpectedly passed runtime validation"
    );
    for encoded in FORMER_PUBLIC_TEMPLATE_KEYS {
        assert!(
            !EXAMPLE.contains(encoded),
            "former arbitrary template key remains published: {encoded}"
        );
    }
}
