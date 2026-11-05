import math

import numpy as np
import pytest

from sargnc.aircraft import _core as C
from sargnc.aircraft import load_aircraft
from sargnc.aircraft.model import elevon_mix
from sargnc.aircraft.performance import curve, summarize
from sargnc.aircraft.rotations import enu_to_ned, euler_to_quat, ned_to_enu, quat_to_euler
from sargnc.aircraft.trim import dynamic_modes, linearize, trim


@pytest.fixture(scope="module")
def ac():
    return load_aircraft("gildo")


def _no_aero(ac):
    P = ac.P.copy()
    for name in C.PARAM_NAMES[C.CL0:C.CN_DA + 1]:
        if name not in ("alpha0", "M", "oswald_e"):
            P[C.PARAM_NAMES.index(name)] = 0.0
    return P


def test_mass_budget_and_energy(ac):
    assert ac.mass == pytest.approx(sum(ac.mass_budget.values()))
    assert ac.energy_J / 3600 == pytest.approx(6 * 2 * 5.0 * 0.5 * (4.15 + 3.30), rel=1e-9)


def test_rotations_roundtrip():
    for e in [(0.3, -0.2, 2.5), (-1.0, 0.7, -3.0), (0.0, 1.2, 0.1)]:
        np.testing.assert_allclose(quat_to_euler(euler_to_quat(*e)), e, atol=1e-12)
    p = np.array([[1.0, 2.0, 3.0]])
    np.testing.assert_allclose(enu_to_ned(p), [[2.0, 1.0, -3.0]])
    np.testing.assert_allclose(ned_to_enu(enu_to_ned(p)), p)


def test_ballistic_free_fall(ac):
    P = _no_aero(ac)
    x = np.zeros(C.NX)
    x[6:10] = euler_to_quat(0.3, 0.2, 1.0)
    x[2] = -44330.0  # ISA density ~0 here, removing the coefficient-free post-stall lift term
    R = C.rot_body_to_ned(*x[6:10])
    v0 = np.array([5.0, -2.0, 1.0])
    x[3:6] = R.T @ v0
    y = C.rk4(x, np.zeros(3), np.zeros(3), P, 0.01, 300)
    t = 3.0
    np.testing.assert_allclose(y[0:3], x[0:3] + v0 * t + np.array([0, 0, 0.5 * C.G * t * t]), atol=1e-6)


def test_torque_free_spin_conserves_momentum(ac):
    P = _no_aero(ac)
    x = np.zeros(C.NX)
    x[6:10] = euler_to_quat(0.1, -0.2, 0.3)
    x[10:13] = [1.0, 0.5, -2.0]
    J = np.array([[ac["Jx"], 0, -ac["Jxz"]], [0, ac["Jy"], 0], [-ac["Jxz"], 0, ac["Jz"]]])

    def h_inertial(s):
        return C.rot_body_to_ned(*s[6:10]) @ (J @ s[10:13])

    y = C.rk4(x, np.zeros(3), np.zeros(3), P, 0.002, 2500)
    np.testing.assert_allclose(h_inertial(y), h_inertial(x), rtol=1e-6, atol=1e-8)
    assert np.linalg.norm(y[6:10]) == pytest.approx(1.0, abs=1e-12)


def test_cruise_trim_lift_equals_weight(ac):
    t = trim(ac, 18.0, 2000.0)
    assert t.ok
    o = t.outputs
    lift = 0.5 * o["rho"] * 18.0**2 * ac["S"] * o["CL"]
    assert lift + o["thrust"] * math.sin(t.alpha) == pytest.approx(ac.weight, rel=0.01)
    assert abs(t.beta) < 1e-6 and abs(t.phi) < 1e-6


def test_turn_and_climb_trims(ac):
    t = trim(ac, 18.0, 2000.0, radius=80.0)
    assert t.ok and t.phi == pytest.approx(math.atan(18.0**2 / (C.G * 80.0)), abs=math.radians(1.5))
    c = trim(ac, 18.0, 2000.0, gamma=math.radians(5))
    assert c.ok and c.dt > trim(ac, 18.0, 2000.0).dt


def test_modes_stable_except_slow_spiral(ac):
    modes = {m.name: m for m in dynamic_modes(linearize(ac, trim(ac, 18.0, 2000.0))[0])}
    for name in ("short period", "phugoid", "dutch roll", "roll"):
        assert modes[name].eig.real < 0, name
    assert modes["spiral"].time_const > 20.0


def test_performance_regression(ac):
    s = summarize(ac, curve(ac, 2000.0, n=20))
    assert 100 < s.endurance_cruise_min < 140
    assert 5.0 < s.climb_max < 9.0
    assert 26.0 < s.v_max_level < 31.0


def test_elevon_mix_limits():
    lim = math.radians(25)
    de, da = elevon_mix(math.radians(20), math.radians(20), lim)
    assert abs(de + da) <= lim + 1e-12 and abs(de - da) <= lim + 1e-12
    assert elevon_mix(0.1, 0.05, lim) == pytest.approx((0.1, 0.05))
