"""Map specification: fixed ENU origin, rectangular extent and working resolution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class MapSpec:
    """Terrain map for a site. Extent is in ENU metres relative to the origin."""

    name: str
    origin_lat: float
    origin_lon: float
    east_m: tuple[float, float]
    north_m: tuple[float, float]
    resolution_m: float = 5.0
    dem_source: str = "swissalti3d"

    def __post_init__(self) -> None:
        if not (-90 < self.origin_lat < 90 and -180 <= self.origin_lon <= 180):
            raise ValueError(f"map '{self.name}': origin ({self.origin_lat}, {self.origin_lon}) is not a valid lat/lon")
        for axis, (lo, hi) in (("east", self.east_m), ("north", self.north_m)):
            if not hi > lo:
                raise ValueError(f"map '{self.name}': {axis} extent must be [min, max] with max > min, got {[lo, hi]}")
        if not 0.5 <= self.resolution_m <= 30.0:
            raise ValueError(f"map '{self.name}': resolution_m={self.resolution_m} outside [0.5, 30] m")

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(e_min, e_max, n_min, n_max) in ENU metres."""
        return (*self.east_m, *self.north_m)

    def margin_to_edge(self, e: float, n: float) -> float:
        """Distance from (e, n) to the nearest map edge (negative if outside)."""
        e0, e1, n0, n1 = self.bounds
        return min(e - e0, e1 - e, n - n0, n1 - n)

    def cache_key(self) -> str:
        d = asdict(self)
        d.pop("name")
        return hashlib.sha1(json.dumps(d, sort_keys=True).encode()).hexdigest()[:10]
