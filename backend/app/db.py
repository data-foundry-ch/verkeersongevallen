"""DuckDB connection for API."""

from __future__ import annotations

import os
import threading
from pathlib import Path

import duckdb
import yaml

_local = threading.local()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_app_config() -> dict:
    path = _project_root() / "config" / "app.yml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_db_path() -> Path:
    env_path = os.environ.get("DATABASE_PATH", "").strip()
    if env_path:
        p = Path(env_path)
        return p if p.is_absolute() else _project_root() / p
    cfg = _load_app_config()
    rel = cfg.get("database_path", "data/processed/accidents.duckdb")
    p = Path(rel)
    return p if p.is_absolute() else _project_root() / p


def get_connection(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    """One read-only DuckDB connection per thread (safe for FastAPI thread pool)."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        return conn

    db_path = get_db_path()
    if not db_path.exists():
        raise FileNotFoundError(
            f"DuckDB database not found at {db_path}. Run the pipeline: make ingest normalize bins"
        )
    conn = duckdb.connect(str(db_path), read_only=read_only)
    conn.execute("INSTALL spatial;")
    conn.execute("LOAD spatial;")
    _local.conn = conn
    return conn


def close_connection() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None
