"""Analytic test terrains (plane, cone, Gaussian hill) with exact heights and gradients."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.typing import NDArray

from sargnc.terrain.grid import TerrainGrid

Field = Callable[[NDArray, NDArray], tuple[NDArray, NDArray, NDArray]]


@dataclass(frozen=True)
class Analytic:
    """An analytic surface: f(x, y) -> (z, dz/dx, dz/dy)."""

    f: Field

    def grid(self, half_extent: float, d: float) -> TerrainGrid:
        n = int(round(2 * half_extent / d)) + 1
        ax = -half_extent + d * np.arange(n)
        xx, yy = np.meshgrid(ax, ax)
        return TerrainGrid(self.f(xx, yy)[0], -half_extent, -half_extent, d)


def plane(z0: float = 100.0, sx: float = 0.2, sy: float = -0.1) -> Analytic:
    return Analytic(lambda x, y: (z0 + sx * x + sy * y, np.full_like(x, sx), np.full_like(y, sy)))


def cone(apex: float = 500.0, slope: float = 0.6, base: float = 0.0, cx: float = 0.0, cy: float = 0.0) -> Analytic:
    """Circular cone z = max(base, apex - slope*r)."""

    def f(x: NDArray, y: NDArray):
        dx, dy = x - cx, y - cy
        r = np.hypot(dx, dy)
        z = np.maximum(base, apex - slope * r)
        on = (z > base) & (r > 0)
        rs = np.where(r > 0, r, 1.0)
        return z, np.where(on, -slope * dx / rs, 0.0), np.where(on, -slope * dy / rs, 0.0)

    return Analytic(f)


def gaussian(amp: float = 300.0, sigma: float = 200.0, base: float = 1000.0, cx: float = 0.0, cy: float = 0.0) -> Analytic:
    def f(x: NDArray, y: NDArray):
        dx, dy = x - cx, y - cy
        g = amp * np.exp(-(dx**2 + dy**2) / (2 * sigma**2))
        return base + g, -g * dx / sigma**2, -g * dy / sigma**2

    return Analytic(f)
