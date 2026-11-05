#!/usr/bin/env python3
"""Download the DEM for a scenario's area and cache the ENU terrain grid."""

from __future__ import annotations

import argparse
import logging

import numpy as np

from sargnc.scenario import load_area
from sargnc.terrain.build import load_terrain, terrain_cache_path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("config", help="scenario YAML")
    ap.add_argument("--rebuild", action="store_true", help="ignore the cached grid")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    area = load_area(args.config)
    t = load_terrain(area, rebuild=args.rebuild)
    e0, e1, n0, n1 = area.search_bounds
    xx, yy = np.meshgrid(np.arange(e0, e1 + 1, t.d), np.arange(n0, n1 + 1, t.d))
    zs = t.elevation(xx, yy)
    print(f"{terrain_cache_path(area)}")
    print(f"grid {t.shape[1]}x{t.shape[0]} @ {t.d} m, domain z {t.z.min():.0f}..{t.z.max():.0f} m")
    print(f"search area z {np.nanmin(zs):.0f}..{np.nanmax(zs):.0f} m, "
          f"median slope {np.degrees(np.nanmedian(t.slope(xx, yy))):.1f} deg")


if __name__ == "__main__":
    main()
