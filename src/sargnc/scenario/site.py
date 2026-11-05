"""Site: the fixed terrain map plus the base camp the UAV operates from."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from sargnc.terrain.mapspec import MapSpec


@dataclass(frozen=True)
class Loiter:
    """Circular loiter (climb-out / return holding pattern), ENU metres."""

    east: float
    north: float
    radius_m: float
    height_agl_m: float
    clockwise: bool = False


@dataclass(frozen=True)
class Base:
    """Base camp: launch and recovery point for all operations."""

    name: str
    east: float
    north: float
    launch_heading_deg: float  # clockwise from north
    home_loiter: Loiter

    @property
    def en(self) -> np.ndarray:
        return np.array([self.east, self.north])


@dataclass(frozen=True)
class Site:
    name: str
    map: MapSpec
    base: Base
    min_edge_margin_m: float = 1000.0
