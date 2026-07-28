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
    });
  });
});
