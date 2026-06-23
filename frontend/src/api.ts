import type {
  FilterState,
  GeoJSONFeatureCollection,
  MetaResponse,
  RoadSummary,
  StatsResponse,
} from "./types";
import { enrichBinProperties } from "./map/density";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

function buildQuery(params: Record<string, string | number | boolean | string[] | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    if (Array.isArray(v)) {
      v.forEach((item) => sp.append(k, item));
    } else {
      sp.set(k, String(v));
    }
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.text();
    if (body.trimStart().startsWith("<!doctype") || body.trimStart().startsWith("<html")) {
      throw new Error(
        "API not reachable. Restart the backend: .\\make.ps1 backend (port 8001). " +
          "Port 8000 is used by another app on this machine.",
      );
    }
    try {
      const parsed = JSON.parse(body) as { detail?: string };
      if (parsed.detail) throw new Error(parsed.detail);
    } catch (e) {
      if (e instanceof Error && e.message !== body) throw e;
    }
    if (res.status === 500) {
      throw new Error(`Server error (${res.status}). Restart backend: .\\make.ps1 backend`);
    }
    throw new Error(body || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchMeta(): Promise<MetaResponse> {
  return fetchJson(`${API_BASE}/meta`);
}

export async function fetchRoads(q?: string): Promise<RoadSummary[]> {
  return fetchJson(`${API_BASE}/roads${buildQuery({ q })}`);
}

export async function fetchBins(filters: FilterState): Promise<GeoJSONFeatureCollection> {
  const data = await fetchJson<GeoJSONFeatureCollection>(
    `${API_BASE}/road/${filters.road}/bins${buildQuery({
      bin_size_km: filters.binSizeKm,
      year_from: filters.yearFrom,
      year_to: filters.yearTo,
      main_road_only: true,
    })}`,
  );
  const yearSpan = Math.max(filters.yearTo - filters.yearFrom + 1, 1);
  return {
    ...data,
    features: data.features.map((feature) => ({
      ...feature,
      properties: enrichBinProperties(feature.properties, yearSpan),
    })),
  };
}

export async function fetchStats(road: string): Promise<StatsResponse> {
  return fetchJson(`${API_BASE}/road/${road}/stats`);
}

export interface HealthResponse {
  status: string;
  database: string;
  duckdb_ok: boolean;
  api_version?: string;
}

export async function fetchHealth(): Promise<HealthResponse> {
  return fetchJson(`${API_BASE}/health`);
}
