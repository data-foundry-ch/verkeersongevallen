"""Road configuration helpers (implemented roads list from app.yml)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import HTTPException


@lru_cache(maxsize=1)
def load_app_config() -> dict:
    path = Path(__file__).resolve().parents[2] / "config" / "app.yml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def implemented_roads(cfg: dict | None = None) -> list[str]:
    """Canonical road numbers enabled in the API (e.g. A2, A1)."""
    cfg = cfg or load_app_config()
    roads = cfg.get("implemented_roads")
    if roads:
        return [str(r).upper() for r in roads]
    return [str(cfg.get("target_road", "A2")).upper()]


def default_road(cfg: dict | None = None) -> str:
    cfg = cfg or load_app_config()
    return str(cfg.get("target_road", implemented_roads(cfg)[0])).upper()


def normalize_road_number(road: str) -> str:
    return road.strip().upper()


def assert_implemented_road(road: str, cfg: dict | None = None) -> str:
    """Return canonical road number or raise 501 if not implemented."""
    canonical = normalize_road_number(road)
    allowed = implemented_roads(cfg)
    if canonical not in allowed:
        raise HTTPException(
            status_code=501,
            detail=f"Road {canonical} is not implemented. Available: {', '.join(allowed)}",
        )
    return canonical
