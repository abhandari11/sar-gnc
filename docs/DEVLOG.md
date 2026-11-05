# Dev log

## 2026-11-05: session 1: skeleton, terrain, terrain API, first visualisation
- **Environment:** the shell had ROS 2 Humble + `~/Projects/ros2_workspace` sourced from `~/.bashrc`.
  This set PYTHONPATH, ROS_*, AMENT_*, COLCON_PREFIX_PATH, CMAKE_PREFIX_PATH, LD_LIBRARY_PATH
  (including `px4_ws/src/acados/lib`) and ACADOS_SOURCE_DIR. I wrote `scripts/env.sh` to neutralise
  them for its shell only, and confirmed the venv's `sys.path` contains no ROS entries. System Python
  is 3.10.12. The global `gh` token had expired, so gh now uses a project-local config.
- **Packages:** numpy 2.2.6, numba 0.68.1, rasterio 1.4.4 (bundled GDAL 3.10.3), pyproj 3.7.1,
  plotly 7.1.0, kaleido ≥1 with Chrome in `.cache/chrome`.
- **Terrain:** swissALTI3D 2 m via STAC, 30 tiles (2026 release), cached as an 801² 5 m ENU grid. The
  grid matches the raw DEM to a median |Δ| of 0.43 m.
- **API:** `TerrainGrid` (elevation/gradient/slope/aspect/normal/AGL, save/load). Numba kernels for
  bilinear and Catmull-Rom sampling. Exact DDA ray caster; `ray_intersect` and `line_of_sight`
  broadcast over (..., 3).
- **Tests:** 23 passing: plane exactness, Gaussian accuracy, cone slope/normal/aspect, AGL, ray vs
  analytic plane and vs dense march, vertical/upward/buried rays, LOS over a hill, frames (round trip,
  curvature, LV95), config validation, site index.
- **Visualisation:** `run_scenario.py` writes `terrain_map.png`, `terrain_3d.html` (1 MB) and
  `terrain_3d.png`. `publish.py` copies them to `docs/site/` and rebuilds `index.html`.
- **Bugs found and fixed this session:**
  - Hillshade was lit from the SW instead of the NW because `LightSource` assumes row 0 = north. It now
    shades the flipped array.
  - The 3-D title overlapped the plotly toolbar at phone width. The toolbar is now vertical.
- **GitHub:** gh 2.4 (Ubuntu package) device login into `.gh/`. The first code expired, the second
  worked. Created the public repo `abhandari11/sar-gnc` and enabled Pages from `/docs`. Results are at
  https://abhandari11.github.io/sar-gnc/site/. `~/.gitconfig` and `~/.config/gh` are unchanged.
- **Next:** T3 scenario schema (priors, no-fly zones, targets, wind block).

## 2026-11-05: session 2: base camp, polygon search regions, Gildo, basic flight simulator
- **User direction:**
  - A mountaineering/ski base camp at about (1000 E, 2000 N), fixed for all operations; the UAV
    launches from and returns to it.
  - The search area becomes user-defined later.
  - Start on the aircraft (named "Gildo"), its flight dynamics and a basic simulator.
- **Base:**
  - The requested point was the north edge of the old 4 × 4 km map, at the west end of Seealpsee on a
    13–15° slope.
  - Added a level-pad siting helper; it put the base at (1020, 1945), 1147 m.
  - Extended the map to 4.6 × 5.4 km. The new edge-margin validation caught a 900 m margin on the
    loiter circle, hence the east extent of 2600.
  - Added lake shading on maps (dead-flat connected regions); it reproduces Seealpsee at
    1141.9 m, ≈ 0.11 km².
- **Refactor:**
  - `MapSpec` replaces `AreaSpec`.
  - Sites, scenarios and flights are separate configs.
  - `SearchRegion` handles polygons.
- **Gildo v0:**
  - Spec, model, trim, linearisation and performance; see docs/GILDO.md.
  - Two spec corrections after the first numbers: motor KV 420 → 380, v_min 14 → 15.5 m/s.
- **Simulator:** autopilot, guidance, mission manager and simulator.
- **First demo flight completed:** 15.6 min, 27.8 Wh, minimum 29 m above ground after launch.
- **Bugs and tuning fixed after reading the plots:**
  - Hold-zone altitude gain was too high (20° dive for a 21 m step).
  - Climb-zone integrator windup after a launch over-speed.
  - Pitch-for-airspeed off the launcher flew into the ground (fixed pitch restored at 15°).
  - Phase labels overlapped the panel title.
  - `publish.py` copied the 7 MB raw log; it now copies only manifest-listed files.
  - The parallel terrain kernel was used for single points, causing thread churn.
- **Tests:** 42 passing (14 new for the aircraft and simulator, plus site/region tests). The
  aircraft tests check ballistic free fall, torque-free momentum conservation, trim lift = weight,
  turn bank and mode stability, plus a performance regression. The simulator tests are an
  end-to-end mission over a synthetic hill, flown calm and in 7 m/s wind.
- **Not done:** the dataviz palette validator needs Node ≥ 14 and the system has 12, so it didn't run.
  The six phase colours are the skill's pre-validated default slots 1–6, in order.
- **Next:**
  - Discuss Gildo's spec open questions.
  - T3c priors, no-fly zones and targets.
  - T4 Dryden + terrain wind into the sim.
  - Recovery at base.
