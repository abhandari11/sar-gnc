#!/usr/bin/env python3
"""Copy run outputs into docs/site/<run>/ and rebuild the mobile index page."""

from __future__ import annotations

import argparse
import shutil

from sargnc.paths import outputs_dir, project_root
from sargnc.viz.site import Manifest, write_index


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("runs", nargs="*", help="run names (default: most recently modified run)")
    args = ap.parse_args()
    site = project_root() / "docs" / "site"
    runs = args.runs or [max((p for p in outputs_dir().glob("*/manifest.json")),
                             key=lambda p: p.stat().st_mtime).parent.name]
    for run in runs:
        src = outputs_dir() / run
        if not (src / "manifest.json").exists():
            raise SystemExit(f"{src} has no manifest.json; run scripts/run_scenario.py first")
        dst = site / run
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True)
        files = ["manifest.json"] + [a.file for a in Manifest.read(src).artifacts]
        for f in files:
            shutil.copy2(src / f, dst / f)
        print(f"published {run} -> {dst} ({len(files)} files)")
    (site / ".nojekyll").touch()
    print(write_index(site))


if __name__ == "__main__":
    main()
