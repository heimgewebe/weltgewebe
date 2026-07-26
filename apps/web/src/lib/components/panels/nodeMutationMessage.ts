import { ApiRequestError } from "$lib/api/domainWrites";

export type NodeMutationAction = "save" | "delete";

function errorBodyParts(body: unknown): string[] {
  if (typeof body === "string") return [body];
  if (!body || typeof body !== "object") return [];

  const record = body as Record<string, unknown>;
  return [record.code, record.message, record.error].filter(
    (value): value is string => typeof value === "string",
  );
}

function hasErrorReason(error: ApiRequestError, reason: string): boolean {
  return errorBodyParts(error.body).some(
    (part) => part === reason || part.includes(reason),
  );
}

export function nodeMutationMessage(
  error: unknown,
  action: NodeMutationAction,
): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 401 || error.status === 403) {
      return "Diese Garnrolle darf derzeit nicht schreiben.";
    }
    if (error.status === 404) return "Der Knoten existiert nicht mehr.";
    if (error.status === 400) {
      return "Die Eingaben sind ungültig. Bitte prüfe alle Felder.";
    }
    if (error.status === 409) {
      if (action === "delete") {
        if (
          hasErrorReason(error, "node_conversation_not_empty") ||
          hasErrorReason(
            error,
            "node deletion blocked because its public conversation contains contributions",
          ) ||
          hasErrorReason(
            error,
            "node deletion blocked by existing conversation messages",
          )
        ) {
          return "Dieser Knoten kann nicht gelöscht werden, weil sein öffentliches Gespräch Beiträge enthält. Das Gespräch bleibt als Teil der öffentlichen Geschichte geschützt; du kannst den Knoten weiterhin bearbeiten.";
        }
        if (
          hasErrorReason(
            error,
            "node deletion requires matching node and edge write sources",
          )
        ) {
          return "Der Knoten kann derzeit wegen einer technischen Inkonsistenz nicht gelöscht werden. Es wurde nichts verändert.";
        }
        if (
          hasErrorReason(
            error,
            "node deletion blocked by ambiguous edge endpoint",
          )
        ) {
          return "Der Knoten kann derzeit nicht sicher gelöscht werden, weil mindestens eine Verbindung nicht eindeutig zugeordnet ist. Es wurde nichts verändert.";
        }
      }
      return action === "delete"
        ? "Der Knoten konnte wegen eines Datenkonflikts nicht gelöscht werden. Es wurde nichts verändert."
        : "Der Knoten konnte wegen eines Datenkonflikts nicht geändert werden. Es wurde nichts verändert.";
    }
    if (error.status === 428) {
      return "Die geladene Knotenversion ist unvollständig. Bitte öffne den Knoten erneut und versuche es noch einmal.";
    }
  }
  return action === "delete"
    ? "Der Knoten konnte nicht gelöscht werden."
    : "Die Änderung konnte nicht gespeichert werden.";
}
