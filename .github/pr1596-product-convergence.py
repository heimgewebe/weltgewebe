from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 occurrence, found {count}")
    return text.replace(old, new, 1)


# Backend route: distinguish JSONL's lack of a conversation subsystem.
path = "apps/api/src/routes/nodes.rs"
text = read(path)
text = replace_once(
    text,
    """    NodeConversationDeleteEffect, NodeCreateError, NodeDeleteOutcome, NodePatchInput,
    NodeWriteError,
""",
    """    NodeConversationDeleteEffect, NodeCreateError, NodePatchInput, NodeWriteError,
""",
    "nodes import",
)
text = replace_once(
    text,
    """pub enum NodeDeleteConversationResponse {
    DeletedEmpty,
""",
    """pub enum NodeDeleteConversationResponse {
    NotApplicable,
    DeletedEmpty,
""",
    "not applicable response variant",
)
old = """    let outcome = match state.config.domain_node_write_source {
        DomainNodeWriteSource::Jsonl => {
            // Keep the edge lock until the node file has also been replaced. Otherwise a
            // concurrent edge create could attach a new edge between cascade cleanup and
            // node deletion, leaving an orphan behind.
            let _edge_persist_guard = edge_create_persist_lock().lock().await;
            let outcome = delete_node_and_edges_jsonl(
                &id,
                EdgeEndpointCollisionEvidence {
                    account_exists: account_collision_exists,
                    role_exists: false,
                },
            )
            .await
            .map_err(|error| {
                tracing::error!(%error, node_id = %id, "failed to delete node and edges from JSONL");
                if error.kind() == std::io::ErrorKind::InvalidData {
                    NodeMutationError::Message(
                        StatusCode::CONFLICT,
                        "node deletion blocked by ambiguous edge endpoint".to_string(),
                    )
                } else {
                    NodeMutationError::Status(StatusCode::INTERNAL_SERVER_ERROR)
                }
            })?;
            if !outcome.node_deleted {
                return Err(NodeMutationError::Status(StatusCode::INTERNAL_SERVER_ERROR));
            }
            NodeDeleteOutcome {
                removed_edge_ids: outcome.removed_edge_ids,
                conversation: NodeConversationDeleteEffect::DeletedEmpty,
            }
        }
        DomainNodeWriteSource::Postgres => {
            let pool = state
                .db_pool
                .as_ref()
                .ok_or(NodeMutationError::Status(StatusCode::INTERNAL_SERVER_ERROR))?;
            delete_node_with_edges_in_postgres(pool, &id)
                .await
                .map_err(|error| map_postgres_node_delete_error(error, &id))?
        }
    };

    let mut edges = state.edges.write().await;
    for edge_id in cached_edge_ids
        .iter()
        .chain(outcome.removed_edge_ids.iter())
    {
        edges.remove(edge_id);
    }
"""
new = """    let (persisted_edge_ids, conversation) = match state.config.domain_node_write_source {
        DomainNodeWriteSource::Jsonl => {
            // Keep the edge lock until the node file has also been replaced. Otherwise a
            // concurrent edge create could attach a new edge between cascade cleanup and
            // node deletion, leaving an orphan behind.
            let _edge_persist_guard = edge_create_persist_lock().lock().await;
            let outcome = delete_node_and_edges_jsonl(
                &id,
                EdgeEndpointCollisionEvidence {
                    account_exists: account_collision_exists,
                    role_exists: false,
                },
            )
            .await
            .map_err(|error| {
                tracing::error!(%error, node_id = %id, "failed to delete node and edges from JSONL");
                if error.kind() == std::io::ErrorKind::InvalidData {
                    NodeMutationError::Message(
                        StatusCode::CONFLICT,
                        "node deletion blocked by ambiguous edge endpoint".to_string(),
                    )
                } else {
                    NodeMutationError::Status(StatusCode::INTERNAL_SERVER_ERROR)
                }
            })?;
            if !outcome.node_deleted {
                return Err(NodeMutationError::Status(StatusCode::INTERNAL_SERVER_ERROR));
            }
            (
                outcome.removed_edge_ids,
                NodeDeleteConversationResponse::NotApplicable,
            )
        }
        DomainNodeWriteSource::Postgres => {
            let pool = state
                .db_pool
                .as_ref()
                .ok_or(NodeMutationError::Status(StatusCode::INTERNAL_SERVER_ERROR))?;
            let outcome = delete_node_with_edges_in_postgres(pool, &id)
                .await
                .map_err(|error| map_postgres_node_delete_error(error, &id))?;
            (outcome.removed_edge_ids, outcome.conversation.into())
        }
    };

    let mut edges = state.edges.write().await;
    for edge_id in cached_edge_ids.iter().chain(persisted_edge_ids.iter()) {
        edges.remove(edge_id);
    }
"""
text = replace_once(text, old, new, "node delete source outcome")
text = replace_once(
    text,
    """    tracing::info!(event = "node.deleted.collective", node_id = %id, removed_edges = outcome.removed_edge_ids.len(), "Node collectively deleted");
    let response = NodeDeleteResponse {
        node_id: id,
        node_state: "removed",
        removed_edge_ids: outcome.removed_edge_ids,
        conversation: outcome.conversation.into(),
    };
""",
    """    tracing::info!(event = "node.deleted.collective", node_id = %id, removed_edges = persisted_edge_ids.len(), "Node collectively deleted");
    let response = NodeDeleteResponse {
        node_id: id,
        node_state: "removed",
        removed_edge_ids: persisted_edge_ids,
        conversation,
    };
""",
    "node delete response",
)
write(path, text)

