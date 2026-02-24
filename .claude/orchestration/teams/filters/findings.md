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

### New Filter Names

| Filter Class | `name` attribute |
|-------------|-----------------|
| OpticalFlowParticlesFilter | `"optical_flow_particles"` |
| StipplingFilter | `"stippling"` |
| UVDisplacementFilter | `"uv_displacement"` |
| EdgeSmoothFilter | `"edge_smooth"` |
| RadialCollapseFilter | `"radial_collapse"` |
| PhysarumFilter | `"physarum"` |
| BoidsFilter | `"boids"` |

### All filters follow the standard contract

- Input: `(H, W, 3)` BGR uint8 C-contiguous
- Output: same shape and dtype
- No-op: returns `frame` (same reference)
- Modification: `frame.copy(order='C')` then in-place
- Stateful filters: implement `reset()`
- LUT-cached filters: `_params_dirty` flag pattern

## Provided to Other Teams

- 7 new filter classes registered in `adapters/processors/filters/__init__.py`
- All filters accept optional `analysis` dict from perception pipeline
- Stateful filters respond to `reset()` calls
