/**
 * Shared typed-Faden visual tokens.
 *
 * Whenever one Fadenart continues from the MapLibre canvas into DOM geometry,
 * both renderers must use the same numeric gauge. The conversation Faden and
 * its node ring therefore share one width token; the knotting Faden and the
 * stitched X share another. This prevents count- or renderer-specific widths
 * from silently drifting apart.
 *
 * This module has no imports of its own so it can be safely imported by both
 * `edges.ts` and `weaveRuntime.ts` without risking a circular dependency.
 */

/** Conversation Faden and conversation-ring yarn gauge, in screen pixels. */
export const CONVERSATION_THREAD_WIDTH_PX = 1.75;

/** Base conversation-ring diameter before count scaling, as a root percentage. */
export const CONVERSATION_RING_BASE_DIAMETER_PERCENT = 48;

/** Knotting Faden line width, in CSS/canvas pixels. Same unit space as the
 * MapLibre `line-width` paint property and the marker DOM's CSS `width`, so
 * a value here reads at the identical on-screen thickness in both places. */
export const KNOTTING_THREAD_WIDTH_PX = 4.15;
