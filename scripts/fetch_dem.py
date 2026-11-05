#!/usr/bin/env python3
"""Download the DEM for a site (or a scenario's site) and cache the ENU terrain grid."""

from __future__ import annotations

import argparse
import logging

from sargnc.scenario import load_scenario, load_site
from sargnc.scenario.config import read_yaml
from sargnc.terrain.build import load_terrain, terrain_cache_path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("config", help="site YAML (configs/sites/*.yaml) or scenario YAML")
    ap.add_argument("--rebuild", action="store_true", help="ignore the cached grid")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    site = load_site(args.config) if "base" in read_yaml(args.config) else load_scenario(args.config).site
    t = load_terrain(site.map, rebuild=args.rebuild)
    b = site.base
    print(terrain_cache_path(site.map))
    print(f"grid {t.shape[1]}x{t.shape[0]} @ {t.d} m, z {t.z.min():.0f}..{t.z.max():.0f} m")
    print(f"base '{b.name}' at E {b.east:.0f} N {b.north:.0f}, ground {float(t.elevation(b.east, b.north)):.0f} m")


if __name__ == "__main__":
    main()
