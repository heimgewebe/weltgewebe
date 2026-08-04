import { describe, expect, it } from "vitest";
import {
  FADEN_LIFETIME_MS,
  normalizeEdgeLifecycle,
} from "$lib/map/edgeLifecycle";
import type {
  Edge,
  MapEntityNode,
  MapEntityWebgemeindezentrum,
} from "$lib/map/types";
import {
  MAX_VISIBLE_PROPOSAL_ARCS,
  WEAVE_ZONE_ORDER,
  deriveEntityWeave,
  projectEntityWeaves,
  voteStitchConicGradient,
} from "./weaveModel";

const createdAt = Date.parse("2026-08-01T10:00:00Z");
const nowMs = createdAt + 60_000;

function node(overrides: Partial<MapEntityNode> = {}): MapEntityNode {
  return {
    type: "node",
    id: "node-1",
    title: "Gemeinschaftsgarten",
    kind: "Garten",
    tags: ["Natur", "Bildung"],
    created_at: new Date(createdAt).toISOString(),
    lat: 53.5,
    lon: 10,
    ...overrides,
  };
}

function center(): MapEntityWebgemeindezentrum {
  return {
    type: "webgemeindezentrum",
    id: "center-1",
    title: "Webgemeindezentrum",
    lat: 53.5,
    lon: 10,
    summary: "Treffpunkt",
    tags: ["Webgemeindezentrum"],
    created_at: new Date(createdAt).toISOString(),
    updated_at: new Date(createdAt).toISOString(),
    location_state: "confirmed",
    location_state_label: "Bestätigt",
    faden_endpoint_id: "22222222-2222-5222-8222-222222222222",
    conversation_id: "33333333-3333-5333-8333-333333333333",
    location_label: "Park",
    meeting_note: "Treffpunkt",
    access_note: "Zugänglich",
    ortsweberei: {
      id: "ow-1",
      slug: "hamm",
      name: "Ortsweberei Hamm",
      gewebezelle_id: "hamm.weltgewebe.net",
    },
  };
}

function edge(
  id: string,
  fadenType: Edge["faden_type"],
  subjectId: string | undefined,
  targetId = "node-1",
  created = createdAt,
) {
  return normalizeEdgeLifecycle({
    id,
    source_id: `account-${id}`,
    source_type: "account",
    target_id: targetId,
    target_type: "node",
    edge_kind: "reference",
    faden_type: fadenType,
    faden_subject_id: subjectId,
    created_at: new Date(created).toISOString(),
    expires_at: new Date(created + FADEN_LIFETIME_MS).toISOString(),
  });
}

