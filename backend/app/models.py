"""Pydantic response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    database: str
    duckdb_ok: bool
    api_version: str


class MetaResponse(BaseModel):
    target_road: str
    implemented_roads: list[str]
    year_from: int | None
    year_to: int | None
    total_accident_count: int
    a2_accident_count: int
    a2_unresolved_count: int
    severities: list[str]
    bin_sizes_km: list[int]
    a2_segment_count: int
    a2_mainroad_segment_count: int
    geometry_direction: str = "H"


class RoadSummary(BaseModel):
    road_number: str
    segment_count: int
    accident_count: int
    bbox: list[float] | None
    status: str


class YearlyStat(BaseModel):
    accident_year: int
    accident_count: int


class SeverityStat(BaseModel):
    severity: str | None
    accident_count: int


class LocationQualityStat(BaseModel):
    location_quality: str
    accident_count: int


class TopBinStat(BaseModel):
    bin_id: str
    bin_start_m: float
    bin_end_m: float
    accident_count: int


class StatsResponse(BaseModel):
    road_number: str
    total_accidents: int
    unresolved_accidents: int
    by_year: list[YearlyStat]
    by_severity: list[SeverityStat]
    by_location_quality: list[LocationQualityStat]
    top_bins: list[TopBinStat]
    # Legacy aliases for A2 consumers
    total_a2_accidents: int | None = None
    unresolved_a2_accidents: int | None = None


class GeoJSONResponse(BaseModel):
    type: str = "FeatureCollection"
    features: list[dict[str, Any]] = Field(default_factory=list)
