"""Euler (3-2-1) / quaternion helpers and ENU <-> NED conversion."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray


def euler_to_quat(phi: float, theta: float, psi: float) -> NDArray[np.float64]:
    cp, sp = math.cos(phi / 2), math.sin(phi / 2)
    ct, st = math.cos(theta / 2), math.sin(theta / 2)
    cs, ss = math.cos(psi / 2), math.sin(psi / 2)
    return np.array([
        cs * ct * cp + ss * st * sp,
        cs * ct * sp - ss * st * cp,
        cs * st * cp + ss * ct * sp,
        ss * ct * cp - cs * st * sp,
    ])


def quat_to_euler(q: ArrayLike) -> tuple[float, float, float]:
    e0, e1, e2, e3 = (float(v) for v in q)
    phi = math.atan2(2 * (e0 * e1 + e2 * e3), e0**2 + e3**2 - e1**2 - e2**2)
    theta = math.asin(max(-1.0, min(1.0, 2 * (e0 * e2 - e1 * e3))))
    psi = math.atan2(2 * (e0 * e3 + e1 * e2), e0**2 + e1**2 - e2**2 - e3**2)
    return phi, theta, psi


def enu_to_ned(p: ArrayLike) -> NDArray[np.float64]:
    p = np.asarray(p, float)
    return np.stack([p[..., 1], p[..., 0], -p[..., 2]], axis=-1)


def ned_to_enu(p: ArrayLike) -> NDArray[np.float64]:
    p = np.asarray(p, float)
    return np.stack([p[..., 1], p[..., 0], -p[..., 2]], axis=-1)


def wrap_pi(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi
