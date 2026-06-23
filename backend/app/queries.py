"""Parameterized SQL queries for road accident API."""

from __future__ import annotations

from typing import Any

from backend.app.road_bins import GEOMETRY_DIRECTION, build_road_bins_sql

_BIN_CACHE: dict[tuple, list[tuple]] = {}
_BIN_CACHE_MAX = 48


def table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        [name],
    ).fetchone()
    return bool(row and row[0] > 0)


def normalized_tables_ready(conn) -> bool:
    return table_exists(conn, "roads_norm") and table_exists(conn, "accidents_norm")


def fetch_meta(conn, road_number: str, bin_sizes: list[int]) -> dict[str, Any]:
    if not normalized_tables_ready(conn):
        raise LookupError("Normalized tables not built")

    road_number = road_number.upper()
    if table_exists(conn, "raw_bron_accidents"):
        total_sql = "(SELECT COUNT(*) FROM raw_bron_accidents)"
    else:
        total_sql = "(SELECT COUNT(*) FROM accidents_norm)"

    row = conn.execute(
        f"""
        SELECT
            {total_sql} AS total,
            (SELECT COUNT(*) FROM accidents_norm WHERE road_number_norm = ?) AS road_acc,
            (SELECT COUNT(*) FROM accidents_norm
             WHERE road_number_norm = ? AND location_quality = 'unresolved') AS unresolved,
            (SELECT COUNT(*) FROM roads_norm WHERE road_number_norm = ?) AS segments,
            (SELECT MIN(accident_year) FROM accidents_norm WHERE road_number_norm = ?) AS y_min,
            (SELECT MAX(accident_year) FROM accidents_norm WHERE road_number_norm = ?) AS y_max
        """,
        [road_number, road_number, road_number, road_number, road_number],
    ).fetchone()

    severities = [
        r[0]
        for r in conn.execute(
            """
            SELECT DISTINCT severity FROM accidents_norm
            WHERE road_number_norm = ? AND severity IS NOT NULL ORDER BY 1
            """,
            [road_number],
        ).fetchall()
    ]

    hr_segments = conn.execute(
        """
        SELECT COUNT(*) FROM roads_norm
        WHERE road_number_norm = ? AND COALESCE(carriageway, '') = 'HR'
        """,
        [road_number],
    ).fetchone()[0]

    return {
        "total_accident_count": int(row[0]),
        "road_accident_count": int(row[1]),
        "road_unresolved_count": int(row[2]),
        "road_segment_count": int(row[3]),
        "road_mainroad_segment_count": int(hr_segments),
        "year_from": int(row[4]) if row[4] is not None else None,
        "year_to": int(row[5]) if row[5] is not None else None,
        "severities": severities,
        "bin_sizes_km": bin_sizes,
    }


