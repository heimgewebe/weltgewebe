export function countUnicodeCodePoints(value: string): number {
  let count = 0;
  for (const codePoint of value) {
    if (codePoint) count += 1;
  }
  return count;
}

const PROFILE_TAG_PREFIXES = ["skill:", "good:", "interest:"] as const;

export function validateProfileTags(
  values: readonly [string, string, string],
): string[] | null {
  const tags: string[] = [];
  const seen = new Set<string>();
  for (const [index, value] of values.entries()) {
    for (const rawEntry of value.split(",")) {
      const entry = rawEntry.trim();
      if (!entry) continue;
      const tag = PROFILE_TAG_PREFIXES[index] + entry;
      if (countUnicodeCodePoints(tag) > 64) return null;
      if (seen.has(tag)) continue;
      seen.add(tag);
      tags.push(tag);
      if (tags.length > 62) return null;
    }
  }
  return tags;
}
