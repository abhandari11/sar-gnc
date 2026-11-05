"""Build a cached ENU terrain grid for an AreaSpec from a DEM source."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge
from scipy.ndimage import gaussian_filter, map_coordinates

from sargnc.paths import data_dir
from sargnc.terrain.area import AreaSpec
from sargnc.terrain.frames import LocalENU
from sargnc.terrain.grid import TerrainGrid
from sargnc.terrain.sources import get_source

log = logging.getLogger(__name__)


def terrain_cache_path(area: AreaSpec) -> Path:
    return data_dir() / "terrain" / f"{area.name}_{area.cache_key()}.npz"


def load_terrain(area: AreaSpec, rebuild: bool = False) -> TerrainGrid:
    """Return the cached ENU terrain for `area`, building it on first use."""
    path = terrain_cache_path(area)
    if path.exists() and not rebuild:
        return TerrainGrid.load(path)
    grid = build_terrain(area)
    grid.save(path)
    log.info("cached terrain -> %s", path)
    return grid


def _enu_axes(area: AreaSpec) -> tuple[np.ndarray, np.ndarray]:
    e0, e1, n0, n1 = area.domain_bounds
    d = area.resolution_m
    return e0 + d * np.arange(int(round((e1 - e0) / d)) + 1), n0 + d * np.arange(int(round((n1 - n0) / d)) + 1)


def build_terrain(area: AreaSpec) -> TerrainGrid:
    """Download tiles, mosaic, low-pass, and resample onto a local ENU grid.

    ENU origin: search-area centre at height 0 of the DEM vertical datum, so z reads as
    altitude above that datum with earth curvature included.
    """
    src = get_source(area.dem_source)
    frame = LocalENU(area.center_lat, area.center_lon, 0.0)
    xs, ys = _enu_axes(area)
    ee, nn = np.meshgrid(xs, ys)

    margin = 200.0
    e0, e1, n0, n1 = area.domain_bounds
    ce = np.array([e0 - margin, e1 + margin, e1 + margin, e0 - margin])
    cn = np.array([n0 - margin, n0 - margin, n1 + margin, n1 + margin])
    lat, lon, _ = frame.enu_to_geodetic(ce, cn, np.zeros(4))
    tiles = src.fetch(lon.min(), lat.min(), lon.max(), lat.max(), data_dir() / "raw" / src.name)
    log.info("%s: %d tiles", src.name, len(tiles))

    datasets = [rasterio.open(p) for p in tiles]
    try:
        nodata = datasets[0].nodata
        mosaic, transform = merge(datasets, nodata=nodata if nodata is not None else -9999.0)
        crs = datasets[0].crs.to_string()
    finally:
        for ds in datasets:
            ds.close()
    dem = mosaic[0].astype(np.float64)
    bad = ~np.isfinite(dem) | (dem == (nodata if nodata is not None else -9999.0))

    ratio = area.resolution_m / abs(transform.a)
    if ratio > 1.0:
        filled = np.where(bad, np.nanmedian(np.where(bad, np.nan, dem)), dem)
        dem = gaussian_filter(filled, sigma=0.5 * ratio)

    inv = ~transform
    u = np.full_like(ee, float(np.median(dem[~bad])))
    for _ in range(2):  # fixed-point on height so the vertical through each node is exact
        px, py, _ = frame.enu_to_crs(ee, nn, u, crs)
        col, row = inv * (px, py)
        h = map_coordinates(dem, [row - 0.5, col - 0.5], order=1, mode="nearest")
        hole = map_coordinates(bad.astype(np.float32), [row - 0.5, col - 0.5], order=1, mode="nearest") > 0
        _, _, u = frame.crs_to_enu(px, py, h, crs)
    if np.any(hole):
        raise RuntimeError(f"DEM has {int(hole.sum())} nodata cells inside the domain of '{area.name}'")

    meta = {
        "area": area.name,
        "source": src.name,
        "source_crs": crs,
        "native_resolution_m": abs(transform.a),
        "tiles": sorted(p.name for p in tiles),
        "search_bounds": list(area.search_bounds),
    }
    return TerrainGrid(u, float(xs[0]), float(ys[0]), area.resolution_m, frame, meta)
