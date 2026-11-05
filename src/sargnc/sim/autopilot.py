"""Successive-loop-closure autopilot (Beard & McLain ch. 6) with an altitude state machine.

Lateral: course -> roll -> aileron. Longitudinal: hold zone uses altitude -> pitch and airspeed ->
throttle; climb/descend zones use full/idle throttle with airspeed -> pitch.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from sargnc.aircraft import _core as C
from sargnc.aircraft.model import Aircraft, elevon_mix
from sargnc.aircraft.rotations import wrap_pi
from sargnc.aircraft.trim import Trim, linearize, trim


@dataclass(frozen=True)
class Gains:
    kp_phi: float
    kd_phi: float
    ki_phi: float
    kp_chi: float
    ki_chi: float
    kp_theta: float
    kd_theta: float
    k_theta_dc: float
    kp_h: float
    ki_h: float
    kp_v: float
    ki_v: float
    kp_v2: float
    ki_v2: float
    trim: Trim


def design_gains(ac: Aircraft, Va: float, h: float) -> Gains:
    """Loop gains from the model's transfer-function coefficients at a cruise trim."""
    t = trim(ac, Va, h)
    rho = C.isa_density(h)
    S, b, c = ac["S"], ac["b"], ac["c"]
    Jx, Jy, Jz, Jxz = ac["Jx"], ac["Jy"], ac["Jz"], ac["Jxz"]
    gam = Jx * Jz - Jxz**2
    g3, g4 = Jz / gam, Jxz / gam
    cp_p = g3 * ac["Cl_p"] + g4 * ac["Cn_p"]
    cp_da = g3 * ac["Cl_da"] + g4 * ac["Cn_da"]
    a_phi1 = -0.5 * rho * Va**2 * S * b * cp_p * b / (2 * Va)
    a_phi2 = 0.5 * rho * Va**2 * S * b * cp_da

    da_max, e_phi_max, z_phi = math.radians(15), math.radians(20), 0.9
    kp_phi = da_max / e_phi_max * math.copysign(1, a_phi2)
    wn_phi = math.sqrt(abs(a_phi2) * abs(kp_phi))
    kd_phi = (2 * z_phi * wn_phi - a_phi1) / a_phi2
    wn_chi, z_chi = wn_phi / 10.0, 1.0
    kp_chi = 2 * z_chi * wn_chi * Va / C.G
    ki_chi = wn_chi**2 * Va / C.G

    a_th1 = -rho * Va**2 * c * S * ac["Cm_q"] * c / (2 * Jy * 2 * Va)
    a_th2 = -rho * Va**2 * c * S * ac["Cm_alpha"] / (2 * Jy)
    a_th3 = rho * Va**2 * c * S * ac["Cm_de"] / (2 * Jy)
    de_max, e_th_max, z_th = math.radians(15), math.radians(10), 0.8
    kp_th = de_max / e_th_max * math.copysign(1, a_th3)
    wn_th = math.sqrt(a_th2 + kp_th * a_th3)
    kd_th = (2 * z_th * wn_th - a_th1) / a_th3
    k_dc = kp_th * a_th3 / (a_th2 + kp_th * a_th3)

    wn_h, z_h = wn_th / 50.0, 1.0
    kp_h = 2 * z_h * wn_h / (k_dc * Va)
    ki_h = wn_h**2 / (k_dc * Va)

    A, B = linearize(ac, t)
    a_v1, a_v2 = -A[3, 3], B[3, 2]
    wn_v, z_v = 0.6, 1.0
    kp_v = (2 * z_v * wn_v - a_v1) / a_v2
    ki_v = wn_v**2 / a_v2
    wn_v2, z_v2 = wn_th / 15.0, 1.0
    kp_v2 = (a_v1 - 2 * z_v2 * wn_v2) / (k_dc * C.G)
    ki_v2 = -wn_v2**2 / (k_dc * C.G)
    return Gains(kp_phi, kd_phi, 0.0, kp_chi, ki_chi, kp_th, kd_th, k_dc, kp_h, ki_h, kp_v, ki_v, kp_v2, ki_v2, t)


