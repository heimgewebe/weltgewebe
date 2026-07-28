import { describe, expect, it } from "vitest";
import { validateProfileTags } from "./codePointInput";

describe("persisted Garnrolle tags", () => {
  it("counts the category prefix against the 64-codepoint tag limit", () => {
    expect(validateProfileTags(["🐋".repeat(58), "", ""])).toEqual([
      `skill:${"🐋".repeat(58)}`,
    ]);
    expect(validateProfileTags(["", "🐋".repeat(59), ""])).toEqual([
      `good:${"🐋".repeat(59)}`,
    ]);
    expect(validateProfileTags(["", "", "🐋".repeat(55)])).toEqual([
      `interest:${"🐋".repeat(55)}`,
    ]);
    expect(validateProfileTags(["🐋".repeat(59), "", ""])).toBeNull();
    expect(validateProfileTags(["", "🐋".repeat(60), ""])).toBeNull();
    expect(validateProfileTags(["", "", "🐋".repeat(56)])).toBeNull();
  });

  it("deduplicates like the server and counts both required tags", () => {
    const values = Array.from({ length: 62 }, (_, index) => `Tag ${index}`);
    const valid = validateProfileTags([`${values.join(",")}, Tag 0`, "", ""]);
    const invalid = validateProfileTags([`${values.join(",")},Tag 62`, "", ""]);

    expect(valid).toHaveLength(62);
    expect(invalid).toBeNull();
  });
});
