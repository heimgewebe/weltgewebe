#![allow(dead_code)]

use serde::Deserialize;
use url::Url;

#[derive(Debug, Deserialize)]
struct PostgresProofContract {
    schema_version: u32,
    disposable_database_name_markers: Vec<String>,
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
        !parsed.disposable_database_name_markers.is_empty(),
        "postgres proof contract must define disposable database markers"
    );
    parsed
}

pub fn assert_disposable_database_name(name: &str) {
    let contract = contract();
    assert!(
        !name.is_empty()
            && contract
                .disposable_database_name_markers
                .iter()
                .any(|marker| name.contains(marker)),
        "PostgreSQL proof refuses non-disposable database name {name:?}; expected one of markers {:?}",
        contract.disposable_database_name_markers
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
    assert_disposable_database_name(database);
}