@dataclass
class Command:
    course: float          # rad, NED (clockwise from north)
    altitude: float        # m (z up)
    airspeed: float        # m/s
    roll_ff: float = 0.0   # rad
    pitch_override: float | None = None
    throttle_override: float | None = None


class Autopilot:
    HOLD, CLIMB, DESCEND = "hold", "climb", "descend"

    def __init__(self, ac: Aircraft, gains: Gains, dt: float, h_band: float = 25.0,
                 climb_throttle: float = 0.9, descend_throttle: float = 0.0,
                 hold_pitch_authority: float = math.radians(10), roll_rate_max: float = math.radians(45)):
        self.ac, self.g, self.dt = ac, gains, dt
        self.h_band, self.climb_throttle, self.descend_throttle = h_band, climb_throttle, descend_throttle
        self.hold_pitch_authority, self.roll_rate_max = hold_pitch_authority, roll_rate_max
        self.i_chi = self.i_h = self.i_v = self.i_v2 = 0.0
        self.phi_c = 0.0
        self.zone = self.HOLD

    def update(self, cmd: Command, chi: float, phi: float, theta: float, p: float, q: float,
               h: float, Va: float) -> np.ndarray:
        g, lim, dt = self.g, self.ac.limits, self.dt
        # lateral
        e_chi = wrap_pi(cmd.course - chi)
        phi_c = g.kp_chi * e_chi + g.ki_chi * self.i_chi + cmd.roll_ff
        phi_c_sat = max(-lim.bank_max, min(lim.bank_max, phi_c))
        if phi_c == phi_c_sat:
            self.i_chi += dt * e_chi
        step = self.roll_rate_max * dt
        self.phi_c += max(-step, min(step, phi_c_sat - self.phi_c))
        da = g.kp_phi * (self.phi_c - phi) - g.kd_phi * p

        # longitudinal state machine
        e_h = cmd.altitude - h
        if e_h > self.h_band:
            self.zone = self.CLIMB
        elif e_h < -self.h_band:
            self.zone = self.DESCEND
        elif abs(e_h) < 0.5 * self.h_band:
            self.zone = self.HOLD
        e_v = cmd.airspeed - Va
        if self.zone == self.HOLD:
            e_hc = max(-self.h_band, min(self.h_band, e_h))
            i_h = self.i_h + dt * e_hc
            d_theta = g.kp_h * e_hc + g.ki_h * i_h
            auth = self.hold_pitch_authority
            theta_c = g.trim.theta + max(-auth, min(auth, d_theta))
            if abs(d_theta) < auth:
                self.i_h = i_h
            dt_c = g.trim.dt + g.kp_v * e_v + g.ki_v * self.i_v
            if 0.0 < dt_c < 1.0:
                self.i_v += dt * e_v
            self.i_v2 = 0.0
        else:
            i_v2 = self.i_v2 + dt * e_v
            base = g.trim.theta + (math.radians(8) if self.zone == self.CLIMB else -math.radians(4))
            theta_c = base + g.kp_v2 * e_v + g.ki_v2 * i_v2
            if lim.pitch_min < theta_c < lim.pitch_max:
                self.i_v2 = i_v2
            dt_c = self.climb_throttle if self.zone == self.CLIMB else self.descend_throttle
            self.i_h = 0.0
        if Va < lim.v_min:
            theta_c -= 0.05 * (lim.v_min - Va)
        if cmd.pitch_override is not None:
            theta_c = cmd.pitch_override
        if cmd.throttle_override is not None:
            dt_c = cmd.throttle_override
        theta_c = max(lim.pitch_min, min(lim.pitch_max, theta_c))
        de = g.trim.de + g.kp_theta * (theta_c - theta) - g.kd_theta * q
        de, da = elevon_mix(de, da, lim.elevon_max)
        return np.array([de, da, max(0.0, min(1.0, dt_c))])
