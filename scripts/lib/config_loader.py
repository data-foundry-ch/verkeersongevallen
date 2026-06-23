"""YAML configuration loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from scripts.lib.paths import config_path, project_root


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_app_config() -> dict[str, Any]:
    return load_yaml(config_path("app.yml"))


def load_column_map() -> dict[str, Any]:
    primary = config_path("column_map.yml")
    if primary.exists():
        return load_yaml(primary)
    generated = config_path("column_map.generated.yml")
    if generated.exists():
        return load_yaml(generated)
    raise FileNotFoundError(
        "No column_map.yml found. Run `make profile` first or create config/column_map.yml"
    )


def resolve_path(relative: str) -> Path:
    p = Path(relative)
    if p.is_absolute():
        return p
    return project_root() / p
