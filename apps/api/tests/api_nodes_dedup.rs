use anyhow::Result;
use serial_test::serial;
mod helpers;

use helpers::set_gewebe_in_dir;
use std::{fs, path::PathBuf};

fn make_tmp_dir() -> tempfile::TempDir {
    tempfile::tempdir().expect("tmpdir")
}
fn write_lines(path: &PathBuf, lines: &[&str]) {
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(path, lines.join("\n")).unwrap();
}

#[tokio::test]
#[serial]
async fn nodes_load_deduplication_last_write_wins() -> Result<()> {
    // 1. Setup Environment
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");
    let nodes_file = in_dir.join("demo.nodes.jsonl");
    let _env = set_gewebe_in_dir(&in_dir);

    // 2. Write nodes file with duplicate IDs
    // Node "n1" appears twice. First with title "Old", second with title "New".
    write_lines(
        &nodes_file,
        &[
            r#"{"id":"n1","kind":"test","title":"Old","location":{"lat":0.0,"lon":0.0}}"#,
            r#"{"id":"n2","kind":"test","title":"Other","location":{"lat":0.0,"lon":0.0}}"#,
            r#"{"id":"n1","kind":"test","title":"New","location":{"lat":1.0,"lon":1.0}}"#,
        ],
    );

    // 3. Initialize App (triggers load_nodes)
    // We need to initialize the full state to run load_nodes()
    // The helpers/test infrastructure usually handles this via `helpers::test_state` or `run()`,
    // but here we want to test the *result* of the loading.
    // The easiest way is to spin up the router which loads state.
    // However, `api_router()` expects `ApiState`. We need to construct `ApiState` which calls `load_nodes`.

    // We will use the `weltgewebe_api::run` approach or manually construct state.
    // Since `load_nodes` is called inside `run` or `main`, let's check how `lib.rs` constructs it.
    // `state` construction logic is in `lib.rs`, but not exposed as a public function for testing easily
    // except via `run()`. But `run()` starts a server.

    // Alternative: directly call `load_nodes` and inspect the result.
    // `load_nodes` is public.

    let nodes = weltgewebe_api::routes::nodes::load_nodes().await;

    // 4. Verify Deduplication
    assert_eq!(nodes.len(), 2, "Should have 2 unique nodes");

    // Verify "n1" is the "New" one
    let n1 = nodes
        .iter()
        .find(|n| n.id == "n1")
        .expect("n1 should exist");
    assert_eq!(
        n1.title, "New",
        "Should use the last occurrence (Last-Write-Wins)"
    );
    assert_eq!(n1.location.lat, 1.0);

    // Verify "n2" exists
    let n2 = nodes
        .iter()
        .find(|n| n.id == "n2")
        .expect("n2 should exist");
    assert_eq!(n2.title, "Other");

    Ok(())
}
