export interface MetaResponse {
  target_road: string;
  implemented_roads: string[];
  year_from: number | null;
  year_to: number | null;
  total_accident_count: number;
  a2_accident_count: number;
  a2_unresolved_count: number;
  severities: string[];
  bin_sizes_km: number[];
  a2_segment_count: number;
  a2_mainroad_segment_count: number;
  geometry_direction: string;
}

export interface RoadSummary {
  road_number: string;
  segment_count: number;
  accident_count: number;
  bbox: [number, number, number, number] | null;
  status: "implemented" | "not_implemented_yet";
}

export interface BinProperties {
  bin_id: string;
  road_number: string;
  bin_size_km: number;
  bin_start_m: number;
  bin_end_m: number;
  accident_count: number;
  fatal_count: number;
  injury_count: number;
  density_per_km_year: number;
  year_span: number;
  geometry_quality: string;
}

export interface BinsFilterMeta {
  main_road_only: boolean;
  direction: string;
  feature_count: number;
  accident_count: number;
}

export interface GeoJSONFeatureCollection {
  type: "FeatureCollection";
  filter?: BinsFilterMeta;
  features: Array<{
    type: "Feature";
    geometry: GeoJSON.Geometry;
    properties: BinProperties;
  }>;
}

export interface StatsResponse {
  road_number: string;
  total_accidents: number;
  unresolved_accidents: number;
  by_year: { accident_year: number; accident_count: number }[];
  by_severity: { severity: string | null; accident_count: number }[];
  by_location_quality: { location_quality: string; accident_count: number }[];
  top_bins: {
    bin_id: string;
    bin_start_m: number;
    bin_end_m: number;
    accident_count: number;
  }[];
  total_a2_accidents?: number;
  unresolved_a2_accidents?: number;
}

export interface FilterState {
  road: string;
  yearFrom: number;
  yearTo: number;
  binSizeKm: number;
}

export interface SelectedBin extends BinProperties {}

export type MapSelection =
  | { type: "bin"; binId: string }
  | { type: "km"; roadKm: number }
  | null;
