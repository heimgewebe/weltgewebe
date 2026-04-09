export interface Location {
  lat: number;
  lon: number;
}

export interface Module {
  id: string;
  label: string;
  locked: boolean;
  type: string;
}

export interface Node {
  id: string;
  kind: string;
  title: string;
  created_at: string;
  updated_at: string;
  summary?: string | null;
  info?: string | null;
  tags: string[];
  location: Location;
  modules?: Module[];
}

export interface AccountBase {
  id: string;
  title: string;
  summary?: string | null;
  created_at: string;
  tags: string[];
  modules?: Module[];
}

export interface AccountVerortet extends AccountBase {
  type: "garnrolle";
  mode: "verortet";
  location?: Location; // internal (omitted in public API responses)
  public_pos?: Location; // projected
  radius_m: number;
}

export interface AccountRon extends AccountBase {
  type: "ron";
  mode: "ron";
  location?: never;
  public_pos?: never;
  radius_m: number;
}

export type Account = AccountVerortet | AccountRon;


export interface Edge {
  id: string;
  source_id: string;
  target_id: string;
  edge_kind: string;
}

export interface MapEntityBase {
  id: string;
  title: string;
  lat: number;
  lon: number;
  summary?: string | null;
  modules?: Module[];
  created_at?: string;
  tags?: string[];
  weight?: number;
}

export interface MapNodeEntity extends MapEntityBase {
  type: 'node';
  info?: string | null;
  updated_at?: string;
  kind?: string;
}

export interface MapGarnrolleEntity extends MapEntityBase {
  type: 'garnrolle';
}

export interface MapRonEntity extends MapEntityBase {
  type: 'ron';
}

export interface MapAccountEntity extends MapEntityBase {
  type: 'account'; // Fallback for backwards compatibility if needed, but should be avoided
}

export type MapEntityViewModel = MapNodeEntity | MapGarnrolleEntity | MapRonEntity | MapAccountEntity;

export type RenderableMapPoint = MapEntityViewModel; // Alias for backward compatibility during refactor, will be phased out in dependent files
