"""Wind model interface and a steady (uniform, constant) wind."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class WindModel(Protocol):
    def __call__(self, t: float, p_ned: NDArray[np.float64]) -> NDArray[np.float64]:
        """Wind velocity (NED, m/s) at time t and NED position p."""
        ...


@dataclass(frozen=True)
class SteadyWind:
    """Uniform wind; `from_deg` is the meteorological direction the wind blows FROM (clockwise from north)."""

    speed_mps: float = 0.0
    from_deg: float = 0.0

    @property
    def ned(self) -> NDArray[np.float64]:
        a = math.radians(self.from_deg)
        return -self.speed_mps * np.array([math.cos(a), math.sin(a), 0.0])

    def __call__(self, t: float, p_ned: NDArray[np.float64]) -> NDArray[np.float64]:
        return self.ned
