const NODE_KIND_LABELS: Record<string, string> = {
  standard: "Allgemeiner Knoten",
  event: "Ereignis",
  resource: "Ressource",
};

export function nodeKindLabel(kind?: string | null): string {
  if (!kind) return "Knoten";
  return NODE_KIND_LABELS[kind.toLowerCase()] ?? "Knoten";
}
