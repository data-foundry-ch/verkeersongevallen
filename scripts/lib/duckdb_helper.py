"""DuckDB connection helper with spatial extension."""

from __future__ import annotations

from pathlib import Path

import duckdb


def connect_duckdb(db_path: Path, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path), read_only=read_only)
    conn.execute("INSTALL spatial;")
    conn.execute("LOAD spatial;")
    return conn


def run_sql_file(conn: duckdb.DuckDBPyConnection, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    for statement in _split_statements(sql):
        if statement.strip():
            conn.execute(statement)


def _split_statements(sql: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        current.append(line)
        if stripped.endswith(";"):
            parts.append("\n".join(current))
            current = []
    if current:
        parts.append("\n".join(current))
    return parts
