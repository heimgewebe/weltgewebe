import type { MapEntityViewModel } from "$lib/map/types";

export type RelatedMapSelection = {
  type: "node" | "garnrolle";
  id: string;
  title?: string;
  data?: MapEntityViewModel;
};

export type MapDomainChanged = {
  kind: "node";
  id: string;
  action: "updated" | "deleted" | "archived";
};
