import type { LayoutLoad } from "./$types";

export const prerender = true;
export const ssr = false;

export const load: LayoutLoad = ({ url }) => {
  const canonical = new URL(url.pathname, url.origin).toString();

  return {
    canonical,
  };
};
