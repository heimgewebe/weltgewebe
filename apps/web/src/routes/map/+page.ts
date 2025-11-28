import type { PageLoad } from './$types';
import { drawerQueryDefaults, readDrawerParam } from './drawerDefaults';

export const load: PageLoad = ({ url }) => {
  const params = url.searchParams;

  const leftOpen = readDrawerParam(params, 'l');
  const rightOpen = readDrawerParam(params, 'r');
  const topOpen = readDrawerParam(params, 't');

  return { leftOpen, rightOpen, topOpen };
};
