import type { ExpressionSpecification } from "maplibre-gl";
import type { ColorStep } from "./colorScale";
import { binExtrusionHeightExpression, binLineExpression, binWidthExpression } from "./colorScale";

export const BIN_SOURCE_ID = "a2-bins";
export const BIN_LAYER_ID = "a2-bins-layer";
export const BIN_HIGHLIGHT_SOURCE_ID = "a2-bins-highlight";
export const BIN_HIGHLIGHT_LAYER_ID = "a2-bins-highlight-layer";
export const BIN_EXTRUSION_SOURCE_ID = "a2-bins-extrusion";
export const BIN_EXTRUSION_LAYER_ID = "a2-bins-extrusion-layer";
export const ACCIDENT_SOURCE_ID = "a2-accidents";
export const ACCIDENT_LAYER_ID = "a2-accidents-layer";

export const BIN_INTERACTIVE_LAYER_IDS = [BIN_EXTRUSION_LAYER_ID, BIN_LAYER_ID] as const;

export function binLayerPaint(
  steps: ColorStep[],
  baseOpacity = 0.92,
): {
  "line-color": ExpressionSpecification;
  "line-width": ExpressionSpecification;
  "line-opacity": ExpressionSpecification;
} {
  return {
    "line-color": binLineExpression(steps) as ExpressionSpecification,
    "line-width": [
      "case",
      ["boolean", ["feature-state", "selected"], false],
      10,
      binWidthExpression(steps) as ExpressionSpecification,
    ] as ExpressionSpecification,
    "line-opacity": [
      "case",
      ["boolean", ["feature-state", "selected"], false],
      1,
      ["boolean", ["feature-state", "dimmed"], false],
      baseOpacity * 0.24,
      baseOpacity,
    ] as ExpressionSpecification,
  };
}

export function binExtrusionLayerPaint(steps: ColorStep[]): {
  "fill-extrusion-color": ExpressionSpecification;
  "fill-extrusion-height": ExpressionSpecification;
  "fill-extrusion-opacity": number;
  "fill-extrusion-base": number;
} {
  return {
    "fill-extrusion-color": binLineExpression(steps) as ExpressionSpecification,
    "fill-extrusion-height": binExtrusionHeightExpression() as ExpressionSpecification,
    "fill-extrusion-opacity": 0.78,
    "fill-extrusion-base": 0,
  };
}

export function binHighlightLayerPaint(): {
  "line-color": string;
  "line-width": number;
  "line-opacity": number;
  "line-blur": number;
} {
  return {
    "line-color": "#ffffff",
    "line-width": 12,
    "line-opacity": 0.85,
    "line-blur": 1.5,
  };
}

export function binExtrusionColorPaint(steps: ColorStep[]): ExpressionSpecification {
  return binLineExpression(steps) as ExpressionSpecification;
}

export function binExtrusionHeightPaint(): ExpressionSpecification {
  return binExtrusionHeightExpression() as ExpressionSpecification;
}

export function accidentLayerPaint(): {
  "circle-radius": number;
  "circle-color": string;
  "circle-opacity": number;
} {
  return {
    "circle-radius": 4,
    "circle-color": "#1a1a2e",
    "circle-opacity": 0.65,
  };
}

export { binLineExpression };