# JSONL API proof: the conversation subsystem is not applicable.
path = "apps/api/tests/api_collective_mutations.rs"
text = read(path)
text = replace_once(
    text,
    '    assert_eq!(receipt["conversation"]["effect"], "deleted_empty");\n',
    '    assert_eq!(receipt["conversation"]["effect"], "not_applicable");\n',
    "primary JSONL effect",
)
write(path, text)

# Runtime-validated browser contract.
path = "apps/web/src/lib/api/domainWrites.ts"
text = read(path)
text = replace_once(
    text,
    """export type NodeDeleteConversationEffect =
  | { effect: "deleted_empty" }
  | { effect: "archived"; archive_id: string; archive_url: string };
""",
    """export type NodeDeleteConversationEffect =
  | { effect: "not_applicable" }
  | { effect: "deleted_empty" }
  | { effect: "archived"; archive_id: string; archive_url: string };
""",
    "TypeScript effect union",
)
marker = """export interface NodeDeleteReceipt {
  node_id: string;
  node_state: "removed";
  removed_edge_ids: string[];
  conversation: NodeDeleteConversationEffect;
}

"""
addition = marker + """function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseNodeDeleteReceipt(
  value: unknown,
  expectedNodeId: string,
): NodeDeleteReceipt {
  if (!isRecord(value)) {
    throw new ApiRequestError(502, value);
  }
  const removedEdgeIds = value.removed_edge_ids;
  const conversation = value.conversation;
  if (
    value.node_id !== expectedNodeId ||
    value.node_state !== "removed" ||
    !Array.isArray(removedEdgeIds) ||
    !removedEdgeIds.every((edgeId) => typeof edgeId === "string") ||
    !isRecord(conversation)
  ) {
    throw new ApiRequestError(502, value);
  }

  const effect = conversation.effect;
  let parsedConversation: NodeDeleteConversationEffect;
  if (effect === "not_applicable" || effect === "deleted_empty") {
    parsedConversation = { effect };
  } else if (
    effect === "archived" &&
    typeof conversation.archive_id === "string" &&
    conversation.archive_id.length > 0 &&
    typeof conversation.archive_url === "string" &&
    conversation.archive_url ===
      `/api/conversations/${conversation.archive_id}`
  ) {
    parsedConversation = {
      effect,
      archive_id: conversation.archive_id,
      archive_url: conversation.archive_url,
    };
  } else {
    throw new ApiRequestError(502, value);
  }

  return {
    node_id: expectedNodeId,
    node_state: "removed",
    removed_edge_ids: [...removedEdgeIds],
    conversation: parsedConversation,
  };
}

"""
text = replace_once(text, marker, addition, "node delete runtime parser")
text = replace_once(
    text,
    """  return deleteJson<NodeDeleteReceipt>(
    `/api/nodes/${encodeURIComponent(id)}`,
    etag,
  ).catch((error) => preserveOnlyMatchingNodeConflict(error, id));
""",
    """  return deleteJson<unknown>(
    `/api/nodes/${encodeURIComponent(id)}`,
    etag,
  )
    .then((value) => parseNodeDeleteReceipt(value, id))
    .catch((error) => preserveOnlyMatchingNodeConflict(error, id));
""",
    "deleteNode parser use",
)
write(path, text)

