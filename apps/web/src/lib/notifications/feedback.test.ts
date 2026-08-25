import { describe, expect, it } from "vitest";
import { NotificationsApiError } from "../api/notifications";
import { PUSH_PERMISSION_BLOCKED, describeNotificationError } from "./feedback";

describe("notification feedback", () => {
  it("maps store failures safely", () => {
    const error = new NotificationsApiError(
      500,
      "notification_database_error",
      "internal database detail",
    );

    const message = describeNotificationError(error, "load");

    expect(message).toContain("gerade nicht erreichbar");
    expect(message).toContain("Nachrichten bleiben im Postfach");
    expect(message).not.toContain("internal database detail");
  });

  it("hides unknown backend messages", () => {
    const error = new NotificationsApiError(
      500,
      "unexpected_backend_failure",
      "sensitive implementation detail",
    );

    expect(describeNotificationError(error, "preference")).toBe(
      "Die Push-Einstellung konnte nicht gespeichert werden. Versuche es erneut.",
    );
  });

  it("hides raw browser errors while enabling", () => {
    expect(
      describeNotificationError(
        new Error("Failed to fetch https://internal.example.invalid"),
        "device-enable",
      ),
    ).toBe(
      "Dieses Gerät konnte nicht für Push eingerichtet werden. Versuche es erneut.",
    );
  });

  it("hides raw browser errors while disabling", () => {
    expect(
      describeNotificationError(
        new Error("DELETE https://internal.example.invalid failed"),
        "device-disable",
      ),
    ).toBe(
      "Push konnte auf diesem Gerät nicht deaktiviert werden. Versuche es erneut.",
    );
  });

  it("surfaces expired sessions while disabling", () => {
    const error = new NotificationsApiError(
      401,
      "unauthorized",
      "raw authentication detail",
    );

    expect(describeNotificationError(error, "device-disable")).toBe(
      "Deine Sitzung ist abgelaufen. Melde dich erneut an.",
    );
  });

  it("explains device limit", () => {
    const error = new NotificationsApiError(
      429,
      "push_subscription_limit_reached",
      "the account has reached the active Web Push device limit",
    );

    expect(describeNotificationError(error, "device-enable")).toBe(
      "Für dieses Konto sind bereits 20 Geräte für Push registriert. Deaktiviere Push auf einem anderen Gerät und versuche es erneut.",
    );
  });

  it("maps denied browser permission", () => {
    if (typeof DOMException === "undefined") return;

    expect(
      describeNotificationError(
        new DOMException("permission denied", "NotAllowedError"),
        "device-enable",
      ),
    ).toBe(PUSH_PERMISSION_BLOCKED);
  });
});
