#!/usr/bin/env python3
"""Split the full pipeline DuckDB into raw archive + deployment database.

Step 1 (raw):   accidents_raw.duckdb — raw BRON/NWB tables + staging (re-ingest / re-normalize)
Step 2 (deploy): accidents_deploy.duckdb — only tables the live map API uses (upload to Render)

Usage:
    python scripts/05_split_databases.py raw
    python scripts/05_split_databases.py deploy
    python scripts/05_split_databases.py all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.lib.config_loader import load_app_config, resolve_path  # noqa: E402
from scripts.lib.duckdb_helper import connect_duckdb  # noqa: E402

# Re-normalize without re-ingest (optional future pipeline from raw archive).
RAW_EXTRA_TABLES = ("accidents_staging", "road_points_norm")

# Live API + frontend: roads_norm, accidents_norm, raw_nwb_hectointervallen, accidents_staging
def _file_size_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


def _list_tables(conn, prefix: str | None = None) -> list[str]:
    rows = conn.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'main' AND table_type = 'BASE TABLE'
        ORDER BY 1
        """
    ).fetchall()
    names = [str(r[0]) for r in rows]
    if prefix:
        return [n for n in names if n.startswith(prefix)]
    return names


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        [name],
    ).fetchone()
    return bool(row and row[0] > 0)


def _copy_table(conn_dst, table: str) -> int:
    conn_dst.execute(f"DROP TABLE IF EXISTS {table}")
    conn_dst.execute(f"CREATE TABLE {table} AS SELECT * FROM conn_src.{table}")
    return conn_dst.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _attach_source(conn_dst, source: Path) -> None:
    path = str(source.resolve()).replace("'", "''")
    conn_dst.execute(f"ATTACH '{path}' AS conn_src (READ_ONLY)")


def _implemented_roads(cfg: dict) -> list[str]:
    roads = cfg.get("implemented_roads")
    if roads:
        return [str(r).upper() for r in roads]
    return [str(cfg.get("target_road", "A2")).upper()]


def export_raw(source: Path, target: Path) -> None:
    if not source.exists():
        raise SystemExit(f"Source database not found: {source}. Run the pipeline first.")

    if target.exists():
        target.unlink()

    print(f"Step 1 — raw archive: {target}")
    src = connect_duckdb(source, read_only=True)
    dst = connect_duckdb(target)
    _attach_source(dst, source)

    raw_tables = _list_tables(src, "raw_")
    tables = raw_tables + [t for t in RAW_EXTRA_TABLES if _table_exists(src, t)]

    if not raw_tables:
        raise SystemExit("No raw_* tables in source. Run ingest before split.")

    total_rows = 0
    for table in tables:
        if not _table_exists(src, table):
            print(f"  skip {table} (missing)")
            continue
        n = _copy_table(dst, table)
        total_rows += n
        print(f"  {table}: {n:,} rows")

    dst.execute("DETACH conn_src")
    dst.execute("CHECKPOINT")
    dst.close()
    src.close()

    print(f"Raw archive: {_file_size_mb(target):.1f} MB, {len(tables)} tables, {total_rows:,} rows")


def export_deploy(source: Path, target: Path, cfg: dict) -> None:
    if not source.exists():
        raise SystemExit(f"Source database not found: {source}. Run normalize before deploy export.")

    for required in ("roads_norm", "accidents_norm", "raw_nwb_hectointervallen"):
        conn = connect_duckdb(source, read_only=True)
        if not _table_exists(conn, required):
            conn.close()
            raise SystemExit(f"Missing {required}. Run normalize first.")
        conn.close()

    roads = _implemented_roads(cfg)
    placeholders = ", ".join("?" for _ in roads)

    if target.exists():
        target.unlink()

    print(f"Step 2 — deploy database: {target}")
    print(f"  implemented_roads: {', '.join(roads)}")

    src = connect_duckdb(source, read_only=True)
    dst = connect_duckdb(target)
    _attach_source(dst, source)

    dst.execute(
        f"""
        CREATE TABLE roads_norm AS
        SELECT * FROM conn_src.roads_norm
        WHERE road_number_norm IN ({placeholders})
        """,
        roads,
    )
    n_roads = dst.execute("SELECT COUNT(*) FROM roads_norm").fetchone()[0]
    print(f"  roads_norm: {n_roads:,} rows")

    dst.execute(
        f"""
        CREATE TABLE accidents_norm AS
        SELECT * FROM conn_src.accidents_norm
        WHERE road_number_norm IN ({placeholders})
        """,
        roads,
    )
    n_acc = dst.execute("SELECT COUNT(*) FROM accidents_norm").fetchone()[0]
    print(f"  accidents_norm: {n_acc:,} rows")

    dst.execute(
        """
        CREATE TABLE raw_nwb_hectointervallen AS
        SELECT hi.*
        FROM conn_src.raw_nwb_hectointervallen hi
        INNER JOIN roads_norm r
            ON CAST(hi.WVK_ID AS VARCHAR) = r.wegvak_id
        """
    )
    n_hi = dst.execute("SELECT COUNT(*) FROM raw_nwb_hectointervallen").fetchone()[0]
    print(f"  raw_nwb_hectointervallen: {n_hi:,} rows (trimmed to implemented roads)")

    if _table_exists(src, "accidents_staging"):
        dst.execute(
            """
            CREATE TABLE accidents_staging AS
            SELECT s.accident_id, s.fatal_count, s.injury_count
            FROM conn_src.accidents_staging s
            INNER JOIN accidents_norm a ON a.accident_id = s.accident_id
            """
        )
        n_st = dst.execute("SELECT COUNT(*) FROM accidents_staging").fetchone()[0]
        print(f"  accidents_staging: {n_st:,} rows (fatal/injury columns only)")
    else:
        dst.execute(
            """
            CREATE TABLE accidents_staging (
                accident_id VARCHAR,
                fatal_count INTEGER,
                injury_count INTEGER
            )
            """
        )
        print("  accidents_staging: empty (source missing)")

    dst.execute("DETACH conn_src")
    dst.execute("CHECKPOINT")
    dst.close()
    src.close()

    print(f"Deploy database: {_file_size_mb(target):.1f} MB")
    print("Upload accidents_deploy.duckdb to object storage for Render (not the 4GB full file).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Split DuckDB into raw archive + deploy export")
    parser.add_argument(
        "step",
        choices=("raw", "deploy", "all"),
        help="raw = step 1 archive, deploy = step 2 API DB, all = both",
    )
    args = parser.parse_args()

    cfg = load_app_config()
    source = resolve_path(cfg.get("database_path", "data/processed/accidents.duckdb"))
    raw_path = resolve_path(cfg.get("raw_database_path", "data/processed/accidents_raw.duckdb"))
    deploy_path = resolve_path(cfg.get("deploy_database_path", "data/processed/accidents_deploy.duckdb"))

    raw_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Source: {source} ({_file_size_mb(source):.1f} MB)" if source.exists() else f"Source: {source} (missing)")

    if args.step in ("raw", "all"):
        export_raw(source, raw_path)
    if args.step in ("deploy", "all"):
        export_deploy(source, deploy_path, cfg)


if __name__ == "__main__":
    main()
