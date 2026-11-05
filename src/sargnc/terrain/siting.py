"""Find level, dry ground near a requested point (e.g. a launch/recovery pad)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from scipy import ndimage

from sargnc.terrain.grid import TerrainGrid


def water_mask(t: TerrainGrid, slope_deg: float = 0.25, min_area_m2: float = 5000.0) -> np.ndarray:
    """Grid-node mask of lakes: connected dead-flat regions larger than min_area_m2."""
    flat = ndimage.binary_opening(np.degrees(t.grid_slope()) < slope_deg, iterations=1)
    lab, n = ndimage.label(flat)
    if n == 0:
        return flat
    sizes = ndimage.sum(flat, lab, index=np.arange(1, n + 1)) * t.d**2
    keep = np.concatenate([[False], sizes >= min_area_m2])
    return keep[lab]


@dataclass(frozen=True)
class PadSite:
    east: float
    north: float
    elevation: float
    max_slope_deg: float
    moved_m: float


def find_level_site(
    t: TerrainGrid,
    east: float,
    north: float,
    search_radius_m: float = 300.0,
    pad_radius_m: float = 30.0,
    max_slope_deg: float = 8.0,
    water_slope_deg: float = 0.25,
    step_m: float = 5.0,
) -> PadSite:
    """Nearest point to (east, north) whose pad disc has slope <= max_slope_deg and is not water.

    Water is detected as a pad that is mostly dead flat (slope < water_slope_deg), which is how
    lakes appear in the DEM.
    """
    ring = np.arange(-pad_radius_m, pad_radius_m + 1e-9, step_m)
    de, dn = np.meshgrid(ring, ring)
    keep = np.hypot(de, dn) <= pad_radius_m
    de, dn = de[keep], dn[keep]

    c = np.arange(-search_radius_m, search_radius_m + 1e-9, step_m)
    ce, cn = np.meshgrid(c, c)
    order = np.argsort(np.hypot(ce, cn), axis=None)
    for k in order:
        e, n = east + ce.flat[k], north + cn.flat[k]
        if np.hypot(ce.flat[k], cn.flat[k]) > search_radius_m:
            break
        s = np.degrees(t.slope(e + de, n + dn))
        if np.any(np.isnan(s)):
            continue
        if s.max() <= max_slope_deg and np.mean(s < water_slope_deg) < 0.5:
            return PadSite(float(e), float(n), float(t.elevation(e, n)), float(s.max()),
                           float(np.hypot(e - east, n - north)))
    raise ValueError(f"no level dry pad within {search_radius_m} m of ({east}, {north})")
