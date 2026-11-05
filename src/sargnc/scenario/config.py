"""YAML loading. Stage 1 task 1-2 scope: the `area` section only."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import Any

import yaml

from sargnc.terrain.area import AreaSpec


class ScenarioError(ValueError):
    """Invalid scenario file."""


def read_yaml(path: Path) -> dict[str, Any]:
    with open(path) as f:
        doc = yaml.safe_load(f)
    if not isinstance(doc, dict):
        raise ScenarioError(f"{path}: top level must be a mapping")
    return doc


def area_from_dict(d: dict[str, Any], where: str = "area") -> AreaSpec:
    if not isinstance(d, dict):
        raise ScenarioError(f"{where}: must be a mapping")
    allowed = {"name", "center", "size_m", "buffer_m", "resolution_m", "dem_source"}
    unknown = set(d) - allowed
    if unknown:
        raise ScenarioError(f"{where}: unknown keys {sorted(unknown)}; allowed {sorted(allowed)}")
    for key in ("name", "center"):
        if key not in d:
            raise ScenarioError(f"{where}.{key}: required")
    c = d["center"]
    if not (isinstance(c, dict) and {"lat", "lon"} <= set(c)):
        raise ScenarioError(f"{where}.center: expected {{lat: <deg>, lon: <deg>}}, got {c!r}")
    size = d.get("size_m", [1400.0, 1400.0])
    if isinstance(size, (int, float)):
        size = [size, size]
    if not (isinstance(size, list) and len(size) == 2):
        raise ScenarioError(f"{where}.size_m: expected number or [east, north], got {size!r}")
    defaults = {f.name: f.default for f in fields(AreaSpec)}
    try:
        return AreaSpec(
            name=str(d["name"]),
            center_lat=float(c["lat"]),
            center_lon=float(c["lon"]),
            size_e_m=float(size[0]),
            size_n_m=float(size[1]),
            buffer_m=float(d.get("buffer_m", defaults["buffer_m"])),
            resolution_m=float(d.get("resolution_m", defaults["resolution_m"])),
            dem_source=str(d.get("dem_source", defaults["dem_source"])),
        )
    except (TypeError, ValueError) as e:
        raise ScenarioError(f"{where}: {e}") from e


def load_area(path: str | Path) -> AreaSpec:
    path = Path(path)
    doc = read_yaml(path)
    if "area" not in doc:
        raise ScenarioError(f"{path}: missing required section 'area'")
    return area_from_dict(doc["area"], f"{path.name}:area")
