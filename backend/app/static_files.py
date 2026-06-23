"""Serve Vite production build from frontend/dist (monolith / showcase deploy)."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


def static_dist_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


def static_files_enabled() -> bool:
    dist = static_dist_dir()
    return dist.is_dir() and (dist / "index.html").is_file()


def mount_showcase_frontend(app: FastAPI) -> None:
    """Mount SPA assets and fallback. Call after all /api routes are registered."""
    dist = static_dist_dir()
    if not static_files_enabled():
        logger.info("frontend/dist not found — running API-only (use Vite dev server locally)")
        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="showcase-assets")

    @app.get("/", include_in_schema=False)
    async def showcase_index() -> FileResponse:
        return FileResponse(dist / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def showcase_spa(full_path: str) -> FileResponse:
        if full_path.startswith("api") or full_path in ("docs", "openapi.json", "redoc"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = dist / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")

    logger.info("Serving showcase frontend from %s", dist)
