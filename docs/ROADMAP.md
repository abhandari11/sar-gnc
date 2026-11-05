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
- [ ] **T3 Scenario YAML:** launch/home, priors (weighted polygons + Gaussian blobs → normalised grid),
      no-fly zones, hidden targets, wind block, validation with clear errors
- [ ] **T4 Wind:** steady + Dryden (seeded), `TerrainWindModel` interface + ridge-lift/lee-sink placeholder
- [ ] **T5 Viz:** prior heatmap / no-fly / launch / target overlays on the 2-D map; priors draped in 3-D;
      slope map; visibility map (fraction of the search area visible from altitude X)
- [ ] **T6** Second example scenario (different terrain character), `run_scenario.py` produces everything

## Stage 2: 6-DOF flight sim and autopilot (not started)
- Flying-wing 6-DOF model, energy/battery model, autopilot (TECS + L1/NPFG-style lateral)
- Consumes `TerrainGrid.agl`, `line_of_sight` and the wind interface (`WindField.sample(p, t)`)

## Stage 3: factor-graph search planner (not started)
- Combines vehicle performance/energy, terrain, wind, sensor detection model and the scenario prior

## Open questions
1. Sensor model for Stage 3: camera FOV and detection probability vs. range and incidence angle. This
   decides whether LOS should target a point on the ground or a person-height offset.
2. Vertical datum: heights are LN02 (≈ MSL). When Stage 2 simulates GNSS, decide whether to add a
   geoid model (EGM2008) or keep everything in orthometric height.
3. Is a second test area wanted outside Switzerland (e.g. USGS 3DEP, US Rockies)? That needs a second
   `DemSource`.
4. Vehicle class assumptions (wingspan, cruise speed, minimum turn radius) set the buffer and
   resolution; 1.3 km and 5 m are placeholders until Stage 2 picks the airframe.
