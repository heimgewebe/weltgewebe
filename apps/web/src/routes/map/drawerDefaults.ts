export const drawerQueryDefaults = {
  l: true,
  r: false,
  t: false,
} as const;

export type DrawerKey = keyof typeof drawerQueryDefaults;

export function readDrawerParam(params: URLSearchParams, key: DrawerKey) {
  return params.has(key) ? params.get(key) === "1" : drawerQueryDefaults[key];
}

export function writeDrawerParam(
  params: URLSearchParams,
  key: DrawerKey,
  value: boolean,
) {
  if (value === drawerQueryDefaults[key]) {
    params.delete(key);
  } else {
    params.set(key, value ? "1" : "0");
  }
}
