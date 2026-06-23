"""FastAPI application — multi-road accident map endpoints."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from backend.app.db import close_connection, get_connection, get_db_path
from backend.app.geojson import rows_to_feature_collection
from backend.app.models import (
    HealthResponse,
    LocationQualityStat,
    MetaResponse,
    RoadSummary,
    SeverityStat,
    StatsResponse,
    TopBinStat,
    YearlyStat,
)
from backend.app.queries import (
    fetch_accidents_per_km,
    fetch_meta,
    fetch_road_accidents,
    fetch_road_bins,
    fetch_road_stats,
    fetch_road_summary,
    normalized_tables_ready,
    table_exists,
)
from backend.app.road_bins import GEOMETRY_DIRECTION
from backend.app.roads_config import (
    assert_implemented_road,
    default_road,
    implemented_roads,
    load_app_config,
)
from backend.app.static_files import mount_showcase_frontend, static_files_enabled

logger = logging.getLogger(__name__)

_LOCAL_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def _cors_origins() -> list[str]:
    """Local dev origins plus CORS_ORIGINS env (comma-separated production URLs)."""
    extra = os.environ.get("CORS_ORIGINS", "")
    from_env = [o.strip() for o in extra.split(",") if o.strip()]
    return list(dict.fromkeys(_LOCAL_CORS_ORIGINS + from_env))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_connection(read_only=True)
    yield
    close_connection()


app = FastAPI(title="Dutch Road Accident Map", version="0.2.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request, exc: Exception):
    logger.exception("Unhandled API error")
    return JSONResponse(status_code=500, content={"detail": str(exc)})

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api")
def api_root() -> dict:
    cfg = load_app_config()
    roads = implemented_roads(cfg)
    return {
        "app": "Dutch Road Accident Map",
        "default_road": default_road(cfg),
        "implemented_roads": roads,
        "docs": "/docs",
        "health": "/api/health",
        "meta": "/api/meta",
        "showcase_ui": static_files_enabled(),
    }


def _normalize_direction(direction: str | None) -> str | None:
    if direction is None or direction.lower() in ("all", ""):
        return None
    d = direction.upper()
    if d not in ("H", "T"):
        raise HTTPException(status_code=400, detail="direction must be H, T, or all")
    return d


def _require_normalized_data(conn) -> None:
    if not normalized_tables_ready(conn):
        raise HTTPException(
            status_code=404,
            detail="Road data not found. Run the pipeline first.",
        )


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    db_path = get_db_path()
    ok = False
    data_ok = False
    try:
        conn = get_connection(read_only=True)
        conn.execute("SELECT 1").fetchone()
        data_ok = normalized_tables_ready(conn)
        ok = True
    except Exception:
        ok = False
    status = "ok" if ok and data_ok else ("degraded" if ok else "error")
    return HealthResponse(
        status=status,
        database=str(db_path),
        duckdb_ok=ok and data_ok,
        api_version=app.version,
    )


@app.get("/api/meta", response_model=MetaResponse)
def meta() -> MetaResponse:
    cfg = load_app_config()
    target = default_road(cfg)
    conn = get_connection(read_only=True)
    _require_normalized_data(conn)
    data = fetch_meta(conn, target, cfg.get("available_bin_sizes_km", [1, 2, 5, 10, 20]))

    return MetaResponse(
        target_road=target,
        implemented_roads=implemented_roads(cfg),
        year_from=data["year_from"] or cfg.get("initial_year_from"),
        year_to=data["year_to"] or cfg.get("initial_year_to"),
        total_accident_count=data["total_accident_count"],
        a2_accident_count=data["road_accident_count"],
        a2_unresolved_count=data["road_unresolved_count"],
        severities=data["severities"],
        bin_sizes_km=data["bin_sizes_km"],
        a2_segment_count=data["road_segment_count"],
        a2_mainroad_segment_count=data.get("road_mainroad_segment_count", 0),
        geometry_direction=cfg.get("geometry_direction", GEOMETRY_DIRECTION),
    )


@app.get("/api/roads", response_model=list[RoadSummary])
def roads(q: Annotated[str | None, Query()] = None) -> list[RoadSummary]:
    cfg = load_app_config()
    conn = get_connection(read_only=True)
    _require_normalized_data(conn)

    results: list[RoadSummary] = []
    for road in implemented_roads(cfg):
        summary = fetch_road_summary(conn, road)
        results.append(
            RoadSummary(
                road_number=road,
                segment_count=summary["segment_count"],
                accident_count=summary["accident_count"],
                bbox=summary["bbox"],
                status="implemented",
            )
        )

    if q:
        query_road = q.strip().upper()
        if query_road not in {r.road_number for r in results}:
            results.append(
                RoadSummary(
                    road_number=query_road,
                    segment_count=0,
                    accident_count=0,
                    bbox=None,
                    status="not_implemented_yet",
                )
            )
    return results


@app.get("/api/road/{road}/bins")
def road_bins(
    road: str,
    bin_size_km: Annotated[int, Query()] = 1,
    year_from: Annotated[int | None, Query()] = None,
    year_to: Annotated[int | None, Query()] = None,
    severity: Annotated[list[str] | None, Query()] = None,
    main_road_only: Annotated[bool, Query()] = True,
    direction: Annotated[str | None, Query()] = None,
) -> dict:
    road_number = assert_implemented_road(road)
    cfg = load_app_config()
    allowed = cfg.get("available_bin_sizes_km", [1, 2, 5, 10, 20])
    if bin_size_km not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid bin_size_km. Allowed: {allowed}")

    dir_norm = _normalize_direction(direction)
    conn = get_connection(read_only=True)
    _require_normalized_data(conn)
    try:
        rows = fetch_road_bins(
            conn,
            road_number,
            bin_size_km,
            year_from,
            year_to,
            severity,
            main_road_only=main_road_only,
            direction=dir_norm,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Bin query failed: {exc}") from exc

    columns = [
        "bin_id",
        "road_number",
        "bin_size_km",
        "bin_start_m",
        "bin_end_m",
        "length_m",
        "geometry_quality",
        "accident_count",
        "fatal_count",
        "injury_count",
        "year_span",
        "density_per_km_year",
        "geojson",
    ]
    fc = rows_to_feature_collection(rows, columns)
    acc_idx = columns.index("accident_count")
    fc["filter"] = {
        "main_road_only": main_road_only,
        "direction": dir_norm or "all",
        "feature_count": len(fc["features"]),
        "accident_count": sum(int(r[acc_idx] or 0) for r in rows),
    }
    return fc


@app.get("/api/road/{road}/accidents-per-km")
def road_accidents_per_km(
    road: str,
    year_from: Annotated[int | None, Query()] = None,
    year_to: Annotated[int | None, Query()] = None,
    severity: Annotated[list[str] | None, Query()] = None,
    main_road_only: Annotated[bool, Query()] = True,
    direction: Annotated[str | None, Query()] = None,
) -> dict:
    """Accident counts per official road kilometer (hm/10 from BRON)."""
    road_number = assert_implemented_road(road)
    dir_norm = _normalize_direction(direction)
    conn = get_connection(read_only=True)
    _require_normalized_data(conn)
    rows = fetch_accidents_per_km(
        conn,
        road_number,
        year_from,
        year_to,
        severity,
        main_road_only=main_road_only,
        direction=dir_norm,
    )
    return {
        "road_number": road_number,
        "unit": "km",
        "km_source": "HECTOMETER/10",
        "main_road_only": main_road_only,
        "direction": dir_norm or "all",
        "rows": [
            {"road_km": int(r[0]), "accident_count": int(r[1])}
            for r in rows
        ],
    }


@app.get("/api/road/{road}/accidents")
def road_accidents(
    road: str,
    year_from: Annotated[int | None, Query()] = None,
    year_to: Annotated[int | None, Query()] = None,
    severity: Annotated[list[str] | None, Query()] = None,
    main_road_only: Annotated[bool, Query()] = True,
    direction: Annotated[str | None, Query()] = None,
) -> dict:
    road_number = assert_implemented_road(road)
    cfg = load_app_config()
    limit = int(cfg.get("max_accident_points", 10000))
    dir_norm = _normalize_direction(direction)

    conn = get_connection(read_only=True)
    _require_normalized_data(conn)
    rows = fetch_road_accidents(
        conn,
        road_number,
        year_from,
        year_to,
        severity,
        limit,
        main_road_only=main_road_only,
        direction=dir_norm,
    )

    columns = ["accident_id", "accident_year", "severity", "location_quality", "road_number_norm", "geojson"]
    return rows_to_feature_collection(rows, columns)


@app.get("/api/road/{road}/stats", response_model=StatsResponse)
def road_stats(road: str) -> StatsResponse:
    road_number = assert_implemented_road(road)
    conn = get_connection(read_only=True)
    _require_normalized_data(conn)

    data = fetch_road_stats(conn, road_number)
    return StatsResponse(
        road_number=road_number,
        total_accidents=data["total_accidents"],
        unresolved_accidents=data["unresolved_accidents"],
        by_year=[
            YearlyStat(accident_year=y, accident_count=n) for y, n in data["by_year"]
        ],
        by_severity=[
            SeverityStat(severity=s, accident_count=n) for s, n in data["by_severity"]
        ],
        by_location_quality=[
            LocationQualityStat(location_quality=lq, accident_count=n)
            for lq, n in data["by_location_quality"]
        ],
        top_bins=[
            TopBinStat(
                bin_id=str(r[0]),
                bin_start_m=float(r[1]),
                bin_end_m=float(r[2]),
                accident_count=int(r[3] or 0),
            )
            for r in data["top_bins"]
        ],
        total_a2_accidents=data["total_accidents"] if road_number == "A2" else None,
        unresolved_a2_accidents=data["unresolved_accidents"] if road_number == "A2" else None,
    )


mount_showcase_frontend(app)
