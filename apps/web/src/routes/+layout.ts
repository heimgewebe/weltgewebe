import type { LayoutLoad } from './$types';

const SITE_ORIGIN = 'https://weltgewebe.de';

export const load: LayoutLoad = ({ url }) => {
  const canonical = new URL(url.pathname, SITE_ORIGIN).toString();

  return {
    canonical
  };
};
