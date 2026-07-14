import type { Plugin } from "vite";

export const DEFAULT_PUBLIC_ORIGIN: string;

export function normalizePublicOrigin(value: unknown): string;
export function renderRobots(origin: string): string;
export function renderSitemap(origin: string): string;
export function createPublicWebAssetsPlugin(options?: {
  origin?: string;
}): Plugin;
