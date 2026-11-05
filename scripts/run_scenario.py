#!/usr/bin/env python3
"""Run a scenario YAML and write all Stage 1 outputs into outputs/<run>/."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone

import numpy as np

from sargnc.paths import outputs_dir
from sargnc.scenario import load_area
from sargnc.terrain.build import load_terrain
from sargnc.viz.map2d import terrain_map
from sargnc.viz.plot3d import write_terrain_html, write_terrain_png
from sargnc.viz.site import Artifact, Manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("config", help="scenario YAML")
    ap.add_argument("--run", help="run name (default: area name)")
    ap.add_argument("--max-nodes", type=int, default=401, help="3-D mesh nodes per axis before decimation")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for noisy in ("kaleido", "choreographer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    area = load_area(args.config)
    run = args.run or area.name
    out = outputs_dir() / run
    out.mkdir(parents=True, exist_ok=True)
    t = load_terrain(area)
    sb = area.search_bounds

    e0, e1, n0, n1 = sb
    xx, yy = np.meshgrid(np.arange(e0, e1 + 1, t.d), np.arange(n0, n1 + 1, t.d))
    zs = t.elevation(xx, yy)
    slope = np.degrees(t.slope(xx, yy))
    summary = {
        "centre": f"{area.center_lat:.4f} N, {area.center_lon:.4f} E",
        "search area": f"{area.size_e_m / 1000:.1f} × {area.size_n_m / 1000:.1f} km",
        "DEM domain": f"{(t.bounds[1] - t.bounds[0]) / 1000:.1f} × {(t.bounds[3] - t.bounds[2]) / 1000:.1f} km "
                      f"(buffer {area.buffer_m:.0f} m)",
        "grid": f"{t.shape[1]} × {t.shape[0]} @ {t.d:g} m",
        "source": f"{t.meta.get('source')} {t.meta.get('native_resolution_m', 0):g} m",
        "search-area elevation": f"{np.nanmin(zs):.0f}–{np.nanmax(zs):.0f} m",
        "slope median / p90": f"{np.nanmedian(slope):.0f}° / {np.nanpercentile(slope, 90):.0f}°",
    }

    title = area.name.replace("_", " ").title()
    terrain_map(t, out / "terrain_map.png", title, sb)
    _, fig3d = write_terrain_html(t, out / "terrain_3d.html", title, sb, args.max_nodes)
    size_mb = (out / "terrain_3d.html").stat().st_size / 1e6
    png3d = write_terrain_png(fig3d, out / "terrain_3d.png")
    Manifest(
        run=run, title=title, created=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), summary=summary,
        artifacts=[a for a in [
            Artifact("terrain_map.png", "Terrain map", "image",
                     "Tinted hillshade, 50 m contours (250 m labelled). Black box = search area; + = ENU origin."),
            Artifact("terrain_3d.html", "Open interactive 3-D terrain", "html",
                     f"Drag to rotate, pinch to zoom. True vertical scale. {size_mb:.1f} MB."),
            png3d and Artifact("terrain_3d.png", "3-D preview", "image",
                               "Static render of the 3-D view from the south-east; black line = search area."),
        ] if a],
    ).write(out)
    print(out)


if __name__ == "__main__":
    main()
