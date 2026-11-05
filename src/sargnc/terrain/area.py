"""Search-area specification: centre, size, buffer and working resolution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AreaSpec:
    """Rectangular search area aligned with local East/North, plus a turning buffer.

    The DEM domain is the search rectangle grown by `buffer_m` on every side.
    """

    name: str
    center_lat: float
    center_lon: float
    size_e_m: float = 1400.0
    size_n_m: float = 1400.0
    buffer_m: float = 1300.0
    resolution_m: float = 5.0
    dem_source: str = "swissalti3d"

    def __post_init__(self) -> None:
        if not (-90 < self.center_lat < 90 and -180 <= self.center_lon <= 180):
            raise ValueError(f"area '{self.name}': centre ({self.center_lat}, {self.center_lon}) is not a valid lat/lon")
        if self.size_e_m <= 0 or self.size_n_m <= 0:
            raise ValueError(f"area '{self.name}': size must be positive, got {self.size_e_m} x {self.size_n_m} m")
        if self.buffer_m < 1000.0:
            raise ValueError(f"area '{self.name}': buffer_m={self.buffer_m} < 1000 m minimum turning buffer")
        if not 0.5 <= self.resolution_m <= 30.0:
            raise ValueError(f"area '{self.name}': resolution_m={self.resolution_m} outside [0.5, 30] m")

    @property
    def search_bounds(self) -> tuple[float, float, float, float]:
        """(e_min, e_max, n_min, n_max) of the search rectangle in ENU metres."""
        he, hn = self.size_e_m / 2, self.size_n_m / 2
        return (-he, he, -hn, hn)

    @property
    def domain_bounds(self) -> tuple[float, float, float, float]:
        e0, e1, n0, n1 = self.search_bounds
        b = self.buffer_m
        return (e0 - b, e1 + b, n0 - b, n1 + b)

    def cache_key(self) -> str:
        d = asdict(self)
        d.pop("name")
        return hashlib.sha1(json.dumps(d, sort_keys=True).encode()).hexdigest()[:10]
