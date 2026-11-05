# Design decisions

Each decision is a default chosen to keep moving. Revisit by editing the entry and noting it in DEVLOG.

## D1: Test area: Alpstein, Meglisalp basin (Appenzell, CH), centre 47.2493 N, 9.3800 E
- *Updated by D12/D13 (2026-11-05): the map is now a fixed site extent and the search area is a polygon.*
- Rugged without being alpine-glacial. In the 1.4 × 1.4 km search box, elevation runs 1515–2221 m,
  median slope 32° and p90 57°, with karst ridges and cliff bands (the Marwees ridge on the south
  edge). Over the 4 × 4 km domain, z runs 1142–2434 m (Seealpsee valley to Altmann summit).
- The Alpstein is a heavily hiked massif with regular mountain-rescue callouts: steep grass, scree and
  cliffs where a lost or injured hiker is hard to see. That makes it a realistic SAR setting.
- Its features exercise the later stages: lee/ridge flows across SW–NE ridges for wind, strong LOS
  occlusion for detection, and a deep valley for terrain following.
- The first-pass centre (47.2520 N) mostly covered gentle pasture. It was moved 300 m south to take in
  the cliff band.

## D2: DEM source: swissALTI3D 2 m (swisstopo open data, STAC API, no login)
- Native 2 m is finer than the 10 m requirement and needs no account. Tiles are 1 km² COGs in
  LV95/LN02.
- The 2 m product is used, not 0.5 m: 0.5 m has 16× the data with no benefit at a 5 m working
  resolution. 30 tiles = 37 MB.
- The latest release year is used per tile (all 2026 for this area).
- `terrain/sources.py` defines a `DemSource` protocol. USGS 3DEP and Copernicus GLO-30 can be added
  without touching the rest; GLO-30 isn't needed for this area.

## D3: Working resolution 5 m, anti-aliased resampling
- Grid: 801 × 801 nodes = 4.0 × 4.0 km. One grid is 2 MB compressed. Fast enough for numba LOS
  sweeps and fine enough for a ~1–2 m wingspan aircraft.
- Before bilinear sampling, the 2 m source is Gaussian-filtered with σ = 0.5 × (5 / 2) px to avoid
  aliasing.
- Check against the raw 2 m DEM at 2000 random points: median −0.14 m, median |Δ| 0.43 m, p95 2.8 m.
  The tail is cliff edges softened by the filter.

## D4: Buffer 1300 m on every side (requirement ≥ 1000 m)
- Leaves room for loiter and turn-around manoeuvres outside the box and gives a round 4.0 km domain.
- `AreaSpec` rejects buffers below 1000 m.

## D5: Frame: local ENU tangent plane, origin at the search-area centre, h0 = 0 m
- The ENU origin sits at height 0 of the DEM's vertical datum, so z ≈ altitude above mean sea level.
  Altitudes therefore stay readable and match aviation conventions.
- Grid nodes are exact ENU positions. The DEM is resampled through ENU → ECEF → WGS84 → LV95, with a
  2-step fixed point on height so each node's vertical is exact. Earth-curvature drop is included
  (≈ 0.3 m at the domain corner).
- LN02 orthometric heights are treated as ellipsoidal in that transform. The geoid offset is about
  constant (~50 m) over 4 km, so it only shifts the frame vertically; see ROADMAP open question 2.
- Stage 2 will add ENU ↔ NED helpers for the flight dynamics. Planning stays in ENU.

## D6: Interpolation defaults
- `elevation`, `agl` and ray casting use **bilinear** interpolation. The ray caster is exact for that
  surface, so AGL and LOS always agree.
- `gradient`, `slope`, `aspect` and `normal` default to **bicubic** (Catmull-Rom, a = −0.5). It is C1,
  so normals don't jump at cell edges, which matters for a future wind/terrain model and smooth
  guidance.
- Both methods reproduce planes exactly. On a Gaussian hill, bicubic error is < 0.1 m at 10 m spacing.

## D7: Ray casting: exact cell traversal (DDA) plus a per-cell quadratic, not ray marching
- Within a cell, ray height minus bilinear height is a quadratic in t, so the first root gives the exact
  hit. That means no step-size tuning and no missed thin ridges.