describe("woven node projection", () => {
  it("keeps the canonical core, conversation, proposal and attached-vote order", () => {
    const weave = deriveEntityWeave(node(), [], nowMs);
    expect(WEAVE_ZONE_ORDER).toEqual([
      "knotting",
      "conversation",
      "proposal",
      "vote",
    ]);
    expect(weave.zoneOrder).toEqual(WEAVE_ZONE_ORDER);
  });

  it("derives topic color from the node while action type remains a separate count", () => {
    const weave = deriveEntityWeave(
      node(),
      [edge("knot", "knotting", "node-1")],
      nowMs,
    );
    expect(weave.themeSegments.map((theme) => theme.label)).toEqual([
      "Natur",
      "Bildung",
      "Garten",
    ]);
    expect(
      weave.themeSegments.every((theme) => /^#[0-9a-f]{6}$/i.test(theme.color)),
    ).toBe(true);
    expect(weave.knottingThreadCount).toBe(1);
    expect(weave.primaryThemeColor).toBe(weave.themeSegments[0].color);
  });

  it("builds several proposal arcs and binds conversations and votes to their proposal", () => {
    const weave = deriveEntityWeave(
      node(),
      [
        edge("proposal-a", "proposal", "proposal-a"),
        edge("proposal-b", "proposal", "proposal-b"),
        edge("vote-a", "vote", "proposal-a"),
        edge("discussion-a", "conversation", "proposal-a"),
        edge("general-talk", "conversation", "conversation-node"),
      ],
      nowMs,
    );
    expect(weave.proposalCount).toBe(2);
    expect(weave.proposalArcs).toHaveLength(2);
    const proposalA = weave.proposalArcs.find(
      (arc) => arc.subjectId === "proposal-a",
    );
    expect(proposalA).toMatchObject({
      proposalThreadCount: 1,
      conversationThreadCount: 1,
      voteThreadCount: 1,
      bundledSubjectCount: 1,
    });
    expect(weave.conversationThreadCount).toBe(2);
    expect(weave.voteThreadCount).toBe(1);
  });

  it("does not invent proposal arcs or visible vote counts for orphan votes", () => {
    const weave = deriveEntityWeave(
      node(),
      [edge("vote-orphan", "vote", "proposal-missing")],
      nowMs,
    );
    expect(weave.proposalCount).toBe(0);
    expect(weave.proposalArcs).toEqual([]);
    expect(weave.voteThreadCount).toBe(0);
    expect(weave.totalActiveThreadCount).toBe(0);
  });

  it("binds votes independent of whether the vote or proposal edge arrives first", () => {
    const weave = deriveEntityWeave(
      node(),
      [
        edge("vote-first", "vote", "proposal-a"),
        edge("proposal-second", "proposal", "proposal-a"),
      ],
      nowMs,
    );
    expect(weave.proposalCount).toBe(1);
    expect(weave.voteThreadCount).toBe(1);
    expect(weave.totalActiveThreadCount).toBe(2);
    expect(weave.proposalArcs[0]).toMatchObject({
      subjectId: "proposal-a",
      proposalThreadCount: 1,
      voteThreadCount: 1,
    });
  });

  it("does not attach an active vote to an expired proposal", () => {
    const weave = deriveEntityWeave(
      node(),
      [
        edge(
          "proposal-expired",
          "proposal",
          "proposal-a",
          "node-1",
          createdAt - FADEN_LIFETIME_MS,
        ),
        edge("vote-active", "vote", "proposal-a"),
      ],
      nowMs,
    );
    expect(weave.proposalCount).toBe(0);
    expect(weave.voteThreadCount).toBe(0);
    expect(weave.totalActiveThreadCount).toBe(0);
  });

  it("falls back safely when topic strings are empty", () => {
    expect(
      deriveEntityWeave(node({ kind: "", tags: [""] }), [], nowMs)
        .themeSegments,
    ).toMatchObject([{ label: "Gemeingut" }]);
  });

  it("emits hard transparent gaps around vote stitches", () => {
    expect(voteStitchConicGradient(60, 1)).toBe(
      "conic-gradient(transparent 0deg 28.95deg,#f6ead7 28.95deg 31.05deg,transparent 31.05deg 360deg)",
    );
  });

  it("resolves Webgemeindezentrum activity through the drawable endpoint alias", () => {
    const entity = center();
    const weave = deriveEntityWeave(
      entity,
      [
        edge(
          "proposal-center",
          "proposal",
          "proposal-center",
          entity.faden_endpoint_id,
        ),
      ],
      nowMs,
    );
    expect(weave.proposalCount).toBe(1);
    expect(weave.proposalArcs[0].subjectId).toBe("proposal-center");
  });

  it("indexes relations by drawable target without mutating scene entities", () => {
    const originalNode = node();
    const originalCenter = center();
    const projected = projectEntityWeaves(
      [originalNode, originalCenter],
      [
        edge("talk-node", "conversation", "conversation-node"),
        edge(
          "proposal-center-indexed",
          "proposal",
          "proposal-center-indexed",
          originalCenter.faden_endpoint_id,
        ),
        edge(
          "proposal-unrelated",
          "proposal",
          "proposal-unrelated",
          "node-other",
        ),
      ],
      nowMs,
    );

    expect(originalNode.weave).toBeUndefined();
    expect(originalCenter.weave).toBeUndefined();
    const projectedNode = projected[0] as MapEntityNode;
    const projectedCenter = projected[1] as MapEntityWebgemeindezentrum;
    expect(projectedNode).not.toBe(originalNode);
    expect(projectedNode.weave?.conversationThreadCount).toBe(1);
    expect(projectedNode.weave?.proposalCount).toBe(0);
    expect(projectedCenter.weave?.proposalCount).toBe(1);
  });

  it("omits expired relations from every active zone", () => {
    const weave = deriveEntityWeave(
      node(),
      [edge("expired", "conversation", "conversation-node")],
      createdAt + FADEN_LIFETIME_MS,
    );
    expect(weave.totalActiveThreadCount).toBe(0);
    expect(weave.conversationThreadCount).toBe(0);
    expect(weave.conversationOpacity).toBe(0);
  });

  it("keeps seven proposals separate and uses the eighth visual slot as overflow", () => {
    const sevenEdges = Array.from({ length: 7 }, (_, index) =>
      edge(
        `proposal-seven-${index}`,
        "proposal",
        `proposal-seven-${index}`,
        "node-1",
        createdAt + index,
      ),
    );
    const seven = deriveEntityWeave(node(), sevenEdges, nowMs);
    expect(seven.proposalArcs).toHaveLength(7);
    expect(seven.proposalOverflowCount).toBe(0);

    const eightEdges = [
      ...sevenEdges,
      edge(
        "proposal-eight-7",
        "proposal",
        "proposal-eight-7",
        "node-1",
        createdAt + 7,
      ),
    ];
    const eight = deriveEntityWeave(node(), eightEdges, nowMs);
    expect(eight.proposalArcs).toHaveLength(MAX_VISIBLE_PROPOSAL_ARCS);
    expect(eight.proposalOverflowCount).toBe(1);
    expect(eight.proposalArcs.at(-1)).toMatchObject({
      subjectId: "__proposal-overflow__",
      bundledSubjectCount: 1,
    });
  });

  it("keeps recent proposals separate and represents overflow as one truthful bundle", () => {
    const edges = Array.from({ length: 10 }, (_, index) =>
      edge(
        `proposal-${index}`,
        "proposal",
        `proposal-${index}`,
        "node-1",
        createdAt + index,
      ),
    );
    const weave = deriveEntityWeave(node(), edges, nowMs);
    expect(weave.proposalCount).toBe(10);
    expect(weave.proposalArcs).toHaveLength(MAX_VISIBLE_PROPOSAL_ARCS);
    expect(weave.proposalOverflowCount).toBe(3);
    expect(weave.proposalArcs.at(-1)).toMatchObject({
      subjectId: "__proposal-overflow__",
      bundledSubjectCount: 3,
    });
  });
});
