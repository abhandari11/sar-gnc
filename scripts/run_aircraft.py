#!/usr/bin/env python3
"""Aircraft report: spec sheet, steady performance charts and dynamic modes -> outputs/<run>/."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone

from sargnc.aircraft import load_aircraft
from sargnc.aircraft.performance import analyze
from sargnc.aircraft.trim import dynamic_modes, linearize, trim
from sargnc.paths import outputs_dir
from sargnc.viz.performance import performance_figure
from sargnc.viz.site import Artifact, Manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("aircraft", nargs="?", default="gildo", help="name in configs/aircraft/ or a YAML path")
    ap.add_argument("--altitudes", type=float, nargs="+", default=[1150.0, 2000.0, 2500.0])
    args = ap.parse_args()

    ac = load_aircraft(args.aircraft)
    run = ac.name.lower().replace(" ", "_") + "_performance"
    out = outputs_dir() / run
    out.mkdir(parents=True, exist_ok=True)
    perf = analyze(ac, tuple(args.altitudes))
    performance_figure(perf, out / "performance.png", ac.limits.v_cruise, ac.limits.v_min)

    h_ref = 2000.0
    t = trim(ac, ac.limits.v_cruise, h_ref)
    modes = dynamic_modes(linearize(ac, t)[0])
    s2 = next(s for s in perf.summaries if s.h == h_ref) if h_ref in args.altitudes else perf.summaries[0]
    mb = ac.mass_budget
    summary = {
        "mass": f"{ac.mass:.2f} kg (" + ", ".join(f"{k} {v:.2f}" for k, v in mb.items()) + ")",
        "wing": f"span {ac['b']:.2f} m · area {ac['S']:.2f} m² · AR {ac.aspect_ratio:.1f} · "
                f"loading {ac.weight / ac['S']:.0f} N/m²",
        "battery": f"{ac.energy_J / 3600:.0f} Wh ({ac.usable_fraction:.0%} usable) · hotel {ac['P_hotel']:.0f} W",
        "stall (1 g)": " · ".join(f"{s.v_stall:.1f} m/s @ {s.h:.0f} m" for s in perf.summaries),
        "speeds": f"min {ac.limits.v_min:g} · cruise {ac.limits.v_cruise:g} · max level {s2.v_max_level:.1f} m/s "
                  f"@ {s2.h:.0f} m",
        "cruise @ 2000 m": f"{s2.p_cruise:.0f} W · {s2.endurance_cruise_min:.0f} min · {s2.range_cruise_km:.0f} km",
        "best endurance": f"{s2.endurance_max_min:.0f} min at {s2.v_best_endurance:.1f} m/s",
        "best range": f"{s2.range_max_km:.0f} km at {s2.v_best_range:.1f} m/s",
        "max climb": " · ".join(f"{s.climb_max:.1f} m/s @ {s.h:.0f} m" for s in perf.summaries),
        "ceiling (0.5 m/s)": (f"> {perf.ceiling_m:.0f} m ISA (no motor power lapse modelled)" if perf.ceiling_m >= 6000
                              else f"{perf.ceiling_m:.0f} m ISA"),
        "full-throttle current": f"{max(float(c.current_max[c.current_max == c.current_max].max()) for c in perf.curves):.0f} A "
                                 f"(limit {ac.max_current:.0f} A)",
        "turn radius": f"{perf.turn['cruise_radius_30deg_m']:.0f} m at 30° / "
                       f"{perf.turn['cruise_radius_bankmax_m']:.0f} m at {math.degrees(ac.limits.bank_max):.0f}° "
                       f"(cruise) · min {perf.turn['min_radius_m']:.0f} m",
        "trim @ cruise": f"α {math.degrees(t.alpha):.1f}° · δe {math.degrees(t.de):.1f}° · throttle {t.dt:.2f}",
    }
    for m in modes:
        if m.name in ("spiral", "roll"):
            kind = "doubles" if m.eig.real > 0 else "halves"
            summary[f"mode: {m.name}"] = f"{kind} in {m.time_const:.1f} s"
        else:
            summary[f"mode: {m.name}"] = f"ωn {m.wn:.2f} rad/s · ζ {m.zeta:.2f}"
    (out / "performance.json").write_text(json.dumps(
        {"summary": summary, "summaries": [s.__dict__ for s in perf.summaries], "ceiling_m": perf.ceiling_m,
         "turn": perf.turn, "modes": [dict(name=m.name, re=m.eig.real, im=m.eig.imag, wn=m.wn, zeta=m.zeta)
                                      for m in modes]}, indent=2))
    Manifest(
        run=run, title=f"{ac.name} — aircraft", created=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        summary=summary,
        artifacts=[Artifact("performance.png", "Steady performance", "image",
                            "Level-flight battery power, endurance and range, and full-throttle climb vs airspeed "
                            "at base (1150 m), 2000 m and 2500 m. Dashed = cruise, dotted = minimum airspeed.")],
    ).write(out)
    for k, v in summary.items():
        print(f"{k:20s} {v}")


if __name__ == "__main__":
    main()
