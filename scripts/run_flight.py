#!/usr/bin/env python3
"""Fly a closed-loop mission (aircraft + scenario + wind) and write plots to outputs/<run>/."""

from __future__ import annotations

import argparse
import logging
import math
import time
from datetime import datetime, timezone

import numpy as np

from sargnc.paths import outputs_dir
from sargnc.sim.config import load_flight
from sargnc.sim.mission import Mission
from sargnc.sim.simulator import simulate
from sargnc.terrain.build import load_terrain
from sargnc.viz.flight import flight_map, time_histories, track_traces
from sargnc.viz.plot3d import terrain_figure, write_html, write_png
from sargnc.viz.site import Artifact, Manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("config", help="flight YAML (configs/flights/*.yaml)")
    ap.add_argument("--run", help="run name (default: config name)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for noisy in ("kaleido", "choreographer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    fc = load_flight(args.config)
    sc, ac = fc.scenario, fc.aircraft
    t = load_terrain(sc.site.map)
    mission = Mission(fc.mission, sc.site.base, t)
    t0 = time.perf_counter()
    res = simulate(ac, t, mission, fc.wind, fc.control_hz, fc.substeps, fc.t_max)
    wall = time.perf_counter() - t0
    L = res.log
    run = args.run or fc.name
    out = outputs_dir() / run
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / "log.npz", **{k: (v.astype(str) if v.dtype == object else v) for k, v in L.items()})

    title = f"{ac.name} · {fc.name.replace('_', ' ')}"
    flight_map(t, res, out / "flight_map.png", title, sc.search, sc.site.base)
    time_histories(res, out / "time_histories.png", title, math.degrees(ac.limits.bank_max), ac.limits.v_min)
    _, fig = write_html(lambda n: terrain_figure(t, title, sc.search, sc.site.base, track_traces(res), n),
                        out / "flight_3d.html", title, 401)
    fig.update_layout(scene_camera=dict(eye=dict(x=1.25, y=-0.8, z=0.95)))
    png3d = write_png(fig, out / "flight_3d.png")

    flying = L["t"] > 5.0
    summary = {
        "outcome": f"{res.outcome} at {L['t'][-1] / 60:.1f} min (simulated in {wall:.1f} s)",
        "wind": f"{fc.wind.speed_mps:g} m/s from {fc.wind.from_deg:g}° (steady)",
        "altitudes": f"transit {res.meta['transit_alt']:.0f} · target orbit {res.meta['target_alt']:.0f} · "
                     f"home hold {res.meta['home_alt']:.0f} m",
        "min height above ground": f"{np.nanmin(L['agl'][flying]):.0f} m (after launch)",
        "airspeed range": f"{np.nanmin(L['Va'][flying]):.1f}–{np.nanmax(L['Va'][flying]):.1f} m/s",
        "max bank": f"{math.degrees(np.nanmax(np.abs(L['phi']))):.0f}°",
        "energy used": f"{L['energy_Wh'][-1]:.1f} Wh of {ac.usable_energy_J / 3600:.0f} Wh usable",
        "phases": " → ".join(f"{e[1].split(' -> ')[1]} {e[0] / 60:.1f}′" for e in res.events),
    }
    Manifest(
        run=run, title=title, created=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), summary=summary,
        artifacts=[a for a in [
            Artifact("flight_map.png", "Ground track", "image",
                     "Track coloured by mission phase over the terrain (100 m contours). Star = base camp, "
                     "dashed circle = home loiter over Seealpsee, black outline = search region."),
            Artifact("flight_3d.html", "Open interactive 3-D flight", "html",
                     "Track over true-scale terrain; tap the line for time, altitude, AGL and airspeed."),
            png3d and Artifact("flight_3d.png", "3-D preview", "image", "Static 3-D view of the flight."),
            Artifact("time_histories.png", "Time histories", "image",
                     "Altitude vs ground below, height above ground, airspeed, bank, pitch, battery power and "
                     "energy. Background bands = mission phases."),
        ] if a],
    ).write(out)
    for k, v in summary.items():
        print(f"{k:24s} {v}")


if __name__ == "__main__":
    main()
