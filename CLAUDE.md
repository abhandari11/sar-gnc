# CLAUDE.md — sar-gnc

Terrain-aware GNC for a small flying-wing UAV doing search and rescue in mountains.
Stage 1 (current): simulation environment, covering terrain, scenario, wind and visualisation.
Stage 2: 6-DOF flight sim and autopilot. Stage 3: factor-graph search planner. See `docs/ROADMAP.md`.

## Isolation rules (strict)
- This machine also hosts a PX4/ROS 2 workspace (`~/Projects/px4_ws`, `~/Projects/ros2_workspace`,
  `/opt/ros/humble`) that is sourced from `~/.bashrc`. **Never read, write, build, run, import or
  symlink anything there.**
- **Every command starts with** `cd ~/projects/sar-gnc && source scripts/env.sh`. env.sh unsets
  PYTHONPATH, ROS_*/AMENT_*/COLCON_*/CMAKE_PREFIX_PATH/LD_LIBRARY_PATH/ACADOS_*, strips ROS from PATH
  and activates `.venv`. It affects only the current shell.
- Don't modify `~/.bashrc`, `~/.profile` or any global config. No global pip, apt or sudo.
  `gh` uses a project-local config (`GH_CONFIG_DIR=.gh/`).
- All caches stay in the tree: `.cache/` (matplotlib, numba, pip, tmp, kaleido's Chrome, Firefox profile).
- Don't start servers on 14540, 14550, 4560 or 11345. For a preview server use 8765, and only temporarily.

## Conventions
- Frame: local **ENU** (x = East, y = North, z = Up) in metres. Origin is the search-area centre at
  height 0 of the DEM vertical datum, so z reads as altitude above sea level (see DECISIONS D5).
- Terrain grid: `z[i, j]` is at `(x0 + j*d, y0 + i*d)`, where row i increases **northward**.
- Angles are in radians in the API, degrees only in configs and plots.
- Python 3.10, type hints, small modules. Numba kernels live in `terrain/_kernels.py`.
- Comments say what code does; rationale goes in `docs/DECISIONS.md`, history in `docs/DEVLOG.md`.
- Plots are phone-first: portrait PNGs about 1500 px wide, plotly pages under 10 MB with plotly.js
  loaded from the CDN.

## Workflow
- `pytest` must pass before every commit. Commit after each working milestone. Never commit DEM data
  (`data/` and `*.tif`/`*.npz` are gitignored).
- Keep these up to date: `docs/ROADMAP.md` (checklist + open questions), `docs/DEVLOG.md` (one
  dated entry per session) and `docs/DECISIONS.md` (numbered decisions).
- On a design choice, pick a sensible default, log it in DECISIONS and continue. Flag it in the summary.

## Commands
```bash
source scripts/env.sh
pytest
python scripts/fetch_dem.py configs/alpstein_meglisalp.yaml       # download + cache terrain
python scripts/run_scenario.py configs/alpstein_meglisalp.yaml    # -> outputs/<run>/
python scripts/publish.py [run ...]                               # -> docs/site/ + index.html
```
