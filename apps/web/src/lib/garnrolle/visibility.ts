import type { Account, Location } from "$lib/map/types";

export type GarnrolleMapState = "not_on_map" | "exact" | "radius";

/**
 * UI-facing state. `not_on_map` remains part of the compatibility union while
 * callers migrate, but this projector represents the non-public choice as
 * `private`: the persistence state does not prove that onboarding is unfinished.
 */
export type GarnrolleVisibilityState = GarnrolleMapState | "private";

export type GarnrolleVisibilityView = {
  state: GarnrolleVisibilityState;
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
  const mapState = deriveGarnrolleMapState(account);
  if (mapState === "exact") {
    return {
      state: "exact",
      label: "Öffentlich exakt",
      description: "Dein privater Kartenanker wird öffentlich exakt angezeigt.",
      publicPos: account?.public_pos ?? null,
      radiusM: 0,
      canZoomToMap: true,
    };
  }
  if (mapState === "radius") {
    const radiusM = account?.radius_m ?? null;
    return {
      state: "radius",
      label: "Öffentlich ungefähr",
      description: radiusM
        ? `Deine Garnrolle wird öffentlich ungefähr im Umkreis von ${radiusM} m angezeigt.`
        : "Deine Garnrolle wird öffentlich ungefähr angezeigt.",
      publicPos: account?.public_pos ?? null,
      radiusM,
      canZoomToMap: true,
    };
  }
  return {
    state: "private",
    label: "Privat",
    description:
      "Deine Garnrolle hat keine öffentliche Kartenposition. Ein privater Kartenanker kann trotzdem gespeichert sein.",
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