def fetch_road_summary(conn, road_number: str) -> dict[str, Any]:
    road_number = road_number.upper()
    row = conn.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM roads_norm WHERE road_number_norm = ?) AS segs,
            (SELECT COUNT(*) FROM accidents_norm WHERE road_number_norm = ?) AS acc
        """,
        [road_number, road_number],
    ).fetchone()
    return {
        "segment_count": int(row[0]),
        "accident_count": int(row[1]),
        "bbox": fetch_road_bbox(conn, road_number),
    }


def _year_span(
    conn,
    road_number: str,
    year_from: int | None,
    year_to: int | None,
) -> int:
    row = conn.execute(
        "SELECT MIN(accident_year), MAX(accident_year) FROM accidents_norm WHERE road_number_norm = ?",
        [road_number.upper()],
    ).fetchone()
    y_from = year_from if year_from is not None else int(row[0])
    y_to = year_to if year_to is not None else int(row[1])
    return max(1, y_to - y_from + 1)


def _bins_cache_key(
    road_number: str,
    bin_size_km: int,
    year_from: int | None,
    year_to: int | None,
    severities: list[str] | None,
    main_road_only: bool,
    direction: str | None,
) -> tuple:
    return (
        road_number.upper(),
        bin_size_km,
        year_from,
        year_to,
        tuple(severities or ()),
        main_road_only,
        direction,
    )


def fetch_road_bins(
    conn,
    road_number: str,
    bin_size_km: int,
    year_from: int | None,
    year_to: int | None,
    severities: list[str] | None,
    main_road_only: bool = True,
    direction: str | None = None,
) -> list[tuple]:
    """Return bins with carriageway (HR) and direction (H/T) filters — always computed live."""
    road_number = road_number.upper()
    cache_key = _bins_cache_key(
        road_number, bin_size_km, year_from, year_to, severities, main_road_only, direction
    )
    if cache_key in _BIN_CACHE:
        return _BIN_CACHE[cache_key]

    year_span = _year_span(conn, road_number, year_from, year_to)
    sql, params = build_road_bins_sql(
        road_number,
        bin_size_km,
        year_span,
        main_road_only,
        direction,
        year_from,
        year_to,
        severities,
    )
    rows = conn.execute(sql, params).fetchall()

    if len(_BIN_CACHE) >= _BIN_CACHE_MAX:
        _BIN_CACHE.clear()
    _BIN_CACHE[cache_key] = rows
    return rows


def fetch_a2_bins(
    conn,
    bin_size_km: int,
    year_from: int | None,
    year_to: int | None,
    severities: list[str] | None,
    main_road_only: bool = True,
    direction: str | None = None,
) -> list[tuple]:
    return fetch_road_bins(
        conn, "A2", bin_size_km, year_from, year_to, severities, main_road_only, direction
    )


def _segment_filter_sql(main_road_only: bool, direction: str | None) -> str:
    clauses = ["r.road_number_norm = ?"]
    if main_road_only:
        clauses.append("COALESCE(r.carriageway, '') = 'HR'")
    if direction and direction not in ("all", ""):
        clauses.append(f"COALESCE(r.direction, '') = '{direction}'")
    return " AND ".join(clauses)


def fetch_road_accidents(
    conn,
    road_number: str,
    year_from: int | None,
    year_to: int | None,
    severities: list[str] | None,
    limit: int,
    main_road_only: bool = True,
    direction: str | None = None,
) -> list[tuple]:
    road_number = road_number.upper()
    params: list[Any] = [road_number]
    filters = ["a.road_number_norm = ?"]

    if year_from is not None:
        filters.append("a.accident_year >= ?")
        params.append(year_from)
    if year_to is not None:
        filters.append("a.accident_year <= ?")
        params.append(year_to)
    if severities:
        placeholders = ", ".join("?" for _ in severities)
        filters.append(f"a.severity IN ({placeholders})")
        params.extend(severities)

    seg_filter = _segment_filter_sql(main_road_only, direction)
    params.append(road_number)
    params.append(limit)
    sql = f"""
        SELECT
            a.accident_id,
            a.accident_year,
            a.severity,
            a.location_quality,
            a.road_number_norm,
            ST_AsGeoJSON(a.geom_wgs84) AS geojson
        FROM accidents_norm a
        INNER JOIN roads_norm r ON a.wegvak_id = r.wegvak_id
        WHERE {' AND '.join(filters)} AND {seg_filter} AND a.geom_wgs84 IS NOT NULL
        LIMIT ?
    """
    return conn.execute(sql, params).fetchall()


def fetch_a2_accidents(
    conn,
    year_from: int | None,
    year_to: int | None,
    severities: list[str] | None,
    limit: int,
    main_road_only: bool = True,
    direction: str | None = None,
) -> list[tuple]:
    return fetch_road_accidents(
        conn, "A2", year_from, year_to, severities, limit, main_road_only, direction
    )


def fetch_road_bbox(conn, road_number: str) -> list[float] | None:
    road_number = road_number.upper()
    row = conn.execute(
        f"""
        SELECT
            MIN(ST_XMin(g)) AS min_lon,
            MIN(ST_YMin(g)) AS min_lat,
            MAX(ST_XMax(g)) AS max_lon,
            MAX(ST_YMax(g)) AS max_lat
        FROM (
            SELECT ST_Envelope(r.geom_wgs84) AS g
            FROM roads_norm r
            INNER JOIN raw_nwb_hectointervallen hi
                ON CAST(hi.WVK_ID AS VARCHAR) = r.wegvak_id
            WHERE r.geom_wgs84 IS NOT NULL
              AND r.road_number_norm = ?
              AND COALESCE(r.carriageway, '') = 'HR'
              AND COALESCE(r.direction, '') = '{GEOMETRY_DIRECTION}'
        )
        """,
        [road_number],
    ).fetchone()
    if not row or row[0] is None:
        return None
    return [float(row[0]), float(row[1]), float(row[2]), float(row[3])]


def fetch_accidents_per_km(
    conn,
    road_number: str,
    year_from: int | None,
    year_to: int | None,
    severities: list[str] | None,
    main_road_only: bool = True,
    direction: str | None = None,
) -> list[tuple]:
    """Count accidents per official road kilometer (BRON HECTOMETER / 10)."""
    road_number = road_number.upper()
    acc_filters: list[str] = ["a.road_number_norm = ?"]
    params: list = [road_number]
    if year_from is not None:
        acc_filters.append("a.accident_year >= ?")
        params.append(year_from)
    if year_to is not None:
        acc_filters.append("a.accident_year <= ?")
        params.append(year_to)
    if severities:
        placeholders = ", ".join("?" for _ in severities)
        acc_filters.append(f"a.severity IN ({placeholders})")
        params.extend(severities)
    acc_where = " AND ".join(acc_filters)

    seg_clauses = ["a.wegvak_id = r.wegvak_id", "r.road_number_norm = ?"]
    params.append(road_number)
    if main_road_only:
        seg_clauses.append("COALESCE(r.carriageway, '') = 'HR'")
    if direction and direction not in ("all", ""):
        seg_clauses.append(f"COALESCE(r.direction, '') = '{direction.upper()}'")
    seg_filter = " AND ".join(seg_clauses)

    sql = f"""
        WITH scored AS (
            SELECT
                COALESCE(
                    a.hm / 10.0,
                    (TRY_CAST(hi.BEGKM AS DOUBLE) + TRY_CAST(hi.ENDKM AS DOUBLE)) / 2.0
                ) AS road_km
            FROM accidents_norm a
            INNER JOIN roads_norm r ON {seg_filter}
            LEFT JOIN raw_nwb_hectointervallen hi
                ON CAST(hi.WVK_ID AS VARCHAR) = r.wegvak_id
            WHERE {acc_where}
        )
        SELECT
            FLOOR(road_km)::INTEGER AS road_km,
            COUNT(*)::INTEGER AS accident_count
        FROM scored
        WHERE road_km IS NOT NULL
        GROUP BY 1
        ORDER BY 1
    """
    return conn.execute(sql, params).fetchall()


def fetch_road_stats(conn, road_number: str) -> dict[str, Any]:
    road_number = road_number.upper()
    total = conn.execute(
        "SELECT COUNT(*) FROM accidents_norm WHERE road_number_norm = ?",
        [road_number],
    ).fetchone()[0]
    unresolved = conn.execute(
        """
        SELECT COUNT(*) FROM accidents_norm
        WHERE road_number_norm = ? AND location_quality = 'unresolved'
        """,
        [road_number],
    ).fetchone()[0]

    by_year = [
        (int(r[0]), int(r[1]))
        for r in conn.execute(
            """
            SELECT accident_year, COUNT(*) FROM accidents_norm
            WHERE road_number_norm = ? GROUP BY 1 ORDER BY 1
            """,
            [road_number],
        ).fetchall()
    ]
    by_sev = [
        (r[0], int(r[1]))
        for r in conn.execute(
            """
            SELECT severity, COUNT(*) FROM accidents_norm
            WHERE road_number_norm = ? GROUP BY 1 ORDER BY 2 DESC
            """,
            [road_number],
        ).fetchall()
    ]
    by_lq = [
        (str(r[0]), int(r[1]))
        for r in conn.execute(
            """
            SELECT location_quality, COUNT(*) FROM accidents_norm
            WHERE road_number_norm = ? GROUP BY 1 ORDER BY 2 DESC
            """,
            [road_number],
        ).fetchall()
    ]

    top_bins: list[tuple] = []
    if road_number == "A2" and table_exists(conn, "road_bins_a2"):
        top_bins = conn.execute(
            """
            SELECT b.bin_id, b.bin_start_m, b.bin_end_m, SUM(c.accident_count) AS n
            FROM road_bins_a2 b
            LEFT JOIN accident_bin_counts_a2 c
                ON b.bin_id = c.bin_id AND b.bin_size_km = c.bin_size_km
            WHERE b.bin_size_km = 1
            GROUP BY 1, 2, 3 ORDER BY n DESC NULLS LAST LIMIT 10
            """
        ).fetchall()

    return {
        "total_accidents": int(total),
        "unresolved_accidents": int(unresolved),
        "by_year": by_year,
        "by_severity": by_sev,
        "by_location_quality": by_lq,
        "top_bins": top_bins,
    }
