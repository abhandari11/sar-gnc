#!/usr/bin/env python3
"""Run a scenario YAML and write all Stage 1 outputs into outputs/<run>/."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone

import numpy as np

from sargnc.paths import outputs_dir
from sargnc.scenario import load_scenario
from sargnc.terrain.build import load_terrain
from sargnc.viz.map2d import terrain_map
from sargnc.viz.plot3d import terrain_figure, write_html, write_png
from sargnc.viz.site import Artifact, Manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("config", help="scenario YAML")
    ap.add_argument("--run", help="run name (default: scenario name)")
    ap.add_argument("--max-nodes", type=int, default=401, help="3-D mesh nodes per axis before decimation")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for noisy in ("kaleido", "choreographer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    sc = load_scenario(args.config)
    site, region, base = sc.site, sc.search, sc.site.base
    run = args.run or sc.name
    out = outputs_dir() / run
    out.mkdir(parents=True, exist_ok=True)
    t = load_terrain(site.map)

    e0, e1, n0, n1 = region.bounds
    xx, yy = np.meshgrid(np.arange(e0, e1 + 1, t.d), np.arange(n0, n1 + 1, t.d))
    inside = region.contains(xx, yy)
    zs = t.elevation(xx, yy)[inside]
    slope = np.degrees(t.slope(xx, yy))[inside]
    b0, b1, c0, c1 = t.bounds
    summary = {
        "site": f"{site.name} · origin {site.map.origin_lat:.4f} N, {site.map.origin_lon:.4f} E",
        "map": f"{(b1 - b0) / 1000:.1f} × {(c1 - c0) / 1000:.1f} km · {t.shape[1]} × {t.shape[0]} @ {t.d:g} m",
        "base": f"{base.name} · E {base.east:.0f} N {base.north:.0f} · {float(t.elevation(base.east, base.north)):.0f} m",
        "search region": f"{region.name} · {region.area_m2 / 1e6:.2f} km²",
        "search elevation": f"{zs.min():.0f}–{zs.max():.0f} m",
        "slope median / p90": f"{np.median(slope):.0f}° / {np.percentile(slope, 90):.0f}°",
        "source": f"{t.meta.get('source')} {t.meta.get('native_resolution_m', 0):g} m",
    }

    title = sc.name.replace("_", " ").title()
    terrain_map(t, out / "terrain_map.png", title, region, base)
    _, fig3d = write_html(lambda n: terrain_figure(t, title, region, base, max_nodes=n),
                          out / "terrain_3d.html", title, args.max_nodes)
    size_mb = (out / "terrain_3d.html").stat().st_size / 1e6
    png3d = write_png(fig3d, out / "terrain_3d.png")
    Manifest(
        run=run, title=title, created=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), summary=summary,
        artifacts=[a for a in [
            Artifact("terrain_map.png", "Terrain map", "image",
                     "Tinted hillshade, 50 m contours (250 m labelled). Red star = base camp, dashed circle = "
                     "climb-out/return loiter, black outline = search region, + = ENU origin."),
            Artifact("terrain_3d.html", "Open interactive 3-D terrain", "html",
                     f"Drag to rotate, pinch to zoom. True vertical scale. {size_mb:.1f} MB."),
            png3d and Artifact("terrain_3d.png", "3-D preview", "image",
                               "Static 3-D view from the south-east; red diamond = base, black line = search region."),
        ] if a],
    ).write(out)
    print(out)


if __name__ == "__main__":
    main()
