"""Vector-field path following (Beard & McLain ch. 10): straight lines and orbits, NED."""

from __future__ import annotations

import math

import numpy as np

from sargnc.aircraft.rotations import wrap_pi


def _near(angle: float, ref: float) -> float:
    """Shift `angle` by multiples of 2*pi to lie within pi of `ref`."""
    return ref + wrap_pi(angle - ref)


def follow_line(p_ne: np.ndarray, origin_ne: np.ndarray, direction_ne: np.ndarray, chi: float,
                chi_inf: float = math.radians(60), k: float = 0.015) -> float:
    """Course command to converge onto the line through origin along direction."""
    chi_q = _near(math.atan2(direction_ne[1], direction_ne[0]), chi)
    d = p_ne - origin_ne
    e_py = -math.sin(chi_q) * d[0] + math.cos(chi_q) * d[1]
    return chi_q - chi_inf * (2 / math.pi) * math.atan(k * e_py)


def follow_orbit(p_ne: np.ndarray, center_ne: np.ndarray, radius: float, clockwise: bool, chi: float,
                 k: float = 2.0) -> tuple[float, float]:
    """Course command and distance-to-centre for an orbit; clockwise as seen from above."""
    lam = 1.0 if clockwise else -1.0
    d = p_ne - center_ne
    dist = float(np.hypot(*d))
    phi = _near(math.atan2(d[1], d[0]), chi)
    return phi + lam * (math.pi / 2 + math.atan(k * (dist - radius) / radius)), dist
