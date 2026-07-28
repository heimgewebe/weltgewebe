export function countUnicodeCodePoints(value: string): number {
  return [...value].length;
}

export function constrainCodePointInput(
  currentValue: string,
  nextValue: string,
  maxCodePoints: number,
): string {
  const nextCodePoints = [...nextValue];
  if (nextCodePoints.length <= maxCodePoints) return nextValue;

  const currentCodePointCount = countUnicodeCodePoints(currentValue);
  if (nextCodePoints.length <= currentCodePointCount) return nextValue;
  if (currentCodePointCount >= maxCodePoints) return currentValue;

  return nextCodePoints.slice(0, maxCodePoints).join("");
}
