#!/usr/bin/env python3
"""Diagnose hm-bin geometry gaps and per-km accident counts."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402
from backend.app.a2_bins import build_filtered_bins_sql  # noqa: E402
from scripts.lib.config_loader import load_app_config, resolve_path  # noqa: E402

c = duckdb.connect(str(resolve_path(load_app_config()["database_path"])), read_only=True)
c.execute("LOAD spatial")

sql, p = build_filtered_bins_sql(5, 10, True, None, 2015, 2024, None)
rows = c.execute(sql, p).fetchall()

empty = [r for r in rows if r[6] == "empty" or r[-1] is None]
thin = []
for r in rows:
    if not r[-1]:
        continue
    glen = c.execute(
        "SELECT ST_Length(ST_Transform(ST_GeomFromGeoJSON(?), 'EPSG:4326', 'EPSG:28992', always_xy := true))",
        [r[-1]],
    ).fetchone()[0]
    length_m = float(r[5])
    if length_m > 0 and glen / length_m < 0.5:
        thin.append((r[0], float(r[3]) / 1000, float(r[4]) / 1000, round(glen / 1000, 2), int(r[7])))

print("=== Bins summary ===")
print("total bins:", len(rows))
print("no geometry:", len(empty))
print("thin geometry (<50%):", len(thin))
if empty:
    print("empty examples:", [(r[0], float(r[3]) / 1000, float(r[4]) / 1000, r[7]) for r in empty[:5]])
if thin:
    print("thin examples (id, km_start, km_end, drawn_km, accidents):", thin[:10])

# Boxtel area ~ km 120-140 (rough) - check bins
print("\n=== Bins km 115-145 (Boxtel corridor) ===")
for r in rows:
    s, e = float(r[3]) / 1000, float(r[4]) / 1000
    if e > 115 and s < 145:
        has = "geom" if r[-1] else "EMPTY"
        glen = 0
        if r[-1]:
            glen = c.execute(
                "SELECT ROUND(ST_Length(ST_Transform(ST_GeomFromGeoJSON(?), 'EPSG:4326', 'EPSG:28992', always_xy := true))/1000,2)",
                [r[-1]],
            ).fetchone()[0]
        print(f"  {s:.1f}-{e:.1f} km  acc={int(r[7]):4d}  drawn={glen}km  {has}")

# km without H hectointervallen coverage
print("\n=== Official km ranges missing H HR hectointervallen segments ===")
gaps = c.execute(
    """
    WITH km_extent AS (
        SELECT MIN(TRY_CAST(hi.BEGKM AS DOUBLE)) km_min, MAX(TRY_CAST(hi.ENDKM AS DOUBLE)) km_max
        FROM raw_nwb_hectointervallen hi
        JOIN roads_a2_norm r ON CAST(hi.WVK_ID AS VARCHAR)=r.wegvak_id
        WHERE COALESCE(r.carriageway,'')='HR' AND COALESCE(r.direction,'')='H'
    ),
    covered AS (
        SELECT gs.km
        FROM km_extent e,
        LATERAL (SELECT UNNEST(generate_series(FLOOR(e.km_min)::INT, CEIL(e.km_max)::INT)) km) gs
        WHERE EXISTS (
            SELECT 1 FROM raw_nwb_hectointervallen hi
            JOIN roads_a2_norm r ON CAST(hi.WVK_ID AS VARCHAR)=r.wegvak_id
            WHERE COALESCE(r.carriageway,'')='HR' AND COALESCE(r.direction,'')='H'
              AND TRY_CAST(hi.BEGKM AS DOUBLE) <= gs.km AND TRY_CAST(hi.ENDKM AS DOUBLE) > gs.km
        )
    ),
    all_km AS (
        SELECT UNNEST(generate_series(FLOOR((SELECT km_min FROM km_extent))::INT,
                                      CEIL((SELECT km_max FROM km_extent))::INT)) km
    )
    SELECT COUNT(*) FROM all_km a WHERE NOT EXISTS (SELECT 1 FROM covered c WHERE c.km=a.km)
    """
).fetchone()[0]
print("integer km marks without H HR segment:", gaps)

print("\n=== Accidents per km (official hm/10), 2015-2024 HR ===")
per_km = c.execute(
    """
    SELECT
        FLOOR(COALESCE(a.hm/10.0, (TRY_CAST(hi.BEGKM AS DOUBLE)+TRY_CAST(hi.ENDKM AS DOUBLE))/2))::INT AS road_km,
        COUNT(*) AS n
    FROM accidents_a2_norm a
    JOIN roads_a2_norm r ON a.wegvak_id=r.wegvak_id
    LEFT JOIN raw_nwb_hectointervallen hi ON CAST(hi.WVK_ID AS VARCHAR)=r.wegvak_id
    WHERE COALESCE(r.carriageway,'')='HR'
      AND a.accident_year BETWEEN 2015 AND 2024
      AND COALESCE(a.hm/10.0, (TRY_CAST(hi.BEGKM AS DOUBLE)+TRY_CAST(hi.ENDKM AS DOUBLE))/2) IS NOT NULL
    GROUP BY 1
    ORDER BY 1
    LIMIT 8
    """
).fetchall()
print("first km:", per_km)
tail = c.execute(
    """
    SELECT
        FLOOR(COALESCE(a.hm/10.0, (TRY_CAST(hi.BEGKM AS DOUBLE)+TRY_CAST(hi.ENDKM AS DOUBLE))/2))::INT AS road_km,
        COUNT(*) AS n
    FROM accidents_a2_norm a
    JOIN roads_a2_norm r ON a.wegvak_id=r.wegvak_id
    LEFT JOIN raw_nwb_hectointervallen hi ON CAST(hi.WVK_ID AS VARCHAR)=r.wegvak_id
    WHERE COALESCE(r.carriageway,'')='HR'
      AND a.accident_year BETWEEN 2015 AND 2024
    GROUP BY 1
    ORDER BY 1 DESC
    LIMIT 5
    """
).fetchall()
print("last km:", tail)

# Boxtel km 120-140 accident density
boxtel = c.execute(
    """
    SELECT FLOOR(COALESCE(a.hm/10.0, (TRY_CAST(hi.BEGKM AS DOUBLE)+TRY_CAST(hi.ENDKM AS DOUBLE))/2))::INT km,
           COUNT(*) n
    FROM accidents_a2_norm a
    JOIN roads_a2_norm r ON a.wegvak_id=r.wegvak_id
    LEFT JOIN raw_nwb_hectointervallen hi ON CAST(hi.WVK_ID AS VARCHAR)=r.wegvak_id
    WHERE COALESCE(r.carriageway,'')='HR' AND a.accident_year BETWEEN 2015 AND 2024
      AND COALESCE(a.hm/10.0, (TRY_CAST(hi.BEGKM AS DOUBLE)+TRY_CAST(hi.ENDKM AS DOUBLE))/2) BETWEEN 115 AND 145
    GROUP BY 1 ORDER BY 1
    """
).fetchall()
print("\nBoxtel corridor accidents per km:", boxtel)
