"""Build a cached ENU terrain grid for a MapSpec from a DEM source."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge
from scipy.ndimage import gaussian_filter, map_coordinates

from sargnc.paths import data_dir
from sargnc.terrain.mapspec import MapSpec
from sargnc.terrain.frames import LocalENU
from sargnc.terrain.grid import TerrainGrid
from sargnc.terrain.sources import get_source

log = logging.getLogger(__name__)


def terrain_cache_path(spec: MapSpec) -> Path:
    return data_dir() / "terrain" / f"{spec.name}_{spec.cache_key()}.npz"


def load_terrain(spec: MapSpec, rebuild: bool = False) -> TerrainGrid:
    """Return the cached ENU terrain for `spec`, building it on first use."""
    path = terrain_cache_path(spec)
    if path.exists() and not rebuild:
        return TerrainGrid.load(path)
    grid = build_terrain(spec)
    grid.save(path)
    log.info("cached terrain -> %s", path)
    return grid


def _enu_axes(spec: MapSpec) -> tuple[np.ndarray, np.ndarray]:
    e0, e1, n0, n1 = spec.bounds
    d = spec.resolution_m
    return e0 + d * np.arange(int(round((e1 - e0) / d)) + 1), n0 + d * np.arange(int(round((n1 - n0) / d)) + 1)


def build_terrain(spec: MapSpec) -> TerrainGrid:
    """Download tiles, mosaic, low-pass, and resample onto a local ENU grid.

    ENU origin: map origin at height 0 of the DEM vertical datum, so z reads as
    altitude above that datum with earth curvature included.
    """
    src = get_source(spec.dem_source)
    frame = LocalENU(spec.origin_lat, spec.origin_lon, 0.0)
    xs, ys = _enu_axes(spec)
    ee, nn = np.meshgrid(xs, ys)

    margin = 200.0
    e0, e1, n0, n1 = spec.bounds
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

    ratio = spec.resolution_m / abs(transform.a)
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
        raise RuntimeError(f"DEM has {int(hole.sum())} nodata cells inside the map '{spec.name}'")

    meta = {
        "map": spec.name,
        "source": src.name,
        "source_crs": crs,
        "native_resolution_m": abs(transform.a),
        "tiles": sorted(p.name for p in tiles),
    }
    return TerrainGrid(u, float(xs[0]), float(ys[0]), spec.resolution_m, frame, meta)
