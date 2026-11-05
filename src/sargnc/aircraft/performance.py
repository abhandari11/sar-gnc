"""Steady-state performance: power, endurance, range, climb, turn, ceiling."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from sargnc.aircraft import _core as C
from sargnc.aircraft.model import Aircraft
from sargnc.aircraft.trim import trim


@dataclass
class PerfCurve:
    h: float
    V: NDArray[np.float64]
    p_batt: NDArray[np.float64]      # W, level flight, incl. hotel load
    throttle: NDArray[np.float64]
    endurance_min: NDArray[np.float64]
    range_km: NDArray[np.float64]
    climb: NDArray[np.float64]       # m/s at full throttle
    current_max: NDArray[np.float64]  # A at full throttle


@dataclass
class PerfSummary:
    h: float
    v_stall: float
    v_best_endurance: float
    endurance_max_min: float
    v_best_range: float
    range_max_km: float
    v_max_level: float
    climb_max: float
    v_best_climb: float
    p_cruise: float
    endurance_cruise_min: float
    range_cruise_km: float


@dataclass
class Performance:
    aircraft: str
    curves: list[PerfCurve]
    summaries: list[PerfSummary]
    ceiling_m: float
    turn: dict[str, float] = field(default_factory=dict)


def curve(ac: Aircraft, h: float, n: int = 40) -> PerfCurve:
    vs = ac.stall_speed(h)
    V = np.linspace(1.08 * vs, ac.limits.v_max + 2.0, n)
    P, T, E, Rg, CL, IM = (np.full(n, np.nan) for _ in range(6))
    for i, v in enumerate(V):
        t = trim(ac, float(v), h)
        if t.ok:
            P[i], T[i] = t.outputs["p_batt"], t.dt
            E[i] = ac.usable_energy_J / P[i] / 60.0
            Rg[i] = E[i] * 60.0 * v / 1000.0
        c = trim(ac, float(v), h, throttle=1.0)
        if c.residual < 1e-6:
            CL[i] = v * math.sin(c.gamma)
            IM[i] = c.outputs["current"]
    return PerfCurve(h, V, P, T, E, Rg, CL, IM)


def summarize(ac: Aircraft, c: PerfCurve) -> PerfSummary:
    ie, ir, ic = np.nanargmax(c.endurance_min), np.nanargmax(c.range_km), np.nanargmax(c.climb)
    level = c.V[np.isfinite(c.throttle) & (c.throttle <= 1.0)]
    tc = trim(ac, ac.limits.v_cruise, c.h)
    pc = tc.outputs["p_batt"]
    ec = ac.usable_energy_J / pc / 60.0
    return PerfSummary(c.h, ac.stall_speed(c.h), float(c.V[ie]), float(c.endurance_min[ie]), float(c.V[ir]),
                       float(c.range_km[ir]), float(level.max()), float(c.climb[ic]), float(c.V[ic]), pc, ec,
                       ec * 60.0 * ac.limits.v_cruise / 1000.0)


def ceiling(ac: Aircraft, min_climb: float = 0.5) -> float:
    """Altitude where the best full-throttle climb rate falls to min_climb (bisection, ISA)."""
    def best(h):
        vs = ac.stall_speed(h)
        return max(v * math.sin(trim(ac, float(v), h, throttle=1.0).gamma)
                   for v in np.linspace(1.15 * vs, 1.8 * vs, 8))
    lo, hi = 0.0, 6000.0
    if best(hi) > min_climb:
        return hi
    for _ in range(25):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if best(mid) > min_climb else (lo, mid)
    return 0.5 * (lo + hi)


def analyze(ac: Aircraft, altitudes=(1150.0, 2000.0, 2500.0)) -> Performance:
    curves = [curve(ac, h) for h in altitudes]
    v = ac.limits.v_cruise
    bank = ac.limits.bank_max
    turn = {
        "cruise_radius_30deg_m": v**2 / (C.G * math.tan(math.radians(30))),
        "cruise_radius_bankmax_m": v**2 / (C.G * math.tan(bank)),
        "min_radius_m": ac.limits.v_min**2 / (C.G * math.tan(bank)),
        "load_factor_bankmax": 1.0 / math.cos(bank),
    }
    return Performance(ac.name, curves, [summarize(ac, c) for c in curves], ceiling(ac), turn)
