"""Text file detection and DuckDB CSV ingestion helpers."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import duckdb


ENCODINGS = ("UTF-8", "latin-1", "cp1252")
DELIMITERS = (",", ";", "\t", "|")


@dataclass
class TextProfile:
    path: Path
    encoding: str
    delimiter: str
    header: bool
    columns: list[str]
    row_count: int
    sample_rows: list[dict[str, str]]


def detect_text_format(path: Path, sample_lines: int = 5) -> tuple[str, str, bool]:
    raw = path.read_bytes()[:65536]
    encoding = "UTF-8"
    for enc in ENCODINGS:
        try:
            raw.decode(enc)
            encoding = enc
            break
        except UnicodeDecodeError:
            continue

    text = raw.decode(encoding, errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()][:sample_lines]
    if not lines:
        return encoding, ",", True

    best_delim = ","
    best_score = -1
    for delim in DELIMITERS:
        score = lines[0].count(delim)
        if score > best_score:
            best_score = score
            best_delim = delim

    header = lines[0].startswith('"') or best_delim in lines[0]
    return encoding, best_delim, header


def _read_csv_header(path: Path, encoding: str, delimiter: str) -> list[str]:
    with path.open(encoding=encoding, newline="") as f:
        row = next(csv.reader(f, delimiter=delimiter))
    return [h.strip().strip('"') for h in row]


def profile_text_file(path: Path) -> TextProfile:
    encoding, delimiter, header = detect_text_format(path)
    rel = path.as_posix()
    conn = duckdb.connect()
    conn.execute("INSTALL spatial; LOAD spatial;")

    query = f"""
        SELECT *
        FROM read_csv(
            '{rel}',
            header={str(header).lower()},
            delim='{delimiter}',
            encoding='{encoding}',
            all_varchar=true,
            sample_size=-1
        )
        LIMIT 5
    """
    cur = conn.execute(query)
    columns = [d[0].strip('"') for d in cur.description]
    sample_rows_raw = cur.fetchall()
    sample_rows = [dict(zip(columns, row, strict=False)) for row in sample_rows_raw]
    count = conn.execute(
        f"""
        SELECT COUNT(*) FROM read_csv(
            '{rel}', header={str(header).lower()}, delim='{delimiter}',
            encoding='{encoding}', all_varchar=true, sample_size=-1
        )
        """
    ).fetchone()[0]
    conn.close()

    return TextProfile(
        path=path,
        encoding=encoding,
        delimiter=delimiter,
        header=header,
        columns=columns,
        row_count=int(count),
        sample_rows=sample_rows,
    )


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _csv_source_sql(path: Path, profile: TextProfile) -> str:
    rel = path.resolve().as_posix()
    return f"""
        read_csv(
            '{rel}',
            header={str(profile.header).lower()},
            delim='{profile.delimiter}',
            encoding='{profile.encoding}',
            all_varchar=true,
            sample_size=-1
        )
    """


def _clean_columns_sql(path: Path, profile: TextProfile) -> str:
    clean_cols = _read_csv_header(path, profile.encoding, profile.delimiter)
    conn = duckdb.connect()
    cur = conn.execute(f"SELECT * FROM {_csv_source_sql(path, profile)} LIMIT 0")
    raw_cols = [d[0] for d in cur.description]
    conn.close()

    parts = []
    for raw, clean in zip(raw_cols, clean_cols, strict=False):
        parts.append(
            f"TRIM(BOTH '\"' FROM CAST({_quote_ident(raw)} AS VARCHAR)) AS {_quote_ident(clean)}"
        )
    return f"SELECT {', '.join(parts)} FROM {_csv_source_sql(path, profile)}"


def ingest_text_to_table(
    conn: duckdb.DuckDBPyConnection,
    path: Path,
    table_name: str,
    source_label: str | None = None,
) -> int:
    profile = profile_text_file(path)
    label = source_label or path.name

    conn.execute(f"DROP TABLE IF EXISTS {table_name}")
    clean_sql = _clean_columns_sql(path, profile)
    conn.execute(
        f"""
        CREATE TABLE {table_name} AS
        SELECT
            src.*,
            '{label}' AS _source_file,
            CURRENT_TIMESTAMP AS _ingested_at
        FROM ({clean_sql}) src
        """
    )
    return conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
