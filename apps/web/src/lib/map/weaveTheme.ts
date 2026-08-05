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

/**
 * Only these exact technical namespaces may be stripped for the final visible
 * label. Generic "word:" prefixes stay — meaningful topics such as
 * `kunst:öffentlicher raum` must not lose their colon-bearing identity text.
 * Identity, deduplication, hash, colour and segment ids always keep the full
 * normalised text, including any colon.
 */
const TECHNICAL_NAMESPACE_ALLOWLIST = new Set(["thema"]);

/**
 * FNV-1a over Unicode code points. Iterating the string already yields full
 * code points (including supplementary-plane characters); hashing must not fall
 * back to UTF-16 code units via `charCodeAt`, or emoji/astral topics would only
 * fold the high surrogate into the colour.
 */
function hash(value: string): number {
  let result = 2166136261;
  for (const character of value) {
    const codePoint = character.codePointAt(0);
    if (codePoint === undefined) continue;
    result = Math.imul(result ^ codePoint, 16777619);
  }
  return result >>> 0;
}

function countGraphemes(value: string): number {
  if (typeof Intl !== "undefined" && "Segmenter" in Intl) {
    return Array.from(
      new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(value),
    ).length;
  }
  // Fallback: code points, still safer than UTF-16 code units for astral text.
  return Array.from(value).length;
}

function takeGraphemes(value: string, maxGraphemes: number): string {
  if (maxGraphemes <= 0) return "";
  if (typeof Intl !== "undefined" && "Segmenter" in Intl) {
    let taken = "";
    let count = 0;
    for (const { segment } of new Intl.Segmenter(undefined, {
      granularity: "grapheme",
    }).segment(value)) {
      if (count >= maxGraphemes) break;
      taken += segment;
      count += 1;
    }
    return taken;
  }
  return Array.from(value).slice(0, maxGraphemes).join("");
}

/**
 * Canonical text of one topic: compatibility-normalised, whitespace-unified and
 * trimmed. No prefix stripping and no case folding — identity, hash, colour and
 * segment ids all consume this exact form.
 */
export function normalizeWeaveTopicText(value: string): string {
  return value.normalize("NFKC").replace(/\s+/gu, " ").trim();
}

/**
 * Identity of one topic. Exact user contract:
 * `value.normalize('NFKC').replace(/\s+/g, ' ').trim()`.
 * Never shortened, never case-folded, never prefix-stripped. Ignore/compare
 * helpers may still fold case separately.
 */
export function weaveTopicIdentity(label: string): string {
  return normalizeWeaveTopicText(label);
}

/** Case-insensitive membership in the technical ignore set only. */
function isIgnoredThemeIdentity(identity: string): boolean {
  return IGNORED_THEMES.has(identity.toLocaleLowerCase("de-DE"));
}

/**
 * Drop only an allowlisted technical namespace for display. Meaningful colons
 * (`Kunst: Öffentlicher Raum`, `kunst:öffentlicher raum`) stay intact.
 */
function stripAllowlistedTechnicalNamespace(value: string): string {
  const colon = value.indexOf(":");
  if (colon <= 0) return value;
  const namespace = value.slice(0, colon);
  if (!TECHNICAL_NAMESPACE_ALLOWLIST.has(namespace)) return value;
  const remainder = value.slice(colon + 1).trim();
  return remainder || value;
}

/**
 * Shortening is a late presentation decision and carries no identity.
 * Only at this stage may an allowlisted technical namespace be dropped and the
 * remaining grapheme clusters truncated for the visible label.
 */
export function weaveTopicDisplayLabel(label: string): string {
  const normalised = normalizeWeaveTopicText(label);
  const withoutNoise = stripAllowlistedTechnicalNamespace(normalised);
  const display = withoutNoise || normalised;
  if (countGraphemes(display) <= WEAVE_TOPIC_DISPLAY_MAX_LENGTH) return display;
  const body = takeGraphemes(
    display,
    Math.max(0, WEAVE_TOPIC_DISPLAY_MAX_LENGTH - 1),
  ).trimEnd();
  return `${body}…`;
}

/**
 * Full normalised topic texts, deduplicated by identity, never truncated and
 * never hard-capped. The model keeps every distinct topic; the X core later
 * compresses the visual to at most four primary arm colours.
 */
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
    if (!label || isIgnoredThemeIdentity(key) || seen.has(key)) continue;
    seen.add(key);
    result.push(label);
  }
  return result.length ? result : ["Gemeingut"];
}

/** Testable FNV-1a of the topic identity over Unicode code points. */
export function weaveTopicHash(label: string): number {
  return hash(weaveTopicIdentity(label));
}

export function weaveTopicColor(label: string): string {
  return COLORS[weaveTopicHash(label) % COLORS.length];
}

export function primaryWeaveColor(entity: WeaveEntity): string {
  return weaveTopicColor(weaveTopics(entity)[0] ?? "Gemeingut");
}
