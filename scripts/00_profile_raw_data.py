#!/usr/bin/env python3
"""Profile raw NWB and BRON data; emit reports and generated column map."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.lib.config_loader import load_column_map, load_yaml, resolve_path  # noqa: E402
from scripts.lib.paths import config_path, data_path, project_root  # noqa: E402
from scripts.lib.road_normalize import is_target_a2, normalize_road_number  # noqa: E402
from scripts.lib.text_reader import detect_text_format, profile_text_file  # noqa: E402

ROAD_HINTS = re.compile(
    r"(weg|road|route|nummer|number|wegnum|wegnr|routeltr|routenr|wegbh|beh|hmp)",
    re.I,
)
ID_HINTS = re.compile(r"(^id$|_id$|^id_|nummer|code|fk_)", re.I)
YEAR_HINTS = re.compile(r"(jaar|year|datum|date)", re.I)
GEO_HINTS = re.compile(r"(geom|wkt|x_coord|y_coord|lon|lat|coord)", re.I)
A2_PATTERNS = re.compile(r"a\s*2|002|^2$|rijksweg\s*2|autosnelweg\s*2|a2", re.I)


def walk_data_dirs() -> tuple[Path, Path]:
    nwb = data_path("raw", "nwb")
    bron = data_path("raw", "bron")
    if not nwb.exists():
        raise FileNotFoundError(f"NWB directory missing: {nwb}")
    if not bron.exists():
        raise FileNotFoundError(f"BRON directory missing: {bron}")
    return nwb, bron


def profile_shapefile(path: Path) -> dict[str, Any]:
    conn = duckdb.connect()
    conn.execute("INSTALL spatial; LOAD spatial;")
    rel = path.resolve().as_posix()
    info: dict[str, Any] = {"path": str(path), "type": "shapefile"}

    try:
        cols = conn.execute(
            f"DESCRIBE SELECT * FROM ST_Read('{rel}') LIMIT 0"
        ).fetchall()
        info["columns"] = [{"name": c[0], "type": c[1]} for c in cols]
        count = conn.execute(f"SELECT COUNT(*) FROM ST_Read('{rel}')").fetchone()[0]
        info["row_count"] = int(count)
        sample = conn.execute(f"SELECT * FROM ST_Read('{rel}') LIMIT 3").fetchdf()
        info["sample_rows"] = sample.to_dict(orient="records")
        geom_types = conn.execute(
            f"""
            SELECT ST_GeometryType(geom) AS gtype, COUNT(*) AS n
            FROM ST_Read('{rel}')
            GROUP BY 1
            """
        ).fetchall()
        info["geometry_types"] = {str(r[0]): int(r[1]) for r in geom_types}

        prj = path.with_suffix(".prj")
        if prj.exists():
            info["crs_prj"] = prj.read_text(encoding="utf-8", errors="replace")[:500]
            if "RD_New" in info["crs_prj"] or "Amersfoort" in info["crs_prj"]:
                info["crs_inferred"] = "EPSG:28992 (RD New)"
            else:
                info["crs_inferred"] = "unknown — inspect .prj manually"
    except Exception as exc:
        info["error"] = str(exc)
    finally:
        conn.close()
    return info


def classify_columns(columns: list[str]) -> dict[str, list[str]]:
    return {
        "likely_id": [c for c in columns if ID_HINTS.search(c)],
        "likely_road_number": [c for c in columns if ROAD_HINTS.search(c)],
        "likely_year_date": [c for c in columns if YEAR_HINTS.search(c)],
        "likely_geometry": [c for c in columns if GEO_HINTS.search(c)],
    }


def distinct_values(conn: duckdb.DuckDBPyConnection, table_sql: str, col: str, limit: int = 30) -> list[tuple[str, int]]:
    safe_col = col.strip('"')
    try:
        rows = conn.execute(
            f"""
            SELECT CAST("{safe_col}" AS VARCHAR) AS v, COUNT(*) AS n
            FROM ({table_sql}) t
            WHERE "{safe_col}" IS NOT NULL AND CAST("{safe_col}" AS VARCHAR) != ''
            GROUP BY 1 ORDER BY n DESC LIMIT {limit}
            """
        ).fetchall()
        return [(str(r[0]), int(r[1])) for r in rows]
    except Exception:
        return []


def search_a2_candidates(
    conn: duckdb.DuckDBPyConnection,
    table_sql: str,
    columns: list[str],
) -> dict[str, Any]:
    results: dict[str, Any] = {"columns_searched": [], "matches": []}
    col_map = load_column_map()
    a2_cfg = col_map.get("a2", {})

    for col in columns:
        col_upper = col.strip('"').upper()
        if not (
            ROAD_HINTS.search(col)
            or col_upper in {"WEGNR_HMP", "WEGNUMMER", "ROUTELTR", "ROUTENR", "WEGBEHSRT"}
        ):
            continue
        safe_col = col.strip('"')
        results["columns_searched"].append(safe_col)
        try:
            rows = conn.execute(
                f"""
                SELECT CAST("{safe_col}" AS VARCHAR) AS v, COUNT(*) AS n
                FROM ({table_sql}) t
                WHERE "{safe_col}" IS NOT NULL
                GROUP BY 1
                """
            ).fetchall()
            for val, cnt in rows:
                sval = str(val).strip()
                if A2_PATTERNS.search(sval) or sval.upper() == "A2":
                    results["matches"].append({"column": safe_col, "value": sval, "count": int(cnt)})
                elif is_target_a2(
                    normalize_road_number(sval),
                    sval,
                    None,
                    None,
                    None,
                    a2_cfg,
                ):
                    results["matches"].append({"column": safe_col, "value": sval, "count": int(cnt)})
        except Exception as exc:
            results["matches"].append({"column": safe_col, "error": str(exc)})
    return results


def build_generated_column_map(profiles: dict[str, Any]) -> dict[str, Any]:
    base = load_column_map() if config_path("column_map.yml").exists() else _empty_column_map()
    base["_generated_at"] = datetime.now(timezone.utc).isoformat()
    base["_note"] = "Review and copy relevant fields to config/column_map.yml"
    return base


def _empty_column_map() -> dict[str, Any]:
    return yaml.safe_load(
        (project_root() / "config" / "column_map.yml").read_text(encoding="utf-8")
    )


def profile_all() -> dict[str, Any]:
    nwb_dir, bron_dir = walk_data_dirs()
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "nwb_files": [],
        "bron_files": [],
        "a2_detection": {},
        "next_steps": [],
    }

    conn = duckdb.connect()
    conn.execute("INSTALL spatial; LOAD spatial;")

    for path in sorted(nwb_dir.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        entry: dict[str, Any] = {"name": path.name, "size_bytes": path.stat().st_size}
        if path.suffix.lower() == ".shp":
            entry.update(profile_shapefile(path))
            if "columns" in entry:
                entry["column_hints"] = classify_columns([c["name"] for c in entry["columns"]])
                rel = path.resolve().as_posix()
                a2 = search_a2_candidates(
                    conn,
                    f"SELECT * FROM ST_Read('{rel}')",
                    [c["name"] for c in entry["columns"]],
                )
                if a2["matches"]:
                    report["a2_detection"][path.name] = a2
        elif path.suffix.lower() in {".txt", ".csv", ".tsv"}:
            try:
                tp = profile_text_file(path)
                entry.update(
                    {
                        "type": "text",
                        "encoding": tp.encoding,
                        "delimiter": tp.delimiter,
                        "row_count": tp.row_count,
                        "columns": tp.columns,
                        "column_hints": classify_columns(tp.columns),
                        "sample_rows": tp.sample_rows[:3],
                    }
                )
                rel = path.resolve().as_posix()
                enc, delim, header = detect_text_format(path)
                table_sql = f"""
                    SELECT * FROM read_csv(
                        '{rel}', header={str(header).lower()}, delim='{delim}',
                        encoding='{enc}', all_varchar=true, sample_size=-1
                    )
                """
                for col in entry["column_hints"]["likely_road_number"][:8]:
                    entry.setdefault("distinct_road_values", {})[col] = distinct_values(
                        conn, table_sql, col, limit=15
                    )
                a2 = search_a2_candidates(conn, table_sql, tp.columns)
                if a2["matches"]:
                    report["a2_detection"][path.name] = a2
            except Exception as exc:
                entry["error"] = str(exc)
        else:
            entry["type"] = path.suffix.lower() or "unknown"
        report["nwb_files"].append(entry)

    for path in sorted(bron_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".txt", ".csv"}:
            continue
        entry: dict[str, Any] = {"name": path.name, "size_bytes": path.stat().st_size}
        try:
            tp = profile_text_file(path)
            entry.update(
                {
                    "type": "text",
                    "encoding": tp.encoding,
                    "delimiter": tp.delimiter,
                    "row_count": tp.row_count,
                    "columns": tp.columns,
                    "column_hints": classify_columns(tp.columns),
                    "sample_rows": tp.sample_rows[:3],
                }
            )
            rel = path.resolve().as_posix()
            enc, delim, header = detect_text_format(path)
            table_sql = f"""
                SELECT * FROM read_csv(
                    '{rel}', header={str(header).lower()}, delim='{delim}',
                    encoding='{enc}', all_varchar=true, sample_size=-1
                )
            """
            a2 = search_a2_candidates(conn, table_sql, tp.columns)
            if a2["matches"]:
                report["a2_detection"][path.name] = a2
        except Exception as exc:
            entry["error"] = str(exc)
        report["bron_files"].append(entry)

    conn.close()

    # A2 reliability assessment
    wegvak_a2 = report["a2_detection"].get("wegvakken.txt", {})
    a2_matches = wegvak_a2.get("matches", [])
    wegnr_hmp = [m for m in a2_matches if m.get("column") == "WEGNR_HMP" and m.get("value") == "A2"]
    report["a2_detection_summary"] = {
        "candidate_road_columns": list(
            {m["column"] for f in report["a2_detection"].values() for m in f.get("matches", []) if "column" in m}
        ),
        "wegvakken_a2_via_wegnr_hmp": wegnr_hmp[0]["count"] if wegnr_hmp else 0,
        "automatic_detection_reliable": bool(wegnr_hmp),
        "recommended_a2_key": "WEGNR_HMP = 'A2'" if wegnr_hmp else "manual mapping required",
    }

    if not wegnr_hmp:
        report["next_steps"].append("Fill a2.allowed_raw_road_number_values in config/column_map.yml")
    report["next_steps"].append("Review config/column_map.yml id/geometry columns against profile")
    report["next_steps"].append("Run `make ingest` after confirming mappings")

    return report


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Raw Data Profile Report",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "## Summary",
        "",
    ]
    for f in report["nwb_files"]:
        if f.get("row_count"):
            lines.append(f"- **NWB {f['name']}**: {f['row_count']:,} rows")
    for f in report["bron_files"]:
        if f.get("row_count"):
            lines.append(f"- **BRON {f['name']}**: {f['row_count']:,} rows")

    lines.extend(["", "## A2 detection candidates", ""])
    summary = report.get("a2_detection_summary", {})
    lines.append(f"- Automatic detection reliable: **{summary.get('automatic_detection_reliable')}**")
    lines.append(f"- Recommended key: **{summary.get('recommended_a2_key')}**")
    lines.append(f"- WEGNR_HMP A2 row count: **{summary.get('wegvakken_a2_via_wegnr_hmp')}**")
    lines.append("")
    for fname, det in report.get("a2_detection", {}).items():
        lines.append(f"### {fname}")
        for m in det.get("matches", [])[:20]:
            lines.append(f"- `{m.get('column')}` = `{m.get('value')}` → {m.get('count', m.get('error'))} rows")
        lines.append("")

    lines.extend(["## Next steps", ""])
    for step in report.get("next_steps", []):
        lines.append(f"- {step}")

    lines.extend(["", "## NWB files", ""])
    for f in report["nwb_files"]:
        lines.append(f"### {f['name']}")
        if f.get("columns"):
            cols = f["columns"]
            if cols and isinstance(cols[0], dict):
                col_names = [c.get("name", str(c)) for c in cols]
            else:
                col_names = [str(c) for c in cols]
            lines.append(f"Columns ({len(col_names)}): `{', '.join(col_names[:20])}`…")
        if f.get("crs_inferred"):
            lines.append(f"CRS: {f['crs_inferred']}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    out_dir = data_path("processed")
    out_dir.mkdir(parents=True, exist_ok=True)

    report = profile_all()
    json_path = out_dir / "profile_report.json"
    md_path = out_dir / "profile_report.md"
    gen_path = config_path("column_map.generated.yml")

    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    write_markdown(report, md_path)

    generated = build_generated_column_map(report)
    gen_path.write_text(yaml.dump(generated, sort_keys=False, allow_unicode=True), encoding="utf-8")

    print(f"Profile report: {md_path}")
    print(f"JSON report:    {json_path}")
    print(f"Generated map:  {gen_path}")
    summary = report.get("a2_detection_summary", {})
    print(f"\nA2 detection reliable: {summary.get('automatic_detection_reliable')}")
    print(f"WEGNR_HMP A2 segments: {summary.get('wegvakken_a2_via_wegnr_hmp')}")


if __name__ == "__main__":
    main()
