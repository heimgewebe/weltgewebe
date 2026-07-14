/// Encode a finalized SHA-256 digest exactly as the legacy `LowerHex`
/// implementation did: 64 lowercase hexadecimal ASCII characters.
pub(crate) fn encode_sha256_digest(digest: impl AsRef<[u8]>) -> String {
    hex::encode(digest)
}

#[cfg(test)]
mod tests {
    use super::encode_sha256_digest;
    use sha2::{Digest, Sha256};

    #[test]
    fn preserves_legacy_lowercase_hex_for_known_sha256_vectors() {
        let cases = [
            (
                b"".as_slice(),
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            ),
            (
                b"abc".as_slice(),
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            ),
            (
                b"286".as_slice(),
                "00328ce57bbc14b33bd6695bc8eb32cdf2fb5f3a7d89ec14a42825e15d39df60",
            ),
        ];

        for (input, expected) in cases {
            let encoded = encode_sha256_digest(Sha256::digest(input));
            assert_eq!(encoded, expected);
            assert_eq!(encoded.len(), 64);
            assert!(encoded
                .bytes()
                .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte)));
        }
    }
}
