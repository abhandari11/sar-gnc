"""Regular ENU height field with elevation, gradient, slope, normal and AGL queries."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from sargnc.terrain import _kernels as K
from sargnc.terrain.frames import LocalENU

Method = Literal["bilinear", "bicubic"]
_METHODS = {"bilinear": K.BILINEAR, "bicubic": K.BICUBIC}


@dataclass
class TerrainGrid:
    """Height field z[i, j] at east = x0 + j*d, north = y0 + i*d (metres, ENU)."""

    z: NDArray[np.float64]
    x0: float
    y0: float
    d: float
    frame: LocalENU | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.z = np.ascontiguousarray(self.z, dtype=np.float64)
        if self.z.ndim != 2 or min(self.z.shape) < 2:
            raise ValueError(f"terrain z must be 2-D with >= 2 samples per axis, got {self.z.shape}")
        if not np.all(np.isfinite(self.z)):
            raise ValueError("terrain z contains NaN/inf")

    @property
    def shape(self) -> tuple[int, int]:
        return self.z.shape  # type: ignore[return-value]

    @property
    def x(self) -> NDArray[np.float64]:
        return self.x0 + self.d * np.arange(self.shape[1])

    @property
    def y(self) -> NDArray[np.float64]:
        return self.y0 + self.d * np.arange(self.shape[0])

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(e_min, e_max, n_min, n_max)."""
        ny, nx = self.shape
        return (self.x0, self.x0 + (nx - 1) * self.d, self.y0, self.y0 + (ny - 1) * self.d)

    def _query(self, x: ArrayLike, y: ArrayLike, method: Method) -> tuple[NDArray, NDArray, NDArray]:
        xb, yb = np.broadcast_arrays(np.asarray(x, float), np.asarray(y, float))
        fn = K.sample if xb.size >= 256 else K.sample_serial
        h, gx, gy = fn(self.z, self.x0, self.y0, self.d, xb.ravel(), yb.ravel(), _METHODS[method])
        return h.reshape(xb.shape), gx.reshape(xb.shape), gy.reshape(xb.shape)

    def elevation(self, x: ArrayLike, y: ArrayLike, method: Method = "bilinear") -> NDArray:
        """Terrain height [m]; NaN outside the grid."""
        return self._query(x, y, method)[0]

    def gradient(self, x: ArrayLike, y: ArrayLike, method: Method = "bicubic") -> tuple[NDArray, NDArray]:
        """(dz/de, dz/dn), dimensionless."""
        _, gx, gy = self._query(x, y, method)
        return gx, gy

    def slope(self, x: ArrayLike, y: ArrayLike, method: Method = "bicubic") -> NDArray:
        """Slope angle [rad]."""
        gx, gy = self.gradient(x, y, method)
        return np.arctan(np.hypot(gx, gy))

    def aspect(self, x: ArrayLike, y: ArrayLike, method: Method = "bicubic") -> NDArray:
        """Downslope azimuth [rad], clockwise from north."""
        gx, gy = self.gradient(x, y, method)
        return np.mod(np.arctan2(-gx, -gy), 2 * np.pi)

    def normal(self, x: ArrayLike, y: ArrayLike, method: Method = "bicubic") -> NDArray:
        """Upward unit surface normal, shape (..., 3)."""
        gx, gy = self.gradient(x, y, method)
        n = np.stack([-gx, -gy, np.ones_like(gx)], axis=-1)
        return n / np.linalg.norm(n, axis=-1, keepdims=True)

    def agl(self, points: ArrayLike, method: Method = "bilinear") -> NDArray:
        """Height above ground of ENU points with shape (..., 3)."""
        p = np.asarray(points, float)
        return p[..., 2] - self.elevation(p[..., 0], p[..., 1], method)

    def grid_slope(self) -> NDArray:
        """Slope angle [rad] at every grid node (central differences)."""
        gy, gx = np.gradient(self.z, self.d)
        return np.arctan(np.hypot(gx, gy))

    def decimated(self, step: int) -> "TerrainGrid":
        return TerrainGrid(self.z[::step, ::step], self.x0, self.y0, self.d * step, self.frame, dict(self.meta))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        f = self.frame
        np.savez_compressed(
            path,
            z=self.z.astype(np.float32),
            geom=np.array([self.x0, self.y0, self.d]),
            frame=np.array([f.lat0, f.lon0, f.h0] if f else [np.nan] * 3),
            meta=np.array(json.dumps(self.meta)),
        )

    @classmethod
    def load(cls, path: Path) -> "TerrainGrid":
        with np.load(path) as a:
            x0, y0, d = a["geom"]
            fr = a["frame"]
            frame = None if np.isnan(fr[0]) else LocalENU(*map(float, fr))
            return cls(a["z"].astype(np.float64), float(x0), float(y0), float(d), frame, json.loads(str(a["meta"])))
