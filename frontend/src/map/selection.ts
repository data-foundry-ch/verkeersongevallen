import type { GeoJSONFeatureCollection, MapSelection } from "../types";

export function selectionBinIds(
  bins: GeoJSONFeatureCollection | undefined,
  selection: MapSelection,
): string[] {
  if (!selection || !bins) return [];

  if (selection.type === "bin") {
    return [selection.binId];
  }

  const startM = selection.roadKm * 1000;
  const endM = (selection.roadKm + 1) * 1000;
  return bins.features
    .filter(
      (feature) =>
        feature.properties.bin_start_m < endM && feature.properties.bin_end_m > startM,
    )
    .map((feature) => feature.properties.bin_id);
}

export function isBarHighlighted(
  selection: MapSelection,
  binId: string,
  binStartM: number,
  binEndM: number,
): boolean {
  if (!selection) return false;
  if (selection.type === "bin") return selection.binId === binId;
  const startM = selection.roadKm * 1000;
  const endM = (selection.roadKm + 1) * 1000;
  return binStartM < endM && binEndM > startM;
}

export function highlightFeatures(
  bins: GeoJSONFeatureCollection | undefined,
  selection: MapSelection,
): GeoJSON.Feature[] {
  if (!bins || !selection) return [];
  const ids = new Set(selectionBinIds(bins, selection));
  return bins.features.filter((feature) => ids.has(feature.properties.bin_id));
}

export function boundsFromFeatures(
  features: GeoJSON.Feature[],
): [number, number, number, number] | null {
  let minLng = Infinity;
  let minLat = Infinity;
  let maxLng = -Infinity;
  let maxLat = -Infinity;

  const extendCoord = (coord: number[]) => {
    const [lng, lat] = coord;
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) return;
    minLng = Math.min(minLng, lng);
    minLat = Math.min(minLat, lat);
    maxLng = Math.max(maxLng, lng);
    maxLat = Math.max(maxLat, lat);
  };

  for (const feature of features) {
    const { geometry } = feature;
    if (geometry.type === "LineString") {
      geometry.coordinates.forEach(extendCoord);
    } else if (geometry.type === "MultiLineString") {
      geometry.coordinates.forEach((line) => line.forEach(extendCoord));
    }
  }

  if (!Number.isFinite(minLng)) return null;
  return [minLng, minLat, maxLng, maxLat];
}

export function selectionLabel(
  bins: GeoJSONFeatureCollection | undefined,
  selection: MapSelection,
): string | null {
  if (!selection) return null;
  if (selection.type === "km") {
    return `km ${selection.roadKm} (hm ${selection.roadKm * 10}–${selection.roadKm * 10 + 9})`;
  }
  const bin = bins?.features.find((f) => f.properties.bin_id === selection.binId)?.properties;
  if (!bin) return null;
  return `km ${(bin.bin_start_m / 1000).toFixed(1)}–${(bin.bin_end_m / 1000).toFixed(1)}`;
}
