# Design decisions

Each decision is a default chosen to keep moving. Revisit by editing the entry and noting it in DEVLOG.

## D1: Test area: Alpstein, Meglisalp basin (Appenzell, CH), centre 47.2493 N, 9.3800 E
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
  constant (~50 m) over 4 km, so it only shifts the frame vertically; see open question 3.
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
