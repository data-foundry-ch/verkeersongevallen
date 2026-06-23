"""Build road bins from official hectometer km (BRON/NWB) + H-carriageway geometry."""

from __future__ import annotations

from typing import Any

GEOMETRY_DIRECTION = "H"
HM_TO_KM = 10.0
ROADS_TABLE = "roads_norm"
ACCIDENTS_TABLE = "accidents_norm"


def _is_bidirectional_accidents(direction: str | None) -> bool:
    return direction in (None, "", "all")


def _geometry_direction(direction: str | None) -> str:
    if direction and direction not in ("all", ""):
        return direction.upper()
    return GEOMETRY_DIRECTION


def _geometry_segment_filter(main_road_only: bool, direction: str | None) -> str:
    clauses = ["r.geom_rd IS NOT NULL", "r.road_number_norm = ?"]
    if main_road_only:
        clauses.append("COALESCE(r.carriageway, '') = 'HR'")
    clauses.append(f"COALESCE(r.direction, '') = '{_geometry_direction(direction)}'")
    return " AND ".join(clauses)


def _accident_road_filter(main_road_only: bool, direction: str | None) -> str:
    clauses = ["r.road_number_norm = ?"]
    if main_road_only:
        clauses.append("COALESCE(r.carriageway, '') = 'HR'")
    if direction and direction not in ("all", "") and not _is_bidirectional_accidents(direction):
        clauses.append(f"COALESCE(r.direction, '') = '{direction.upper()}'")
    return " AND ".join(clauses)


