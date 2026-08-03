import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createWeberProposal,
  formatRemaining,
  statusLabel,
  submitVote,
} from "./governance";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("governance API", () => {
  it("creates only a Weberantrag and trims the summary", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "p1", kind: "weberantrag" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createWeberProposal("  Ich möchte mitweben.  ");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/proposals",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({
          kind: "weberantrag",
          summary: "Ich möchte mitweben.",
        }),
      }),
    );
  });

  it("binds an application opened in a center to that exact center", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "p2", kind: "weberantrag" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createWeberProposal(
      "Ich möchte vor Ort mitweben.",
      "webgemeindezentrum-hammer-park",
    );

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({
      kind: "weberantrag",
      summary: "Ich möchte vor Ort mitweben.",
      webgemeindezentrum_id: "webgemeindezentrum-hammer-park",
    });
  });

  it("sends one current vote without any quorum field", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ choice: "ja" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await submitVote("proposal 1", "ja");

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({ choice: "ja" });
    expect(init.method).toBe("PUT");
  });

  it("preserves HTTP status for understandable UI errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("wrong phase", { status: 409 })),
    );

    await expect(submitVote("p1", "nein")).rejects.toMatchObject({
      status: 409,
      message: "wrong phase",
    });
  });
});

describe("governance presentation", () => {
  it("renders phase labels", () => {
    expect(statusLabel("consent")).toBe("Offene Konsentphase");
    expect(statusLabel("voting")).toBe("Gespräch und Abstimmung");
  });

  it("formats remaining time without inventing a quorum", () => {
    expect(formatRemaining(7 * 86_400 + 2 * 3_600)).toBe("7 T. 2 Std.");
    expect(formatRemaining(undefined)).toBe("abgeschlossen");
  });
});