# Focused unit proofs for the runtime parser.
path = "apps/web/src/lib/api/domainWrites.test.ts"
text = read(path)
text = replace_once(
    text,
    'import { deleteNode, replaceNode, updateOwnGarnrolle } from "./domainWrites";\n',
    'import {\n  ApiRequestError,\n  deleteNode,\n  replaceNode,\n  updateOwnGarnrolle,\n} from "./domainWrites";\n',
    "domainWrites test imports",
)
anchor = """  it("keeps the structured delete conflict from JSON responses", async () => {
"""
tests = """  it("accepts the JSONL not-applicable deletion effect", async () => {
    const receipt = {
      node_id: "node-a",
      node_state: "removed",
      removed_edge_ids: [],
      conversation: { effect: "not_applicable" },
    } as const;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(receipt), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(deleteNode("node-a")).resolves.toEqual(receipt);
  });

  it("rejects malformed successful deletion receipts", async () => {
    const malformed = {
      node_id: "node-a",
      node_state: "removed",
      removed_edge_ids: [],
      conversation: {
        effect: "archived",
        archive_id: "conversation-a",
        archive_url: "/api/conversations/another-conversation",
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(malformed), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    const error = await deleteNode("node-a").catch((reason) => reason);
    expect(error).toBeInstanceOf(ApiRequestError);
    expect(error).toMatchObject({ status: 502, body: malformed });
  });

""" + anchor
text = replace_once(text, anchor, tests, "runtime validation tests")
write(path, text)

