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

export const currentBasemap: BasemapConfig = {
  mode: "remote-style",
  styleUrl: "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
  center: [10.0386, 53.555], // Hammer Park, Hamm
  zoom: 15,
  minZoom: 10,
  maxZoom: 18,
  pitch: 0,
  bearing: 0,
};
