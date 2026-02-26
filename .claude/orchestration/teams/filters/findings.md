# Filters Team -- Findings

## Phase 1: Research & Design

### Existing Filter Patterns Surveyed

| File | Pattern | Key Takeaway |
|------|---------|--------------|
| `base.py` | BaseFilter with `name`, `enabled`, `apply()` | Must extend BaseFilter, set unique `name` |
| `brightness.py` | No-op via config attribute check | Return `frame` (same ref) for no-op |
| `edges.py` | Uses `get_cached_conversion` for BGR2GRAY | Use conversion_cache for shared color conversions |
| `detail.py` | CLAHE + sharpening, conversion_cache | Complex filters still follow same pattern |
| `invert.py` | Simplest: `np.subtract(255, frame)` | Always guard with no-op check first |
| `cpp_invert.py` | C++ wrapper: ImportError fallback | Copy this pattern exactly for C++ wrappers |
| `conversion_cache.py` | Global singleton, keyed by `(frame_id, conversion_code)` | Multiple filters sharing BGR2GRAY compute it once |

### Algorithm Designs

1. **Optical Flow Particles** -- Dense optical flow (Farneback) between consecutive frames. Spawn particles at high-motion regions. Each particle: position, velocity, lifetime, color. Update positions using flow vectors. Render as circles.
2. **Stippling / Pointillism** -- Grid-jittered sampling. Grid spacing based on `density`. Dot size inversely proportional to local luminance. LUT-cached grid.
3. **UV Math Displacement** -- Parametric remap tables (sin/cos/spiral/noise). `cv2.remap()` for fast application. Phase animation via cheap float increment.
4. **Edge-Aware Smoothing** -- `cv2.bilateralFilter` with configurable d, sigma_color, sigma_space. Blendable with original.
5. **Radial Collapse / Singularity** -- Polar coordinate remap. Radius distorted with exponential falloff from center. LUT-cached maps.
6. **Physarum Simulation Overlay** -- Agent-based simulation on reduced-resolution trail map. Sense-rotate-deposit-diffuse-decay loop.
7. **Boids / Flocking Particles** -- Separation + alignment + cohesion. Vectorized numpy pairwise distances.

### Classification Table

| Filter | Base Pattern | State | Caching | C++ Plan |
|--------|-------------|-------|---------|----------|
| Optical Flow Particles | Stateful | `_prev_gray`, `_particles`, `_last_shape` | None | Optional |
| Stippling | LUT-cached | None | `_grid`, `_params_dirty` | Not needed |
| UV Math Displacement | LUT-cached | `_phase` (cheap) | `_base_map_x/y`, `_params_dirty` | Not needed |
| Edge-Aware Smoothing | Simple | None | None | Not needed |
| Radial Collapse | LUT-cached | None | `_map_x/y`, `_params_dirty` | Not needed |
| Physarum Simulation | Stateful + C++ | `_trail_map`, `_agents`, `_last_shape` | None | Required |
| Boids | Stateful | `_positions`, `_velocities`, `_last_shape` | None | Optional |

### Latency Estimates (640x480)

| Filter | Python (ms) | C++ (ms) | Notes |
|--------|-------------|----------|-------|
| Optical Flow Particles | 4-8 | 1-3 | Farneback ~2ms |
| Stippling | <1 (hit), 2-3 (rebuild) | -- | Grid cached |
| UV Math Displacement | <2 (hit) | -- | cv2.remap is fast |
| Edge-Aware Smoothing | 2-4 | -- | bilateralFilter already C++ |
| Radial Collapse | <2 (hit) | -- | cv2.remap, maps cached |
| Physarum | 15-30 | 2-5 | Python limited to ~2000 agents |
| Boids | 3-8 (200 boids) | <1 | O(N^2) vectorized numpy |

## API Contracts

### Filter Summary Table

