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
- **Next:** GitHub push (needs gh device login + visibility choice), then T3 scenario schema.
