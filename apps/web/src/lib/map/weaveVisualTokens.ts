/**
 * Shared knotting-thread visual tokens.
 *
 * The knotting Faden (rendered as a MapLibre line layer in `overlay/edges.ts`)
 * and the stitched X at a node's centre (rendered as DOM in
 * `overlay/weaveRuntime.ts` / `overlay/markers.css`) must read as one
 * continuous physical thread, not as a line feeding into a separately
 * dimensioned patch. Both sides import the same numeric token instead of
 * keeping their own copy that could silently drift apart.
 *
 * This module has no imports of its own so it can be safely imported by both
 * `edges.ts` and `weaveRuntime.ts` without risking a circular dependency.
 */

/** Knotting Faden line width, in CSS/canvas pixels. Same unit space as the
 * MapLibre `line-width` paint property and the marker DOM's CSS `width`, so
 * a value here reads at the identical on-screen thickness in both places. */
export const KNOTTING_THREAD_WIDTH_PX = 4.15;
