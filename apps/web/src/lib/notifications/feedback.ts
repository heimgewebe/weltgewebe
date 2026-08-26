import { NotificationsApiError } from "../api/notifications";

export type NotificationErrorContext =
  | "load"
  | "preference"
  | "device-enable"
  | "device-disable";

export const PUSH_PERMISSION_BLOCKED =
  "Benachrichtigungen sind für CommonThing blockiert. Erlaube sie in den Browser- oder Systemeinstellungen und kehre danach zu dieser Seite zurück.";

const fallbackMessages: Record<NotificationErrorContext, string> = {
  load: "Die Benachrichtigungseinstellungen konnten nicht geladen werden. Versuche es erneut.",
  preference:
    "Die Push-Einstellung konnte nicht gespeichert werden. Versuche es erneut.",
  "device-enable":
    "Dieses Gerät konnte nicht für Push eingerichtet werden. Versuche es erneut.",
  "device-disable":
    "Push konnte auf diesem Gerät nicht deaktiviert werden. Versuche es erneut.",
};

export function describeNotificationError(
  cause: unknown,
  context: NotificationErrorContext,
): string {
  if (cause instanceof NotificationsApiError) {
    if (cause.status === 401) {
      return "Deine Sitzung ist abgelaufen. Melde dich erneut an.";
    }

    switch (cause.code) {
      case "notification_store_unavailable":
      case "notification_database_error":
        return "Die Benachrichtigungseinstellungen sind gerade nicht erreichbar. Deine Nachrichten bleiben im Postfach. Versuche es später erneut.";
      case "push_not_configured":
        return "Push ist auf diesem CommonThing-Server derzeit nicht verfügbar. Deine Nachrichten bleiben im Postfach.";
      case "push_delivery_unavailable":
        return "Push ist vorübergehend nicht verfügbar. Deine Nachrichten bleiben im Postfach. Versuche es später erneut.";
      case "invalid_push_subscription":
        return "Dieses Gerät konnte nicht für Push registriert werden. Lade die Seite neu und versuche es erneut.";
      case "push_subscription_limit_reached":
        return "Für dieses Konto sind bereits 20 Geräte für Push registriert. Deaktiviere Push auf einem anderen Gerät und versuche es erneut.";
      default:
        return fallbackMessages[context];
    }
  }

  if (typeof DOMException !== "undefined" && cause instanceof DOMException) {
    if (cause.name === "NotAllowedError") return PUSH_PERMISSION_BLOCKED;
    if (cause.name === "AbortError") {
      return "Der Browser konnte den Push-Dienst gerade nicht erreichen. Versuche es später erneut.";
    }
    if (cause.name === "InvalidStateError") {
      return "Push kann in dieser Browser-Ansicht gerade nicht eingerichtet werden. Lade die Seite neu und versuche es erneut.";
    }
  }

  return fallbackMessages[context];
}
