#!/usr/bin/env python3
"""Validate A2 pipeline outputs and write validation report."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.lib.config_loader import load_app_config, resolve_path  # noqa: E402
from scripts.lib.duckdb_helper import connect_duckdb  # noqa: E402
from scripts.lib.paths import data_path  # noqa: E402


def main() -> None:
    app_cfg = load_app_config()
    db_path = resolve_path(app_cfg["database_path"])
    conn = connect_duckdb(db_path, read_only=True)

    lines = [
        "# A2 Validation Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    issues: list[str] = []

    raw_acc = conn.execute("SELECT COUNT(*) FROM raw_bron_accidents").fetchone()[0]
    norm_acc = conn.execute("SELECT COUNT(*) FROM accidents_norm").fetchone()[0]
    a2_acc = conn.execute("SELECT COUNT(*) FROM accidents_a2_norm").fetchone()[0]
    unresolved = conn.execute(
        "SELECT COUNT(*) FROM accidents_a2_norm WHERE location_quality = 'unresolved'"
    ).fetchone()[0]

    lines.extend(
        [
            "## Row counts",
            "",
            f"- Raw accidents: {raw_acc:,}",
            f"- Normalized accidents: {norm_acc:,}",
            f"- A2 accidents: {a2_acc:,}",
            f"- A2 unresolved: {unresolved:,} ({100 * unresolved / max(a2_acc, 1):.1f}%)",
            "",
        ]
    )
    if raw_acc != norm_acc:
        issues.append(f"Row count mismatch: raw={raw_acc} vs norm={norm_acc}")

    a2_segs = conn.execute("SELECT COUNT(*) FROM roads_a2_norm").fetchone()[0]
    missing_geom = conn.execute(
        "SELECT COUNT(*) FROM roads_a2_norm WHERE geom_rd IS NULL"
    ).fetchone()[0]
    lines.extend(
        [
            "## A2 road segments",
            "",
            f"- Segment count: {a2_segs:,}",
            f"- Missing geometry: {missing_geom:,}",
            "",
        ]
    )
    if a2_segs == 0:
        issues.append("No A2 segments")

    invalid_bins = conn.execute(
        "SELECT COUNT(*) FROM road_bins_a2 WHERE geom_rd IS NULL OR NOT ST_IsValid(geom_rd)"
    ).fetchone()[0]
    bin_count = conn.execute("SELECT COUNT(*) FROM road_bins_a2 WHERE bin_size_km = 1").fetchone()[0]
    lines.extend(
        [
            "## A2 bins (1 km)",
            "",
            f"- Bin count: {bin_count:,}",
            f"- Invalid geometries: {invalid_bins:,}",
            "",
        ]
    )

    lines.extend(["## A2 accidents by year", ""])
    for row in conn.execute(
        """
        SELECT accident_year, COUNT(*) AS n
        FROM accidents_a2_norm GROUP BY 1 ORDER BY 1
        """
    ).fetchall():
        lines.append(f"- {row[0]}: {row[1]:,}")

    lines.extend(["", "## A2 accidents by severity", ""])
    for row in conn.execute(
        """
        SELECT COALESCE(severity, '(null)'), COUNT(*) AS n
        FROM accidents_a2_norm GROUP BY 1 ORDER BY n DESC
        """
    ).fetchall():
        lines.append(f"- {row[0]}: {row[1]:,}")

    lines.extend(["", "## Location quality distribution", ""])
    for row in conn.execute(
        """
        SELECT location_quality, COUNT(*) AS n
        FROM accidents_a2_norm GROUP BY 1 ORDER BY n DESC
        """
    ).fetchall():
        lines.append(f"- {row[0]}: {row[1]:,}")

    lines.extend(["", "## CRS sanity (WGS84 bbox)", ""])
    bbox = conn.execute(
        """
        SELECT
            MIN(ST_XMin(envelope)) AS min_lon,
            MIN(ST_YMin(envelope)) AS min_lat,
            MAX(ST_XMax(envelope)) AS max_lon,
            MAX(ST_YMax(envelope)) AS max_lat
        FROM (
            SELECT ST_Envelope(geom_wgs84) AS envelope
            FROM roads_a2_norm WHERE geom_wgs84 IS NOT NULL
        )
        """
    ).fetchone()
    if bbox and bbox[0] is not None:
        lines.append(f"- Bbox: [{bbox[0]:.4f}, {bbox[1]:.4f}, {bbox[2]:.4f}, {bbox[3]:.4f}]")
        if not (3 <= bbox[0] <= 8 and 3 <= bbox[2] <= 8):
            issues.append(f"Longitude out of NL range: {bbox[0]}, {bbox[2]}")
        if not (50 <= bbox[1] <= 54 and 50 <= bbox[3] <= 54):
            issues.append(f"Latitude out of NL range: {bbox[1]}, {bbox[3]}")
    else:
        issues.append("Could not compute WGS84 bbox")

    rd = conn.execute(
        """
        SELECT MIN(ST_XMin(envelope)), MIN(ST_YMin(envelope)),
               MAX(ST_XMax(envelope)), MAX(ST_YMax(envelope))
        FROM (
            SELECT ST_Envelope(geom_rd) AS envelope
            FROM roads_a2_norm WHERE geom_rd IS NOT NULL
        )
        """
    ).fetchone()
    if rd and rd[0]:
        lines.extend(["", "## RD coordinate ranges", "", f"- X: {rd[0]:.0f} – {rd[2]:.0f}", f"- Y: {rd[1]:.0f} – {rd[3]:.0f}"])

    lines.extend(["", "## Top 10 bins by accident count (1 km)", ""])
    for row in conn.execute(
        """
        SELECT b.bin_id, b.bin_start_m, b.bin_end_m, SUM(c.accident_count) AS n
        FROM road_bins_a2 b
        LEFT JOIN accident_bin_counts_a2 c ON b.bin_id = c.bin_id AND b.bin_size_km = c.bin_size_km
        WHERE b.bin_size_km = 1
        GROUP BY 1, 2, 3 ORDER BY n DESC NULLS LAST LIMIT 10
        """
    ).fetchall():
        lines.append(f"- {row[0]} ({row[1]:.0f}–{row[2]:.0f} m): {row[3] or 0:,}")

    lines.extend(["", "## Issues", ""])
    if issues:
        for i in issues:
            lines.append(f"- ⚠ {i}")
    else:
        lines.append("- None detected")

    out = data_path("processed", "validation_report_a2.md")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Validation report: {out}")
    if issues:
        print(f"Warnings: {len(issues)}")
        for i in issues:
            print(f"  - {i}")
    conn.close()


if __name__ == "__main__":
    main()
