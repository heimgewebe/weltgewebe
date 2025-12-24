export interface Location {
  lat: number;
  lon: number;
}

export interface Node {
  id: string;
  kind: string;
  title: string;
  created_at: string;
  updated_at: string;
  summary?: string;
  tags: string[];
  location: Location;
}

export interface Account {
  id: string;
  type: string;
  title: string;
  summary?: string;
  tags: string[];
  // Location is internal/legacy and might be removed in public views
  location?: Location;
  // Public position is the projected view
  public_pos?: Location;
  visibility: string;
  radius_m: number;
  ron_flag: boolean;
}
