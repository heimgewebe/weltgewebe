#![allow(dead_code)]

use serde::Deserialize;
use url::Url;

#[derive(Debug, Deserialize)]
struct PostgresProofContract {
    schema_version: u32,
    disposable_database_name_segments: Vec<String>,
    pgbouncer_port: u16,
}

fn contract() -> PostgresProofContract {
    let parsed: PostgresProofContract = serde_json::from_str(include_str!(
        "../../../../scripts/ci/postgres-proof-contract.json"
    ))
    .expect("postgres proof contract JSON must parse");
    assert_eq!(
        parsed.schema_version, 1,
        "unsupported postgres proof contract schema"
    );
    assert!(
        !parsed.disposable_database_name_segments.is_empty(),
        "postgres proof contract must define disposable database segments"
    );
    parsed
}

pub fn assert_disposable_database_name(name: &str) {
    let contract = contract();
    assert!(
        !name.is_empty()
            && name.chars().all(|character| {
                character.is_ascii_alphanumeric() || matches!(character, '_' | '-' | '.')
            }),
        "PostgreSQL proof refuses unsafe disposable database identifier {name:?}"
    );
    let final_segment = name
        .split(['_', '-', '.'])
        .rfind(|segment| !segment.is_empty());
    assert!(
        name.starts_with("weltgewebe_")
            && final_segment.is_some_and(|segment| {
                contract
                    .disposable_database_name_segments
                    .iter()
                    .any(|expected| segment == expected)
            }),
        "PostgreSQL proof refuses non-disposable database name {name:?}; expected weltgewebe_ prefix and final delimited segment from {:?}",
        contract.disposable_database_name_segments
    );
}

pub fn validated_direct_disposable_url(raw: String) -> String {
    assert_direct_disposable_database_url(&raw);
    raw
}

pub fn assert_direct_disposable_database_url(raw: &str) {
    let contract = contract();
    let url = Url::parse(raw).expect("PostgreSQL proof URL must parse");
    assert!(
        matches!(url.scheme(), "postgres" | "postgresql"),
        "PostgreSQL proof URL must use postgres/postgresql scheme"
    );
    assert!(
        url.host_str().is_some(),
        "PostgreSQL proof URL must contain a host"
    );
    assert_ne!(
        url.port().unwrap_or(5432),
        contract.pgbouncer_port,
        "PostgreSQL proof requires direct PostgreSQL, not PgBouncer"
    );
    let database = url.path().trim_start_matches('/');
    assert!(
        !database.contains('%'),
        "PostgreSQL proof database path must not contain percent-encoding"
    );
    assert_disposable_database_name(database);
}
