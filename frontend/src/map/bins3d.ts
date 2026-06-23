import buffer from "@turf/buffer";
import { lineString } from "@turf/helpers";
import type { GeoJSONFeatureCollection } from "../types";
import { extrusionHeightMeters } from "./colorScale";

/** Half-width of the extruded ribbon along each bin segment (meters). */
export const BIN_BUFFER_METERS = 15;

export function binsToExtrusionPolygons(
  bins: GeoJSONFeatureCollection,
): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];

  for (const bin of bins.features) {
    const { geometry, properties } = bin;
    const lineParts: GeoJSON.Position[][] = [];

    if (geometry.type === "LineString") {
      lineParts.push(geometry.coordinates);
    } else if (geometry.type === "MultiLineString") {
      lineParts.push(...geometry.coordinates);
    } else {
      continue;
    }

    for (const coords of lineParts) {
      if (coords.length < 2) continue;
      const density = Number(properties.density_per_km_year) || 0;
      const line = lineString(coords, properties as GeoJSON.GeoJsonProperties);
      const polygon = buffer(line, BIN_BUFFER_METERS, { units: "meters" });
      if (polygon) {
        polygon.properties = {
          ...(properties as GeoJSON.GeoJsonProperties),
          extrusion_height_m: extrusionHeightMeters(density),
        };
        features.push(polygon);
      }
    }
  }

  return { type: "FeatureCollection", features };
}
