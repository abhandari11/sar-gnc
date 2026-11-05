"""Closed-loop flight simulation of an aircraft over terrain with wind."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from sargnc.aircraft import _core as C
from sargnc.aircraft.model import Aircraft
from sargnc.aircraft.rotations import euler_to_quat, quat_to_euler
from sargnc.sim.autopilot import Autopilot, design_gains
from sargnc.sim.mission import Mission
from sargnc.terrain.grid import TerrainGrid
from sargnc.wind.steady import WindModel

LOG_KEYS = ("t", "east", "north", "alt", "terrain", "agl", "Va", "Vg", "alpha", "beta", "phi", "theta", "psi",
            "chi", "p", "q", "r", "de", "da", "throttle", "thrust", "current", "p_batt", "energy_Wh",
            "alt_cmd", "Va_cmd", "chi_cmd", "wind_n", "wind_e", "phase")


@dataclass
class SimResult:
    log: dict[str, np.ndarray]
    events: list[tuple[float, str]]
    outcome: str
    mission: Mission
    meta: dict = field(default_factory=dict)


def launch_state(ac: Aircraft, terrain: TerrainGrid, east: float, north: float, heading_deg: float,
                 wind_ned: np.ndarray, pitch_deg: float = 8.0, height_agl: float = 2.0) -> np.ndarray:
    """Catapult exit state at the base: launch airspeed along the heading, wings level."""
    x = np.zeros(C.NX)
    z = float(terrain.elevation(east, north)) + height_agl
    x[0:3] = [north, east, -z]
    q = euler_to_quat(0.0, math.radians(pitch_deg), math.radians(heading_deg))
    x[6:10] = q
    R = C.rot_body_to_ned(*q)
    x[3:6] = R.T @ wind_ned + np.array([ac.limits.v_launch, 0.0, 0.0])
    return x


def simulate(ac: Aircraft, terrain: TerrainGrid, mission: Mission, wind: WindModel,
             control_hz: float = 50.0, substeps: int = 4, t_max: float = 1800.0) -> SimResult:
    dt = 1.0 / control_hz
    gains = design_gains(ac, mission.spec.airspeed, mission.transit_alt)
    ap = Autopilot(ac, gains, dt)
    b = mission.base
    x = launch_state(ac, terrain, b.east, b.north, b.launch_heading_deg, wind(0.0, np.zeros(3)))
    u_act = np.array([gains.trim.de, 0.0, 1.0])
    a_servo = 1.0 - math.exp(-dt / ac.limits.servo_tau)
    n = int(t_max * control_hz) + 1
    log = {k: np.full(n, np.nan) for k in LOG_KEYS}
    log["phase"] = np.empty(n, dtype=object)
    outcome = "time limit"
    k = 0
    for k in range(n):
        t = k * dt
        w = wind(t, x[0:3])
        phi, theta, psi = quat_to_euler(x[6:10])
        R = C.rot_body_to_ned(*x[6:10])
        v_ned = R @ x[3:6]
        chi = math.atan2(v_ned[1], v_ned[0])
        Vg = math.hypot(v_ned[0], v_ned[1])
        p_enu = np.array([x[1], x[0], -x[2]])
        ground = float(terrain.elevation(p_enu[0], p_enu[1]))
        agl = p_enu[2] - ground
        out = ac.outputs(x, u_act, w)

        cmd = mission.command(t, dt, p_enu, chi, Vg, agl)
        row = dict(t=t, east=p_enu[0], north=p_enu[1], alt=p_enu[2], terrain=ground, agl=agl, Va=out["Va"], Vg=Vg,
                   alpha=out["alpha"], beta=out["beta"], phi=phi, theta=theta, psi=psi, chi=chi,
                   p=x[10], q=x[11], r=x[12], de=u_act[0], da=u_act[1], throttle=u_act[2], thrust=out["thrust"],
                   current=out["current"], p_batt=out["p_batt"], energy_Wh=x[13] / 3600.0,
                   alt_cmd=cmd.altitude if cmd else np.nan, Va_cmd=cmd.airspeed if cmd else np.nan,
                   chi_cmd=cmd.course if cmd else np.nan, wind_n=w[0], wind_e=w[1], phase=mission.phase)
        for key, v in row.items():
            log[key][k] = v
        if cmd is None:
            outcome = "mission complete"
            break
        if not np.isfinite(ground):
            outcome = "left terrain map"
            mission.events.append((t, outcome))
            break
        if agl < 0.0 and t > 0.5:
            outcome = "terrain impact"
            mission.events.append((t, outcome))
            break
        if x[13] >= ac.usable_energy_J:
            outcome = "battery reserve reached"
            mission.events.append((t, outcome))
            break

        u_cmd = ap.update(cmd, chi, phi, theta, x[10], x[11], p_enu[2], out["Va"])
        u_act[:2] += a_servo * (u_cmd[:2] - u_act[:2])
        u_act[2] = u_cmd[2]
        x = ac.step(x, u_act, w, dt, substeps)
    log = {key: v[: k + 1] for key, v in log.items()}
    return SimResult(log, list(mission.events), outcome, mission,
                     dict(gains=gains, transit_alt=mission.transit_alt, target_alt=mission.target_alt,
                          return_alt=mission.return_alt, home_alt=mission.home_alt))
