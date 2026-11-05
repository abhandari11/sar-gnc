"""Flight-run YAML: scenario + aircraft + wind + mission + sim settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sargnc.aircraft import Aircraft, load_aircraft
from sargnc.paths import project_root
from sargnc.scenario import Scenario, ScenarioError, load_scenario
from sargnc.scenario.config import _en, _num, _section, read_yaml
from sargnc.sim.mission import MissionSpec
from sargnc.wind import SteadyWind


@dataclass
class FlightConfig:
    name: str
    scenario: Scenario
    aircraft: Aircraft
    wind: SteadyWind
    mission: MissionSpec
    control_hz: float
    substeps: int
    t_max: float


def load_flight(path: str | Path) -> FlightConfig:
    path = Path(path)
    w = path.name
    d = _section(read_yaml(path), w, {"name", "scenario", "aircraft", "mission"}, {"wind", "sim"})
    sc_path = project_root() / "configs" / f"{d['scenario']}.yaml"
    if not sc_path.exists():
        raise ScenarioError(f"{w}: scenario '{d['scenario']}' not found at {sc_path}")
    wd = _section(d.get("wind", {"speed_mps": 0, "from_deg": 0}), f"{w}:wind", {"speed_mps", "from_deg"})
    m = _section(d["mission"], f"{w}:mission", {"waypoints_m"},
                 {"airspeed_mps", "terrain_clearance_m", "corridor_half_width_m", "orbit", "home_hold_s"})
    if not isinstance(m["waypoints_m"], list) or not m["waypoints_m"]:
        raise ScenarioError(f"{w}:mission.waypoints_m: need at least one {{east, north}} waypoint")
    wps = tuple(_en(p, f"{w}:mission.waypoints_m[{i}]") for i, p in enumerate(m["waypoints_m"]))
    orb = _section(m.get("orbit", {"radius_m": 150, "turns": 2}), f"{w}:mission.orbit", {"radius_m", "turns"})
    spec = MissionSpec(
        airspeed=_num(m.get("airspeed_mps", 18.0), f"{w}:mission.airspeed_mps"),
        clearance_m=_num(m.get("terrain_clearance_m", 120.0), f"{w}:mission.terrain_clearance_m"),
        corridor_half_width_m=_num(m.get("corridor_half_width_m", 150.0), f"{w}:mission.corridor_half_width_m"),
        waypoints_en=wps,
        orbit_radius_m=_num(orb["radius_m"], f"{w}:mission.orbit.radius_m"),
        orbit_turns=_num(orb["turns"], f"{w}:mission.orbit.turns"),
        home_hold_s=_num(m.get("home_hold_s", 60.0), f"{w}:mission.home_hold_s"),
    )
    ac = load_aircraft(str(d["aircraft"]))
    if not ac.limits.v_min <= spec.airspeed <= ac.limits.v_max:
        raise ScenarioError(f"{w}:mission.airspeed_mps {spec.airspeed} outside {ac.name} limits "
                            f"[{ac.limits.v_min}, {ac.limits.v_max}]")
    s = _section(d.get("sim", {}), f"{w}:sim", set(), {"control_hz", "substeps", "t_max_s"})
    return FlightConfig(str(d["name"]), load_scenario(sc_path), ac,
                        SteadyWind(_num(wd["speed_mps"], f"{w}:wind.speed_mps"), _num(wd["from_deg"], f"{w}:wind.from_deg")),
                        spec, _num(s.get("control_hz", 50), f"{w}:sim.control_hz"), int(s.get("substeps", 4)),
                        _num(s.get("t_max_s", 1800), f"{w}:sim.t_max_s"))