# Durable archive receipt in the node panel.
path = "apps/web/src/lib/components/panels/NodePanel.svelte"
text = read(path)
text = replace_once(
    text,
    """    replaceNode,
  } from "$lib/api/domainWrites";
""",
    """    replaceNode,
    type NodeDeleteReceipt,
  } from "$lib/api/domainWrites";
""",
    "NodePanel receipt type import",
)
text = replace_once(
    text,
    """    action: "updated" | "deleted";
  };
""",
    """    action: "updated" | "deleted";
    preservePanel?: boolean;
  };
""",
    "NodePanel domain event",
)
text = replace_once(
    text,
    """  let mutationError = "";
""",
    """  let mutationError = "";
  let archiveReceipt:
    | Extract<NodeDeleteReceipt["conversation"], { effect: "archived" }>
    | null = null;
""",
    "archive receipt state",
)
text = replace_once(
    text,
    """    mutationError = "";
  }
""",
    """    mutationError = "";
    archiveReceipt = null;
  }
""",
    "archive receipt reset",
)
old_remove = """    const confirmed = window.confirm(
      "Knoten wirklich löschen? Alle verbundenen Fäden werden gelöscht. Bestehende Gesprächsbeiträge bleiben als schreibgeschütztes Archiv erhalten.",
    );
    if (!confirmed) return;

    deleting = true;
    mutationError = "";
    try {
      await deleteNode(id, nodeDetails?.updated_at);
      dispatch("domainChanged", { kind: "node", id, action: "deleted" });
"""
new_remove = """    const confirmed = window.confirm(
      "Knoten aus dem Gewebe entfernen? Alle verbundenen Fäden werden entfernt. Bestehende Gesprächsbeiträge bleiben als schreibgeschütztes Archiv erhalten.",
    );
    if (!confirmed) return;

    deleting = true;
    mutationError = "";
    try {
      const receipt = await deleteNode(id, nodeDetails?.updated_at);
      if (receipt.conversation.effect === "archived") {
        archiveReceipt = receipt.conversation;
        editing = false;
        activeTab = "uebersicht";
        dispatch("domainChanged", {
          kind: "node",
          id,
          action: "deleted",
          preservePanel: true,
        });
      } else {
        dispatch("domainChanged", { kind: "node", id, action: "deleted" });
      }
"""
text = replace_once(text, old_remove, new_remove, "NodePanel remove handler")
text = replace_once(
    text,
    """<div class="node-mode" class:editing>
  <h3>{nodeDetails?.title || $selection?.data?.title || $selection?.id}</h3>
""",
    """<div class="node-mode" class:editing>
  {#if archiveReceipt}
    <section
      class="archive-receipt"
      data-testid="node-archive-receipt"
      role="status"
    >
      <h3>Knoten aus dem Gewebe entfernt</h3>
      <p>
        Bestehende Gesprächsbeiträge bleiben als schreibgeschütztes Archiv
        erhalten.
      </p>
      <a href={archiveReceipt.archive_url}>Archiv öffnen</a>
    </section>
  {:else}
  <h3>{nodeDetails?.title || $selection?.data?.title || $selection?.id}</h3>
""",
    "NodePanel archive receipt view",
)
text = replace_once(
    text,
    """  {/if}
</div>

<style>
""",
    """  {/if}
  {/if}
</div>

<style>
""",
    "NodePanel archive receipt branch close",
)
text = text.replace(
    '{deleting ? "Löscht…" : "Knoten löschen"}',
    '{deleting ? "Entfernt…" : "Aus dem Gewebe entfernen"}',
)
if "Knoten löschen" in text:
    raise SystemExit("old NodePanel delete label remains")
text = replace_once(
    text,
    """  h3 {
""",
    """  .archive-receipt {
    display: grid;
    gap: 0.75rem;
  }
  .archive-receipt p {
    margin: 0;
    color: var(--muted);
  }
  .archive-receipt a {
    width: fit-content;
    font-weight: 700;
  }
  h3 {
""",
    "NodePanel archive receipt styles",
)
write(path, text)

# Preserve the panel only for an archived receipt, while always refreshing map data.
path = "apps/web/src/lib/components/ContextPanel.svelte"
text = read(path)
text = replace_once(
    text,
    """    action: "updated" | "deleted";
  };
""",
    """    action: "updated" | "deleted";
    preservePanel?: boolean;
  };
""",
    "ContextPanel domain event",
)
write(path, text)

path = "apps/web/src/routes/map/+page.svelte"
text = read(path)
text = replace_once(
    text,
    """  async function handleDomainChanged(
    event: CustomEvent<{ action: "updated" | "deleted" }>,
  ) {
    if (event.detail.action === "deleted") leaveToNavigation();
    await invalidate("weltgewebe:domain-data");
  }
""",
    """  async function handleDomainChanged(
    event: CustomEvent<{
      action: "updated" | "deleted";
      preservePanel?: boolean;
    }>,
  ) {
    if (event.detail.action === "deleted" && !event.detail.preservePanel) {
      leaveToNavigation();
    }
    await invalidate("weltgewebe:domain-data");
  }
""",
    "map domain change handler",
)
write(path, text)

# E2E mock: default JSONL semantics and optional archived response.
path = "apps/web/tests/fixtures/mockApi.ts"
text = read(path)
text = replace_once(
    text,
    """export interface MockApiOptions {
""",
    """export type MockNodeDeleteConversation =
  | { effect: "not_applicable" }
  | { effect: "archived"; archive_id: string; archive_url: string };

export interface MockApiOptions {
""",
    "mock delete type",
)
text = replace_once(
    text,
    """  auth?: { authenticated: boolean; account_id?: string; role?: string };
}
""",
    """  auth?: { authenticated: boolean; account_id?: string; role?: string };
  nodeDeleteConversation?: MockNodeDeleteConversation;
}
""",
    "mock options",
)
text = replace_once(
    text,
    """  let currentRole = options.auth?.role ?? "gast";
""",
    """  let currentRole = options.auth?.role ?? "gast";
  const nodeDeleteConversation = options.nodeDeleteConversation ?? {
    effect: "not_applicable" as const,
  };
""",
    "mock delete default",
)
text = replace_once(
    text,
    """            conversation: { effect: "deleted_empty" },
""",
    """            conversation: nodeDeleteConversation,
""",
    "mock delete response",
)
write(path, text)

