"""Numba 6-DOF flying-wing core (Beard & McLain model structure, NED world / FRD body).

State x (14): pn, pe, pd, u, v, w, e0, e1, e2, e3, p, q, r, E_batt[J].
Controls u (3): de (elevator, rad), da (aileron, rad), dt (throttle 0..1).
"""

from __future__ import annotations

import math

import numpy as np
from numba import njit

G = 9.80665
NX = 14

PARAM_NAMES = (
    "mass", "Jx", "Jy", "Jz", "Jxz", "S", "b", "c",
    "CL0", "CL_alpha", "CL_q", "CL_de", "alpha0", "M", "CD_p", "oswald_e", "CD_de2",
    "Cm0", "Cm_alpha", "Cm_q", "Cm_de",
    "CY_beta", "CY_p", "CY_r", "CY_da",
    "Cl_beta", "Cl_p", "Cl_r", "Cl_da",
    "Cn_beta", "Cn_p", "Cn_r", "Cn_da",
    "D_prop", "CT0", "CT1", "CT2", "CQ0", "CQ1", "CQ2",
    "KV", "R_motor", "i0", "eta_esc",
    "n_series", "v_cell_full", "v_cell_empty", "E_capacity", "P_hotel",
)
(MASS, JX, JY, JZ, JXZ, S_, B_, C_,
 CL0, CL_A, CL_Q, CL_DE, ALPHA0, M_, CD_P, OSW, CD_DE2,
 CM0, CM_A, CM_Q, CM_DE,
 CY_B, CY_P, CY_R, CY_DA,
 CLL_B, CLL_P, CLL_R, CLL_DA,
 CN_B, CN_P, CN_R, CN_DA,
 D_PROP, CT0, CT1, CT2, CQ0, CQ1, CQ2,
 KV, R_MOT, I0, ETA_ESC,
 N_SER, V_FULL, V_EMPTY, E_CAP, P_HOTEL) = range(len(PARAM_NAMES))

# Outputs of aero_prop()
OUT_NAMES = ("Va", "alpha", "beta", "thrust", "omega", "current", "p_batt", "CL", "CD", "rho")
NOUT = len(OUT_NAMES)


@njit(cache=True)
def isa_density(h):
    """ISA density [kg/m^3] at geopotential altitude h [m] (troposphere)."""
    return 1.225 * (1.0 - 2.25577e-5 * h) ** 4.2559


@njit(cache=True)
def rot_body_to_ned(e0, e1, e2, e3):
    R = np.empty((3, 3))
    R[0, 0] = e0 * e0 + e1 * e1 - e2 * e2 - e3 * e3
    R[0, 1] = 2.0 * (e1 * e2 - e3 * e0)
    R[0, 2] = 2.0 * (e1 * e3 + e2 * e0)
    R[1, 0] = 2.0 * (e1 * e2 + e3 * e0)
    R[1, 1] = e0 * e0 - e1 * e1 + e2 * e2 - e3 * e3
    R[1, 2] = 2.0 * (e2 * e3 - e1 * e0)
    R[2, 0] = 2.0 * (e1 * e3 - e2 * e0)
    R[2, 1] = 2.0 * (e2 * e3 + e1 * e0)
    R[2, 2] = e0 * e0 - e1 * e1 - e2 * e2 + e3 * e3
    return R


@njit(cache=True)
def battery_ocv(E_used, P):
    soc = 1.0 - E_used / P[E_CAP]
    if soc < 0.0:
        soc = 0.0
    return P[N_SER] * (P[V_EMPTY] + (P[V_FULL] - P[V_EMPTY]) * soc)


@njit(cache=True)
def propulsion(Va, dt, E_used, rho, P):
    """Steady motor/prop balance. Returns thrust [N], omega [rad/s], motor current [A], battery power [W]."""
    vin = dt * battery_ocv(E_used, P)
    if vin < 0.05:
        return 0.0, 0.0, 0.0, P[P_HOTEL]  # folded prop
    D = P[D_PROP]
    kq = P[KV]
    R = P[R_MOT]
    a = rho * D ** 5 * P[CQ0] / (4.0 * math.pi ** 2)
    b = rho * D ** 4 * P[CQ1] * Va / (2.0 * math.pi) + kq * kq / R
    c = rho * D ** 3 * P[CQ2] * Va * Va - kq * vin / R + kq * P[I0]
    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        disc = 0.0
    om = (-b + math.sqrt(disc)) / (2.0 * a)
    if om < 0.0:
        om = 0.0
    T = (rho * D ** 4 * P[CT0] * om * om / (4.0 * math.pi ** 2)
         + rho * D ** 3 * P[CT1] * Va * om / (2.0 * math.pi)
         + rho * D ** 2 * P[CT2] * Va * Va)
    i = (vin - kq * om) / R
    if i < 0.0:
        i = 0.0
    return T, om, i, vin * i / P[ETA_ESC] + P[P_HOTEL]


