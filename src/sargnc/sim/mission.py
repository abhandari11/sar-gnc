"""Mission manager: launch from base, climb over the home loiter, transit, orbit, return, hold."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from sargnc.scenario.site import Base
from sargnc.sim.autopilot import Command
from sargnc.sim.guidance import follow_line, follow_orbit
from sargnc.terrain.grid import TerrainGrid


@dataclass(frozen=True)
class MissionSpec:
    airspeed: float = 18.0
    clearance_m: float = 120.0
    corridor_half_width_m: float = 150.0
    waypoints_en: tuple[tuple[float, float], ...] = ()
    orbit_radius_m: float = 150.0
    orbit_turns: float = 2.0
    home_hold_s: float = 60.0
    launch_pitch_deg: float = 15.0
    launch_agl_m: float = 30.0


def corridor_max(t: TerrainGrid, a_en: np.ndarray, b_en: np.ndarray, half_width: float, step: float = 10.0) -> float:
    """Highest terrain within half_width of segment a-b (both ends inclusive)."""
    L = float(np.hypot(*(b_en - a_en)))
    s = np.linspace(0, 1, max(2, int(L / step) + 1))
    ax = a_en + (b_en - a_en) * s[:, None]
    off = np.arange(-half_width, half_width + 1e-9, step)
    ang = np.linspace(0, 2 * np.pi, 16, endpoint=False)
    d = (b_en - a_en) / L if L > 0 else np.array([1.0, 0.0])
    nrm = np.array([-d[1], d[0]])
    pts = (ax[:, None, :] + off[None, :, None] * nrm).reshape(-1, 2)
    caps = np.concatenate([e + half_width * np.column_stack([np.cos(ang), np.sin(ang)]) for e in (a_en, b_en)])
    pts = np.vstack([pts, caps])
    return float(np.nanmax(t.elevation(pts[:, 0], pts[:, 1])))


def disc_max(t: TerrainGrid, c_en: np.ndarray, radius: float, step: float = 10.0) -> float:
    g = np.arange(-radius, radius + 1e-9, step)
    ee, nn = np.meshgrid(g, g)
    m = np.hypot(ee, nn) <= radius
    return float(np.nanmax(t.elevation(c_en[0] + ee[m], c_en[1] + nn[m])))


@dataclass
class Mission:
    """State machine producing autopilot commands. Positions in ENU (east, north); z up."""

    spec: MissionSpec
    base: Base
    terrain: TerrainGrid
    phase: str = "launch"
    leg: int = 0
    t_phase: float = 0.0
    orbit_angle: float = 0.0
    _last_bearing: float | None = None
    events: list[tuple[float, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        b, lo, sp, t = self.base, self.base.home_loiter, self.spec, self.terrain
        self.home_c = np.array([lo.east, lo.north])
        self.home_alt = disc_max(t, self.home_c, lo.radius_m) + lo.height_agl_m
        pts = [self.home_c] + [np.array(w, float) for w in sp.waypoints_en]
        self.legs = list(zip(pts[:-1], pts[1:]))
        alts = [corridor_max(t, a, b_, sp.corridor_half_width_m) + sp.clearance_m for a, b_ in self.legs]
        target = pts[-1]
        self.return_alt = corridor_max(t, target, self.home_c, sp.corridor_half_width_m) + sp.clearance_m
        self.transit_alt = max(alts + [self.return_alt, self.home_alt])
        self.target_c = target
        self.target_alt = disc_max(t, target, sp.orbit_radius_m + 50.0) + sp.clearance_m

    def _set(self, phase: str, t: float) -> None:
        self.events.append((t, f"{self.phase} -> {phase}"))
        self.phase, self.t_phase = phase, 0.0
        self._last_bearing = None

    def _orbit(self, p_ne: np.ndarray, c_en: np.ndarray, radius: float, cw: bool, chi: float, Vg: float):
        c_ne = c_en[::-1]
        chi_c, dist = follow_orbit(p_ne, c_ne, radius, cw, chi)
        ff = 0.0
        if abs(dist - radius) < 0.5 * radius:
            ff = (1 if cw else -1) * math.atan(Vg**2 / (9.80665 * radius))
        bearing = math.atan2(p_ne[1] - c_ne[1], p_ne[0] - c_ne[0])
        if self._last_bearing is not None and abs(dist - radius) < 0.3 * radius:
            self.orbit_angle += abs((bearing - self._last_bearing + math.pi) % (2 * math.pi) - math.pi)
        self._last_bearing = bearing
        return chi_c, ff

    def command(self, t: float, dt: float, p_enu: np.ndarray, chi: float, Vg: float, agl: float) -> Command | None:
        """Return the command for this step, or None when the mission is complete."""
        self.t_phase += dt
        sp, b = self.spec, self.base
        p_ne = np.array([p_enu[1], p_enu[0]])
        h = float(p_enu[2])
        V = sp.airspeed
        cw = b.home_loiter.clockwise

        if self.phase == "launch":
            hd = math.radians(b.launch_heading_deg)
            chi_c = follow_line(p_ne, np.array([b.north, b.east]), np.array([math.cos(hd), math.sin(hd)]), chi)
            if agl >= sp.launch_agl_m and self.t_phase > 2.0:
                self._set("climb", t)
            return Command(chi_c, h + 100.0, V, pitch_override=math.radians(sp.launch_pitch_deg),
                           throttle_override=1.0)

        if self.phase == "climb":
            chi_c, ff = self._orbit(p_ne, self.home_c, b.home_loiter.radius_m, cw, chi, Vg)
            if h >= self.transit_alt - 10.0:
                self._set("transit", t) if self.legs else self._set("return", t)
            return Command(chi_c, self.transit_alt, V, ff)

        if self.phase == "transit":
            a, w = self.legs[self.leg]
            d = (w - a) / np.linalg.norm(w - a)
            chi_c = follow_line(p_ne, a[::-1], d[::-1], chi)
            if np.dot(p_enu[:2] - w, d) >= 0.0:
                self.leg += 1
                if self.leg >= len(self.legs):
                    self.orbit_angle = 0.0
                    self._set("orbit", t)
            return Command(chi_c, self.transit_alt, V)

        if self.phase == "orbit":
            chi_c, ff = self._orbit(p_ne, self.target_c, sp.orbit_radius_m, cw, chi, Vg)
            done_turns = self.orbit_angle >= 2 * math.pi * sp.orbit_turns
            alt = self.return_alt if done_turns else self.target_alt
            if done_turns and h >= self.return_alt - 10.0:
                self._set("return", t)
            return Command(chi_c, alt, V, ff)

        if self.phase == "return":
            a = self.target_c
            d = (self.home_c - a) / np.linalg.norm(self.home_c - a)
            chi_c = follow_line(p_ne, a[::-1], d[::-1], chi)
            if np.hypot(*(p_enu[:2] - self.home_c)) < 2.0 * b.home_loiter.radius_m:
                self._set("home", t)
            return Command(chi_c, self.return_alt, V)

        if self.phase == "home":
            chi_c, ff = self._orbit(p_ne, self.home_c, b.home_loiter.radius_m, cw, chi, Vg)
            if abs(h - self.home_alt) < 10.0 and self.t_phase > sp.home_hold_s:
                self._set("done", t)
                return None
            return Command(chi_c, self.home_alt, V, ff)
        return None
