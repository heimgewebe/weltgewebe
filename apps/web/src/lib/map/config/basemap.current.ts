export type BasemapMode = "remote-style";

export type BasemapConfig = {
  mode: BasemapMode;
  styleUrl: string;
  center: [number, number];
  zoom: number;
  minZoom?: number;
  maxZoom?: number;
  pitch?: number;
  bearing?: number;
};

export const HAMMER_PARK_CENTER = {
  lat: 53.5585,
  lon: 10.058,
};

export const currentBasemap: BasemapConfig = {
  mode: "remote-style",
  styleUrl: "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
  center: [HAMMER_PARK_CENTER.lon, HAMMER_PARK_CENTER.lat], // Hammer Park, Hamm
  zoom: 15,
  minZoom: 10,
  maxZoom: 18,
  pitch: 0,
  bearing: 0,
};