# Browser proofs: ordinary removal closes; archive removal retains a receipt.
path = "apps/web/tests/node-mutations.spec.ts"
text = read(path)
text = text.replace("Knoten wirklich löschen", "Knoten aus dem Gewebe entfernen")
text = text.replace(
    'name: "Knoten löschen"',
    'name: "Aus dem Gewebe entfernen"',
)
anchor = """  test("Gast kann einen selbst geknüpften Knoten bearbeiten", async ({
"""
archived_test = """  test("archivierte Gesprächsbeiträge bleiben nach der Entfernung erreichbar", async ({
    page,
  }) => {
    await mockApiResponses(page, {
      auth: {
        authenticated: true,
        account_id: "e2e-weber",
        role: "weber",
      },
      nodeDeleteConversation: {
        effect: "archived",
        archive_id: "70000000-0000-4000-8000-000000000001",
        archive_url:
          "/api/conversations/70000000-0000-4000-8000-000000000001",
      },
    });
    await page.goto("/map");

    const panel = await openFirstNode(page);
    const markerCountBeforeDelete = await page.locator(".map-marker").count();
    await panel.getByRole("tab", { name: "Bearbeiten" }).click();
    page.once("dialog", async (dialog) => {
      expect(dialog.message()).toContain("Aus dem Gewebe entfernen");
      await dialog.accept();
    });
    await panel
      .getByRole("button", { name: "Aus dem Gewebe entfernen" })
      .click();

    const receipt = panel.getByTestId("node-archive-receipt");
    await expect(receipt).toBeVisible();
    await expect(
      receipt.getByRole("link", { name: "Archiv öffnen" }),
    ).toHaveAttribute(
      "href",
      "/api/conversations/70000000-0000-4000-8000-000000000001",
    );
    await expect(page.locator(".map-marker")).toHaveCount(
      markerCountBeforeDelete - 1,
    );
  });

""" + anchor
text = replace_once(text, anchor, archived_test, "archived browser proof")
write(path, text)

# Normative spec: explicit JSONL effect and durable UI receipt.
path = "docs/specs/objektlebenszyklen-und-loeschwirkungen.md"
text = read(path)
anchor = """oder bei vorhandenen Beiträgen:
"""
jsonl = """Für einen JSONL-Betrieb ohne Conversation-Subsystem lautet die Wirkung:

```json
{
  "node_id": "…",
  "node_state": "removed",
  "removed_edge_ids": ["…"],
  "conversation": {
    "effect": "not_applicable"
  }
}
```

`not_applicable` bedeutet ausschließlich, dass dieser Persistenzpfad keine
Conversation verwaltet. Es darf nicht als Löschung einer leeren Conversation
interpretiert werden.

""" + anchor
text = replace_once(text, anchor, jsonl, "JSONL lifecycle effect")
text = replace_once(
    text,
    """Ein Client darf den Erfolg nicht allein aus einem leeren HTTP-Status ableiten,
wenn Nebenwirkungen für den Nutzer relevant sind.
""",
    """Ein Client darf den Erfolg nicht allein aus einem leeren HTTP-Status ableiten,
wenn Nebenwirkungen für den Nutzer relevant sind. Bei `archived` bleibt nach
der Kartenaktualisierung eine sichtbare Quittung mit direktem Link
`Archiv öffnen` erhalten. Daraus folgt keine allgemeine Archivübersicht.
""",
    "visible archive receipt doctrine",
)
write(path, text)
