"""GeoJSON builders."""

from __future__ import annotations

import json
import math
from typing import Any


def rows_to_feature_collection(rows: list[tuple], columns: list[str]) -> dict[str, Any]:
    geojson_key = "geojson" if "geojson" in columns else "geometry_json"
    geojson_idx = columns.index(geojson_key)
    features: list[dict[str, Any]] = []
    for row_idx, row in enumerate(rows):
        if len(row) != len(columns):
            raise ValueError(
                f"Row {row_idx} has {len(row)} values, expected {len(columns)}: {columns}"
            )
        props = {
            columns[i]: _json_safe(row[i])
            for i in range(len(columns))
            if i != geojson_idx
        }
        _ensure_density_per_km_year(props)
        geom_json = row[geojson_idx]
        if geom_json is None:
            continue
        geometry = json.loads(geom_json) if isinstance(geom_json, str) else geom_json
        features.append({"type": "Feature", "geometry": geometry, "properties": props})
    return {"type": "FeatureCollection", "features": features}


def _ensure_density_per_km_year(props: dict[str, Any]) -> None:
    raw = props.get("density_per_km_year")
    if isinstance(raw, (int, float)) and math.isfinite(float(raw)):
        props["density_per_km_year"] = float(raw)
        return

    legacy = props.get("density_per_km")
    span = max(int(props.get("year_span") or 1), 1)
    if isinstance(legacy, (int, float)) and math.isfinite(float(legacy)):
        props["density_per_km_year"] = float(legacy) / span
        return

    count = float(props.get("accident_count") or 0)
    length_m = float(props.get("length_m") or 0)
    if length_m > 0:
        props["density_per_km_year"] = count / (length_m / 1000.0) / span
    else:
        props["density_per_km_year"] = 0.0

    if props.get("year_span") is None:
        props["year_span"] = span


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float, str, bool)):
        return value
    if hasattr(value, "as_integer_ratio"):  # Decimal
        return float(value)
    return str(value)
