"""Aircraft definition loaded from YAML, wrapping the numba core."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from numpy.typing import NDArray

from sargnc.aircraft import _core as C
from sargnc.paths import project_root


@dataclass(frozen=True)
class Limits:
    elevon_max: float          # rad
    servo_tau: float           # s
    bank_max: float            # rad
    pitch_min: float
    pitch_max: float
    v_min: float               # m/s
    v_cruise: float
    v_max: float
    v_launch: float


@dataclass
class Aircraft:
    name: str
    P: NDArray[np.float64]
    limits: Limits
    mass_budget: dict[str, float] = field(default_factory=dict)
    usable_fraction: float = 0.85
    max_current: float = 40.0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __getitem__(self, name: str) -> float:
        return float(self.P[C.PARAM_NAMES.index(name)])

    @property
    def mass(self) -> float:
        return self["mass"]

    @property
    def weight(self) -> float:
        return self.mass * C.G

    @property
    def aspect_ratio(self) -> float:
        return self["b"] ** 2 / self["S"]

    @property
    def energy_J(self) -> float:
        return self["E_capacity"]

    @property
    def usable_energy_J(self) -> float:
        return self.energy_J * self.usable_fraction

    def deriv(self, x: NDArray, u: NDArray, wind_ned: NDArray = np.zeros(3)) -> NDArray:
        return C.deriv(np.asarray(x, float), np.asarray(u, float), np.asarray(wind_ned, float), self.P)

    def step(self, x: NDArray, u: NDArray, wind_ned: NDArray, dt: float, substeps: int = 1) -> NDArray:
        return C.rk4(np.asarray(x, float), np.asarray(u, float), np.asarray(wind_ned, float), self.P,
                     dt / substeps, substeps)

    def outputs(self, x: NDArray, u: NDArray, wind_ned: NDArray = np.zeros(3)) -> dict[str, float]:
        _, _, out = C.aero_prop(np.asarray(x, float), np.asarray(u, float), np.asarray(wind_ned, float), self.P)
        return dict(zip(C.OUT_NAMES, map(float, out)))

    def stall_speed(self, h: float, n_load: float = 1.0) -> float:
        """1-g (or n-g) stall speed from the model's peak lift coefficient."""
        a = np.radians(np.linspace(0, 30, 3001))
        x = np.zeros(C.NX)
        x[6] = 1.0
        x[2] = -h
        cl = []
        for al in a:
            x[3], x[5] = 20 * math.cos(al), 20 * math.sin(al)
            cl.append(C.aero_prop(x, np.zeros(3), np.zeros(3), self.P)[2][7])
        clmax = max(cl)
        return math.sqrt(2 * n_load * self.weight / (C.isa_density(h) * self["S"] * clmax))


def _req(d: dict, key: str, where: str) -> Any:
    if key not in d:
        raise ValueError(f"{where}: missing '{key}'")
    return d[key]


def load_aircraft(name_or_path: str | Path) -> Aircraft:
    """Load configs/aircraft/<name>.yaml (or a path)."""
    p = Path(name_or_path)
    if not p.suffix:
        p = project_root() / "configs" / "aircraft" / f"{name_or_path}.yaml"
    d = yaml.safe_load(p.read_text())
    w = p.name
    geo, mb, inr = _req(d, "geometry", w), _req(d, "mass_budget_kg", w), _req(d, "inertia_kgm2", w)
    aero, prop, bat, lim = (_req(d, k, w) for k in ("aero", "propulsion", "battery", "limits"))
    v_nom = 0.5 * (bat["cell_v_full"] + bat["cell_v_empty"])
    e_cap = bat["cells_series"] * bat["cells_parallel"] * bat["cell_capacity_ah"] * 3600.0 * v_nom
    vals = {
        "mass": float(sum(mb.values())), "Jx": inr["Jx"], "Jy": inr["Jy"], "Jz": inr["Jz"], "Jxz": inr["Jxz"],
        "S": geo["wing_area_m2"], "b": geo["span_m"], "c": geo["mean_chord_m"],
        "alpha0": math.radians(aero["alpha_stall_deg"]), "M": aero["stall_sharpness"],
        "D_prop": prop["prop_diameter_m"],
        "CT0": prop["CT"][0], "CT1": prop["CT"][1], "CT2": prop["CT"][2],
        "CQ0": prop["CQ"][0], "CQ1": prop["CQ"][1], "CQ2": prop["CQ"][2],
        "KV": 60.0 / (2 * math.pi * prop["motor_kv_rpm_per_v"]), "R_motor": prop["motor_resistance_ohm"],
        "i0": prop["motor_no_load_current_a"], "eta_esc": prop["esc_efficiency"],
        "n_series": bat["cells_series"], "v_cell_full": bat["cell_v_full"], "v_cell_empty": bat["cell_v_empty"],
        "E_capacity": e_cap, "P_hotel": bat["hotel_power_w"],
    }
    for k in C.PARAM_NAMES:
        if k not in vals:
            vals[k] = _req(aero, k, f"{w}:aero")
    P = np.array([float(vals[k]) for k in C.PARAM_NAMES])
    r = math.radians
    limits = Limits(r(lim["elevon_max_deg"]), lim["servo_time_constant_s"], r(lim["bank_max_deg"]),
                    r(lim["pitch_min_deg"]), r(lim["pitch_max_deg"]), lim["airspeed_min_mps"],
                    lim["airspeed_cruise_mps"], lim["airspeed_max_mps"], lim["launch_speed_mps"])
    return Aircraft(f"{d['name']} {d.get('version', '')}".strip(), P, limits, dict(mb),
                    bat["usable_fraction"], prop["max_current_a"], d)


def elevon_mix(de: float, da: float, max_defl: float) -> tuple[float, float]:
    """Limit virtual (de, da) so both elevons (de +/- da) stay within +/-max_defl."""
    right, left = de + da, de - da
    right = min(max(right, -max_defl), max_defl)
    left = min(max(left, -max_defl), max_defl)
    return 0.5 * (right + left), 0.5 * (right - left)
