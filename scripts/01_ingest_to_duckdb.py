#!/usr/bin/env python3
"""Ingest raw NWB and BRON files into DuckDB."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.lib.config_loader import load_app_config, load_column_map, resolve_path  # noqa: E402
from scripts.lib.duckdb_helper import connect_duckdb, run_sql_file  # noqa: E402
from scripts.lib.paths import data_path, project_root, sql_path  # noqa: E402
from scripts.lib.text_reader import ingest_text_to_table  # noqa: E402

NWB_TABLES = [
    ("wegvakken", "raw_nwb_wegvakken"),
    ("puntlocaties", "raw_nwb_puntlocaties"),
    ("hectopunten", "raw_nwb_hectopunten"),
    ("hectointervallen", "raw_nwb_hectointervallen"),
    ("juncties", "raw_nwb_juncties"),
    ("junctiehectometrering", "raw_nwb_junctiehectometrering"),
]


def ingest_shapefile(conn, shp_path: Path, table: str) -> int:
    rel = shp_path.resolve().as_posix()
    conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.execute(
        f"""
        CREATE TABLE {table} AS
        SELECT
            *,
            '{shp_path.name}' AS _source_file,
            CURRENT_TIMESTAMP AS _ingested_at
        FROM ST_Read('{rel}')
        """
    )
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def main() -> None:
    app_cfg = load_app_config()
    col_map = load_column_map()
    db_path = resolve_path(app_cfg.get("database_path", "data/processed/accidents.duckdb"))

    conn = connect_duckdb(db_path)
    run_sql_file(conn, sql_path("00_init.sql"))

    counts: dict[str, int] = {}

    nwb = col_map.get("nwb", {})
    for key, table in NWB_TABLES:
        cfg = nwb.get(key, {})
        path = resolve_path(cfg.get("path", f"data/raw/nwb/{key}.txt"))
        if not path.exists():
            print(f"WARNING: missing {path}, skipping {table}")
            continue
        n = ingest_text_to_table(conn, path, table, path.name)
        counts[table] = n
        print(f"Ingested {table}: {n:,} rows from {path.name}")

    geo_cfg = nwb.get("wegvakgeografie", {})
    shp = resolve_path(geo_cfg.get("path", "data/raw/nwb/wegvakgeografie.shp"))
    if shp.exists():
        n = ingest_shapefile(conn, shp, "raw_nwb_wegvakgeografie")
        counts["raw_nwb_wegvakgeografie"] = n
        print(f"Ingested raw_nwb_wegvakgeografie: {n:,} rows")
    else:
        print(f"WARNING: shapefile missing at {shp}")

    bron_cfg = col_map.get("bron", {}).get("accidents", {})
    bron_path = resolve_path(bron_cfg.get("path", "data/raw/bron/ongevallen.txt"))
    if bron_path.exists():
        n = ingest_text_to_table(conn, bron_path, "raw_bron_accidents", bron_path.name)
        counts["raw_bron_accidents"] = n
        print(f"Ingested raw_bron_accidents: {n:,} rows")
    else:
        raise FileNotFoundError(f"BRON accidents file not found: {bron_path}")

    print(f"\nDuckDB database: {db_path}")
    for table, n in counts.items():
        print(f"  {table}: {n:,}")

    conn.close()


if __name__ == "__main__":
    main()
