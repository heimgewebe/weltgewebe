import { afterEach, describe, expect, it, vi } from "vitest";
import { accountAttentionInvalidation } from "$lib/accountAttention";
import { markDirectConversationRead } from "$lib/api/directMessages";
import {
  createWeberProposal,
  submitVeto,
  submitVote,
} from "$lib/api/governance";

function currentRevision(): { value: number; unsubscribe: () => void } {
  let value = -1;
  const unsubscribe = accountAttentionInvalidation.subscribe((revision) => {
    value = revision;
  });
  return {
    get value() {
      return value;
    },
    unsubscribe,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("account attention invalidation", () => {
  it("invalidates after a Weber application has been stored", async () => {
    const revision = currentRevision();
    const before = revision.value;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ id: "p1", kind: "weberantrag" }), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await createWeberProposal("Ich möchte mitweben.");

    expect(revision.value).toBe(before + 1);
    revision.unsubscribe();
  });

  it("does not invalidate when a Weber application fails", async () => {
    const revision = currentRevision();
    const before = revision.value;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("conflict", { status: 409 })),
    );

    await expect(createWeberProposal()).rejects.toMatchObject({ status: 409 });

    expect(revision.value).toBe(before);
    revision.unsubscribe();
  });

  it("invalidates after successful vote and veto writes", async () => {
    const revision = currentRevision();
    const before = revision.value;
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ choice: "ja" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            weber_account_id: "weber-a",
            weber_title: "Ada",
            reason: "Einwand",
            created_at: "2026-08-17T12:00:00Z",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await submitVote("proposal-1", "ja");
    expect(revision.value).toBe(before + 1);

    await submitVeto("proposal-2", "Einwand");
    expect(revision.value).toBe(before + 2);
    revision.unsubscribe();
  });

  it("invalidates after unread direct messages are marked read", async () => {
    const revision = currentRevision();
    const before = revision.value;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
    );

    await markDirectConversationRead("conversation-1", "message-3");

    expect(revision.value).toBe(before + 1);
    revision.unsubscribe();
  });
});
