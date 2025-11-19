import type { LayoutLoad } from "./$types";

export const load: LayoutLoad = ({ url }) => {
  const canonical = new URL(url.pathname, url.origin).toString();

  return {
    canonical,
  };
};
