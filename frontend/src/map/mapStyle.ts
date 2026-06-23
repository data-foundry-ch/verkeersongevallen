import type { StyleSpecification } from "maplibre-gl";

/**
 * Basemap presets (MapLibre style.json URLs).
 *
 * Browse more styles:
 * - Carto basemaps (free, no key): https://github.com/CartoDB/basemap-styles
 * - OpenFreeMap gallery: https://openfreemap.org/
 * - MapLibre demo styles: https://maplibre.org/maplibre-gl-js/docs/examples/
 * - MapTiler style browser (API key): https://cloud.maptiler.com/maps/
 *
 * Override at build/runtime: VITE_MAP_STYLE_URL=<style.json url>
 * Or pick a preset name: VITE_MAP_STYLE=positron | voyager | osm-raster
 */
export const MAP_STYLE_PRESETS = {
  /** Light grey background, subtle road network — good for data overlays. */
  positron: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  /** Slightly richer colours; roads and labels a bit clearer. */
  voyager: "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
  /** Dark background for high-contrast overlays. */
  "dark-matter": "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  /** Original busy OSM raster tiles. */
  "osm-raster": "osm-raster",
} as const;

export type MapStylePreset = keyof typeof MAP_STYLE_PRESETS;

const OSM_RASTER_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

function resolveMapStyle(): string | StyleSpecification {
  const directUrl = import.meta.env.VITE_MAP_STYLE_URL as string | undefined;
  if (directUrl?.trim()) return directUrl.trim();

  const preset = (import.meta.env.VITE_MAP_STYLE as MapStylePreset | undefined) ?? "positron";
  const presetUrl = MAP_STYLE_PRESETS[preset] ?? MAP_STYLE_PRESETS.positron;
  if (presetUrl === "osm-raster") return OSM_RASTER_STYLE;
  return presetUrl;
}

export const MAP_STYLE = resolveMapStyle();
