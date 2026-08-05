/**
 * Edge lines are only meaningful while their endpoint markers are shown.
 * Hiding nodes therefore hides lines as well.
 */
export function areMapEdgesVisuallyEnabled(
  showEdges: boolean,
  showNodes: boolean,
): boolean {
  return showEdges && showNodes;
}
