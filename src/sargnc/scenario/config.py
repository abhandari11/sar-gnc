"""YAML loading and validation for sites and scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from sargnc.paths import project_root
from sargnc.scenario.region import SearchRegion
from sargnc.scenario.site import Base, Loiter, Site
from sargnc.terrain.mapspec import MapSpec


class ScenarioError(ValueError):
    """Invalid site or scenario file."""


@dataclass
class Scenario:
    name: str
    site: Site
    search: SearchRegion


def read_yaml(path: Path) -> dict[str, Any]:
    with open(path) as f:
        doc = yaml.safe_load(f)
    if not isinstance(doc, dict):
        raise ScenarioError(f"{path}: top level must be a mapping")
    return doc


def _section(d: Any, where: str, required: set[str], optional: set[str] = frozenset()) -> dict[str, Any]:
    if not isinstance(d, dict):
        raise ScenarioError(f"{where}: must be a mapping, got {type(d).__name__}")
    missing = required - set(d)
    if missing:
        raise ScenarioError(f"{where}: missing required key(s) {sorted(missing)}")
    unknown = set(d) - required - set(optional)
    if unknown:
        raise ScenarioError(f"{where}: unknown key(s) {sorted(unknown)}; allowed {sorted(required | set(optional))}")
    return d


def _num(v: Any, where: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ScenarioError(f"{where}: expected a number, got {v!r}")
    return float(v)


def _pair(v: Any, where: str) -> tuple[float, float]:
    if not (isinstance(v, (list, tuple)) and len(v) == 2):
        raise ScenarioError(f"{where}: expected [a, b], got {v!r}")
    return _num(v[0], f"{where}[0]"), _num(v[1], f"{where}[1]")


def _en(v: Any, where: str) -> tuple[float, float]:
    d = _section(v, where, {"east", "north"})
    return _num(d["east"], f"{where}.east"), _num(d["north"], f"{where}.north")


def site_from_dict(doc: dict[str, Any], where: str) -> Site:
    _section(doc, where, {"site", "base"})
    s = _section(doc["site"], f"{where}:site", {"name", "origin", "extent_m"},
                 {"resolution_m", "dem_source", "min_edge_margin_m"})
    o = _section(s["origin"], f"{where}:site.origin", {"lat", "lon"})
    ext = _section(s["extent_m"], f"{where}:site.extent_m", {"east", "north"})
    try:
        spec = MapSpec(
            name=str(s["name"]),
            origin_lat=_num(o["lat"], f"{where}:site.origin.lat"),
            origin_lon=_num(o["lon"], f"{where}:site.origin.lon"),
            east_m=_pair(ext["east"], f"{where}:site.extent_m.east"),
            north_m=_pair(ext["north"], f"{where}:site.extent_m.north"),
            resolution_m=_num(s.get("resolution_m", 5.0), f"{where}:site.resolution_m"),
            dem_source=str(s.get("dem_source", "swissalti3d")),
        )
    except ValueError as e:
        if isinstance(e, ScenarioError):
            raise
        raise ScenarioError(f"{where}:site: {e}") from e
    margin = _num(s.get("min_edge_margin_m", 1000.0), f"{where}:site.min_edge_margin_m")

    b = _section(doc["base"], f"{where}:base", {"name", "position_m", "launch_heading_deg", "home_loiter"})
    be, bn = _en(b["position_m"], f"{where}:base.position_m")
    lo = _section(b["home_loiter"], f"{where}:base.home_loiter", {"center_m", "radius_m", "height_agl_m"},
                  {"clockwise"})
    le, ln = _en(lo["center_m"], f"{where}:base.home_loiter.center_m")
    loiter = Loiter(le, ln, _num(lo["radius_m"], f"{where}:base.home_loiter.radius_m"),
                    _num(lo["height_agl_m"], f"{where}:base.home_loiter.height_agl_m"), bool(lo.get("clockwise", False)))
    if loiter.radius_m <= 0 or loiter.height_agl_m <= 0:
        raise ScenarioError(f"{where}:base.home_loiter: radius_m and height_agl_m must be > 0")
    base = Base(str(b["name"]), be, bn, _num(b["launch_heading_deg"], f"{where}:base.launch_heading_deg") % 360.0,
                loiter)
    for label, (e, n) in (("base.position_m", (be, bn)), ("base.home_loiter.center_m", (le, ln))):
        m = spec.margin_to_edge(e, n)
        if m < margin:
            raise ScenarioError(f"{where}:{label} ({e:.0f}, {n:.0f}) is {m:.0f} m from the map edge; "
                                f"need >= {margin:.0f} m (enlarge site.extent_m)")
    return Site(spec.name, spec, base, margin)


def load_site(path: str | Path) -> Site:
    path = Path(path)
    return site_from_dict(read_yaml(path), path.name)


def _resolve_site(ref: str, cfg_path: Path) -> Path:
    for cand in (cfg_path.parent / "sites" / f"{ref}.yaml", cfg_path.parent / f"{ref}.yaml",
                 project_root() / "configs" / "sites" / f"{ref}.yaml"):
        if cand.exists():
            return cand
    raise ScenarioError(f"{cfg_path.name}: site '{ref}' not found (looked for configs/sites/{ref}.yaml)")


def region_from_dict(d: Any, where: str) -> SearchRegion:
    s = _section(d, where, set(), {"name", "rectangle", "polygons"})
    if ("rectangle" in s) == ("polygons" in s):
        raise ScenarioError(f"{where}: give exactly one of 'rectangle' or 'polygons'")
    name = str(s.get("name", "search area"))
    try:
        if "rectangle" in s:
            r = _section(s["rectangle"], f"{where}.rectangle", {"center_m", "size_m"})
            return SearchRegion.rectangle(_en(r["center_m"], f"{where}.rectangle.center_m"),
                                          _pair(r["size_m"], f"{where}.rectangle.size_m"), name)
        polys = s["polygons"]
        if not isinstance(polys, list) or not polys:
            raise ScenarioError(f"{where}.polygons: expected a non-empty list of polygons")
        return SearchRegion([np.asarray(p, float) for p in polys], name)
    except ScenarioError:
        raise
    except (ValueError, TypeError) as e:
        raise ScenarioError(f"{where}: {e}") from e


def load_scenario(path: str | Path) -> Scenario:
    path = Path(path)
    doc = read_yaml(path)
    _section(doc, path.name, {"name", "site", "search"})
    site_path = _resolve_site(str(doc["site"]), path)
    site = load_site(site_path)
    region = region_from_dict(doc["search"], f"{path.name}:search")
    e0, e1, n0, n1 = region.bounds
    m = min(site.map.margin_to_edge(e0, n0), site.map.margin_to_edge(e1, n1))
    if m < site.min_edge_margin_m:
        raise ScenarioError(f"{path.name}:search extends to within {m:.0f} m of the map edge; "
                            f"need >= {site.min_edge_margin_m:.0f} m")
    return Scenario(str(doc["name"]), site, region)
