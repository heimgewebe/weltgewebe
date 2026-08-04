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

function hash(value: string): number {
  let result = 2166136261;
  for (const character of value) {
    result = Math.imul(result ^ character.charCodeAt(0), 16777619);
  }
  return result >>> 0;
}

export function weaveTopics(entity: WeaveEntity): string[] {
  const raw: Array<string | null | undefined> =
    entity.type === "webgemeindezentrum"
      ? ["Gemeinschaft", "Mitentscheiden"]
      : [...(entity.tags ?? []), entity.kind];
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of raw) {
    if (typeof value !== "string") continue;
    const label = value.replace(/^[^:]{1,24}:/, "").trim();
    const key = label.toLowerCase();
    if (!label || IGNORED_THEMES.has(key) || seen.has(key)) continue;
    seen.add(key);
    result.push(label.length > 42 ? `${label.slice(0, 39).trimEnd()}…` : label);
    if (result.length === 6) break;
  }
  return result.length ? result : ["Gemeingut"];
}

export function weaveTopicColor(label: string): string {
  return COLORS[hash(label.toLowerCase()) % COLORS.length];
}

export function primaryWeaveColor(entity: WeaveEntity): string {
  return weaveTopicColor(weaveTopics(entity)[0] ?? "Gemeingut");
}
