# Roadmap

## Stage 1: simulation environment
- [x] Isolated project skeleton, venv, `scripts/env.sh` (ROS/PX4 variables neutralised)
- [x] **T1 Terrain:** swissALTI3D 2 m → 5 m ENU grid, 1.4 × 1.4 km search area + 1.3 km buffer, cached
- [x] **T2 Terrain API:** bilinear/bicubic elevation, gradient, slope, aspect, normal, AGL
- [x] **T2** Exact vectorised ray/terrain intersection + line of sight (numba, parallel)
- [x] **T2** Unit tests on plane / cone / Gaussian hill
- [x] First visualisation: hillshade + contours map PNG, interactive 3-D plotly page, 3-D preview PNG
- [x] `scripts/publish.py` → `docs/site/` with a mobile index page
- [x] Public GitHub repo + Pages from `/docs`: https://abhandari11.github.io/sar-gnc/site/
- [x] **T3a Site + base:** fixed map extent, base camp Seealpsee (1020, 1945) with level-pad siting,
      launch heading, home loiter over the lake; star on the map; lake (water) shading
- [x] **T3b Search region as polygons** (rectangle is a placeholder; user-drawn input later)
- [ ] **T3c** Priors (weighted polygons + Gaussian blobs → normalised grid), no-fly zones, hidden
      targets, wind block in the scenario YAML
- [ ] **T3d** User input for search areas (lat/lon polygons in YAML first, then phone-friendly drawing)
- [ ] **T4 Wind:** steady + Dryden (seeded), `TerrainWindModel` interface + ridge-lift/lee-sink placeholder
- [ ] **T5 Viz:** prior heatmap / no-fly / launch / target overlays on the 2-D map; priors draped in 3-D;
      slope map; visibility map (fraction of the search area visible from altitude X)
- [ ] **T6** Second example scenario (different terrain character), `run_scenario.py` produces everything

## Stage 2: 6-DOF flight sim and autopilot (started 2026-11-05, ahead of T3c–T5 at the user's request)
- [x] Gildo v0 spec + config (`configs/aircraft/gildo.yaml`, `docs/GILDO.md`)
- [x] 6-DOF quaternion model, Beard & McLain flying-wing aero, motor/prop/battery energy (numba RK4)
- [x] Trim (straight, climb, turn, fixed-throttle), linearisation, dynamic modes
- [x] Performance analysis + phone chart (power, endurance, range, climb vs airspeed and altitude)
- [x] Successive-loop-closure autopilot, vector-field line/orbit guidance
- [x] Mission manager: launch → climb over lake → transit → orbit → return → home hold, terrain-safe altitudes
- [x] Demo flight with steady wind; map / 3-D / time-history outputs
- [ ] Dryden turbulence + terrain wind field (T4) wired into the sim
- [ ] Recovery/landing at base (method TBD, see GILDO open question 2)
- [ ] Tangent orbit entry, Dubins-style transitions, wind-aware orbit speed
- [ ] Sensor model (camera footprint on terrain, using `ray_intersect`) for Stage 3
- [ ] AVL/XFLR5 aero for a real Gildo planform

## Stage 3: factor-graph search planner (not started)
- Combines vehicle performance/energy, terrain, wind, sensor detection model and the scenario prior

## Open questions
0. Gildo spec questions (payload mass, launch/recovery, cruise speed vs wind, cold derating):
   see docs/GILDO.md.
1. Sensor model for Stage 3: camera FOV and detection probability vs. range and incidence angle. This
   decides whether LOS should target a point on the ground or a person-height offset.
2. Vertical datum: heights are LN02 (≈ MSL). When Stage 2 simulates GNSS, decide whether to add a
   geoid model (EGM2008) or keep everything in orthometric height.
3. Is a second test area wanted outside Switzerland (e.g. USGS 3DEP, US Rockies)? That needs a second
   `DemSource`.
4. Vehicle class assumptions (wingspan, cruise speed, minimum turn radius) set the buffer and
   resolution; 1.3 km and 5 m are placeholders until Stage 2 picks the airframe.
