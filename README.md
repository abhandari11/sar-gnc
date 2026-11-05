# sar-gnc

Terrain-aware guidance, navigation and control for a small flying-wing UAV doing search and rescue in
mountainous terrain.

**Status: Stage 1, simulation environment.** Real DEM terrain in a local ENU frame, fast terrain
queries, and exact ray casting / line of sight are done. Scenario, wind and the full visualisation
set are next. See [docs/ROADMAP.md](docs/ROADMAP.md).

Published results (phone-friendly): **https://abhandari11.github.io/sar-gnc/site/** (source: [docs/site/](docs/site/index.html)).

## Setup (Ubuntu 22.04, headless, no GPU)
```bash
cd ~/projects/sar-gnc
python3 -m venv .venv
source scripts/env.sh          # isolates the shell from ROS/PX4 and activates the venv
pip install -e ".[dev]"
pip install "kaleido>=1" && plotly_get_chrome -y --path .cache/chrome   # optional static 3-D PNGs
```

## Use
```bash
source scripts/env.sh
python scripts/run_scenario.py configs/alpstein_meglisalp.yaml   # writes outputs/alpstein_meglisalp/
python scripts/publish.py                                        # copies to docs/site/, rebuilds index
pytest
```

## Terrain API
```python
from sargnc.scenario import load_area
from sargnc.terrain.build import load_terrain
from sargnc.terrain import line_of_sight, ray_intersect

t = load_terrain(load_area("configs/alpstein_meglisalp.yaml"))   # TerrainGrid, ENU metres
t.elevation(e, n)            # bilinear (default) or method="bicubic"; NaN off-grid
t.gradient(e, n); t.slope(e, n); t.aspect(e, n); t.normal(e, n)
t.agl(points)                # points (..., 3)
r, hit = ray_intersect(t, origins, directions, max_range)   # exact vs the bilinear surface
vis = line_of_sight(t, p0, p1)                               # broadcasts (..., 3)
```

## Layout
```
scripts/      env.sh, fetch_dem.py, run_scenario.py, publish.py
src/sargnc/   terrain/ scenario/ wind/ viz/
configs/      scenario YAMLs
data/         DEM tiles + cached grids (gitignored)
outputs/      run outputs (gitignored)
docs/         ROADMAP, DEVLOG, DECISIONS, site/ (published pages)
tests/
```

Terrain data: swissALTI3D © swisstopo (open government data).
