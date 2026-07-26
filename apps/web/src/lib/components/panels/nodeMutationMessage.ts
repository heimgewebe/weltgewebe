import { ApiRequestError } from "$lib/api/domainWrites";

export type NodeMutationAction = "save" | "delete";

export function nodeMutationMessage(
  error: unknown,
  action: NodeMutationAction,
): string {
  const deleting = action === "delete";
  if (error instanceof ApiRequestError) {
    if (error.status === 401 || error.status === 403) {
      return "Diese Garnrolle darf derzeit nicht schreiben.";
    }
    if (error.status === 404) return "Der Knoten existiert nicht mehr.";
    if (error.status === 400) {
      return "Die Eingaben sind ungültig. Bitte prüfe alle Felder.";
    }
    if (error.status === 409) {
      const reason =
        typeof error.body === "string"
          ? error.body
          : (error.body as { code?: unknown } | undefined)?.code;
      if (
        deleting &&
        (reason === "node_conversation_not_empty" ||
          (typeof reason === "string" &&
            reason.includes("conversation contains contributions")))
      ) {
        return "Dieser Knoten kann nicht gelöscht werden, weil sein öffentliches Gespräch Beiträge enthält. Die öffentliche Geschichte bleibt geschützt; du kannst ihn weiter bearbeiten.";
      }
      return `Der Knoten konnte wegen eines Datenkonflikts nicht ${deleting ? "gelöscht" : "geändert"} werden. Es wurde nichts verändert.`;
    }
    if (error.status === 428) {
      return "Die geladene Knotenversion ist unvollständig. Bitte öffne den Knoten erneut und versuche es noch einmal.";
    }
  }
  return deleting
    ? "Der Knoten konnte nicht gelöscht werden."
    : "Die Änderung konnte nicht gespeichert werden.";
}
