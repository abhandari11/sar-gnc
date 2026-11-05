import math

import numpy as np
import pytest

from sargnc.aircraft import load_aircraft
from sargnc.scenario.site import Base, Loiter
from sargnc.sim.guidance import follow_line, follow_orbit
from sargnc.sim.mission import Mission, MissionSpec, corridor_max
from sargnc.sim.simulator import simulate
from sargnc.terrain import synthetic as syn
from sargnc.wind import SteadyWind


def test_wind_convention():
    np.testing.assert_allclose(SteadyWind(5.0, 270.0).ned, [0.0, 5.0, 0.0], atol=1e-12)  # westerly blows east
    np.testing.assert_allclose(SteadyWind(4.0, 0.0)(0.0, np.zeros(3)), [-4.0, 0.0, 0.0], atol=1e-12)


def test_guidance_geometry():
    assert follow_line(np.array([0.0, 0.0]), np.zeros(2), np.array([1.0, 1.0]), 0.0) == pytest.approx(math.pi / 4)
    off = follow_line(np.array([0.0, 100.0]), np.zeros(2), np.array([1.0, 0.0]), 0.0)
    assert off < 0  # right of a northbound line -> steer left (west)
    chi, d = follow_orbit(np.array([0.0, 100.0]), np.zeros(2), 100.0, True, 0.0)
    assert d == pytest.approx(100.0) and chi == pytest.approx(math.pi)  # east of centre, clockwise -> south


def test_corridor_max_hill():
    t = syn.gaussian(300.0, 100.0, 1000.0).grid(1000.0, 10.0)
    assert corridor_max(t, np.array([-800.0, 300.0]), np.array([800.0, 300.0]), 50.0) < 1100
    assert corridor_max(t, np.array([-800.0, 0.0]), np.array([800.0, 0.0]), 50.0) == pytest.approx(1300, abs=1)


@pytest.mark.parametrize("wind", [SteadyWind(0.0, 0.0), SteadyWind(7.0, 300.0)])
def test_mission_over_synthetic_hill(wind):
    ac = load_aircraft("gildo")
    t = syn.gaussian(400.0, 300.0, 1000.0, cx=1500.0, cy=1500.0).grid(3500.0, 10.0)
    base = Base("B", 0.0, 0.0, 90.0, Loiter(300.0, 0.0, 90.0, 100.0))
    m = Mission(MissionSpec(waypoints_en=((1500.0, 1500.0),), orbit_radius_m=150.0, orbit_turns=1.0,
                            home_hold_s=20.0), base, t)
    assert m.transit_alt == pytest.approx(1400.0 + 120.0, abs=2)
    r = simulate(ac, t, m, wind, t_max=1500.0)
    L = r.log
    assert r.outcome == "mission complete", r.events
    flying = L["t"] > 5
    assert np.nanmin(L["agl"][flying]) > 20.0
    assert np.nanmin(L["Va"][flying]) > ac.limits.v_min - 1.0 and np.nanmax(L["Va"]) < ac.limits.v_max
    assert np.nanmax(np.abs(L["phi"])) < ac.limits.bank_max + math.radians(5)
    phases = [e[1].split(" -> ")[1] for e in r.events]
    assert phases == ["climb", "transit", "orbit", "return", "home", "done"]
