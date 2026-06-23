#!/usr/bin/env python3
"""Build A2 distance bins and accident counts per bin."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.lib.config_loader import load_app_config, resolve_path  # noqa: E402
from scripts.lib.duckdb_helper import connect_duckdb, run_sql_file  # noqa: E402
from scripts.lib.paths import sql_path  # noqa: E402

# Option C: H carriageway geometry; accidents from both directions on hoofdrijbaan.
GEOMETRY_DIRECTION = "H"
HR_GEOM_WHERE = (
    f"geom_rd IS NOT NULL AND COALESCE(carriageway, '') = 'HR' "
    f"AND COALESCE(direction, '') = '{GEOMETRY_DIRECTION}'"
)
HR_ANY_WHERE = "geom_rd IS NOT NULL AND COALESCE(carriageway, '') = 'HR'"


def _along_track_chain_sql(seg_where: str) -> str:
    return f"""
    CREATE OR REPLACE TABLE a2_segments_dedup AS
    WITH bounds AS (
        SELECT
            MIN(ST_X(ST_Centroid(geom_rd))) AS min_x,
            MIN(ST_Y(ST_Centroid(geom_rd))) AS min_y,
            MAX(ST_X(ST_Centroid(geom_rd))) AS max_x,
            MAX(ST_Y(ST_Centroid(geom_rd))) AS max_y,
            GREATEST(
                SQRT(
                    POW(MAX(ST_X(ST_Centroid(geom_rd))) - MIN(ST_X(ST_Centroid(geom_rd))), 2)
                    + POW(MAX(ST_Y(ST_Centroid(geom_rd))) - MIN(ST_Y(ST_Centroid(geom_rd))), 2)
                ),
                1.0
            ) AS axis_len
        FROM roads_a2_norm
        WHERE {seg_where}
    ),
    axis AS (
        SELECT
            min_x,
            min_y,
            (max_x - min_x) / axis_len AS ux,
            (max_y - min_y) / axis_len AS uy
        FROM bounds
    ),
    ordered AS (
        SELECT
            s.wegvak_id,
            s.geom_rd,
            s.start_hm,
            s.end_hm,
            ST_Length(s.geom_rd) AS seg_len_m,
            FLOOR(
                ((ST_X(ST_Centroid(s.geom_rd)) - a.min_x) * a.ux
                 + (ST_Y(ST_Centroid(s.geom_rd)) - a.min_y) * a.uy)
                / 100
            ) AS bucket,
            ROW_NUMBER() OVER (
                ORDER BY
                    ((ST_X(ST_Centroid(s.geom_rd)) - a.min_x) * a.ux
                     + (ST_Y(ST_Centroid(s.geom_rd)) - a.min_y) * a.uy),
                    s.wegvak_id
            ) AS seg_ord
        FROM roads_a2_norm s
        CROSS JOIN axis a
        WHERE {seg_where}
    )
    SELECT
        wegvak_id,
        geom_rd,
        start_hm,
        end_hm,
        seg_len_m,
        seg_ord
    FROM ordered;

    CREATE OR REPLACE TABLE a2_wegvak_map AS
    WITH bounds AS (
        SELECT
            MIN(ST_X(ST_Centroid(geom_rd))) AS min_x,
            MIN(ST_Y(ST_Centroid(geom_rd))) AS min_y,
            MAX(ST_X(ST_Centroid(geom_rd))) AS max_x,
            MAX(ST_Y(ST_Centroid(geom_rd))) AS max_y,
            GREATEST(
                SQRT(
                    POW(MAX(ST_X(ST_Centroid(geom_rd))) - MIN(ST_X(ST_Centroid(geom_rd))), 2)
                    + POW(MAX(ST_Y(ST_Centroid(geom_rd))) - MIN(ST_Y(ST_Centroid(geom_rd))), 2)
                ),
                1.0
            ) AS axis_len
        FROM roads_a2_norm
        WHERE {HR_ANY_WHERE}
    ),
    axis AS (
        SELECT
            min_x,
            min_y,
            (max_x - min_x) / axis_len AS ux,
            (max_y - min_y) / axis_len AS uy
        FROM bounds
    ),
    all_hr AS (
        SELECT
            r.wegvak_id,
            FLOOR(
                ((ST_X(ST_Centroid(r.geom_rd)) - a.min_x) * a.ux
                 + (ST_Y(ST_Centroid(r.geom_rd)) - a.min_y) * a.uy)
                / 100
            ) AS bucket
        FROM roads_a2_norm r
        CROSS JOIN axis a
        WHERE {HR_ANY_WHERE}
    ),
    geom_hr AS (
        SELECT wegvak_id, bucket
        FROM all_hr
        INNER JOIN a2_segments_dedup g USING (wegvak_id)
    ),
    canonical AS (
        SELECT bucket, MIN(wegvak_id) AS canonical_wegvak_id
        FROM geom_hr
        GROUP BY bucket
    )
    SELECT
        a.wegvak_id,
        COALESCE(c.canonical_wegvak_id, a.wegvak_id) AS canonical_wegvak_id
    FROM all_hr a
    LEFT JOIN canonical c ON a.bucket = c.bucket;
    """


def build_bins_sql(bin_sizes: list[int]) -> str:
    sizes_sql = ", ".join(str(s) for s in bin_sizes)
    chain_sql = _along_track_chain_sql(HR_GEOM_WHERE)
    return f"""
    {chain_sql}

    CREATE OR REPLACE TABLE a2_chain AS
    SELECT
        *,
        SUM(seg_len_m) OVER (ORDER BY seg_ord ROWS UNBOUNDED PRECEDING) - seg_len_m AS chain_start_m,
        SUM(seg_len_m) OVER (ORDER BY seg_ord ROWS UNBOUNDED PRECEDING) AS chain_end_m
    FROM a2_segments_dedup;

    CREATE OR REPLACE TABLE a2_total AS
    SELECT COALESCE(MAX(chain_end_m), 0) AS total_length_m FROM a2_chain;

    CREATE OR REPLACE TABLE accidents_a2_chainage AS
    WITH point_chain AS (
        SELECT
            a.accident_id,
            a.accident_year,
            a.severity,
            a.wegvak_id,
            c.chain_start_m + ST_LineLocatePoint(c.geom_rd, a.geom_rd) * c.seg_len_m AS chain_m,
            ROW_NUMBER() OVER (
                PARTITION BY a.accident_id
                ORDER BY ST_Distance(a.geom_rd, c.geom_rd), c.seg_ord
            ) AS rn
        FROM accidents_a2_norm a
        INNER JOIN a2_chain c ON a.geom_rd IS NOT NULL
        WHERE EXISTS (
            SELECT 1 FROM roads_a2_norm r
            WHERE a.wegvak_id = r.wegvak_id AND COALESCE(r.carriageway, '') = 'HR'
        )
    )
    SELECT accident_id, accident_year, severity, wegvak_id, chain_m
    FROM point_chain
    WHERE rn = 1

    UNION ALL

    SELECT
        a.accident_id,
        a.accident_year,
        a.severity,
        a.wegvak_id,
        CASE
            WHEN c.wegvak_id IS NOT NULL AND a.hm IS NOT NULL
                 AND c.start_hm IS NOT NULL AND c.end_hm IS NOT NULL
                 AND ABS(c.end_hm - c.start_hm) > 0
            THEN c.chain_start_m + LEAST(GREATEST(
                (a.hm - LEAST(c.start_hm, c.end_hm)) / ABS(c.end_hm - c.start_hm),
                0.0), 1.0) * c.seg_len_m
            WHEN c.wegvak_id IS NOT NULL
            THEN c.chain_start_m + c.seg_len_m * 0.5
            ELSE NULL
        END AS chain_m
    FROM accidents_a2_norm a
    LEFT JOIN a2_wegvak_map m ON a.wegvak_id = m.wegvak_id
    LEFT JOIN a2_chain c ON COALESCE(m.canonical_wegvak_id, a.wegvak_id) = c.wegvak_id
    WHERE a.geom_rd IS NULL;

    CREATE OR REPLACE TABLE road_bins_a2 AS
    WITH sizes AS (SELECT UNNEST([{sizes_sql}]) AS bin_size_km),
    totals AS (SELECT total_length_m FROM a2_total),
    bin_defs AS (
        SELECT
            s.bin_size_km,
            gs.bin_idx,
            gs.bin_idx * s.bin_size_km * 1000.0 AS bin_start_m,
            LEAST((gs.bin_idx + 1) * s.bin_size_km * 1000.0, t.total_length_m) AS bin_end_m
        FROM sizes s
        CROSS JOIN totals t
        CROSS JOIN LATERAL (
            SELECT UNNEST(generate_series(
                0,
                GREATEST(CEIL(t.total_length_m / (s.bin_size_km * 1000.0))::INTEGER - 1, 0)
            )) AS bin_idx
        ) gs
        WHERE t.total_length_m > 0
    ),
    clipped AS (
        SELECT
            b.bin_size_km,
            b.bin_idx,
            b.bin_start_m,
            b.bin_end_m,
            c.wegvak_id,
            CASE
                WHEN c.seg_len_m > 0 AND c.chain_end_m > b.bin_start_m AND c.chain_start_m < b.bin_end_m
                THEN ST_LineSubstring(
                    c.geom_rd,
                    GREATEST(0.0, (b.bin_start_m - c.chain_start_m) / c.seg_len_m),
                    LEAST(1.0, (b.bin_end_m - c.chain_start_m) / c.seg_len_m)
                )
                ELSE NULL
            END AS geom_clip
        FROM bin_defs b
        INNER JOIN a2_chain c
            ON c.chain_end_m > b.bin_start_m AND c.chain_start_m < b.bin_end_m
    ),
    bins_merged AS (
        SELECT
            b.bin_size_km,
            b.bin_idx,
            b.bin_start_m,
            b.bin_end_m,
            ST_LineMerge(ST_Collect(LIST(cl.geom_clip))) AS geom_merged
        FROM bin_defs b
        LEFT JOIN clipped cl
            ON b.bin_size_km = cl.bin_size_km AND b.bin_idx = cl.bin_idx AND cl.geom_clip IS NOT NULL
        GROUP BY b.bin_size_km, b.bin_idx, b.bin_start_m, b.bin_end_m
    ),
    bins_resolved AS (
        SELECT
            b.bin_size_km,
            b.bin_idx,
            b.bin_start_m,
            b.bin_end_m,
            d.unnest.geom AS geom_rd,
            ROW_NUMBER() OVER (
                PARTITION BY b.bin_size_km, b.bin_idx
                ORDER BY ST_Length(d.unnest.geom) DESC
            ) AS part_rn
        FROM bins_merged b
        CROSS JOIN UNNEST(ST_Dump(b.geom_merged)) AS d
        WHERE b.geom_merged IS NOT NULL
    )
    SELECT
        'A2_' || b.bin_size_km || 'km_' || LPAD(CAST(b.bin_idx AS VARCHAR), 5, '0') AS bin_id,
        'A2' AS road_number,
        b.bin_size_km,
        b.bin_start_m,
        b.bin_end_m,
        b.bin_end_m - b.bin_start_m AS length_m,
        b.geom_rd,
        ST_Transform(b.geom_rd, 'EPSG:28992', 'EPSG:4326', always_xy := true) AS geom_wgs84,
        ST_AsGeoJSON(
            ST_Transform(b.geom_rd, 'EPSG:28992', 'EPSG:4326', always_xy := true)
        ) AS geojson,
        'linesubstring' AS geometry_quality
    FROM bins_resolved b
    WHERE b.part_rn = 1

    UNION ALL

    SELECT
        'A2_' || b.bin_size_km || 'km_' || LPAD(CAST(b.bin_idx AS VARCHAR), 5, '0'),
        'A2',
        b.bin_size_km,
        b.bin_start_m,
        b.bin_end_m,
        b.bin_end_m - b.bin_start_m,
        NULL, NULL, NULL,
        'empty'
    FROM bin_defs b
    WHERE NOT EXISTS (
        SELECT 1 FROM clipped cl
        WHERE cl.bin_size_km = b.bin_size_km AND cl.bin_idx = b.bin_idx AND cl.geom_clip IS NOT NULL
    );

    CREATE OR REPLACE TABLE accident_bin_counts_a2 AS
    SELECT
        b.bin_id,
        b.road_number,
        b.bin_size_km,
        a.accident_year,
        a.severity,
        COUNT(*) AS accident_count,
        SUM(CASE WHEN COALESCE(s.fatal_count, 0) > 0 THEN 1 ELSE 0 END) AS fatal_count,
        SUM(CASE WHEN COALESCE(s.injury_count, 0) > 0 THEN 1 ELSE 0 END) AS injury_count
    FROM road_bins_a2 b
    JOIN accidents_a2_chainage ac
        ON ac.chain_m IS NOT NULL
        AND ac.chain_m >= b.bin_start_m
        AND ac.chain_m < b.bin_end_m
    JOIN accidents_a2_norm a ON ac.accident_id = a.accident_id
    LEFT JOIN accidents_staging s ON a.accident_id = s.accident_id
    GROUP BY b.bin_id, b.road_number, b.bin_size_km, a.accident_year, a.severity;
    """


def main() -> None:
    app_cfg = load_app_config()
    db_path = resolve_path(app_cfg["database_path"])
    bin_sizes = app_cfg.get("available_bin_sizes_km", [1, 2, 5, 10, 20])

    conn = connect_duckdb(db_path)

    a2_segs = conn.execute("SELECT COUNT(*) FROM roads_a2_norm").fetchone()[0]
    a2_acc = conn.execute("SELECT COUNT(*) FROM accidents_a2_norm").fetchone()[0]
    print(f"A2 segments: {a2_segs:,}, A2 accidents: {a2_acc:,}")

    if a2_segs == 0:
        raise SystemExit("No A2 road segments found. Check column_map.yml A2 detection.")

    sql = build_bins_sql(bin_sizes)
    for stmt in sql.split(";"):
        s = stmt.strip()
        if s:
            conn.execute(s)

    deduped = conn.execute("SELECT COUNT(*) FROM a2_segments_dedup").fetchone()[0]
    total_km = conn.execute("SELECT total_length_m / 1000 FROM a2_total").fetchone()[0]
    bins = conn.execute("SELECT COUNT(*) FROM road_bins_a2").fetchone()[0]
    counts = conn.execute("SELECT COALESCE(SUM(accident_count), 0) FROM accident_bin_counts_a2").fetchone()[0]
    print(f"a2_segments_dedup ({GEOMETRY_DIRECTION} carriageway): {deduped:,}")
    print(f"a2 chain length: {total_km:.1f} km")
    print(f"road_bins_a2: {bins:,} bins")
    print(f"accident_bin_counts_a2: {counts:,} total counted accidents")

    run_sql_file(conn, sql_path("05_api_views.sql"))
    conn.close()
    print("A2 bin generation complete.")


if __name__ == "__main__":
    main()
