"""Search region: one or more ENU polygons (user-drawn later; a square for now)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from matplotlib.path import Path as MplPath
from numpy.typing import ArrayLike, NDArray


def _signed_area(v: NDArray) -> float:
    x, y = v[:, 0], v[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


@dataclass
class SearchRegion:
    """Union of simple polygons, each an (N, 2) array of [east, north] vertices."""

    polygons: list[NDArray[np.float64]]
    name: str = "search area"
    _paths: list[MplPath] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        polys = []
        for i, p in enumerate(self.polygons):
            v = np.asarray(p, float)
            if v.ndim != 2 or v.shape[1] != 2 or len(v) < 3:
                raise ValueError(f"search polygon {i}: need >= 3 [east, north] vertices, got shape {v.shape}")
            if np.allclose(v[0], v[-1]):
                v = v[:-1]
            if abs(_signed_area(v)) < 1.0:
                raise ValueError(f"search polygon {i}: zero area (collinear or repeated vertices)")
            polys.append(v)
        self.polygons = polys
        self._paths = [MplPath(np.vstack([v, v[:1]]), closed=True) for v in polys]

    @classmethod
    def rectangle(cls, center: ArrayLike, size: ArrayLike, name: str = "search area") -> "SearchRegion":
        (ce, cn), (we, wn) = np.asarray(center, float), np.asarray(size, float)
        he, hn = we / 2, wn / 2
        return cls([np.array([[ce - he, cn - hn], [ce + he, cn - hn], [ce + he, cn + hn], [ce - he, cn + hn]])], name)

    @property
    def area_m2(self) -> float:
        return float(sum(abs(_signed_area(v)) for v in self.polygons))

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        allv = np.vstack(self.polygons)
        return (allv[:, 0].min(), allv[:, 0].max(), allv[:, 1].min(), allv[:, 1].max())

    def contains(self, east: ArrayLike, north: ArrayLike) -> NDArray[np.bool_]:
        e, n = np.broadcast_arrays(np.asarray(east, float), np.asarray(north, float))
        pts = np.column_stack([e.ravel(), n.ravel()])
        inside = np.zeros(len(pts), bool)
        for p in self._paths:
            inside |= p.contains_points(pts)
        return inside.reshape(e.shape)
