from pathlib import Path

root = Path.cwd()


def replace_once(relative: str, old: str, new: str) -> None:
    path = root / relative
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{relative}: expected one match, got {count}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1))


# A node delete spans both node and edge persistence. Mixed sources cannot be
# changed atomically, so reject them instead of deleting from the wrong truth.
replace_once(
    "apps/api/src/routes/nodes.rs",
    "use crate::config::DomainNodeWriteSource;\n",
    "use crate::config::{DomainEdgeWriteSource, DomainNodeWriteSource};\n",
)
replace_once(
    "apps/api/src/routes/nodes.rs",
    '''    reject_node_patch_unless_writable(&state)
        .map_err(|(status, body)| PatchNodeError::Message(status, body))?;
    let _persist_guard = state.nodes_persist.lock().await;
    if state.nodes.read().await.get(&id).is_none() {
''',
    '''    reject_node_patch_unless_writable(&state)
        .map_err(|(status, body)| PatchNodeError::Message(status, body))?;
    let persistence_is_coherent = matches!(
        (
            state.config.domain_node_write_source,
            state.config.domain_edge_write_source,
        ),
        (
            DomainNodeWriteSource::Jsonl,
            DomainEdgeWriteSource::Jsonl,
        ) | (
            DomainNodeWriteSource::Postgres,
            DomainEdgeWriteSource::Postgres,
        )
    );
    if !persistence_is_coherent {
        return Err(PatchNodeError::Message(
            StatusCode::CONFLICT,
            "node deletion requires matching node and edge write sources".to_string(),
        ));
    }
    let _persist_guard = state.nodes_persist.lock().await;
    if state.nodes.read().await.get(&id).is_none() {
''',
)

# Preserve the pre-existing public edge note while adding mutation controls.
replace_once(
    "apps/web/src/lib/components/panels/EdgePanel.svelte",
    '''    created_at?: string;
    source_details?: EdgeParticipantDetails | null;
''',
    '''    created_at?: string;
    note?: string | null;
    source_details?: EdgeParticipantDetails | null;
''',
)
replace_once(
    "apps/web/src/lib/components/panels/EdgePanel.svelte",
    '''        <p>
          <strong>Geknüpft am:</strong>
          {formatDate(edgeDetails?.created_at || $selection?.data?.created_at)}
        </p>

        <div class="participants">
''',
    '''        <p>
          <strong>Geknüpft am:</strong>
          {formatDate(edgeDetails?.created_at || $selection?.data?.created_at)}
        </p>
        {#if edgeDetails?.note || $selection?.data?.note}
          <p><strong>Beschreibung:</strong> {edgeDetails?.note || $selection?.data?.note}</p>
        {/if}

        <div class="participants">
''',
)

# Prove that an incoherent migration configuration fails closed without
# touching the node file.
test_path = root / "apps/api/tests/api_collective_mutations.rs"
test_text = test_path.read_text()
old_import = '''        AppConfig, DomainAccountWriteSource, DomainEdgeWriteSource, DomainNodeWriteSource,
        DomainReadSource,
'''
if old_import not in test_text:
    old_import = '''        AppConfig, DomainAccountWriteSource, DomainEdgeWriteSource, DomainNodeWriteSource,
        DomainReadSource,
'''
# The file already imports both write-source enums; append the contract test.
append_marker = '''#[tokio::test]
#[serial]
async fn guest_cannot_mutate_shared_elements() -> Result<()> {
'''
if test_text.count(append_marker) != 1:
    raise SystemExit("collective test anchor missing")
extra = r'''
#[tokio::test]
#[serial]
async fn node_delete_rejects_mixed_node_and_edge_write_sources() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    let nodes_path = in_dir.join("demo.nodes.jsonl");
    let original = concat!(
        r#"{"id":"n1","kind":"Werkstatt","title":"Alt","address":"Alt 1","location":{"lat":53.5,"lon":10.0},"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}"#,
        "\n",
    );
    write_fixture(&nodes_path, original);
    let _env = set_gewebe_in_dir(&in_dir);
    let mut state = state_for_role(Role::Weber).await?;
    state.config.domain_edge_write_source = DomainEdgeWriteSource::Postgres;
    let (app, cookie) = authenticated_app(state).await;

    let delete = mutation_request("DELETE", "/nodes/n1", &cookie, "");
    let response = app.oneshot(delete).await?;
    assert_eq!(response.status(), StatusCode::CONFLICT);
    assert_eq!(fs::read_to_string(&nodes_path)?, original);

    Ok(())
}

'''
test_path.write_text(test_text.replace(append_marker, extra + append_marker, 1))

print("collective review corrections applied")
