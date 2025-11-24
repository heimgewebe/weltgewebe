import type { LayoutLoad } from "./$types";

// Configure static site generation: prerender all pages at build time,
// disable server-side rendering for a pure static site
export const prerender = true;
export const ssr = false;

export const load: LayoutLoad = ({ url }) => {
  const canonical = new URL(url.pathname, url.origin).toString();

  return {
    canonical,
  };
};
