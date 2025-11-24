import type { LayoutLoad } from "./$types";

// Configure static site generation: prerender all pages at build time
// and disable server-side rendering for deployment as a static site.
export const prerender = true;
export const ssr = false;

export const load: LayoutLoad = ({ url }) => {
  const canonical = new URL(url.pathname, url.origin).toString();

  return {
    canonical,
  };
};