def build_road_bins_sql(
    road_number: str,
    bin_size_km: int,
    year_span: int,
    main_road_only: bool,
    direction: str | None,
    year_from: int | None,
    year_to: int | None,
    severities: list[str] | None,
) -> tuple[str, list[Any]]:
    """Bins along official road km (hm/10); counts from hm; geometry from hectometer clips on H HR."""
    road_number = road_number.upper()
    bidirectional = _is_bidirectional_accidents(direction)
    geom_filter = _geometry_segment_filter(main_road_only, direction)
    accident_road_filter = _accident_road_filter(main_road_only, direction)

    acc_filters: list[str] = ["a.road_number_norm = ?"]
    acc_params: list[Any] = [road_number]
    if year_from is not None:
        acc_filters.append("a.accident_year >= ?")
        acc_params.append(year_from)
    if year_to is not None:
        acc_filters.append("a.accident_year <= ?")
        acc_params.append(year_to)
    if severities:
        placeholders = ", ".join("?" for _ in severities)
        acc_filters.append(f"a.severity IN ({placeholders})")
        acc_params.extend(severities)
    acc_where = " AND ".join(acc_filters)

    suffix = ""
    if main_road_only:
        suffix += "_HR"
    if bidirectional:
        suffix += f"_{_geometry_direction(direction)}"
    elif direction and direction not in ("all", ""):
        suffix += f"_{direction.upper()}"

    sql = f"""
    WITH km_extent AS (
        SELECT
            MIN(TRY_CAST(hi.BEGKM AS DOUBLE)) AS km_min,
            MAX(TRY_CAST(hi.ENDKM AS DOUBLE)) AS km_max
        FROM raw_nwb_hectointervallen hi
        INNER JOIN {ROADS_TABLE} r
            ON CAST(hi.WVK_ID AS VARCHAR) = r.wegvak_id
        WHERE {geom_filter}
    ),
    bin_defs AS (
        SELECT
            gs.bin_idx,
            e.km_min + gs.bin_idx * ? AS bin_start_km,
            LEAST(e.km_min + (gs.bin_idx + 1) * ?, e.km_max) AS bin_end_km
        FROM km_extent e
        CROSS JOIN LATERAL (
            SELECT UNNEST(generate_series(
                0,
                GREATEST(CEIL((e.km_max - e.km_min) / ?)::INTEGER - 1, 0)
            )) AS bin_idx
        ) gs
        WHERE e.km_max > e.km_min
    ),
    h_segments AS (
        SELECT
            r.wegvak_id,
            r.geom_rd,
            TRY_CAST(hi.BEGKM AS DOUBLE) AS beg_km,
            TRY_CAST(hi.ENDKM AS DOUBLE) AS end_km
        FROM {ROADS_TABLE} r
        INNER JOIN raw_nwb_hectointervallen hi
            ON CAST(hi.WVK_ID AS VARCHAR) = r.wegvak_id
        WHERE {geom_filter}
          AND TRY_CAST(hi.BEGKM AS DOUBLE) IS NOT NULL
          AND TRY_CAST(hi.ENDKM AS DOUBLE) IS NOT NULL
          AND ABS(TRY_CAST(hi.ENDKM AS DOUBLE) - TRY_CAST(hi.BEGKM AS DOUBLE)) > 0
    ),
    clipped AS (
        SELECT
            b.bin_idx,
            b.bin_start_km,
            b.bin_end_km,
            ST_LineSubstring(
                s.geom_rd,
                GREATEST(
                    0.0,
                    (GREATEST(b.bin_start_km, s.beg_km) - s.beg_km)
                    / (s.end_km - s.beg_km)
                ),
                LEAST(
                    1.0,
                    (LEAST(b.bin_end_km, s.end_km) - s.beg_km)
                    / (s.end_km - s.beg_km)
                )
            ) AS geom_clip
        FROM bin_defs b
        INNER JOIN h_segments s
            ON s.end_km > b.bin_start_km AND s.beg_km < b.bin_end_km
    ),
    bins_merged AS (
        SELECT
            b.bin_idx,
            b.bin_start_km,
            b.bin_end_km,
            ST_LineMerge(ST_Collect(LIST(cl.geom_clip))) AS geom_merged
        FROM bin_defs b
        LEFT JOIN clipped cl
            ON b.bin_idx = cl.bin_idx AND cl.geom_clip IS NOT NULL
        GROUP BY b.bin_idx, b.bin_start_km, b.bin_end_km
    ),
    bins AS (
        SELECT
            ? || '_' || ? || 'km_' || LPAD(CAST(b.bin_idx AS VARCHAR), 5, '0') || '{suffix}' AS bin_id,
            ? AS road_number,
            ? AS bin_size_km,
            b.bin_start_km * 1000.0 AS bin_start_m,
            b.bin_end_km * 1000.0 AS bin_end_m,
            (b.bin_end_km - b.bin_start_km) * 1000.0 AS length_m,
            m.geom_merged AS geom_rd,
            CASE
                WHEN m.geom_merged IS NULL THEN NULL
                ELSE ST_AsGeoJSON(
                    ST_Transform(m.geom_merged, 'EPSG:28992', 'EPSG:4326', always_xy := true)
                )
            END AS geojson,
            CASE WHEN m.geom_merged IS NULL THEN 'empty' ELSE 'hectometer_km' END AS geometry_quality
        FROM bin_defs b
        LEFT JOIN bins_merged m ON b.bin_idx = m.bin_idx
    ),
    accidents_scored AS (
        SELECT
            a.accident_id,
            COALESCE(
                a.hm / {HM_TO_KM},
                (TRY_CAST(hi.BEGKM AS DOUBLE) + TRY_CAST(hi.ENDKM AS DOUBLE)) / 2.0
            ) AS road_km
        FROM {ACCIDENTS_TABLE} a
        INNER JOIN {ROADS_TABLE} r ON a.wegvak_id = r.wegvak_id
        LEFT JOIN raw_nwb_hectointervallen hi
            ON CAST(hi.WVK_ID AS VARCHAR) = r.wegvak_id
        WHERE {acc_where}
          AND {accident_road_filter}
          AND COALESCE(
              a.hm / {HM_TO_KM},
              (TRY_CAST(hi.BEGKM AS DOUBLE) + TRY_CAST(hi.ENDKM AS DOUBLE)) / 2.0
          ) IS NOT NULL
    ),
    accident_counts AS (
        SELECT
            b.bin_id,
            COUNT(*) AS accident_count,
            SUM(CASE WHEN COALESCE(s.fatal_count, 0) > 0 THEN 1 ELSE 0 END) AS fatal_count,
            SUM(CASE WHEN COALESCE(s.injury_count, 0) > 0 THEN 1 ELSE 0 END) AS injury_count
        FROM bins b
        JOIN accidents_scored ac
            ON ac.road_km >= b.bin_start_m / 1000.0
           AND ac.road_km < b.bin_end_m / 1000.0
        JOIN {ACCIDENTS_TABLE} a ON a.accident_id = ac.accident_id
        LEFT JOIN accidents_staging s ON a.accident_id = s.accident_id
        GROUP BY b.bin_id
    )
    SELECT
        b.bin_id,
        b.road_number,
        b.bin_size_km,
        b.bin_start_m,
        b.bin_end_m,
        b.length_m,
        b.geometry_quality,
        COALESCE(ac.accident_count, 0) AS accident_count,
        COALESCE(ac.fatal_count, 0) AS fatal_count,
        COALESCE(ac.injury_count, 0) AS injury_count,
        {year_span} AS year_span,
        CASE
            WHEN b.length_m > 0
            THEN COALESCE(ac.accident_count, 0) / (b.length_m / 1000.0) / {year_span}
            ELSE 0
        END AS density_per_km_year,
        b.geojson
    FROM bins b
    LEFT JOIN accident_counts ac ON b.bin_id = ac.bin_id
    ORDER BY b.bin_start_m
    """
    params: list[Any] = [
        road_number,  # km_extent
        bin_size_km,
        bin_size_km,
        bin_size_km,
        road_number,  # h_segments
        road_number,
        bin_size_km,
        road_number,
        bin_size_km,
        *acc_params,
        road_number,  # accident_road_filter
    ]
    return sql, params


def build_filtered_bins_sql(
    bin_size_km: int,
    year_span: int,
    main_road_only: bool,
    direction: str | None,
    year_from: int | None,
    year_to: int | None,
    severities: list[str] | None,
    road_number: str = "A2",
) -> tuple[str, list[Any]]:
    """Backward-compatible wrapper defaulting to A2."""
    return build_road_bins_sql(
        road_number,
        bin_size_km,
        year_span,
        main_road_only,
        direction,
        year_from,
        year_to,
        severities,
    )
