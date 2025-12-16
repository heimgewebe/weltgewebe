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
