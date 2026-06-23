/** Resolve accidents per km per year from bin feature properties. */

import type { BinProperties } from "../types";

export function binLengthKm(props: Record<string, unknown>): number {
  const lengthM = Number(props.length_m);
  if (Number.isFinite(lengthM) && lengthM > 0) return lengthM / 1000;

  const start = Number(props.bin_start_m);
  const end = Number(props.bin_end_m);
  if (Number.isFinite(start) && Number.isFinite(end) && end > start) {
    return (end - start) / 1000;
  }

  const binKm = Number(props.bin_size_km);
  if (Number.isFinite(binKm) && binKm > 0) return binKm;
  return 0;
}

export function yearSpan(props: Record<string, unknown>, fallback = 10): number {
  const span = Number(props.year_span);
  return Number.isFinite(span) && span > 0 ? span : fallback;
}

export function densityPerKmYear(
  props: Record<string, unknown>,
  fallbackYearSpan = 10,
): number {
  const direct = Number(props.density_per_km_year);
  if (Number.isFinite(direct)) return direct;

  const legacy = Number(props.density_per_km);
  const span = yearSpan(props, fallbackYearSpan);
  if (Number.isFinite(legacy)) return legacy / span;

  const count = Number(props.accident_count) || 0;
  const lengthKm = binLengthKm(props);
  if (lengthKm > 0) return count / lengthKm / span;
  return 0;
}

export function enrichBinProperties(
  props: BinProperties,
  fallbackYearSpan: number,
): BinProperties {
  const raw = props as unknown as Record<string, unknown>;
  const span = yearSpan(raw, fallbackYearSpan);
  const lengthKm = binLengthKm(raw);
  const count = Number(props.accident_count) || 0;
  const density = lengthKm > 0 ? count / lengthKm / span : 0;
  return {
    ...props,
    year_span: span,
    density_per_km_year: density,
  };
}

export function formatDensityPerKmYear(props: Record<string, unknown>): string {
  return `${densityPerKmYear(props).toFixed(2)}/km/jaar`;
}

/** MapLibre expression — read precomputed density_per_km_year from feature properties. */
export function densityExpression(): unknown[] {
  return ["to-number", ["get", "density_per_km_year"], 0];
}
