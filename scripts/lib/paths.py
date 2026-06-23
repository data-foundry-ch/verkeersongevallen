"""Project root and path helpers."""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def config_path(name: str) -> Path:
    return project_root() / "config" / name


def sql_path(name: str) -> Path:
    return project_root() / "sql" / name


def data_path(*parts: str) -> Path:
    return project_root().joinpath("data", *parts)
