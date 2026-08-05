import { describe, expect, it } from "vitest";
import {
  WEAVE_TOPIC_DISPLAY_MAX_LENGTH,
  weaveTopicColor,
  weaveTopicDisplayLabel,
  weaveTopicHash,
  weaveTopicIdentity,
} from "$lib/map/weaveTheme";

describe("weaveTopicDisplayLabel", () => {
  it("leaves short labels untouched", () => {
    expect(weaveTopicDisplayLabel("Kunst")).toBe("Kunst");
  });

  it("truncates by grapheme clusters without splitting a ZWJ emoji sequence", () => {
    // Family emoji is one grapheme cluster but several code points / UTF-16 units.
    const family = "👨‍👩‍👧‍👦";
    const prefix = "Thema ";
    // Build a string that exceeds the display budget only because of clusters.
    const label = `${prefix}${family.repeat(WEAVE_TOPIC_DISPLAY_MAX_LENGTH)}`;
    const displayed = weaveTopicDisplayLabel(label);

    expect(displayed.endsWith("…")).toBe(true);
    // The truncated body must never contain a broken half of the ZWJ sequence
    // (isolated zero-width joiner without its surrounding emoji parts).
    const body = displayed.slice(0, -1);
    expect(body.includes("\u200D")).toBe(true);
    // Every family cluster that remains must be complete.
    const familiesInBody = body.split(family).length - 1;
    expect(body).toBe(`${prefix}${family.repeat(familiesInBody)}`);
    expect(familiesInBody).toBeGreaterThan(0);
  });

  it("never feeds the shortened form into topic identity", () => {
    const long =
      "Nachbarschaftliche Lebensmittelversorgung Hamburg und Umgebung";
    expect(long.length).toBeGreaterThan(WEAVE_TOPIC_DISPLAY_MAX_LENGTH);
    expect(weaveTopicIdentity(long)).not.toBe(
      weaveTopicIdentity(weaveTopicDisplayLabel(long)),
    );
  });
});

describe("weaveTopicHash code-point hashing", () => {
  it("hashes supplementary-plane topics by full code point, not UTF-16 units", () => {
    // Both smileys share the high surrogate 0xD83D. Hashing only charCodeAt(0)
    // would collapse them; code-point hashing must keep them apart.
    const smile = "😀";
    const grin = "😁";
    expect(smile.charCodeAt(0)).toBe(grin.charCodeAt(0));
    expect(smile.codePointAt(0)).not.toBe(grin.codePointAt(0));
    expect(weaveTopicHash(smile)).not.toBe(weaveTopicHash(grin));
    expect(weaveTopicColor(smile)).toMatch(/^#[0-9a-f]{6}$/i);
  });
});