@njit(cache=True)
def aero_prop(x, u, wind_ned, P):
    """Body forces and moments plus diagnostics. Returns (F[3], Mom[3], out[NOUT])."""
    R = rot_body_to_ned(x[6], x[7], x[8], x[9])
    wb0 = R[0, 0] * wind_ned[0] + R[1, 0] * wind_ned[1] + R[2, 0] * wind_ned[2]
    wb1 = R[0, 1] * wind_ned[0] + R[1, 1] * wind_ned[1] + R[2, 1] * wind_ned[2]
    wb2 = R[0, 2] * wind_ned[0] + R[1, 2] * wind_ned[1] + R[2, 2] * wind_ned[2]
    ur = x[3] - wb0
    vr = x[4] - wb1
    wr = x[5] - wb2
    Va = math.sqrt(ur * ur + vr * vr + wr * wr)
    p, q, r = x[10], x[11], x[12]
    de, da, dt = u[0], u[1], u[2]
    rho = isa_density(-x[2])
    m = P[MASS]

    F = np.zeros(3)
    Mo = np.zeros(3)
    out = np.zeros(NOUT)
    F[0] = m * G * R[2, 0]
    F[1] = m * G * R[2, 1]
    F[2] = m * G * R[2, 2]

    alpha = 0.0
    beta = 0.0
    CL = 0.0
    CD = 0.0
    if Va > 0.5:
        alpha = math.atan2(wr, ur)
        beta = math.asin(max(-1.0, min(1.0, vr / Va)))
        qbar = 0.5 * rho * Va * Va
        S, b, c = P[S_], P[B_], P[C_]
        AR = b * b / S
        Mm, a0 = P[M_], P[ALPHA0]
        e1 = math.exp(-Mm * (alpha - a0))
        e2 = math.exp(Mm * (alpha + a0))
        sig = (1.0 + e1 + e2) / ((1.0 + e1) * (1.0 + e2))
        CL_lin = P[CL0] + P[CL_A] * alpha
        sa = math.sin(alpha)
        ca = math.cos(alpha)
        sgn = 1.0 if alpha >= 0.0 else -1.0
        CL = ((1.0 - sig) * CL_lin + sig * 2.0 * sgn * sa * sa * ca
              + P[CL_Q] * c * q / (2.0 * Va) + P[CL_DE] * de)
        CD = P[CD_P] + CL_lin * CL_lin / (math.pi * P[OSW] * AR) + P[CD_DE2] * de * de
        F[0] += qbar * S * (-CD * ca + CL * sa)
        F[2] += qbar * S * (-CD * sa - CL * ca)
        bh = b / (2.0 * Va)
        F[1] += qbar * S * (P[CY_B] * beta + P[CY_P] * bh * p + P[CY_R] * bh * r + P[CY_DA] * da)
        Mo[0] = qbar * S * b * (P[CLL_B] * beta + P[CLL_P] * bh * p + P[CLL_R] * bh * r + P[CLL_DA] * da)
        Mo[1] = qbar * S * c * (P[CM0] + P[CM_A] * alpha + P[CM_Q] * c * q / (2.0 * Va) + P[CM_DE] * de)
        Mo[2] = qbar * S * b * (P[CN_B] * beta + P[CN_P] * bh * p + P[CN_R] * bh * r + P[CN_DA] * da)

    T, om, i, pb = propulsion(Va, dt, x[13], rho, P)
    F[0] += T
    out[0] = Va
    out[1] = alpha
    out[2] = beta
    out[3] = T
    out[4] = om
    out[5] = i
    out[6] = pb
    out[7] = CL
    out[8] = CD
    out[9] = rho
    return F, Mo, out


@njit(cache=True)
def deriv(x, u, wind_ned, P):
    F, Mo, out = aero_prop(x, u, wind_ned, P)
    e0, e1, e2, e3 = x[6], x[7], x[8], x[9]
    uu, vv, ww = x[3], x[4], x[5]
    p, q, r = x[10], x[11], x[12]
    R = rot_body_to_ned(e0, e1, e2, e3)
    Jx, Jy, Jz, Jxz = P[JX], P[JY], P[JZ], P[JXZ]
    gam = Jx * Jz - Jxz * Jxz
    g1 = Jxz * (Jx - Jy + Jz) / gam
    g2 = (Jz * (Jz - Jy) + Jxz * Jxz) / gam
    g3 = Jz / gam
    g4 = Jxz / gam
    g5 = (Jz - Jx) / Jy
    g6 = Jxz / Jy
    g7 = ((Jx - Jy) * Jx + Jxz * Jxz) / gam
    g8 = Jx / gam
    m = P[MASS]

    xd = np.empty(NX)
    xd[0] = R[0, 0] * uu + R[0, 1] * vv + R[0, 2] * ww
    xd[1] = R[1, 0] * uu + R[1, 1] * vv + R[1, 2] * ww
    xd[2] = R[2, 0] * uu + R[2, 1] * vv + R[2, 2] * ww
    xd[3] = r * vv - q * ww + F[0] / m
    xd[4] = p * ww - r * uu + F[1] / m
    xd[5] = q * uu - p * vv + F[2] / m
    xd[6] = 0.5 * (-p * e1 - q * e2 - r * e3)
    xd[7] = 0.5 * (p * e0 + r * e2 - q * e3)
    xd[8] = 0.5 * (q * e0 - r * e1 + p * e3)
    xd[9] = 0.5 * (r * e0 + q * e1 - p * e2)
    xd[10] = g1 * p * q - g2 * q * r + g3 * Mo[0] + g4 * Mo[2]
    xd[11] = g5 * p * r - g6 * (p * p - r * r) + Mo[1] / Jy
    xd[12] = g7 * p * q - g1 * q * r + g4 * Mo[0] + g8 * Mo[2]
    xd[13] = out[6]
    return xd


@njit(cache=True)
def rk4(x, u, wind_ned, P, dt, n):
    """n RK4 steps of size dt with constant controls and wind; renormalises the quaternion."""
    y = x.copy()
    for _ in range(n):
        k1 = deriv(y, u, wind_ned, P)
        k2 = deriv(y + 0.5 * dt * k1, u, wind_ned, P)
        k3 = deriv(y + 0.5 * dt * k2, u, wind_ned, P)
        k4 = deriv(y + dt * k3, u, wind_ned, P)
        y = y + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        nq = math.sqrt(y[6] ** 2 + y[7] ** 2 + y[8] ** 2 + y[9] ** 2)
        for k in range(6, 10):
            y[k] /= nq
    return y
