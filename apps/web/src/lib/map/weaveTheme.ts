import type {
  MapEntityNode,
  MapEntityWebgemeindezentrum,
} from "$lib/map/types";

export const WEAVE_FALLBACK_COLOR = "#76523d";

const COLORS = [
  "#5f7a55",
  "#4f6682",
  "#765a91",
  "#b37a3e",
  "#9c5547",
  "#397572",
  "#af8d37",
  "#78523f",
  "#65705f",
] as const;
const IGNORED_THEMES = new Set([
  "account",
  "demo",
  "garnrolle",
  "knoten",
  "node",
  "webgemeindezentrum",
]);

export type WeaveEntity = MapEntityNode | MapEntityWebgemeindezentrum;

/** Display-only truncation limit. It never reaches topic identity. */
export const WEAVE_TOPIC_DISPLAY_MAX_LENGTH = 42;

// A purely technical namespace ("thema:kunst") is display noise and is dropped.
// A colon that carries meaning stays: "Kunst: Öffentlicher Raum" is one topic,
// not the topic "Öffentlicher Raum" filed under "Kunst". The two are told apart
// by shape, not by a blanket strip — a namespace is a lowercase identifier
// without spaces that is followed immediately by the value.
const TECHNICAL_NAMESPACE_PREFIX = /^[a-z0-9][a-z0-9._-]{0,23}:(?=\S)/;

function hash(value: string): number {
  let result = 2166136261;
  for (const character of value) {
    result = Math.imul(result ^ character.charCodeAt(0), 16777619);
  }
  return result >>> 0;
}

/**
 * Canonical text of one topic: compatibility-normalized, whitespace-unified and
 * trimmed. Two spellings that differ only in NBSP, repeated spaces or fullwidth
 * forms are the same topic and must produce the same text.
 */
export function normalizeWeaveTopicText(value: string): string {
  return value
    .normalize("NFKC")
    .replace(/\s+/gu, " ")
    .trim()
    .replace(TECHNICAL_NAMESPACE_PREFIX, "")
    .trim();
}

/**
 * Identity of one topic. Derived from the complete normalized text — never from
 * a shortened display form, because two long topics that share a prefix
 * ("… Hamburg" / "… Hannover") are different topics and must stay apart in
 * deduplication, hashing, segment ids and colour.
 */
export function weaveTopicIdentity(label: string): string {
  return normalizeWeaveTopicText(label).toLocaleLowerCase("de-DE");
}

/** Shortening is a late presentation decision and carries no identity. */
export function weaveTopicDisplayLabel(label: string): string {
  return label.length > WEAVE_TOPIC_DISPLAY_MAX_LENGTH
    ? `${label.slice(0, WEAVE_TOPIC_DISPLAY_MAX_LENGTH - 3).trimEnd()}…`
    : label;
}

/** Full normalized topic texts, deduplicated by identity, never truncated. */
export function weaveTopics(entity: WeaveEntity): string[] {
  const raw: Array<string | null | undefined> =
    entity.type === "webgemeindezentrum"
      ? ["Gemeinschaft", "Mitentscheiden"]
      : [...(entity.tags ?? []), entity.kind];
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of raw) {
    if (typeof value !== "string") continue;
    const label = normalizeWeaveTopicText(value);
    const key = weaveTopicIdentity(label);
    if (!label || IGNORED_THEMES.has(key) || seen.has(key)) continue;
    seen.add(key);
    result.push(label);
    if (result.length === 6) break;
  }
  return result.length ? result : ["Gemeingut"];
}

export function weaveTopicColor(label: string): string {
  return COLORS[hash(weaveTopicIdentity(label)) % COLORS.length];
}

export function primaryWeaveColor(entity: WeaveEntity): string {
  return weaveTopicColor(weaveTopics(entity)[0] ?? "Gemeingut");
}