| Filter | `name` | Stateful / `reset()` | LUT-cached | Uses Analysis | Temporal Declarations |
|--------|--------|---------------------|------------|--------------|----------------------|
| OpticalFlowParticlesFilter | `optical_flow_particles` | YES | NO | `optical_flow` (attr) | `needs_optical_flow = True` |
| StipplingFilter | `stippling` | NO | YES (`_params_dirty`) | NO | — |
| UVDisplacementFilter | `uv_displacement` | NO | YES (`_params_dirty`) | NO | — |
| EdgeSmoothFilter | `edge_smooth` | NO | NO | NO | — |
| RadialCollapseFilter | `radial_collapse` | NO | YES (`_params_dirty`) | `face.points` (dict) | — |
| PhysarumFilter | `physarum` | YES | NO | `delta_frame` (attr) | `needs_delta_frame = True` |
| BoidsFilter | `boids` | YES | NO | `hands`, `face.points` (dict) | — |
| CRTGlitchFilter | `crt_glitch` | Minimal | Partial | `optical_flow` (attr), `hands.speed` (dict) | `needs_optical_flow`, `needs_previous_output` |
| GeometricPatternFilter | `geometric_patterns` | Quasi | NO | `face.landmarks`, `hands.landmarks`, `previous_output` | `needs_previous_output = True` |
| CppPhysarumFilter | `cpp_physarum` | YES | NO | NO | — |

### Standard Contract (all filters)

- Input: `(H, W, 3)` BGR uint8 C-contiguous
- Output: same shape and dtype
- No-op: returns `frame` (same reference)
- Modification: `frame.copy(order='C')` then in-place
- Stateful filters: implement `reset()`
- LUT-cached filters: `_params_dirty` flag pattern

### Constructor Parameters (key configurables)

**OpticalFlowParticlesFilter:** `max_particles=2000`, `particle_lifetime=30`, `spawn_threshold=2.0`, `particle_size=2`, `color_mode="flow"`.

**StipplingFilter:** `density=0.5`, `min_dot_size=1`, `max_dot_size=4`, `background_color=(0,0,0)`, `invert_size=False`. Properties: `density`, `min_dot_size`, `max_dot_size` trigger `_params_dirty`.

**UVDisplacementFilter:** `function_type="sin"` (sin/cos/spiral/noise), `amplitude=10.0`, `frequency=2.0`, `phase_speed=0.05`. Properties: `amplitude`, `frequency`, `function_type` trigger `_params_dirty`.

**EdgeSmoothFilter:** `diameter=9`, `sigma_color=75.0`, `sigma_space=75.0`, `strength=1.0`. Caution: `bilateralFilter` at `d=9` can consume 10-20ms on 640x480.

**RadialCollapseFilter:** `center_x=0.5`, `center_y=0.5`, `strength=0.5`, `falloff=0.3`, `mode="collapse"/"expand"`, `follow_face=False`. All core params trigger `_params_dirty`. When `follow_face=True`, LUT cache is invalidated every frame.

**PhysarumFilter:** `num_agents=4000`, `sensor_angle=0.4`, `sensor_distance=9.0`, `turn_speed=0.4`, `move_speed=1.0`, `deposit_amount=10.0`, `decay_factor=0.98`, `diffusion_sigma=0.5`, `opacity=0.7`, `colormap=COLORMAP_INFERNO`, `sim_scale=4`.

**BoidsFilter:** `num_boids=200`, `max_speed=4.0`, `separation_radius=15.0`, `alignment_radius=40.0`, `cohesion_radius=60.0`, `boid_size=2`, `boid_color=(0,255,200)`, `attract_to_analysis=False`. O(N^2) pairwise — keep `num_boids` under ~500.

**CRTGlitchFilter:** `scanline_intensity=0.3`, `aberration_strength=3.0`, `noise_amount=0.05`, `tear_probability=0.1`, `barrel_strength=0.3`, `vhs_tracking=0.0`. Sub-effect toggles: `enable_scanlines`, `enable_aberration`, `enable_noise`, `enable_tear`, `enable_barrel=False`, `enable_vhs=False`.

