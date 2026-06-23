#!/usr/bin/env python3
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
multi = sum(
    1 for r in rows if r[-1] and json.loads(r[-1])["type"] == "MultiLineString"
)
acc = sum(int(r[7]) for r in rows)
short = 0
for r in rows:
    gj = r[-1]
    length_m = float(r[5])
    if not gj or length_m <= 0:
        short += 1
        continue
    glen = c.execute(
        "SELECT ST_Length(ST_Transform(ST_GeomFromGeoJSON(?), 'EPSG:4326', 'EPSG:28992', always_xy := true))",
        [gj],
    ).fetchone()[0]
    if glen / length_m < 0.5:
        short += 1

print("bins:", len(rows), "MultiLineString:", multi)
print("empty:", sum(1 for r in rows if r[6] == "empty"))
print("km range:", float(rows[0][3]) / 1000, "-", float(rows[-1][4]) / 1000)
print("thin bins:", short)
print("accidents:", acc)
print("quality:", rows[0][6] if rows else None)
