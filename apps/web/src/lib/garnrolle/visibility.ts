import type { Account, Location } from "$lib/map/types";

export type GarnrolleMapState = "not_on_map" | "exact" | "radius";

export type GarnrolleVisibilityView = {
  state: GarnrolleMapState;
  label: string;
  description: string;
  publicPos: Location | null;
  radiusM: number | null;
  canZoomToMap: boolean;
};

export function deriveGarnrolleMapState(
  account: Account | null | undefined,
): GarnrolleMapState {
  if (!account?.public_pos) return "not_on_map";
  if ((account.radius_m ?? 0) > 0) return "radius";
  return "exact";
}

export function describeGarnrolleVisibility(
  account: Account | null | undefined,
): GarnrolleVisibilityView {
  const state = deriveGarnrolleMapState(account);
  if (state === "exact") {
    return {
      state,
      label: "Exakt sichtbar",
      description: "Deine Garnrolle steht exakt auf der Karte.",
      publicPos: account?.public_pos ?? null,
      radiusM: 0,
      canZoomToMap: true,
    };
  }
  if (state === "radius") {
    const radiusM = account?.radius_m ?? null;
    return {
      state,
      label: "Im Umkreis sichtbar",
      description: radiusM
        ? `Deine Garnrolle wird öffentlich im Umkreis von ${radiusM} m angezeigt.`
        : "Deine Garnrolle wird öffentlich im Umkreis angezeigt.",
      publicPos: account?.public_pos ?? null,
      radiusM,
      canZoomToMap: true,
    };
  }
  return {
    state,
    label: "Noch nicht auf der Karte",
    description:
      "Deine Garnrolle ist angelegt, hat aber noch keine öffentliche Kartenposition.",
    publicPos: null,
    radiusM: null,
    canZoomToMap: false,
  };
}

export function findOwnGarnrolle(
  accounts: Account[],
  accountId: string | null | undefined,
): Account | null {
  if (!accountId) return null;
  return accounts.find((account) => account.id === accountId) ?? null;
}
