from pathlib import Path
import re

path = Path("apps/api/src/domain_db.rs")
text = path.read_text(encoding="utf-8")
start = text.index("pub async fn delete_node_with_edges_in_postgres(")
end = text.index("\n// ── node-create write path", start)
replacement = r'''#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NodeDeleteConversationEffect {
    DeletedEmpty,
    Archived { conversation_id: String },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NodeDeleteOutcome {
    pub removed_edge_ids: Vec<String>,
    pub conversation: NodeDeleteConversationEffect,
}

pub async fn delete_node_with_effects_in_postgres(
    pool: &PgPool,
    id: &str,
) -> Result<NodeDeleteOutcome, NodeWriteError> {
    let mut tx = pool.begin().await.map_err(NodeWriteError::Database)?;
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

    // Lock the generated conversation before deleting the node. The database
    // trigger owns the archive decision; row existence after DELETE is the
    // authoritative distinction between an archive and an empty cascade.
    let conversation_id: Option<String> = sqlx::query_scalar(
        "SELECT id::text FROM domain_conversations \
         WHERE node_id = $1 AND conversation_type = 'node' AND deleted_at IS NULL \
         FOR UPDATE",
    )
    .bind(id)
    .fetch_optional(&mut *tx)
    .await
    .map_err(NodeWriteError::Database)?;
    let conversation_id = match conversation_id {
        Some(value) => value,
        None => {
            tx.rollback().await.ok();
            return Err(NodeWriteError::Mapping(anyhow::anyhow!(
                "node {id} has no active generated conversation"
            )));
        }
    };

    let account_collision_exists: bool =
        sqlx::query_scalar("SELECT EXISTS (SELECT 1 FROM domain_accounts WHERE id = $1)")
            .bind(id)
            .fetch_one(&mut *tx)
            .await
            .map_err(NodeWriteError::Database)?;
    let role_collision_exists: bool = sqlx::query_scalar(
        "SELECT EXISTS (\
             SELECT 1 FROM domain_edges \
             WHERE (source_id = $1 AND payload->>'source_type' = 'role') \
                OR (target_id = $1 AND payload->>'target_type' = 'role')\
         )",
    )
    .bind(id)
    .fetch_one(&mut *tx)
    .await
    .map_err(NodeWriteError::Database)?;
    let untyped_endpoint_is_ambiguous = account_collision_exists || role_collision_exists;

    let invalid_edge: Option<(String, Option<String>, Option<String>)> = sqlx::query_as(
        "SELECT id, \
                CASE WHEN source_id = $1 THEN payload->>'source_type' ELSE NULL END AS source_type, \
                CASE WHEN target_id = $1 THEN payload->>'target_type' ELSE NULL END AS target_type \
         FROM domain_edges \
         WHERE (source_id = $1 AND (\
                    jsonb_typeof(payload) <> 'object' \
                 OR (payload ? 'source_type' AND (\
                        jsonb_typeof(payload->'source_type') <> 'string' \
                        OR payload->>'source_type' NOT IN ('node', 'account', 'role')\
                    )) \
                 OR (NOT (payload ? 'source_type') AND $2)\
               )) \
            OR (target_id = $1 AND (\
                    jsonb_typeof(payload) <> 'object' \
                 OR (payload ? 'target_type' AND (\
                        jsonb_typeof(payload->'target_type') <> 'string' \
                        OR payload->>'target_type' NOT IN ('node', 'account', 'role')\
                    )) \
                 OR (NOT (payload ? 'target_type') AND $2)\
               )) \
         ORDER BY id \
         LIMIT 1",
    )
    .bind(id)
    .bind(untyped_endpoint_is_ambiguous)
    .fetch_optional(&mut *tx)
    .await
    .map_err(NodeWriteError::Database)?;
    if let Some((edge_id, source_type, target_type)) = invalid_edge {
        tx.rollback().await.ok();
        return Err(NodeWriteError::InvalidEdgeReference(format!(
            "edge {edge_id} has source_type={source_type:?} target_type={target_type:?} for endpoint id {id}"
        )));
    }

    let mut edge_ids: Vec<String> = sqlx::query_scalar(
        "DELETE FROM domain_edges \
         WHERE (source_id = $1 AND (\
                    payload->>'source_type' = 'node' \
                 OR (NOT (payload ? 'source_type') AND NOT $2)\
               )) \
            OR (target_id = $1 AND (\
                    payload->>'target_type' = 'node' \
                 OR (NOT (payload ? 'target_type') AND NOT $2)\
               )) \
         RETURNING id",
    )
    .bind(id)
    .bind(untyped_endpoint_is_ambiguous)
    .fetch_all(&mut *tx)
    .await
    .map_err(NodeWriteError::Database)?;
    edge_ids.sort();
    sqlx::query("DELETE FROM domain_nodes WHERE id = $1")
        .bind(id)
        .execute(&mut *tx)
        .await
        .map_err(NodeWriteError::Database)?;

    let conversation_exists: bool = sqlx::query_scalar(
        "SELECT EXISTS (SELECT 1 FROM domain_conversations WHERE id = $1::uuid)",
    )
    .bind(&conversation_id)
    .fetch_one(&mut *tx)
    .await
    .map_err(NodeWriteError::Database)?;
    let conversation = if conversation_exists {
        NodeDeleteConversationEffect::Archived { conversation_id }
    } else {
        NodeDeleteConversationEffect::DeletedEmpty
    };

    tx.commit().await.map_err(NodeWriteError::Database)?;
    Ok(NodeDeleteOutcome {
        removed_edge_ids: edge_ids,
        conversation,
    })
}

pub async fn delete_node_with_edges_in_postgres(
    pool: &PgPool,
    id: &str,
) -> Result<Vec<String>, NodeWriteError> {
    Ok(delete_node_with_effects_in_postgres(pool, id)
        .await?
        .removed_edge_ids)
}
'''.rstrip()
path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