**GeometricPatternFilter:** `pattern_mode="sacred_geometry"` (sacred_geometry/voronoi/delaunay/lissajous/strange_attractor), `opacity=0.4`, `color=(255,200,100)`, `line_thickness=1`, `scale=1.0`, `animate=True`.

**CppPhysarumFilter:** Same params as PhysarumFilter but higher defaults: `num_agents=10000`, `deposit_amount=5.0`, `decay_factor=0.95`. Falls back to Python PhysarumFilter (capped at 2000 agents) when `filters_cpp` unavailable.

### Analysis Dict Usage Details

| Filter | Key | Access Style | Purpose |
|--------|-----|-------------|---------|
| OpticalFlowParticlesFilter | `analysis.optical_flow` | `getattr` | Shared flow `(H,W,2)` from TemporalManager |
| RadialCollapseFilter | `analysis["face"]["points"]` | dict | Face centroid for `follow_face` mode |
| PhysarumFilter | `analysis.delta_frame` | `getattr` | Motion attractant for trail map |
| BoidsFilter | `analysis["hands"]["left/right"]`, `analysis["face"]["points"]` | dict | Attraction targets when `attract_to_analysis=True` |
| CRTGlitchFilter | `analysis.optical_flow`, `analysis["hands"]["speed"]` | mixed | Motion modulation for glitch intensity |
| GeometricPatternFilter | `analysis["face"]["landmarks"]`, `analysis["hands"]["landmarks"]` | dict | Voronoi/Delaunay seed points |

### Known Issues

1. **OpticalFlowParticles resolution change bug** — `_prev_gray` and `_particles` state not properly reset when frame shape changes mid-stream. Causes OpenCV assertion failure. Intermittent in test suite.
2. **CRTGlitchFilter** declares `needs_previous_output = True` but never reads `previous_output` — wasted temporal allocation.
3. **CRTGlitchFilter barrel distortion** rebuilds remap maps from scratch every frame (no LUT caching).
4. **GeometricPatternFilter** accesses `analysis["hands"]["landmarks"]` but standard hands output uses `"left"`/`"right"` keys — likely returns no points in practice.
5. **GeometricPatternFilter Clifford attractor** uses a pure Python loop (50k iterations) on first compute — can take hundreds of ms.
6. **CppPhysarumFilter** lacks `needs_delta_frame` declaration, so it doesn't receive motion data unlike the Python version.

## Discovered Patterns

1. **Temporal class attributes** are the mechanism for filters to request shared data from TemporalManager: `needs_optical_flow`, `needs_delta_frame`, `needs_previous_output`, `required_input_history`.
2. **Property setters with `_params_dirty`** is the standard for LUT-cached filters (Stippling, UV, RadialCollapse). Non-cached filters use direct attributes.
3. **Resolution change handling**: all stateful filters track `_last_shape` and reinitialize state when it changes.
4. **C++ fallback pattern**: `CppPhysarumFilter` checks for `filters_cpp` at import, falls back lazily to `PhysarumFilter` on first `apply()`. Cap at `min(num_agents, 2000)` for Python fallback.

## Dependencies on Other Teams

- `TemporalManager` (infrastructure/app services) — provides `optical_flow`, `delta_frame`, `previous_output`
- Perception pipeline — provides `analysis` dict with `face`, `hands` keys
- `conversion_cache` — shared BGR2GRAY conversion

## Provided to Other Teams

- 10 filter classes registered in `adapters/processors/filters/__init__.py` (7 original + CRTGlitch, GeometricPatterns, CppPhysarum)
- All filters accept optional `analysis` dict from perception pipeline
- Stateful filters respond to `reset()` calls
- Temporal declarations enable demand-driven buffer allocation in TemporalManager
