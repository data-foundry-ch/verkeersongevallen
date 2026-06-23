"""Backward-compatible re-exports for A2 diagnostics and legacy imports."""

from backend.app.road_bins import (  # noqa: F401
    ACCIDENTS_TABLE,
    GEOMETRY_DIRECTION,
    HM_TO_KM,
    ROADS_TABLE,
    build_filtered_bins_sql,
    build_road_bins_sql,
)
