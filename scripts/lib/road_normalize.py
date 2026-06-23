"""Defensive Dutch road number normalization."""

from __future__ import annotations

import re
from typing import Any


def normalize_road_number(
    road_number_raw: str | None,
    road_type_raw: str | None = None,
    route_letter: str | None = None,
    route_number: str | None = None,
    config: dict[str, Any] | None = None,
) -> str | None:
    """Return canonical road number like A2, N231, or None if not identifiable."""
    candidates: list[str] = []

    if road_number_raw:
        candidates.append(_normalize_token(road_number_raw, config))

    if route_letter and route_number:
        combined = _normalize_token(f"{route_letter}{route_number}", config)
        if combined:
            candidates.append(combined)
        combined_spaced = _normalize_token(f"{route_letter} {route_number}", config)
        if combined_spaced:
            candidates.append(combined_spaced)

    if road_type_raw and road_number_raw:
        rt = road_type_raw.strip().upper()
        num = _extract_number(road_number_raw)
        if num is not None and rt in {"R", "A", "N", "E"}:
            candidates.append(f"{rt}{num}" if rt != "R" else f"A{num}" if _is_autosnelweg(road_number_raw, config) else f"{rt}{num}")

    for c in candidates:
        if c:
            return c

    # Try parsing combined strings like "A20", "N 231"
    if road_number_raw:
        parsed = _parse_combined_road(road_number_raw)
        if parsed:
            return parsed

    return None


def is_target_a2(
    road_number_norm: str | None,
    road_number_raw: str | None,
    road_type_raw: str | None,
    route_letter: str | None,
    route_number: str | None,
    a2_config: dict[str, Any],
) -> bool:
    canonical = a2_config.get("canonical_road_number", "A2")
    if road_number_norm == canonical:
        return True

    allowed_raw = {str(v).upper() for v in a2_config.get("allowed_raw_road_number_values", [])}
    if road_number_raw and str(road_number_raw).strip().upper() in allowed_raw:
        return True
    if road_number_raw and str(road_number_raw).strip().upper() == canonical:
        return True

    allowed_types = {str(v).upper() for v in a2_config.get("allowed_road_type_values", [])}
    route_letters = {str(v).upper() for v in a2_config.get("route_letter_values", [])}
    route_numbers = {str(v).lstrip("0") or "0" for v in a2_config.get("route_number_values", [])}

    if road_type_raw and str(road_type_raw).strip().upper() in allowed_types:
        num = _extract_number(road_number_raw or route_number or "")
        if num == "2":
            return True

    if route_letter and str(route_letter).strip().upper() in route_letters:
        rn = _extract_number(route_number or road_number_raw or "")
        if rn == "2":
            return True

    # WEGNR_HMP style "A2"
    if road_number_raw and _parse_combined_road(str(road_number_raw)) == canonical:
        return True

    return False


def _normalize_token(value: str, config: dict[str, Any] | None) -> str | None:
    v = value.strip()
    if not v:
        return None
    norm_cfg = (config or {}).get("road_number_normalization", {})
    if norm_cfg.get("strip_whitespace", True):
        v = re.sub(r"\s+", "", v)
    if norm_cfg.get("uppercase_letters", True):
        v = v.upper()
    parsed = _parse_combined_road(v)
    return parsed or v


def _parse_combined_road(value: str) -> str | None:
    v = value.strip().upper()
    v = re.sub(r"\s+", "", v)

    m = re.match(r"^(A|N|E)(\d+)$", v)
    if m:
        return f"{m.group(1)}{int(m.group(2))}"

    m = re.match(r"^RIJKSWEG(\d+)$", v.replace(" ", ""))
    if m:
        return f"A{int(m.group(1))}"

    m = re.match(r"^AUTOSNELWEG(\d+)$", v.replace(" ", ""))
    if m:
        return f"A{int(m.group(1))}"

    if v == "A2":
        return "A2"

    return None


def _extract_number(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    if not digits:
        return None
    return str(int(digits))


def _is_autosnelweg(road_number_raw: str, config: dict[str, Any] | None) -> bool:
    # Rijksweg numbered 002 etc. on autosnelwegen often map to A-roads
    num = _extract_number(road_number_raw)
    return num is not None and int(num) < 100
