"""Vectorised ray-terrain intersection and line of sight."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from sargnc.terrain import _kernels as K
from sargnc.terrain.grid import TerrainGrid


def ray_intersect(
    terrain: TerrainGrid,
    origins: ArrayLike,
    directions: ArrayLike,
    max_range: ArrayLike = np.inf,
) -> tuple[NDArray, NDArray]:
    """First intersection of rays with the bilinear terrain surface.

    origins, directions: (..., 3) ENU; directions need not be normalised.
    Returns (range [m], hit point (..., 3)); NaN where the ray leaves the grid or
    exceeds max_range without hitting. An origin below the surface returns range 0.
    """
    o = np.asarray(origins, float)
    v = np.asarray(directions, float)
    o, v = np.broadcast_arrays(o, v)
    shape = o.shape[:-1]
    norm = np.linalg.norm(v, axis=-1)
    if np.any(norm == 0):
        raise ValueError("ray direction must be non-zero")
    u = v / norm[..., None]
    tmax = np.broadcast_to(np.asarray(max_range, float), shape)
    t = K.ray_cast(
        terrain.z, terrain.x0, terrain.y0, terrain.d,
        np.ascontiguousarray(o.reshape(-1, 3)),
        np.ascontiguousarray(u.reshape(-1, 3)),
        np.ascontiguousarray(tmax.reshape(-1)),
    ).reshape(shape)
    return t, o + u * t[..., None]


def line_of_sight(terrain: TerrainGrid, p0: ArrayLike, p1: ArrayLike, tol: float = 0.5) -> NDArray[np.bool_]:
    """True where the segment p0->p1 (..., 3) clears the terrain.

    A hit within `tol` metres of p1 is ignored so that targets lying on the surface
    are visible. Segment parts outside the grid are treated as unobstructed.
    """
    a, b = np.broadcast_arrays(np.asarray(p0, float), np.asarray(p1, float))
    seg = b - a
    length = np.linalg.norm(seg, axis=-1)
    same = length == 0
    seg = np.where(same[..., None], np.array([0.0, 0.0, 1.0]), seg)
    t, _ = ray_intersect(terrain, a, seg, np.maximum(length - tol, 0.0))
    vis = np.isnan(t)
    if np.any(same):
        vis = np.where(same, terrain.agl(a) >= 0, vis)
    return vis
