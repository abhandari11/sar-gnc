"""Local East-North-Up frame tied to a geodetic origin (WGS84)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from numpy.typing import ArrayLike, NDArray
from pyproj import Transformer

_WGS84_GEOD_3D = "EPSG:4979"
_WGS84_ECEF = "EPSG:4978"


@lru_cache(maxsize=None)
def _transformer(src: str, dst: str) -> Transformer:
    return Transformer.from_crs(src, dst, always_xy=True)


@dataclass(frozen=True)
class LocalENU:
    """ENU tangent frame at (lat0, lon0, h0). Heights are metres above the DEM vertical datum."""

    lat0: float
    lon0: float
    h0: float = 0.0

    @property
    def _rot(self) -> NDArray[np.float64]:
        lat, lon = np.radians(self.lat0), np.radians(self.lon0)
        sl, cl, so, co = np.sin(lat), np.cos(lat), np.sin(lon), np.cos(lon)
        return np.array([[-so, co, 0.0], [-sl * co, -sl * so, cl], [cl * co, cl * so, sl]])

    @property
    def _ecef0(self) -> NDArray[np.float64]:
        return np.array(_transformer(_WGS84_GEOD_3D, _WGS84_ECEF).transform(self.lon0, self.lat0, self.h0))

    def geodetic_to_enu(self, lat: ArrayLike, lon: ArrayLike, h: ArrayLike) -> tuple[NDArray, NDArray, NDArray]:
        x, y, z = _transformer(_WGS84_GEOD_3D, _WGS84_ECEF).transform(
            np.asarray(lon, float), np.asarray(lat, float), np.asarray(h, float)
        )
        d = np.stack(np.broadcast_arrays(x, y, z)) - self._ecef0.reshape(3, *([1] * np.ndim(x)))
        enu = np.tensordot(self._rot, d, axes=1)
        return enu[0], enu[1], enu[2]

    def enu_to_geodetic(self, e: ArrayLike, n: ArrayLike, u: ArrayLike) -> tuple[NDArray, NDArray, NDArray]:
        enu = np.stack(np.broadcast_arrays(np.asarray(e, float), np.asarray(n, float), np.asarray(u, float)))
        d = np.tensordot(self._rot.T, enu, axes=1) + self._ecef0.reshape(3, *([1] * (enu.ndim - 1)))
        lon, lat, h = _transformer(_WGS84_ECEF, _WGS84_GEOD_3D).transform(d[0], d[1], d[2])
        return np.asarray(lat), np.asarray(lon), np.asarray(h)

    def crs_to_enu(self, x: ArrayLike, y: ArrayLike, h: ArrayLike, crs: str) -> tuple[NDArray, NDArray, NDArray]:
        """Projected/geographic (x, y) in `crs` plus height -> ENU."""
        lon, lat = _transformer(crs, "EPSG:4326").transform(np.asarray(x, float), np.asarray(y, float))
        return self.geodetic_to_enu(lat, lon, h)

    def enu_to_crs(self, e: ArrayLike, n: ArrayLike, u: ArrayLike, crs: str) -> tuple[NDArray, NDArray, NDArray]:
        lat, lon, h = self.enu_to_geodetic(e, n, u)
        x, y = _transformer("EPSG:4326", crs).transform(lon, lat)
        return np.asarray(x), np.asarray(y), h
