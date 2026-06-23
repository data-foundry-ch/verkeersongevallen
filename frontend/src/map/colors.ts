/** Re-exports for the density color scale (see colorScale.ts). */

export {
  DEFAULT_DENSITY_STEPS as DENSITY_PER_KM_YEAR_STEPS,
  DEFAULT_DENSITY_STEPS as DENSITY_PER_KM_STEPS,
  DEFAULT_DENSITY_STEPS as ACCIDENT_COUNT_STEPS,
  EXTRUSION_METERS_PER_DENSITY,
  type ColorStep,
  binExtrusionHeightExpression,
  binLineExpression,
  binWidthExpression,
  buildColorSteps,
  colorForDensity,
  densitiesFromBins,
  extrusionHeightMeters,
} from "./colorScale";
