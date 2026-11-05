# sar-gnc

Terrain-aware guidance, navigation and control for a small flying-wing UAV doing search and rescue in
mountainous terrain.

**Status:**
- Done:
  - Real DEM terrain (Alpstein, CH) in a local ENU frame, with exact line of sight.
  - A fixed base camp at Seealpsee.
  - Polygon search regions.
- Started (Stage 2):
  - **Gildo**, a 2 m electric flying wing ([docs/GILDO.md](docs/GILDO.md)).
  - A 6-DOF model, autopilot and a terrain-safe demo mission.
- Next: priors, targets, turbulence and terrain wind. See [docs/ROADMAP.md](docs/ROADMAP.md).

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
python scripts/run_scenario.py configs/alpstein_meglisalp.yaml   # terrain map + 3-D, base, search region
python scripts/run_aircraft.py gildo                             # Gildo spec, performance, modes
python scripts/run_flight.py configs/flights/gildo_demo_meglisalp.yaml   # closed-loop demo flight
python scripts/publish.py                                        # copies to docs/site/, rebuilds index
pytest
```

## Terrain API
```python
from sargnc.scenario import load_site
from sargnc.terrain.build import load_terrain
from sargnc.terrain import line_of_sight, ray_intersect

site = load_site("configs/sites/alpstein.yaml")   # map + base camp
t = load_terrain(site.map)                        # TerrainGrid, ENU metres
t.elevation(e, n)            # bilinear (default) or method="bicubic"; NaN off-grid
t.gradient(e, n); t.slope(e, n); t.aspect(e, n); t.normal(e, n)
t.agl(points)                # points (..., 3)
r, hit = ray_intersect(t, origins, directions, max_range)   # exact vs the bilinear surface
vis = line_of_sight(t, p0, p1)                               # broadcasts (..., 3)
```

## Layout
```
scripts/      env.sh, fetch_dem.py, run_scenario.py, run_aircraft.py, run_flight.py, publish.py
src/sargnc/   terrain/ scenario/ wind/ aircraft/ sim/ viz/
configs/      sites/, aircraft/, flights/, scenario YAMLs
data/         DEM tiles + cached grids (gitignored)
outputs/      run outputs (gitignored)
docs/         ROADMAP, DEVLOG, DECISIONS, site/ (published pages)
tests/
```

Terrain data: swissALTI3D © swisstopo (open government data).
