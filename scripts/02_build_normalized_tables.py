#!/usr/bin/env python3
"""Build normalized road and accident tables; filter A2 subsets."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.lib.config_loader import load_app_config, load_column_map, resolve_path  # noqa: E402
from scripts.lib.duckdb_helper import connect_duckdb, run_sql_file  # noqa: E402
from scripts.lib.paths import sql_path  # noqa: E402


def q(col: str | None) -> str:
    """Quote DuckDB identifier (CSV columns retain quoted names)."""
    if not col or col == "NULL":
        return "NULL"
    return f'"{col.strip(chr(34))}"'


def validate_mappings(col_map: dict) -> list[str]:
    warnings: list[str] = []
    nwb = col_map.get("nwb", {})
    wvk = nwb.get("wegvakken", {})
    for key in ("id_col", "road_number_col"):
        if not wvk.get(key):
            warnings.append(f"nwb.wegvakken.{key} is not set")
    bron = col_map.get("bron", {}).get("accidents", {})
    for key in ("accident_id_col", "year_col", "wegvak_id_col"):
        if not bron.get(key):
            warnings.append(f"bron.accidents.{key} is not set")
    return warnings


def build_roads_norm_sql(col_map: dict) -> str:
    wvk = col_map["nwb"]["wegvakken"]
    geo = col_map["nwb"]["wegvakgeografie"]
    a2 = col_map.get("a2", {})

    id_col = q(wvk["id_col"])
    road_num = q(wvk["road_number_col"])
    road_type = q(wvk.get("road_type_col")) if wvk.get("road_type_col") else "NULL"
    road_alt = q(wvk.get("road_number_alt_col")) if wvk.get("road_number_alt_col") else "NULL"
    route_ltr = q(wvk.get("route_letter_col")) if wvk.get("route_letter_col") else "NULL"
    route_nr = q(wvk.get("route_number_col")) if wvk.get("route_number_col") else "NULL"
    from_hm = q(wvk.get("from_hm_col")) if wvk.get("from_hm_col") else "NULL"
    to_hm = q(wvk.get("to_hm_col")) if wvk.get("to_hm_col") else "NULL"
    direction = q(wvk.get("direction_col")) if wvk.get("direction_col") else "NULL"
    carriageway = q(wvk.get("carriageway_col")) if wvk.get("carriageway_col") else "NULL"
    geo_join = q(geo.get("join_col") or geo.get("id_col") or wvk.get("fk_col") or "FK_VELD1")
    wvk_fk = q(wvk.get("fk_col") or "FK_VELD1")

    allowed_raw = a2.get("allowed_raw_road_number_values", ["A2"])
    raw_list = ", ".join(f"'{v}'" for v in allowed_raw)

    return f"""
    CREATE OR REPLACE TABLE roads_norm AS
    WITH base AS (
        SELECT
            CAST(w.{id_col} AS VARCHAR) AS wegvak_id,
            CAST(w.{road_num} AS VARCHAR) AS road_number_raw,
            CAST(w.{road_type} AS VARCHAR) AS road_type_raw,
            CAST(w.{road_alt} AS VARCHAR) AS road_number_alt,
            CAST(w.{route_ltr} AS VARCHAR) AS route_letter,
            CAST(w.{route_nr} AS VARCHAR) AS route_number,
            CAST(w.{direction} AS VARCHAR) AS direction,
            CAST(w.{carriageway} AS VARCHAR) AS carriageway,
            TRY_CAST(w.{from_hm} AS DOUBLE) AS start_hm,
            TRY_CAST(w.{to_hm} AS DOUBLE) AS end_hm,
            g.geom AS geom_rd
        FROM raw_nwb_wegvakken w
        LEFT JOIN raw_nwb_wegvakgeografie g
            ON TRIM(CAST(w.{wvk_fk} AS VARCHAR)) = TRIM(CAST(g.{geo_join} AS VARCHAR))
    ),
    numbered AS (
        SELECT
            *,
            CASE
                WHEN UPPER(TRIM(COALESCE(road_number_raw, ''))) IN ({raw_list}) THEN 'A2'
                WHEN UPPER(TRIM(COALESCE(road_number_raw, ''))) = 'A2' THEN 'A2'
                WHEN UPPER(TRIM(COALESCE(route_letter, ''))) = 'A'
                     AND TRY_CAST(NULLIF(REGEXP_REPLACE(COALESCE(route_number, road_number_alt, ''), '[^0-9]', '', 'g'), '') AS INTEGER) = 2
                THEN 'A2'
                WHEN UPPER(TRIM(COALESCE(road_type_raw, ''))) IN ('R', 'A')
                     AND LPAD(REGEXP_REPLACE(COALESCE(road_number_alt, ''), '[^0-9]', '', 'g'), 1, '0') IN ('2', '02', '002')
                     AND UPPER(TRIM(COALESCE(road_number_raw, ''))) IN ('A2', '002', '2', '02')
                THEN 'A2'
                WHEN REGEXP_MATCHES(UPPER(TRIM(COALESCE(road_number_raw, ''))), '^A2$') THEN 'A2'
                WHEN REGEXP_MATCHES(UPPER(REPLACE(COALESCE(road_number_raw, ''), ' ', '')), '^A2$') THEN 'A2'
                WHEN UPPER(TRIM(COALESCE(route_letter, ''))) || TRY_CAST(
                    NULLIF(REGEXP_REPLACE(COALESCE(route_number, ''), '[^0-9]', '', 'g'), '') AS VARCHAR
                ) = 'A2' THEN 'A2'
                WHEN UPPER(TRIM(COALESCE(route_letter, ''))) = 'A'
                     AND TRY_CAST(NULLIF(REGEXP_REPLACE(COALESCE(route_number, ''), '[^0-9]', '', 'g'), '') AS INTEGER) = 2
                THEN 'A2'
                WHEN road_number_raw IS NOT NULL AND road_number_raw != ''
                THEN UPPER(REPLACE(TRIM(road_number_raw), ' ', ''))
                ELSE NULL
            END AS road_number_norm,
            CASE
                WHEN start_hm IS NOT NULL AND end_hm IS NOT NULL AND start_hm > end_hm
                THEN end_hm ELSE start_hm
            END AS start_hm_adj,
            CASE
                WHEN start_hm IS NOT NULL AND end_hm IS NOT NULL AND start_hm > end_hm
                THEN start_hm ELSE end_hm
            END AS end_hm_adj
        FROM base
    )
    SELECT
        wegvak_id,
        road_number_raw,
        road_type_raw,
        road_number_norm,
        road_type_raw AS road_type,
        direction,
        carriageway,
        start_hm_adj AS start_hm,
        end_hm_adj AS end_hm,
        CASE WHEN geom_rd IS NOT NULL THEN ST_Length(geom_rd) ELSE NULL END AS length_m,
        (road_number_norm = 'A2') AS is_target_a2,
        geom_rd,
        CASE WHEN geom_rd IS NOT NULL
            THEN ST_Transform(geom_rd, 'EPSG:28992', 'EPSG:4326', always_xy := true)
            ELSE NULL
        END AS geom_wgs84,
        CASE WHEN geom_rd IS NOT NULL
            THEN ST_AsGeoJSON(ST_Transform(geom_rd, 'EPSG:28992', 'EPSG:4326', always_xy := true))
            ELSE NULL
        END AS geojson
    FROM numbered;
    """


def build_road_points_sql(col_map: dict) -> str:
    pl = col_map["nwb"]["puntlocaties"]
    pid = q(pl["point_id_col"])
    x_col = q(pl.get("x_col") or "X_COORD")
    y_col = q(pl.get("y_col") or "Y_COORD")

    return f"""
    CREATE OR REPLACE TABLE road_points_norm AS
    WITH pts AS (
        SELECT
            CAST(p.{pid} AS VARCHAR) AS point_id,
            NULL::VARCHAR AS wegvak_id,
            NULL::VARCHAR AS road_number_raw,
            NULL::VARCHAR AS road_number_norm,
            NULL::DOUBLE AS hm,
            TRY_CAST(p.{x_col} AS DOUBLE) AS x_rd,
            TRY_CAST(p.{y_col} AS DOUBLE) AS y_rd
        FROM raw_nwb_puntlocaties p
    ),
    hp AS (
        SELECT
            CAST(h.FK_VELD5 AS VARCHAR) AS point_id,
            CAST(h.WVK_ID AS VARCHAR) AS wegvak_id,
            NULL::VARCHAR AS road_number_raw,
            NULL::VARCHAR AS road_number_norm,
            TRY_CAST(h.HECTOMETER AS DOUBLE) AS hm,
            NULL::DOUBLE AS x_rd,
            NULL::DOUBLE AS y_rd
        FROM raw_nwb_hectopunten h
    ),
    combined AS (
        SELECT * FROM pts
        UNION ALL
        SELECT * FROM hp
    ),
    deduped AS (
        SELECT * EXCLUDE (rn) FROM (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY point_id
                    ORDER BY CASE WHEN x_rd IS NOT NULL THEN 0 ELSE 1 END, hm NULLS LAST
                ) AS rn
            FROM combined
        ) WHERE rn = 1
    ),
    with_geom AS (
        SELECT
            c.point_id,
            COALESCE(c.wegvak_id, r.wegvak_id) AS wegvak_id,
            COALESCE(r.road_number_raw, c.road_number_raw) AS road_number_raw,
            r.road_number_norm,
            c.hm,
            CASE
                WHEN c.x_rd IS NOT NULL AND c.y_rd IS NOT NULL
                THEN ST_Point(c.x_rd, c.y_rd)
                WHEN c.wegvak_id IS NOT NULL AND c.hm IS NOT NULL AND r.geom_rd IS NOT NULL
                THEN ST_LineInterpolatePoint(
                    r.geom_rd,
                    LEAST(GREATEST(
                        (c.hm - COALESCE(r.start_hm, 0)) / NULLIF(
                            ABS(COALESCE(r.end_hm, 0) - COALESCE(r.start_hm, 0)), 0
                        ), 0), 1)
                )
                ELSE NULL
            END AS geom_rd,
            COALESCE(r.is_target_a2, false) AS is_target_a2
        FROM deduped c
        LEFT JOIN roads_norm r ON c.wegvak_id = r.wegvak_id
    )
    SELECT
        point_id,
        wegvak_id,
        road_number_raw,
        road_number_norm,
        hm,
        is_target_a2,
        geom_rd,
        CASE WHEN geom_rd IS NOT NULL
            THEN ST_Transform(geom_rd, 'EPSG:28992', 'EPSG:4326', always_xy := true)
            ELSE NULL
        END AS geom_wgs84
    FROM with_geom;
    """


def build_accidents_norm_sql(col_map: dict) -> str:
    b = col_map["bron"]["accidents"]
    aid = q(b["accident_id_col"])
    year = q(b["year_col"])
    date_col = q(b.get("date_col")) if b.get("date_col") else "NULL"
    hour = q(b.get("hour_col")) if b.get("hour_col") else "NULL"
    sev = q(b.get("severity_col")) if b.get("severity_col") else "NULL"
    atype = q(b.get("accident_type_col")) if b.get("accident_type_col") else "NULL"
    wvk = q(b.get("wegvak_id_col")) if b.get("wegvak_id_col") else "NULL"
    pid = q(b.get("puntlocatie_id_col")) if b.get("puntlocatie_id_col") else "NULL"
    hm = q(b.get("hm_col")) if b.get("hm_col") else "NULL"
    x_col = b.get("x_col")
    y_col = b.get("y_col")
    fatal = q(b.get("fatal_count_col")) if b.get("fatal_count_col") else "NULL"
    injury = q(b.get("injury_count_col")) if b.get("injury_count_col") else "NULL"

    direct_xy = ""
    if x_col and y_col:
        xc, yc = q(x_col), q(y_col)
        direct_xy = f"""
        CASE
            WHEN TRY_CAST(a.{xc} AS DOUBLE) BETWEEN 10000 AND 280000
                 AND TRY_CAST(a.{yc} AS DOUBLE) BETWEEN 300000 AND 620000
            THEN ST_Point(TRY_CAST(a.{xc} AS DOUBLE), TRY_CAST(a.{yc} AS DOUBLE))
            ELSE NULL
        END"""
    else:
        direct_xy = "NULL::GEOMETRY"

    return f"""
    CREATE OR REPLACE TABLE accidents_staging AS
    SELECT
        CAST(a.{aid} AS VARCHAR) AS accident_id,
        TRY_CAST(a.{year} AS INTEGER) AS accident_year,
        TRY_CAST(NULLIF(CAST(a.{date_col} AS VARCHAR), '') AS DATE) AS accident_date,
        TRY_CAST(NULLIF(CAST(a.{hour} AS VARCHAR), '') AS INTEGER) AS accident_hour,
        NULLIF(TRIM(CAST(a.{sev} AS VARCHAR)), '') AS severity,
        CAST(a.{atype} AS VARCHAR) AS accident_type,
        NULL::VARCHAR AS road_number_raw,
        NULL::VARCHAR AS road_type_raw,
        NULL::VARCHAR AS road_number_norm,
        NULLIF(TRIM(CAST(a.{wvk} AS VARCHAR)), '') AS wegvak_id,
        NULLIF(TRIM(CAST(a.{pid} AS VARCHAR)), '') AS point_id,
        TRY_CAST(NULLIF(TRIM(CAST(a.{hm} AS VARCHAR)), '') AS DOUBLE) AS hm,
        TRY_CAST(NULLIF(TRIM(CAST(a.{fatal} AS VARCHAR)), '') AS INTEGER) AS fatal_count,
        TRY_CAST(NULLIF(TRIM(CAST(a.{injury} AS VARCHAR)), '') AS INTEGER) AS injury_count,
        {direct_xy} AS geom_direct
    FROM raw_bron_accidents a;

    CREATE OR REPLACE TABLE accidents_norm AS
    WITH punt_best AS (
        SELECT * EXCLUDE (rn) FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY point_id ORDER BY CASE WHEN geom_rd IS NOT NULL THEN 0 ELSE 1 END) AS rn
            FROM road_points_norm
        ) WHERE rn = 1
    ),
    located AS (
        SELECT
            s.*,
            r.road_number_raw AS wvk_road_raw,
            r.road_number_norm AS wvk_road_norm,
            r.is_target_a2,
            r.geom_rd AS wvk_geom,
            r.start_hm,
            r.end_hm,
            p.geom_rd AS punt_geom,
            CASE
                WHEN s.geom_direct IS NOT NULL THEN s.geom_direct
                WHEN p.geom_rd IS NOT NULL THEN p.geom_rd
                WHEN s.wegvak_id IS NOT NULL AND s.hm IS NOT NULL AND r.geom_rd IS NOT NULL THEN
                    ST_LineInterpolatePoint(
                        r.geom_rd,
                        LEAST(GREATEST(
                            CASE
                                WHEN r.start_hm IS NOT NULL AND r.end_hm IS NOT NULL
                                     AND ABS(r.end_hm - r.start_hm) > 0
                                THEN (s.hm - LEAST(r.start_hm, r.end_hm))
                                     / ABS(r.end_hm - r.start_hm)
                                ELSE s.hm / NULLIF(ST_Length(r.geom_rd), 0) * 1000
                            END,
                        0), 1)
                    )
                WHEN s.wegvak_id IS NOT NULL AND r.geom_rd IS NOT NULL THEN
                    ST_LineInterpolatePoint(r.geom_rd, 0.5)
                ELSE NULL
            END AS geom_rd,
            CASE
                WHEN s.geom_direct IS NOT NULL THEN 'direct_xy'
                WHEN p.geom_rd IS NOT NULL THEN 'puntlocatie'
                WHEN s.wegvak_id IS NOT NULL AND s.hm IS NOT NULL AND r.geom_rd IS NOT NULL THEN 'wegvak_hm_interpolated'
                WHEN s.wegvak_id IS NOT NULL AND r.geom_rd IS NOT NULL THEN 'wegvak_midpoint_fallback'
                ELSE 'unresolved'
            END AS location_quality
        FROM accidents_staging s
        LEFT JOIN roads_norm r ON s.wegvak_id = r.wegvak_id
        LEFT JOIN punt_best p ON s.point_id = p.point_id
    )
    SELECT
        accident_id,
        accident_year,
        accident_date,
        accident_hour,
        severity,
        accident_type,
        COALESCE(wvk_road_raw, road_number_raw) AS road_number_raw,
        road_type_raw,
        wvk_road_norm AS road_number_norm,
        wegvak_id,
        point_id,
        hm,
        geom_rd,
        CASE WHEN geom_rd IS NOT NULL
            THEN ST_Transform(geom_rd, 'EPSG:28992', 'EPSG:4326', always_xy := true)
            ELSE NULL
        END AS geom_wgs84,
        location_quality,
        COALESCE(is_target_a2, false) AS is_target_a2
    FROM located;
    """


def print_counts(conn, label: str, table: str) -> None:
    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{label}: {n:,} rows")


def main() -> None:
    app_cfg = load_app_config()
    col_map = load_column_map()
    db_path = resolve_path(app_cfg["database_path"])

    warnings = validate_mappings(col_map)
    for w in warnings:
        print(f"WARNING: {w}")
    if any("is not set" in w for w in warnings):
        raise SystemExit("Fix column_map.yml before normalizing.")

    conn = connect_duckdb(db_path)
    raw_count = conn.execute("SELECT COUNT(*) FROM raw_bron_accidents").fetchone()[0]
    print(f"Raw accidents: {raw_count:,}")

    print("Building roads_norm...")
    conn.execute(build_roads_norm_sql(col_map))
    print_counts(conn, "roads_norm", "roads_norm")

    conn.execute("CREATE OR REPLACE TABLE roads_a2_norm AS SELECT * FROM roads_norm WHERE is_target_a2 = true")
    print_counts(conn, "roads_a2_norm", "roads_a2_norm")

    print("Building road_points_norm...")
    conn.execute(build_road_points_sql(col_map))
    print_counts(conn, "road_points_norm", "road_points_norm")

    print("Building accidents_norm...")
    for stmt in build_accidents_norm_sql(col_map).split(";"):
        if stmt.strip():
            conn.execute(stmt)
    print_counts(conn, "accidents_norm", "accidents_norm")

    conn.execute(
        "CREATE OR REPLACE TABLE accidents_a2_norm AS SELECT * FROM accidents_norm WHERE is_target_a2 = true"
    )
    print_counts(conn, "accidents_a2_norm", "accidents_a2_norm")

    if conn.execute("SELECT COUNT(*) FROM accidents_norm").fetchone()[0] != raw_count:
        raise SystemExit("ERROR: accident row count mismatch — rows were dropped!")

    conn.close()
    print("\nNormalization complete.")


if __name__ == "__main__":
    main()
