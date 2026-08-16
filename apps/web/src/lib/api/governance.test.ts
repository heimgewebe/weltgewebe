import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createSachProposal,
  createWeberProposal,
  formatRemaining,
  proposalStatusLabel,
  requestProposalRepeal,
  statusLabel,
  submitVote,
  withdrawProposal,
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

  it("creates a node-addressed Sachantrag without requiring a center", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "s1", kind: "sachantrag" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createSachProposal(
      "  Neue Nutzung beschließen  ",
      "  Gemeinsam beraten.  ",
      undefined,
      "node-1",
    );

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({
      kind: "sachantrag",
      title: "Neue Nutzung beschließen",
      summary: "Gemeinsam beraten.",
      target_node_id: "node-1",
    });
  });

  it("withdraws the exact proposal without turning withdrawal into deletion", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ id: "p 1", kind: "weberantrag", status: "withdrawn" }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await withdrawProposal("p 1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/proposals/p%201/withdraw",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
  });

  it("requests repeal as a new proposal and trims only its optional reason", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "r1", kind: "sachantrag" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await requestProposalRepeal("old decision", "  Nicht mehr sinnvoll.  ");

    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/api/proposals/old%20decision/repeal");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      summary: "Nicht mehr sinnvoll.",
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
    expect(statusLabel("withdrawn")).toBe("Zurückgezogen");
  });

  it("renders accepted repeal state without rewriting the stored status", () => {
    expect(proposalStatusLabel({ status: "accepted" })).toBe("Angenommen");
    expect(
      proposalStatusLabel({
        status: "accepted",
        pending_repeal_proposal_id: "repeal-open",
      }),
    ).toBe("Angenommen · Aufhebung läuft");
    expect(
      proposalStatusLabel({
        status: "accepted",
        repealed_by_proposal_id: "repeal-accepted",
      }),
    ).toBe("Aufgehoben");
  });

  it("formats remaining time without inventing a quorum", () => {
    expect(formatRemaining(7 * 86_400 + 2 * 3_600)).toBe("7 T. 2 Std.");
    expect(formatRemaining(undefined)).toBe("abgeschlossen");
  });
});
