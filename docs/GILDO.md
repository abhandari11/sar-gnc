# Gildo: aircraft spec (v0, proposal for discussion)

Gildo is the custom small electric flying wing for mountain SAR. The values below are **v0 design
proposals**, sized from first principles and published small-UAV data, not measured hardware. They
live in `configs/aircraft/gildo.yaml`. Every number in this file is produced by
`python scripts/run_aircraft.py gildo` (outputs in `outputs/gildo_v0_performance/`).

## Design intent
- Hand- or bungee-launched from a base camp at 1100–1500 m. Climbs 1000 m to work ridges at 2000–2500 m.
- About 2 h on station, with enough speed margin to work in 10–12 m/s mountain wind.
- Tight turns (radius under 60 m) for orbiting gullies and valleys.
- Payload: a small stabilised EO/thermal gimbal plus a companion computer for onboard detection.

## Spec sheet (ISA)

| Item | Value |
|---|---|
| Span / wing area / AR | 2.00 m / 0.56 m² / 7.1 |
| Take-off mass | 3.20 kg (airframe 1.05, battery 0.90, propulsion 0.30, avionics 0.30, payload 0.65) |
| Wing loading | 56 N/m² |
| Battery | 6S2P Li-ion 21700, 224 Wh, 85 % usable; 18 W hotel load |
| Propulsion | 380 KV outrunner, 13 in folding pusher prop; full-throttle ~20 A (ESC 40 A) |
| Stall speed (1 g) | 12.4 m/s @ 1150 m · 12.9 @ 2000 m · 13.2 @ 2500 m |
| Airspeeds | min 15.5 (1.2 Vs) · cruise 18 · max level 28.8 m/s @ 2000 m |
| Cruise @ 2000 m | 95 W → **120 min, 130 km** (still air, usable energy) |
| Best endurance / range | 160 min @ 13.9 m/s (below v_min, theoretical) · 137 km @ 15.2 m/s |
| Max climb | 7.7 m/s @ 1150 m · 7.2 @ 2000 m · 6.8 @ 2500 m |
| Turn radius @ cruise | 57 m at 30° bank · 39 m at 40° (bank limit) · 29 m minimum (v_min, 40°) |
| Trim @ cruise | α 2.4°, elevator 0.5°, throttle 0.63 |
| Dynamic modes @ cruise | short period ωn 12.1 rad/s ζ 0.47 · phugoid ωn 0.70 ζ 0.18 · dutch roll ωn 3.1 ζ 0.10 · roll τ½ 0.07 s · spiral doubles in 35 s |

## Model
- **Rigid body:** 6-DOF with a quaternion attitude, NED world frame and FRD body frame. Extra state:
  battery energy drawn [J]. The numba core is `aircraft/_core.py`; integration is RK4 at 200 Hz.
- **Aerodynamics** follow Beard & McLain (*Small Unmanned Aircraft*, 2012) structure:
  - Linear lift blended into a flat-plate post-stall model (sigmoid, α₀ = 10°, M = 50).
  - Drag polar CD = CDp + CL²/(π e AR) + CDδe δe².
  - Body-axis stability derivatives.
  - Elevons are modelled as virtual elevator/aileron, mixed and limited to ±25° per surface, with
    40 ms first-order servos.
- **Coefficients** start from the Zagi flying-wing set (Beard & McLain App. E), adapted to Gildo:
  - CLα 4.5 /rad (lifting-line estimate for AR 7.1).
  - Clp −0.45 (more roll damping at higher AR).
  - Cnβ +0.03 and Cnr −0.03 from winglets. The plain Zagi is directionally near-neutral.
  - Cm0 +0.02 (reflexed section) and Cmα −0.40, about a 9 % static margin.
  - CDp 0.025, including the gimbal pod.
- **Propulsion:** Beard & McLain 2nd-edition motor/prop model. The steady balance of DC motor torque
  and prop torque gives the prop speed. Thrust and torque come from quadratic C_T(J), C_Q(J). Battery
  open-circuit voltage is linear in state of charge (4.15 → 3.30 V/cell). With the throttle at zero
  the prop is treated as folded.
- **Atmosphere:** ISA density from altitude (ENU z ≈ altitude a.s.l., see D5).

## Known limitations (v0)
- The coefficients are not from a vortex-lattice or CFD analysis of the real Gildo geometry. The
  next step is an AVL/XFLR5 run once a planform is drawn (see open questions).
- No motor power lapse, battery voltage sag, temperature effects, ground effect or
  propeller-slipstream effects.
- Dutch roll is lightly damped (ζ 0.10), typical of flying wings. With no rudder, the autopilot can't
  add yaw damping. Bigger winglets or a yaw damper using differential elevon drag are possible options.
- The spiral mode is slightly unstable (doubles in 35 s). The course loop handles it.

## Open questions for the spec
1. **Payload mass:** is a 0.65 kg EO/thermal gimbal plus companion computer right, or lighter
   (fixed thermal camera only, about 0.25 kg)? Mass drives every other number.
2. **Launch and recovery at base:** bungee/hand launch is assumed. Recovery is not modelled yet. The
   options are belly-landing on the meadow, a deep-stall landing, or a net.
3. **Wind envelope:** cruise 18 m/s against 10–12 m/s mountain wind leaves a slow ground speed upwind.
   Should cruise be raised to about 20–22 m/s? That costs about 20 % endurance.
4. **Cold:** Li-ion capacity drops in the cold at altitude (−10 °C means roughly 20 % less). Should
   the usable fraction be derated for winter scenarios?

## Simulator (Stage 2 basic)
- **Autopilot:** successive loop closure (Beard & McLain ch. 6). Gains are computed from the model at
  cruise trim, so changing `gildo.yaml` retunes them automatically.
  - Lateral: course → roll → aileron, with orbit roll feed-forward and a 45 °/s roll-command rate limit.
  - Altitude state machine:
    - **Hold zone** (altitude error within ±25 m): altitude → pitch (±10° authority) and
      airspeed → throttle.
    - **Climb zone:** 90 % throttle, airspeed → pitch.
    - **Descend zone:** idle (folded prop), airspeed → pitch.
  - Integrators use anti-windup. The launch phase holds 15° pitch at full throttle until 30 m above
    ground.
- **Guidance:** vector-field line and orbit following (Beard & McLain ch. 10).
- **Mission manager** (`sim/mission.py`): launch → climb (orbit the home loiter) → transit →
  target orbit → return → home hold.
  - Every altitude is the highest terrain in the leg's corridor (±150 m) or the orbit's disc,
    plus clearance (120 m).
  - Gildo reaches the transit altitude while circling over the lake before departing, so legs never
    climb into terrain.
- **Run:** `python scripts/run_flight.py configs/flights/gildo_demo_meglisalp.yaml`. It simulates
  about 350× faster than real time (15.6 min of flight in under 3 s).
