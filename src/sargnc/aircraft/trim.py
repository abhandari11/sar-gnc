"""Trim (steady straight / climbing / turning flight) and Euler-state linearisation."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares

from sargnc.aircraft import _core as C
from sargnc.aircraft.model import Aircraft
from sargnc.aircraft.rotations import euler_to_quat, quat_to_euler


@dataclass(frozen=True)
class Trim:
    Va: float
    h: float
    gamma: float          # flight-path angle [rad]
    radius: float         # turn radius [m], inf = straight
    alpha: float
    beta: float
    phi: float
    theta: float
    de: float
    da: float
    dt: float
    x: NDArray[np.float64]
    u: NDArray[np.float64]
    residual: float
    outputs: dict

    @property
    def ok(self) -> bool:
        return self.residual < 1e-6 and 0.0 <= self.dt <= 1.0


def _state(Va: float, h: float, alpha: float, beta: float, phi: float, theta: float, psi_dot: float) -> NDArray:
    x = np.zeros(C.NX)
    x[2] = -h
    x[3] = Va * math.cos(alpha) * math.cos(beta)
    x[4] = Va * math.sin(beta)
    x[5] = Va * math.sin(alpha) * math.cos(beta)
    x[6:10] = euler_to_quat(phi, theta, 0.0)
    x[10] = -psi_dot * math.sin(theta)
    x[11] = psi_dot * math.sin(phi) * math.cos(theta)
    x[12] = psi_dot * math.cos(phi) * math.cos(theta)
    return x


def trim(ac: Aircraft, Va: float, h: float, gamma: float = 0.0, radius: float = math.inf,
         throttle: float | None = None) -> Trim:
    """Solve for steady flight. With `throttle` given, gamma becomes the unknown (straight flight only)."""
    psi_dot = 0.0 if math.isinf(radius) else Va * math.cos(gamma) / radius

    def unpack(z):
        if throttle is None:
            a, b, ph, th, de, da, dt = z
        else:
            a, b, ph, th, de, da = z
            dt = throttle
        return a, b, ph, th, de, da, dt

    def res(z):
        a, b, ph, th, de, da, dt = unpack(z)
        x = _state(Va, h, a, b, ph, th, psi_dot)
        u = np.array([de, da, dt])
        xd = C.deriv(x, u, np.zeros(3), ac.P)
        r = [xd[3], xd[4], xd[5], xd[10], xd[11], xd[12]]
        if throttle is None:
            r.append((-xd[2] - Va * math.sin(gamma)) / Va)
        return np.array(r)

    z0 = [0.05, 0.0, math.atan(psi_dot * Va / C.G), 0.05 + gamma, 0.0, 0.0, 0.5]
    lo = [-0.3, -0.3, -1.2, -1.0, -0.6, -0.6, 0.0]
    hi = [0.4, 0.3, 1.2, 1.0, 0.6, 0.6, 1.0]
    if throttle is not None:
        z0, lo, hi = z0[:6], lo[:6], hi[:6]
    sol = least_squares(res, z0, bounds=(lo, hi), xtol=1e-12, ftol=1e-12, gtol=1e-12)
    a, b, ph, th, de, da, dt = unpack(sol.x)
    x = _state(Va, h, a, b, ph, th, psi_dot)
    u = np.array([de, da, dt])
    xd = C.deriv(x, u, np.zeros(3), ac.P)
    g = math.asin(max(-1.0, min(1.0, -xd[2] / Va)))
    return Trim(Va, h, g, radius, a, b, ph, th, de, da, dt, x, u, float(np.sum(sol.fun**2)), ac.outputs(x, u))


# --- linearisation on a 12-state Euler representation ---------------------------------
EULER_STATES = ("pn", "pe", "pd", "u", "v", "w", "phi", "theta", "psi", "p", "q", "r")


def _f_euler(ac: Aircraft, x12: NDArray, u: NDArray) -> NDArray:
    x = np.zeros(C.NX)
    x[0:6] = x12[0:6]
    x[6:10] = euler_to_quat(*x12[6:9])
    x[10:13] = x12[9:12]
    xd = C.deriv(x, u, np.zeros(3), ac.P)
    ph, th, _ = x12[6:9]
    p, q, r = x12[9:12]
    out = np.empty(12)
    out[0:6] = xd[0:6]
    out[6] = p + (q * math.sin(ph) + r * math.cos(ph)) * math.tan(th)
    out[7] = q * math.cos(ph) - r * math.sin(ph)
    out[8] = (q * math.sin(ph) + r * math.cos(ph)) / math.cos(th)
    out[9:12] = xd[10:13]
    return out


def linearize(ac: Aircraft, t: Trim, eps: float = 1e-6) -> tuple[NDArray, NDArray]:
    """A (12x12), B (12x3) about a trim point, by central differences."""
    x12 = np.concatenate([t.x[0:6], quat_to_euler(t.x[6:10]), t.x[10:13]])
    A = np.zeros((12, 12))
    B = np.zeros((12, 3))
    for i in range(12):
        d = np.zeros(12)
        d[i] = eps
        A[:, i] = (_f_euler(ac, x12 + d, t.u) - _f_euler(ac, x12 - d, t.u)) / (2 * eps)
    for i in range(3):
        d = np.zeros(3)
        d[i] = eps
        B[:, i] = (_f_euler(ac, x12, t.u + d) - _f_euler(ac, x12, t.u - d)) / (2 * eps)
    return A, B


LON = [3, 5, 10, 7, 2]   # u, w, q, theta, pd
LAT = [4, 9, 11, 6, 8]   # v, p, r, phi, psi


@dataclass(frozen=True)
class Mode:
    name: str
    eig: complex
    wn: float
    zeta: float
    time_const: float     # s; time to half (stable) / double (unstable) amplitude for real modes


def _mode(name: str, lam: complex) -> Mode:
    wn = abs(lam)
    zeta = -lam.real / wn if wn > 0 else 1.0
    tc = math.log(2) / abs(lam.real) if lam.real != 0 else math.inf
    return Mode(name, complex(lam), wn, zeta, tc)


def dynamic_modes(A: NDArray) -> list[Mode]:
    """Classify longitudinal (short period, phugoid) and lateral (roll, dutch roll, spiral) modes."""
    lon = np.linalg.eigvals(A[np.ix_(LON[:4], LON[:4])])
    lat = np.linalg.eigvals(A[np.ix_(LAT[:4], LAT[:4])])
    modes = []
    osc = sorted([l for l in lon if l.imag > 1e-6], key=abs)
    real_lon = sorted([l for l in lon if abs(l.imag) <= 1e-6], key=abs)
    if len(osc) == 2:
        modes += [_mode("phugoid", osc[0]), _mode("short period", osc[1])]
    else:
        for l in osc + real_lon:
            modes.append(_mode("longitudinal", l))
    dr = [l for l in lat if l.imag > 1e-6]
    real_lat = sorted([l for l in lat if abs(l.imag) <= 1e-6], key=lambda l: abs(l.real))
    if dr:
        modes.append(_mode("dutch roll", dr[0]))
    if len(real_lat) >= 2:
        modes += [_mode("spiral", real_lat[0]), _mode("roll", real_lat[-1])]
    return modes
