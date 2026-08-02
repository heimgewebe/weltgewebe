import { describe, expect, it } from "vitest";
import { deriveTopBarAuthView } from "./topBarAuthState";

describe("deriveTopBarAuthView", () => {
  it("keeps account navigation while authenticated identity is degraded", () => {
    expect(
      deriveTopBarAuthView({
        state: "degraded",
        authenticated: true,
        account_id: "account-a",
        role: "weber",
      }),
    ).toMatchObject({
      showAccountLink: true,
      showLoginLink: false,
      showRetry: true,
      isGuest: false,
    });
  });

  it("keeps retry available while anonymous check is pending", () => {
    expect(
      deriveTopBarAuthView({
        state: "checking",
        authenticated: false,
        role: "gast",
      }),
    ).toMatchObject({
      showAccountLink: false,
      showLoginLink: false,
      showRetry: true,
    });
  });

  it("shows login only after validated guest state", () => {
    expect(
      deriveTopBarAuthView({
        state: "unauthenticated",
        authenticated: false,
        role: "gast",
      }),
    ).toMatchObject({
      showAccountLink: false,
      showLoginLink: true,
      showRetry: false,
      isGuest: false,
    });
  });

  it("marks an authenticated guest so the topbar can surface the role and application entry point", () => {
    expect(
      deriveTopBarAuthView({
        state: "authenticated",
        authenticated: true,
        account_id: "account-guest",
        role: "gast",
      }),
    ).toMatchObject({
      showAccountLink: true,
      isGuest: true,
    });
  });

  it("does not mark an authenticated weber as guest", () => {
    expect(
      deriveTopBarAuthView({
        state: "authenticated",
        authenticated: true,
        account_id: "account-weber",
        role: "weber",
      }),
    ).toMatchObject({
      showAccountLink: true,
      isGuest: false,
    });
  });

  it("does not mark an anonymous visitor as guest, even though the default role value is gast", () => {
    expect(
      deriveTopBarAuthView({
        state: "unauthenticated",
        authenticated: false,
        role: "gast",
      }),
    ).toMatchObject({
      isGuest: false,
    });
  });
});
