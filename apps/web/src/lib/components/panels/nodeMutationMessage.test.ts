import { describe, expect, it } from "vitest";
import { ApiRequestError } from "$lib/api/domainWrites";
import { nodeMutationMessage } from "./nodeMutationMessage";

describe("node mutation messages", () => {
  it("explains the protected public conversation instead of claiming a data conflict", () => {
    const error = new ApiRequestError(
      409,
      "node deletion blocked because its public conversation contains contributions",
    );

    expect(nodeMutationMessage(error, "delete")).toBe(
      "Dieser Knoten kann nicht gelöscht werden, weil sein öffentliches Gespräch Beiträge enthält. Das Gespräch bleibt als Teil der öffentlichen Geschichte geschützt; du kannst den Knoten weiterhin bearbeiten.",
    );
  });

  it("uses the stable structured error code only for delete actions", () => {
    const error = new ApiRequestError(409, {
      code: "node_conversation_not_empty",
      message: "protected",
    });

    expect(nodeMutationMessage(error, "delete")).toContain(
      "öffentliches Gespräch Beiträge enthält",
    );
    expect(nodeMutationMessage(error, "save")).toContain("nicht geändert");
  });

  it("keeps generic save and delete conflicts distinct", () => {
    const error = new ApiRequestError(409, "other conflict");

    expect(nodeMutationMessage(error, "save")).toContain("nicht geändert");
    expect(nodeMutationMessage(error, "delete")).toContain("nicht gelöscht");
  });

  it("explains ambiguous edge protection without exposing backend wording", () => {
    const error = new ApiRequestError(
      409,
      "node deletion blocked by ambiguous edge endpoint",
    );

    expect(nodeMutationMessage(error, "delete")).toContain(
      "Verbindung nicht eindeutig zugeordnet",
    );
  });
});
