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

export interface Account {
  id: string;
  type: string;
  title: string;
  summary?: string | null;
  location: Location;
  public_pos?: Location;
  visibility: string;
  radius_m: number;
  ron_flag: boolean;
  created_at: string;
  tags: string[];
  modules?: Module[];
}

export interface MapPoint {
  id: string;
  lat: number;
  lng: number;
  kind: string; // 'node' | 'account'
  data: Node | Account | unknown;
}

export interface Edge {
  id: string;
  source_id: string;
  target_id: string;
  edge_kind: string;
}

export interface RenderableMapPoint {
  id: string;
  title: string;
  lat: number;
  lon: number;
  summary?: string | null;
  info?: string | null;
  type?: string;
  modules?: Module[];
}
