import type { GeoJSONFeatureCollection } from "../types";
import { densityExpression } from "./density";

export interface ColorStep {
  min: number;
  max: number | null;
  color: string;
  label: string;
}

/** YlOrRd-style ramp: grey (zero) → peach → salmon → coral → red → dark red. */
const PALETTE = ["#e8e8e8", "#fee5d9", "#fcbba1", "#fc9272", "#fb6a4a", "#a50f15"] as const;

/**
 * Fallback for A2 hoofdrijbaan, 5 km bins, 2015–2024 (median ~11 /km/jaar).
 * Previous cutoffs at 4 / 6.5 / 9.5 painted most of the road red.
 */
export const DEFAULT_DENSITY_STEPS: ColorStep[] = [
  { min: 0, max: 0, color: PALETTE[0], label: "0" },
  { min: 0.01, max: 6, color: PALETTE[1], label: "< 6" },
  { min: 6, max: 11, color: PALETTE[2], label: "6–11" },
  { min: 11, max: 16, color: PALETTE[3], label: "11–16" },
  { min: 16, max: 22, color: PALETTE[4], label: "16–22" },
  { min: 22, max: null, color: PALETTE[5], label: "22+" },
];

export function densitiesFromBins(bins: GeoJSONFeatureCollection): number[] {
  return bins.features.map((f) => Number(f.properties.density_per_km_year) || 0);
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  const i = Math.min(sorted.length - 1, Math.max(0, Math.round((p / 100) * (sorted.length - 1))));
  return sorted[i];
}

function roundThreshold(value: number): number {
  if (value <= 0) return 1;
  if (value < 10) return Math.max(1, Math.round(value));
  return Math.round(value / 2) * 2;
}

function formatRangeLabel(min: number, max: number | null): string {
  if (min === 0 && max === 0) return "0";
  if (max === null) return `${min}+`;
  if (min <= 0.01) return `< ${max}`;
  return `${min}–${max}`;
}

/** Build legend/map thresholds from the loaded bin densities (quartiles + p90). */
export function buildColorSteps(densities: number[]): ColorStep[] {
  if (densities.length === 0) return DEFAULT_DENSITY_STEPS;

  const sorted = [...densities].sort((a, b) => a - b);
  const t1 = roundThreshold(percentile(sorted, 25));
  const t2 = Math.max(t1 + 1, roundThreshold(percentile(sorted, 50)));
  const t3 = Math.max(t2 + 1, roundThreshold(percentile(sorted, 75)));
  const t4 = Math.max(t3 + 1, roundThreshold(percentile(sorted, 90)));

  const thresholds = [t1, t2, t3, t4];
  const steps: ColorStep[] = [{ min: 0, max: 0, color: PALETTE[0], label: "0" }];

  steps.push({
    min: 0.01,
    max: t1,
    color: PALETTE[1],
    label: formatRangeLabel(0.01, t1),
  });

  for (let i = 0; i < thresholds.length - 1; i += 1) {
    steps.push({
      min: thresholds[i],
      max: thresholds[i + 1],
      color: PALETTE[i + 2],
      label: formatRangeLabel(thresholds[i], thresholds[i + 1]),
    });
  }

  steps.push({
    min: t4,
    max: null,
    color: PALETTE[5],
    label: formatRangeLabel(t4, null),
  });

  return steps;
}

export function colorForDensity(densityPerKmYear: number, steps = DEFAULT_DENSITY_STEPS): string {
  for (const step of [...steps].reverse()) {
    if (step.max === null && densityPerKmYear >= step.min) return step.color;
    if (step.min === 0 && step.max === 0 && densityPerKmYear === 0) return step.color;
    if (densityPerKmYear >= step.min && (step.max === null || densityPerKmYear <= step.max)) {
      return step.color;
    }
  }
  return steps[0].color;
}

function densityField(): unknown[] {
  return densityExpression();
}

export function binLineExpression(steps: ColorStep[] = DEFAULT_DENSITY_STEPS): unknown[] {
  const d = densityField();
  const ranked = steps
    .filter((s) => !(s.min === 0 && s.max === 0))
    .sort((a, b) => b.min - a.min);

  const cases: unknown[] = ["case"];
  for (const step of ranked) {
    if (step.min <= 0.01) {
      cases.push([">", d, 0], step.color);
    } else {
      cases.push([">=", d, step.min], step.color);
    }
  }
  cases.push(steps.find((s) => s.min === 0 && s.max === 0)?.color ?? PALETTE[0]);
  return cases;
}

export function binWidthExpression(steps: ColorStep[] = DEFAULT_DENSITY_STEPS): unknown[] {
  const d = densityField();
  const thresholds = steps
    .filter((s) => !(s.min === 0 && s.max === 0))
    .sort((a, b) => a.min - b.min);

  const widths = [3, 4, 5, 7, 9, 10];
  const stops: unknown[] = ["interpolate", ["linear"], d, 0, widths[0]];

  thresholds.forEach((step, index) => {
    const value = step.min <= 0.01 ? 0.5 : step.min;
    stops.push(value, widths[Math.min(index + 1, widths.length - 1)]);
  });

  const top = thresholds[thresholds.length - 1];
  if (top) {
    stops.push(top.min + 4, widths[widths.length - 1]);
  }

  return stops;
}

/** Meters of 3D extrusion per accident/km/year — linear, independent of color legend. */
export const EXTRUSION_METERS_PER_DENSITY = 1000;

export function extrusionHeightMeters(densityPerKmYear: number): number {
  return Math.max(0, densityPerKmYear * EXTRUSION_METERS_PER_DENSITY);
}

export function binExtrusionHeightExpression(): unknown[] {
  return ["max", 0, ["to-number", ["get", "extrusion_height_m"], 0]];
}