- A per-cell max-height bound skips the quadratic when the ray is clearly above the cell.
- The ray is parallelised over rays with `prange`. The test suite checks it against a 1 cm dense march
  and against an analytic plane.

## D8: Line-of-sight semantics
- `line_of_sight(p0, p1, tol=0.5)` ignores a hit within 0.5 m of p1, so a target lying on the surface
  is visible.
- Segment parts outside the DEM count as unobstructed. The domain buffer makes this rare for the search
  area.
- An observer below ground is never visible.

## D9: Visualisation format
- 2-D map: a portrait PNG about 1500 × 1700 px that reads on a phone without zooming. It shows tinted
  hillshade lit from the NW, 50 m contours (250 m labelled), a scale bar and a north arrow.
- Elevation uses one sequential hue (sand → umber), not a rainbow. Priors will use a separate blue
  ramp, so the two never compete.
- 3-D: plotly `Surface` at a 10 m mesh (401²), true vertical scale, about 1 MB HTML with plotly.js
  from the CDN. The writer automatically decimates further if a page would exceed 10 MB.
- A static 3-D PNG comes from kaleido with a project-local Chrome (`.cache/chrome`). It's the fallback
  if the repo is private.
- Headless Firefox can't render WebGL on this machine (no GPU), so kaleido is the visual check.

## D10: Isolation details beyond the brief
- The shell had ROS 2 Humble sourced, which sets PYTHONPATH (including `/opt/ros/humble`
  site-packages), AMENT/COLCON/CMAKE prefixes, LD_LIBRARY_PATH (including a `px4_ws/acados` path)
  and ACADOS_SOURCE_DIR. env.sh removes all of these.
- env.sh also sets PYTHONNOUSERSITE=1 and points `TMPDIR`, `MPLCONFIGDIR`, `NUMBA_CACHE_DIR`,
  `PIP_CACHE_DIR` and `XDG_CACHE_HOME` into `.cache/`.
- `GH_CONFIG_DIR=.gh/` is set because the global gh token had expired; logging in again would have
  rewritten `~/.config/gh`.
- `NUMBA_THREADING_LAYER=omp` is set because the system TBB is too old for numba.

## D11: Public repo, GitHub Pages served from `/docs` on `main`
- The user chose public so the interactive 3-D pages open in a phone browser.
- Pages serves `/docs` (`docs/.nojekyll`, files served raw), so the results index is at
  https://abhandari11.github.io/sar-gnc/site/.
- No Actions workflow, because the gh token has `repo` scope only. Pushing `.github/workflows` would
  need the `workflow` scope.
- Pushes authenticate through a credential helper set only in this repo's `.git/config`, which calls
  `gh auth git-credential` with the project-local `GH_CONFIG_DIR`.

## D12: Fixed site with base camp Seealpsee; ENU origin kept at 47.2493 N, 9.3800 E
- The user asked for a base at about (1000 E, 2000 N), used for all operations: mountaineering/skiing
  base camp, UAV launch and return.
- That point lies on a 13–15° slope at the west end of Seealpsee. `terrain/siting.find_level_site`
  looks for the nearest pad within 25 m radius with slope ≤ 6° that isn't water (lakes are dead-flat
  in the DEM). It found **(1020, 1945)**, 1147 m, 59 m from the request.
- That position is fixed in `configs/sites/alpstein.yaml`, not re-solved at run time, so it's
  literally fixed on the map.
- Launch heading 72° ENE along the lake axis.
- Home loiter: centre (1500, 2100), radius 90 m, 120 m above the water (1262 m). The circle lies
  entirely over the lake, the safest spot to climb and descend in a narrow valley.
- The ENU origin is unchanged, so earlier coordinates stay valid.

## D13: Config split: site (map + base) vs scenario (search region) vs flight run
- `configs/sites/<site>.yaml` holds what never changes for an area: the ENU origin, the map extent,
  the DEM settings and the base.
- `configs/<scenario>.yaml` references a site and adds the search region. Priors, targets and wind
  will go here next.
- `configs/flights/<run>.yaml` adds the aircraft, wind and mission.
- The map extent is now explicit: E −2000…2600, N −2000…3400 (4.6 × 5.4 km, 921 × 1081 @ 5 m,
  42 tiles). It covers the base, the home loiter and the search region with ≥ 1000 m margin. The
  loader enforces this margin (`site.min_edge_margin_m`); it caught an initial 900 m loiter margin.
