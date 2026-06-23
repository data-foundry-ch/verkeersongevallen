#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402
from scripts.lib.config_loader import load_app_config, resolve_path  # noqa: E402

db_path = resolve_path(load_app_config()["database_path"])
con = duckdb.connect(str(db_path), read_only=True)
con.execute("LOAD spatial")

# HM-ordered dedupe: one segment per 100m hm bucket (longest HR)
sql = """
WITH hr AS (
    SELECT *, ST_Length(geom_rd) AS seg_len_m,
           (COALESCE(start_hm, end_hm, 0) + COALESCE(end_hm, start_hm, 0)) / 2.0 AS hm_mid
    FROM roads_a2_norm
    WHERE COALESCE(carriageway, '') = 'HR' AND geom_rd IS NOT NULL
),
ranked AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY FLOOR(hm_mid / 100)
            ORDER BY seg_len_m DESC, wegvak_id
        ) AS rn
    FROM hr
),
dedup AS (
    SELECT * FROM ranked WHERE rn = 1
),
ordered AS (
    SELECT *,
        ROW_NUMBER() OVER (ORDER BY hm_mid, wegvak_id) AS seg_ord
    FROM dedup
),
chain AS (
    SELECT *,
        SUM(seg_len_m) OVER (ORDER BY seg_ord ROWS UNBOUNDED PRECEDING) - seg_len_m AS chain_start_m,
        SUM(seg_len_m) OVER (ORDER BY seg_ord ROWS UNBOUNDED PRECEDING) AS chain_end_m
    FROM ordered
),
gaps AS (
    SELECT c1.seg_ord, ST_Distance(ST_EndPoint(c1.geom_rd), ST_StartPoint(c2.geom_rd)) AS jump_m
    FROM chain c1
    JOIN chain c2 ON c2.seg_ord = c1.seg_ord + 1
    WHERE ST_Distance(ST_EndPoint(c1.geom_rd), ST_StartPoint(c2.geom_rd)) > 100
)
SELECT
    (SELECT COUNT(*) FROM dedup),
    (SELECT ROUND(MAX(chain_end_m)/1000, 1) FROM chain),
    (SELECT COUNT(*) FROM gaps),
    (SELECT ROUND(MAX(jump_m), 0) FROM gaps)
"""
print("HM-ordered dedupe:", con.execute(sql).fetchone())

hm = con.execute(
    """
    SELECT
        COUNT(*) AS n,
        COUNT(start_hm) AS with_hm,
        MIN(start_hm) AS hm_min,
        MAX(end_hm) AS hm_max
    FROM roads_a2_norm
    WHERE COALESCE(carriageway, '') = 'HR'
    """
).fetchone()
print("HR hectometer fields:", hm)
