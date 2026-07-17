export const TOOL_ACTION_IDS = {
  find: "find",
  content: "content",
  weave: "weave",
  apply: "apply",
} as const;

export type ToolActionId =
  (typeof TOOL_ACTION_IDS)[keyof typeof TOOL_ACTION_IDS];

export type GovernanceEventId = "proposals" | "open" | "voting";

export type GovernanceEventDefinition = Readonly<{
  id: GovernanceEventId;
  label: string;
  href: string;
  symbol: string;
}>;

export const GOVERNANCE_EVENTS: readonly GovernanceEventDefinition[] = [
  {
    id: "proposals",
    label: "Alle Anträge",
    href: "/antraege",
    symbol: "◇",
  },
  {
    id: "open",
    label: "Offene Entscheidungen",
    href: "/antraege?sicht=offen",
    symbol: "◌",
  },
  {
    id: "voting",
    label: "Gespräch & Abstimmung",
    href: "/antraege?sicht=abstimmung",
    symbol: "◎",
  },
];