- `AreaSpec` was replaced by `MapSpec`.

## D14: Search region is a union of polygons, not a fixed square
- The user wants to draw search areas later and plan patterns smartly. `SearchRegion` therefore
  holds a list of ENU polygons, with area, bounds and point-in-polygon tests. A rectangle is only a
  convenience constructor.
- The Meglisalp square remains as a placeholder in `alpstein_meglisalp.yaml`.
- Planned next step: user input as lat/lon or ENU polygons in YAML, then a phone-drawable input.

## D15: Gildo v0 airframe sizing (proposal, see docs/GILDO.md)
- A 2.0 m span, AR 7.1 flying wing at 3.2 kg with a 224 Wh Li-ion pack. Cruise 18 m/s gives 2 h,
  climb is 7 m/s, and the turn radius is 39 m at 40° bank.
- Sized so that a 1000 m climb from base takes about 3 min and the full-throttle current stays far
  from the ESC limit.
- The first draft had a 420 KV motor, giving 650 W and T/W 0.9 static. That's overpowered, so it
  became 380 KV (T/W ≈ 0.5).
- The first draft's v_min of 14 m/s was only 1.09 Vs at 2000 m. It's now 15.5 m/s (1.2 Vs).

## D16: Aero coefficients: Zagi non-dimensional set + aspect-ratio and winglet corrections
- Beard & McLain's Zagi is the standard published small flying-wing model. Its coefficients are
  dimensionless, so they carry over with geometry and mass scaling.
- Departures from the Zagi set are listed in GILDO.md. Inertias are scaled by m·b² (roll/yaw) and
  m·c² (pitch).
- Replace with AVL/XFLR5 once a planform exists.

## D17: Dynamics in NED/FRD with quaternions, numba core; terrain and planning stay in ENU
- NED/FRD is the aero and PX4 convention, so Stage 2+ can be compared with PX4 logs.
- Conversion is a swap plus a sign flip (`rotations.enu_to_ned`).
- The numba RK4 core runs 4 substeps (200 Hz) per 50 Hz control step. Python handles only the 50 Hz
  autopilot and mission logic: about 350× real time on this machine, fast enough for Monte-Carlo
  runs in Stage 3.
- Single-point terrain lookups now use a serial numba kernel. The parallel kernel's thread start-up
  cost had made the first sim run use 14× more CPU than wall time.

## D18: Autopilot: successive loop closure with an altitude state machine
- It's the textbook structure, and gains computed from the model keep it consistent with the airframe.
- Tuning changes after looking at the first flight:
  - Altitude loop bandwidth: ωθ/50 instead of ωθ/25. The original gain of 0.13 rad/m dove 20° for a
    21 m altitude step.
  - In the hold zone, the altitude error is capped at ±25 m and pitch authority at ±10° around trim.
  - Anti-windup was added on the altitude and airspeed-from-pitch integrators. A launch over-speed
    had wound up the airspeed integrator and stuck pitch at the 20° limit, bleeding airspeed to
    14.8 m/s.
  - Climb throttle is 0.9. At 1.0 the aircraft sat on the pitch limit and over-sped. At 0.8 the
    climb was slower and used more energy (16.5 vs 14 Wh for 720 m), because the longer climb spends
    more time paying drag and the hotel load.
  - The roll command is rate-limited to 45 °/s.
- Launch holds a fixed 15° pitch at full throttle. Pitch-for-airspeed straight off the launcher pitched
  down, since exit speed (16) is below the command (18), and flew into the ground at 1.4 s. 10° pitch
  over-sped to 23.6 m/s.
- Result: airspeed stays within 16.7–21.7 m/s for the whole demo mission, and 18 ± 0.5 outside
  transients.

## D19: Terrain-safe mission altitudes by construction
- Each leg flies at the highest terrain within ±150 m of the leg, plus 120 m. Orbits fly at the
  highest terrain within (radius + 50 m), plus 120 m.
- Gildo climbs to the highest transit altitude while circling over the lake before leaving, and
  climbs back to the return altitude in the target orbit before returning.
- This is deliberately simple and conservative; Stage 3 replaces it with a terrain-following planner.
