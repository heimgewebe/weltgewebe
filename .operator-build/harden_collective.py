from pathlib import Path

root = Path.cwd()


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, got {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1))


# One shared edge persistence lock must cover cascade edge removal and node removal.
edges = root / "apps/api/src/routes/edges.rs"
replace_once(
    edges,
    "fn edge_create_persist_lock() -> &'static Mutex<()> {\n",
    "pub(crate) fn edge_create_persist_lock() -> &'static Mutex<()> {\n",
)
replace_once(
    edges,
    '''pub(crate) async fn delete_edges_referencing_node_jsonl(
    node_id: &str,
) -> std::io::Result<Vec<String>> {
    let _persist_guard = edge_create_persist_lock().lock().await;
''',
    '''pub(crate) async fn delete_edges_referencing_node_jsonl(
    node_id: &str,
) -> std::io::Result<Vec<String>> {
''',
)

nodes = root / "apps/api/src/routes/nodes.rs"
replace_once(
    nodes,
    "    edges::delete_edges_referencing_node_jsonl,\n",
    "    edges::{delete_edges_referencing_node_jsonl, edge_create_persist_lock},\n",
)
replace_once(
    nodes,
    '''        DomainNodeWriteSource::Jsonl => {
            let removed = delete_edges_referencing_node_jsonl(&id).await.map_err(|error| {
''',
    '''        DomainNodeWriteSource::Jsonl => {
            // Keep the edge lock until the node file has also been replaced. Otherwise a
            // concurrent edge create could attach a new edge between cascade cleanup and
            // node deletion, leaving an orphan behind.
            let _edge_persist_guard = edge_create_persist_lock().lock().await;
            let removed = delete_edges_referencing_node_jsonl(&id).await.map_err(|error| {
''',
)

# PostgreSQL cascade holds the node row and edge table against concurrent edge creates.
db = root / "apps/api/src/domain_db.rs"
replace_once(
    db,
    '''    let mut tx = pool.begin().await.map_err(NodeWriteError::Database)?;
    let exists: bool =
        sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM domain_nodes WHERE id = $1)")
            .bind(id)
            .fetch_one(&mut *tx)
            .await
            .map_err(NodeWriteError::Database)?;
    if !exists {
        tx.rollback().await.ok();
        return Err(NodeWriteError::NotFound);
    }

    let edge_ids: Vec<String> = sqlx::query_scalar(
''',
    '''    let mut tx = pool.begin().await.map_err(NodeWriteError::Database)?;
    // Edge creation also takes this table lock. Holding it through both deletes makes
    // "node + attached edges" one closed graph mutation instead of a race-prone pair.
    sqlx::query("LOCK TABLE domain_edges IN EXCLUSIVE MODE")
        .execute(&mut *tx)
        .await
        .map_err(NodeWriteError::Database)?;
    let node_id: Option<String> =
        sqlx::query_scalar("SELECT id FROM domain_nodes WHERE id = $1 FOR UPDATE")
            .bind(id)
            .fetch_optional(&mut *tx)
            .await
            .map_err(NodeWriteError::Database)?;
    if node_id.is_none() {
        tx.rollback().await.ok();
        return Err(NodeWriteError::NotFound);
    }

    let edge_ids: Vec<String> = sqlx::query_scalar(
''',
)

# Canonical product boundary: collective content, protected account identity.
spec = root / "docs/specs/garnrolle-knoten-faden.md"
replace_once(
    spec,
    '''Ein Faden ist nicht automatisch ein Gespräch. Gespräche besitzen eigene Entitäten.

### Autorisierung, Richtung und öffentliche Notizen
''',
    '''Ein Faden ist nicht automatisch ein Gespräch. Gespräche besitzen eigene Entitäten.

## Kollektive Bearbeitung und Löschung

Knoten und Fäden sind gemeinschaftlich verwaltete Gewebeelemente. Sie besitzen kein exklusives Bearbeitungsrecht der ursprünglich knüpfenden Garnrolle. Jede angemeldete Garnrolle mit Schreibrecht darf jeden Knoten und jeden Faden bearbeiten oder löschen.

Dabei gelten folgende Integritätsregeln:

1. Technische Identitäten bleiben geschützt: Eine Garnrolle ist der Account-Ursprung und kein kollektiv löschbares Inhaltsobjekt. Ihr privater Account- und Anmeldezustand darf nicht durch fremde Bearbeitung verändert werden.
2. Beim Löschen eines Knotens werden alle Fäden entfernt, die diesen Knoten als Ursprung oder Ziel verwenden. Es dürfen keine verwaisten Fäden entstehen.
3. IDs und Erstellungszeitpunkte bleiben serververwaltet und können nicht überschrieben werden.
4. Die Oberfläche benennt vor jeder Löschung die konkrete Folge; bei Knoten ausdrücklich auch die Entfernung verbundener Fäden.

### Autorisierung, Richtung und öffentliche Notizen
''',
)

print("collective hardening applied")
