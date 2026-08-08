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
  CONVERSATION_RING_MIN_SCALE,
  CONVERSATION_RING_MAX_SCALE,
  MAX_VISIBLE_PROPOSAL_ARCS,
  MAX_VISIBLE_VOTE_STITCHES,
  MAX_X_CORE_THEMES,
  WEAVE_ZONE_ORDER,
  assignXCoreSegments,
  conversationRingScale,
  deriveArmOverlays,
  deriveEntityWeave,
  deriveWeaveThemeSegments,
  maxWeaveDomNodeBudget,
  projectEntityWeaves,
  targetThemePalette,
  voteStitchConicGradient,
} from "./weaveModel";
import {
  WEAVE_TOPIC_DISPLAY_MAX_LENGTH,
  weaveTopicDisplayLabel,
  weaveTopicIdentity,
  weaveTopics,
} from "./weaveTheme";

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
    expect(weave.primaryThemeColor).toBe(weave.xCoreSegments[0].color);
    expect(weave.xCoreSegments).toHaveLength(4);
  });

  it("colours one theme across all four X arms", () => {
    const arms = assignXCoreSegments(["Natur"]);
    expect(arms).toHaveLength(4);
    expect(new Set(arms.map((arm) => arm.color)).size).toBe(1);
    expect(arms.map((arm) => arm.arm)).toEqual([
      "northwest",
      "northeast",
      "southeast",
      "southwest",
    ]);
  });

  it("keeps one selected controlled topic semantically one-coloured", () => {
    const weave = deriveEntityWeave(
      node({
        tags: ["thema:natur", "Werkstatt"],
        kind: "Garten",
      }),
      [],
      nowMs,
    );

    expect(weave.themeSegments.map((segment) => segment.id)).toEqual([
      "thema:natur",
    ]);
    expect(weave.themeSegments.map((segment) => segment.label)).toEqual([
      "Natur",
    ]);
    const palette = targetThemePalette(weave);
    expect(palette).toHaveLength(1);
    expect(
      new Set(weave.xCoreSegments.map((segment) => segment.color)),
    ).toEqual(new Set(palette));
  });

  it("assigns two themes to the two diagonal strands", () => {
    const arms = assignXCoreSegments(["Natur", "Bildung"]);
    const byArm = Object.fromEntries(
      arms.map((segment) => [segment.arm, segment.themeId]),
    );
    expect(byArm.northwest).toBe(byArm.southeast);
    expect(byArm.northeast).toBe(byArm.southwest);
    expect(byArm.northwest).not.toBe(byArm.northeast);
  });

  it("distributes three and four themes stably across arms", () => {
    const three = assignXCoreSegments(["A", "B", "C"]);
    expect(three.map((segment) => segment.themeId)).toEqual([
      weaveTopicIdentity("A"),
      weaveTopicIdentity("B"),
      weaveTopicIdentity("C"),
      weaveTopicIdentity("A"),
    ]);
    const four = assignXCoreSegments(["A", "B", "C", "D"]);
    expect(four.map((segment) => segment.arm)).toEqual([
      "northwest",
      "northeast",
      "southeast",
      "southwest",
    ]);
    expect(new Set(four.map((segment) => segment.themeId)).size).toBe(4);
  });

  it("deduplicates normalized identities before the four-arm visual cap", () => {
    const arms = assignXCoreSegments([
      "Natur",
      " Natur ",
      "Bildung",
      "Kunst",
      "Handwerk",
    ]);
    expect(arms.map((segment) => segment.themeId)).toEqual([
      weaveTopicIdentity("Natur"),
      weaveTopicIdentity("Bildung"),
      weaveTopicIdentity("Kunst"),
      weaveTopicIdentity("Handwerk"),
    ]);
  });

  it("uses controlled knotting topics exclusively for the visible X colours", () => {
    const weave = deriveEntityWeave(
      node({
        tags: [
          "Werkstatt",
          "thema:natur",
          "thema:kunst",
          "thema:wohnen",
          "offen",
        ],
        kind: "Garten",
      }),
      [],
      nowMs,
    );

    expect(weave.themeSegments.map((segment) => segment.id)).toEqual([
      "thema:wohnen",
      "thema:natur",
      "thema:kunst",
    ]);
    expect(weave.themeSegments.map((segment) => segment.label)).toEqual([
      "Wohnen",
      "Natur",
      "Kunst",
    ]);
    expect(weave.xCoreSegments.map((segment) => segment.themeId)).toEqual([
      "thema:wohnen",
      "thema:natur",
      "thema:kunst",
      "thema:wohnen",
    ]);
  });

  it("keeps more than four theme identities while painting only four arms", () => {
    const tags = ["T1", "T2", "T3", "T4", "T5", "T6"];
    const weave = deriveEntityWeave(
      node({ tags, kind: "Werkstatt" }),
      [],
      nowMs,
    );
    expect(weave.themeSegments.length).toBeGreaterThan(MAX_X_CORE_THEMES);
    expect(weave.xCoreSegments).toHaveLength(4);
    const painted = new Set(
      weave.xCoreSegments.map((segment) => segment.themeId),
    );
    expect(painted.size).toBe(MAX_X_CORE_THEMES);
    expect(weave.themeSegments.some((segment) => segment.arm === null)).toBe(
      true,
    );
  });

  it("keeps two long topics with an identical prefix apart", () => {
    const hamburg = "Nachbarschaftliche Lebensmittelversorgung Hamburg";
    const hannover = "Nachbarschaftliche Lebensmittelversorgung Hannover";
    expect(hamburg.length).toBeGreaterThan(WEAVE_TOPIC_DISPLAY_MAX_LENGTH);
    expect(hannover.length).toBeGreaterThan(WEAVE_TOPIC_DISPLAY_MAX_LENGTH);

    const segments = deriveWeaveThemeSegments(
      node({ tags: [hamburg, hannover], kind: "Versorgung" }),
    );
    const versorgung = segments.filter((segment) =>
      segment.id.startsWith("Nachbarschaftliche"),
    );

    expect(versorgung).toHaveLength(2);
    expect(versorgung[0].id).not.toBe(versorgung[1].id);
    expect(versorgung[0].color).not.toBe(versorgung[1].color);
    // Shortening stays a display decision and never reaches identity.
    expect(versorgung[0].label.length).toBeLessThanOrEqual(
      WEAVE_TOPIC_DISPLAY_MAX_LENGTH,
    );
    expect(versorgung[0].id).toBe(weaveTopicIdentity(hamburg));
  });

  it("normalizes NBSP, repeated whitespace and fullwidth characters into one topic", () => {
    expect(weaveTopicIdentity("Offene Werkstatt")).toBe(
      weaveTopicIdentity("Offene   Werkstatt"),
    );
    expect(weaveTopicIdentity("  Offene Werkstatt  ")).toBe(
      weaveTopicIdentity("Offene Werkstatt"),
    );
    // Fullwidth latin letters are compatibility-equivalent under NFKC.
    expect(weaveTopicIdentity("Ｋｕｎｓｔ")).toBe(weaveTopicIdentity("Kunst"));

    // The first tag separates with NBSP: one topic, so only one segment.
    expect(
      weaveTopics(node({ tags: ["Offene Werkstatt", "Offene Werkstatt"] })),
    ).toEqual(["Offene Werkstatt", "Garten"]);
  });

  it("treats case-different normalised topics as distinct identities", () => {
    expect(weaveTopicIdentity("Kunst")).toBe("Kunst");
    expect(weaveTopicIdentity("kunst")).toBe("kunst");
    expect(weaveTopicIdentity("Kunst")).not.toBe(weaveTopicIdentity("kunst"));
    const topics = weaveTopics(
      node({ tags: ["Kunst", "kunst"], kind: "Atelier" }),
    );
    expect(topics).toEqual(["Kunst", "kunst", "Atelier"]);
    const segments = deriveWeaveThemeSegments(
      node({ tags: ["Kunst", "kunst"], kind: "Atelier" }),
    );
    expect(segments.map((segment) => segment.id)).toEqual([
      "Kunst",
      "kunst",
      "Atelier",
    ]);
    expect(segments[0].color).not.toBe(segments[1].color);
  });

  it("keeps every distinct topic beyond sixteen while painting only four arms", () => {
    const tags = Array.from({ length: 20 }, (_, index) => `Thema-${index + 1}`);
    const topics = weaveTopics(node({ tags, kind: "Knoten" }));
    // kind "Knoten" is ignored; all twenty tags remain as identities.
    expect(topics).toHaveLength(20);
    expect(new Set(topics).size).toBe(20);
    const weave = deriveEntityWeave(node({ tags, kind: "Knoten" }), [], nowMs);
    expect(weave.themeSegments).toHaveLength(20);
    expect(weave.xCoreSegments).toHaveLength(4);
    expect(
      new Set(weave.xCoreSegments.map((segment) => segment.themeId)).size,
    ).toBe(MAX_X_CORE_THEMES);
  });

  it("keeps meaningful colons in identity and only drops allowlisted technical noise for display", () => {
    expect(weaveTopics(node({ tags: ["Kunst: Öffentlicher Raum"] }))).toEqual([
      "Kunst: Öffentlicher Raum",
      "Garten",
    ]);
    // Identity keeps the full normalised text — no prefix strip before hash/id.
    expect(weaveTopics(node({ tags: ["thema:kunst"] }))).toEqual([
      "thema:kunst",
    ]);
    expect(weaveTopicIdentity("thema:kunst")).toBe("thema:kunst");
    expect(weaveTopicDisplayLabel("thema:kunst")).toBe("Kunst");
    // Meaningful lowercase prefix must not be stripped generically.
    expect(weaveTopicDisplayLabel("kunst:öffentlicher raum")).toBe(
      "kunst:öffentlicher raum",
    );
    expect(weaveTopicIdentity("kunst:öffentlicher raum")).toBe(
      "kunst:öffentlicher raum",
    );
    expect(weaveTopicIdentity("Kunst: Öffentlicher Raum")).not.toBe(
      weaveTopicIdentity("Öffentlicher Raum"),
    );
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

  it("emits hard transparent gaps around vote stitches and caps visible stitches", () => {
    expect(voteStitchConicGradient(60, 1)).toBe(
      "conic-gradient(transparent 0deg 28.95deg,#f6ead7 28.95deg 31.05deg,transparent 31.05deg 360deg)",
    );
    const many = voteStitchConicGradient(90, 100);
    const visibleStops = many.match(/#f6ead7/g) ?? [];
    expect(visibleStops).toHaveLength(MAX_VISIBLE_VOTE_STITCHES);
  });

  it("scales conversation-ring diameter with active thread count and saturates", () => {
    expect(conversationRingScale(0)).toBe(0);
    expect(conversationRingScale(Number.NaN)).toBe(0);

    const oneScale = conversationRingScale(1);
    const fewScale = conversationRingScale(4);
    const manyScale = conversationRingScale(40);
    expect(oneScale).toBe(CONVERSATION_RING_MIN_SCALE);
    expect(fewScale).toBeGreaterThan(oneScale);
    expect(manyScale).toBe(CONVERSATION_RING_MAX_SCALE);
    expect(conversationRingScale(20)).toBe(CONVERSATION_RING_MAX_SCALE);
    expect(conversationRingScale(21)).toBe(CONVERSATION_RING_MAX_SCALE);
    expect(conversationRingScale(Number.POSITIVE_INFINITY)).toBe(0);

    const one = deriveEntityWeave(
      node(),
      [edge("talk", "conversation", "conversation-node")],
      nowMs,
    );
    const four = deriveEntityWeave(
      node(),
      Array.from({ length: 4 }, (_, index) =>
        edge(`talk-${index}`, "conversation", `conversation-${index}`),
      ),
      nowMs,
    );
    expect(one.conversationRingScale).toBeCloseTo(oneScale);
    expect(four.conversationThreadCount).toBe(4);
    expect(four.conversationRingScale).toBeGreaterThan(
      one.conversationRingScale,
    );
  });

  it("projects empty arm overlays until a content source exists", () => {
    expect(deriveArmOverlays(node())).toEqual([]);
    expect(deriveEntityWeave(node(), [], nowMs).armOverlays).toEqual([]);
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
    expect(weave.conversationRingScale).toBe(0);
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

  it("exposes a full target theme palette for edge paint", () => {
    const weave = deriveEntityWeave(
      node({ tags: ["Natur", "Bildung", "Kunst"], kind: "Garten" }),
      [],
      nowMs,
    );
    const palette = targetThemePalette(weave);
    expect(palette.length).toBeGreaterThan(1);
    expect(palette.length).toBeLessThanOrEqual(MAX_X_CORE_THEMES);
  });

  it("documents a fixed DOM-node budget for the maximal marker", () => {
    expect(maxWeaveDomNodeBudget()).toBeLessThanOrEqual(40);
    expect(maxWeaveDomNodeBudget()).toBeGreaterThan(10);
  });

  it("keeps weave projection complexity and output within deterministic bounds", () => {
    const entity = node({
      tags: ["Natur", "Bildung", "Kunst", "Handwerk", "Nachbarschaft"],
      kind: "Garten",
    });
    const edges = [
      ...Array.from({ length: 12 }, (_, index) =>
        edge(`k-${index}`, "knotting", "node-1", "node-1", createdAt + index),
      ),
      ...Array.from({ length: 30 }, (_, index) =>
        edge(
          `c-${index}`,
          "conversation",
          "conversation-node",
          "node-1",
          createdAt + index,
        ),
      ),
      ...Array.from({ length: 12 }, (_, index) =>
        edge(
          `p-${index}`,
          "proposal",
          `proposal-${index}`,
          "node-1",
          createdAt + index,
        ),
      ),
      ...Array.from({ length: 40 }, (_, index) =>
        edge(
          `v-${index}`,
          "vote",
          `proposal-${index % 12}`,
          "node-1",
          createdAt + index,
        ),
      ),
    ];

    const weave = deriveEntityWeave(entity, edges, nowMs);
    // Deterministic structural ceilings — not wall-clock flake targets.
    expect(weave.xCoreSegments).toHaveLength(4);
    expect(weave.themeSegments.length).toBeLessThanOrEqual(6);
    expect(weave.proposalArcs).toHaveLength(MAX_VISIBLE_PROPOSAL_ARCS);
    expect(weave.proposalCount).toBe(12);
    expect(weave.proposalOverflowCount).toBe(
      12 - MAX_VISIBLE_PROPOSAL_ARCS + 1,
    );
    expect(weave.armOverlays).toHaveLength(0);
    expect(weave.voteThreadCount).toBe(40);
    for (const arc of weave.proposalArcs) {
      expect(arc.voteThreadCount).toBeLessThanOrEqual(40);
    }

    // Linear output: projecting N entities yields exactly N view models.
    for (const size of [100, 500, 1000] as const) {
      const entities = Array.from({ length: size }, (_, index) =>
        node({ id: `node-${index}`, tags: entity.tags, kind: entity.kind }),
      );
      const projected = projectEntityWeaves(entities, edges, nowMs);
      expect(projected).toHaveLength(size);
      expect(
        projected.every(
          (item) =>
            item.type === "node" && item.weave?.xCoreSegments.length === 4,
        ),
      ).toBe(true);
    }

    // Hang guard only: far above any healthy host; never a tight CI flake gate.
    const started = performance.now();
    for (let index = 0; index < 1000; index += 1) {
      deriveEntityWeave(entity, edges, nowMs + index);
    }
    expect(performance.now() - started).toBeLessThan(30_000);
  });
});
