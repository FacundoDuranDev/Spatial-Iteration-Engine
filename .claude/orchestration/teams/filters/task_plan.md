# Filters Team Task Plan

7-phase plan to build 7 new image filters for the Spatial-Iteration-Engine pipeline.

**Skill reference:** `.claude/skills/filter-development/SKILL.md`
**Extension rules:** `rules/PIPELINE_EXTENSION_RULES.md`
**Latency budget:** `rules/LATENCY_BUDGET.md` -- 5ms combined for ALL active filters
**Performance rules:** `rules/PERFORMANCE_RULES.md` -- 0-1 frame copies per filter

## Filter Inventory

| # | Filter | Category | Stateful | LUT-Cached | C++ Required | Est. Latency (Python) | Est. Latency (C++) |
|---|--------|----------|----------|------------|--------------|----------------------|-------------------|
| 1 | Optical Flow Particles | Particle system | Yes | No | Optional | 4-8ms | 1-3ms |
| 2 | Stippling / Pointillism | Dot placement | No | Yes | No | 1-2ms | -- |
| 3 | UV Math Displacement | Remap | No | Yes | No | 1-3ms | -- |
| 4 | Edge-Aware Smoothing | Convolution | No | No | No | 2-4ms | -- |
| 5 | Radial Collapse / Singularity | Remap | No | Yes | No | 1-3ms | -- |
| 6 | Physarum Simulation Overlay | Simulation | Yes | No | Yes | 15-30ms | 2-5ms |
| 7 | Boids / Flocking Particles | Particle system | Yes | No | Optional | 5-12ms | 1-3ms |

---

## Phase 1: Research & Design

**Goal:** Understand existing filter patterns, design each algorithm, classify implementation strategy, and document findings.

### Tasks

#### 1.1 Survey existing filters for code patterns

Read and document the patterns used by each existing filter:

- `python/ascii_stream_engine/adapters/processors/filters/base.py` -- BaseFilter interface
- `python/ascii_stream_engine/adapters/processors/filters/brightness.py` -- no-op path (returns `frame` when params are neutral)
- `python/ascii_stream_engine/adapters/processors/filters/edges.py` -- conversion cache usage
- `python/ascii_stream_engine/adapters/processors/filters/detail.py` -- CLAHE + sharpening, conversion cache
- `python/ascii_stream_engine/adapters/processors/filters/invert.py` -- simplest filter
- `python/ascii_stream_engine/adapters/processors/filters/cpp_invert.py` -- C++ wrapper with ImportError fallback
- `python/ascii_stream_engine/adapters/processors/filters/cpp_brightness_contrast.py` -- C++ wrapper with params
- `python/ascii_stream_engine/adapters/processors/filters/conversion_cache.py` -- shared BGR2GRAY cache
- `cpp/src/bridge/pybind_filters.cpp` -- `apply_in_place()` helper, binding pattern
- `cpp/include/filters/filter.hpp` -- C++ Filter interface (virtual `apply`)

Document which patterns each new filter will follow.

#### 1.2 Design algorithm for each filter

For each of the 7 filters, write a concise algorithm description:

1. **Optical Flow Particles** -- Compute dense optical flow (Farneback or Lucas-Kanade) between consecutive frames. Spawn particles at high-motion regions. Each particle has position, velocity, lifetime, color. Update positions using flow vectors. Render particles as small circles/dots onto the frame. Analysis-reactive: can use `analysis["pose"]` or `analysis["hands"]` to seed particles at body joints.

2. **Stippling / Pointillism** -- Convert frame to grayscale luminance. Build a density map (darker = more dots). Use Poisson disk sampling or grid-jittered sampling to place dots. Dot size inversely proportional to local luminance. LUT-cached: precompute the sampling grid when resolution or `density` param changes; only resample colors per frame.

3. **UV Math Displacement** -- Build remap tables (`map_x`, `map_y`) using parametric math functions (sin, cos, spiral, noise). Apply `cv2.remap()`. LUT-cached: recompute maps only when `function_type`, `amplitude`, `frequency`, or `phase` params change. Phase can animate by incrementing per frame (cheap float add, no LUT rebuild).

4. **Edge-Aware Smoothing** -- Apply bilateral filter (`cv2.bilateralFilter`) or guided filter. Preserves edges while smoothing flat regions. Parameters: `d` (diameter), `sigma_color`, `sigma_space`. No LUT, no state -- pure convolution per frame.

5. **Radial Collapse / Singularity** -- Build remap tables that warp pixels radially toward/away from a center point. Strength falls off with distance. Uses polar coordinate transform: for each pixel, compute angle and radius from center, modify radius with a power/exponential curve, convert back to cartesian. LUT-cached: rebuild maps when `center`, `strength`, or `falloff` change.

6. **Physarum Simulation Overlay** -- Maintain a population of agents on a 2D trail map (lower resolution than frame). Each agent: sense ahead (3 sensors), rotate toward strongest trail, deposit trail, move forward. Diffuse + decay trail map each step. Overlay trail map onto frame using alpha blending. **Must run in C++** due to per-agent loop (thousands of agents). Python fallback: reduced agent count with numpy vectorization.

7. **Boids / Flocking Particles** -- Maintain a flock of particles with position, velocity. Three rules: separation, alignment, cohesion. Optional: attract toward analysis points (hands, face). Render particles as small triangles/dots. Update loop is O(N^2) for naive, O(N log N) with spatial hashing. C++ recommended for >500 boids.

#### 1.3 Classify implementation strategy

| Filter | Base Pattern | State Management | Caching | C++ Plan |
|--------|-------------|-----------------|---------|----------|
| Optical Flow Particles | Stateful (`.claude/skills` stateful template) | `_prev_frame`, `_particles` list, `_last_shape` | None | Optional: particle update loop |
| Stippling / Pointillism | LUT-cached (`.claude/skills` LUT template) | None | `_sampling_grid`, `_params_dirty` | Not needed |
| UV Math Displacement | LUT-cached | None | `_map_x`, `_map_y`, `_params_dirty` | Not needed |
| Edge-Aware Smoothing | Simple (like brightness.py) | None | None | Not needed (cv2.bilateralFilter is already C++) |
| Radial Collapse / Singularity | LUT-cached | None | `_map_x`, `_map_y`, `_params_dirty` | Not needed |
| Physarum Simulation | Stateful + C++ required | `_trail_map`, `_agents`, `_last_shape` | None | Required: agent loop + diffusion |
| Boids / Flocking Particles | Stateful | `_boids` array, `_last_shape` | None | Optional: update loop |

#### 1.4 Estimate latency and plan C++ acceleration

Reference budget from `rules/LATENCY_BUDGET.md`:

| Filter Type | Budget | Our Filters |
|-------------|--------|-------------|
| LUT-based (precomputed) | <0.5ms cache hit, 1-3ms rebuild | Stippling (rebuild), UV Math, Radial Collapse |
| Convolution-based | 2-5ms | Edge-Aware Smoothing |
| Stateful simulation | 3-10ms (reduce resolution) | Optical Flow Particles, Physarum, Boids |

**C++ mandatory:** Physarum (10k+ agents with per-agent sensor reads)
**C++ recommended:** Optical Flow Particles (particle update), Boids (O(N^2) neighbor search)
**C++ not needed:** Stippling (LUT + vectorized), UV Math (cv2.remap), Edge-Aware (cv2.bilateralFilter), Radial Collapse (cv2.remap)

Heavy filters (Physarum, Boids, Optical Flow) must support reduced simulation resolution:
- Simulate at `frame_size / scale_factor` (default 4x downscale)
- Upscale overlay to frame size before blending
- Document as "heavy" filter in docstring

#### 1.5 Document findings

**Deliverable:** `.claude/orchestration/teams/filters/findings.md`

Contents:
- Algorithm description for each filter
- Classification table
- Latency estimates with measurement methodology
- C++ acceleration plan
- Risk assessment (which filters might exceed budget)
- Dependencies (OpenCV functions, numpy operations)

### Acceptance Criteria

- [ ] All 11 existing filter files have been read and patterns documented
- [ ] Algorithm for each of the 7 filters is described with enough detail to implement
- [ ] Each filter is classified as stateful / LUT-cached / simple / convolution
- [ ] Latency estimates reference the budget rules
- [ ] `findings.md` is written and reviewed

---

## Phase 2: Core Python Implementation

**Goal:** Implement all 7 filters in Python following the BaseFilter pattern exactly.

### Tasks

#### 2.1 Optical Flow Particles (`optical_flow_particles.py`)

**File:** `python/ascii_stream_engine/adapters/processors/filters/optical_flow_particles.py`

```python
class OpticalFlowParticlesFilter(BaseFilter):
    name = "optical_flow_particles"
```

Implementation details:
- Stateful: stores `_prev_gray`, `_particles` (structured numpy array), `_last_shape`
- `reset()`: clears `_prev_gray`, `_particles`, `_last_shape`
- Resolution change: reinitialize all buffers when `frame.shape[:2] != self._last_shape`
- `apply()` flow:
  1. Convert current frame to grayscale (use `get_cached_conversion`)
  2. If `_prev_gray` is None (first frame), store gray, return `frame`
  3. Compute optical flow: `cv2.calcOpticalFlowFarneback(prev, curr, None, 0.5, 3, 15, 3, 5, 1.2, 0)`
  4. Compute flow magnitude, spawn particles where magnitude > threshold
  5. Update existing particles: position += velocity (from flow), lifetime -= 1
  6. Remove dead particles (lifetime <= 0)
  7. Cap particle count at `max_particles` (default 2000)
  8. `out = frame.copy(order='C')`
  9. Render particles onto `out` using `cv2.circle` (vectorized with numpy indexing)
  10. Store current gray as `_prev_gray`
  11. Return `out`
- Analysis-reactive: if `analysis` contains `"hands"` or `"pose"`, boost particle spawn rate near those coordinates
- Parameters: `max_particles` (int), `particle_lifetime` (int frames), `spawn_threshold` (float), `particle_size` (int), `color_mode` ("flow" | "source" | "fixed"), `enabled` (bool)

#### 2.2 Stippling / Pointillism (`stippling.py`)

**File:** `python/ascii_stream_engine/adapters/processors/filters/stippling.py`

```python
class StipplingFilter(BaseFilter):
    name = "stippling"
```

Implementation details:
- LUT-cached: stores `_sampling_grid`, `_params_dirty`, `_last_shape`
- Dirty flag on `density`, `min_dot_size`, `max_dot_size`, `background_color` changes
- Also rebuild grid on resolution change (`_last_shape`)
- `apply()` flow:
  1. If `_params_dirty` or shape changed, rebuild sampling grid:
     - Create grid of candidate points with jitter
     - Grid spacing based on `density` parameter
     - Store as `_sampling_grid` (N, 2) int array of (y, x) coordinates
  2. `out = np.full_like(frame, self._background_color)` -- black or white background
  3. For each grid point, sample the BGR color from `frame` at that position
  4. Compute local luminance to determine dot radius (darker = larger or smaller, configurable)
  5. Draw dots: `cv2.circle(out, (x, y), radius, color, -1)`
  6. Return `out`
- No-op: if `density == 0`, return `frame`
- Parameters: `density` (float 0-1), `min_dot_size` (int), `max_dot_size` (int), `background_color` (tuple), `invert_size` (bool), `enabled` (bool)

#### 2.3 UV Math Displacement (`uv_displacement.py`)

**File:** `python/ascii_stream_engine/adapters/processors/filters/uv_displacement.py`

```python
class UVDisplacementFilter(BaseFilter):
    name = "uv_displacement"
```

Implementation details:
- LUT-cached: stores `_map_x`, `_map_y`, `_params_dirty`, `_last_shape`, `_phase`
- Dirty flag on `function_type`, `amplitude`, `frequency` changes
- Phase animation: increment `_phase` each frame (cheap, no LUT rebuild)
- `apply()` flow:
  1. If `_params_dirty` or shape changed, rebuild base maps:
     - Create meshgrid `(H, W)` of float32 coordinates
     - Apply math function: sin, cos, spiral, radial, noise
     - Store as `_base_map_x`, `_base_map_y`
     - `_params_dirty = False`
  2. Apply phase offset to maps (cheap: add `_phase` to the function argument)
     - `_map_x = _base_map_x + amplitude * sin(frequency * y + _phase)`
     - `_map_y = _base_map_y + amplitude * cos(frequency * x + _phase)`
  3. `out = cv2.remap(frame, _map_x, _map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)`
  4. `_phase += phase_speed`
  5. Return `out`
- No-op: if `amplitude == 0`, return `frame`
- Parameters: `function_type` (str: "sin", "cos", "spiral", "noise"), `amplitude` (float), `frequency` (float), `phase_speed` (float), `enabled` (bool)

#### 2.4 Edge-Aware Smoothing (`edge_smooth.py`)

**File:** `python/ascii_stream_engine/adapters/processors/filters/edge_smooth.py`

```python
class EdgeSmoothFilter(BaseFilter):
    name = "edge_smooth"
```

Implementation details:
- Simple convolution filter, no state, no LUT
- `apply()` flow:
  1. If `strength == 0`, return `frame` (no-op)
  2. `out = cv2.bilateralFilter(frame, d=self._diameter, sigmaColor=self._sigma_color, sigmaSpace=self._sigma_space)`
  3. Optionally blend with original: `cv2.addWeighted(frame, 1 - strength, out, strength, 0)`
  4. Return result
- Note: `cv2.bilateralFilter` already returns a new array, so no explicit copy needed
- Parameters: `diameter` (int, default 9), `sigma_color` (float, default 75), `sigma_space` (float, default 75), `strength` (float 0-1, default 1.0), `enabled` (bool)

#### 2.5 Radial Collapse / Singularity (`radial_collapse.py`)

**File:** `python/ascii_stream_engine/adapters/processors/filters/radial_collapse.py`

```python
class RadialCollapseFilter(BaseFilter):
    name = "radial_collapse"
```

Implementation details:
- LUT-cached: stores `_map_x`, `_map_y`, `_params_dirty`, `_last_shape`
- Dirty flag on `center_x`, `center_y`, `strength`, `falloff`, `mode` changes
- `apply()` flow:
  1. If `_params_dirty` or shape changed, rebuild remap tables:
     - Create meshgrid of float32 coordinates
     - Compute polar coordinates (angle, radius) relative to center
     - Apply distortion: `new_radius = radius * (1 - strength * exp(-radius^2 / falloff^2))` for collapse
     - Or: `new_radius = radius * (1 + strength * exp(-radius^2 / falloff^2))` for expansion
     - Convert back to cartesian, store as `_map_x`, `_map_y`
     - `_params_dirty = False`
  2. `out = cv2.remap(frame, _map_x, _map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)`
  3. Return `out`
- No-op: if `strength == 0`, return `frame`
- Analysis-reactive: if `analysis["face"]` exists, can set center to face centroid
- Parameters: `center_x` (float 0-1, default 0.5), `center_y` (float 0-1, default 0.5), `strength` (float), `falloff` (float), `mode` (str: "collapse" | "expand"), `follow_face` (bool), `enabled` (bool)

#### 2.6 Physarum Simulation Overlay (`physarum.py`)

**File:** `python/ascii_stream_engine/adapters/processors/filters/physarum.py`

```python
class PhysarumFilter(BaseFilter):
    name = "physarum"
```

Implementation details:
- Stateful: stores `_trail_map` (float32 H/scale x W/scale), `_agents` (structured array), `_last_shape`
- **Runs simulation at reduced resolution** (default 1/4 frame size) to meet budget
- `reset()`: clears `_trail_map`, `_agents`, `_last_shape`
- Resolution change: reinitialize all buffers
- `apply()` flow (Python fallback, slow but functional):
  1. Resize frame to simulation resolution
  2. Convert to grayscale luminance for sensing
  3. For each agent (vectorized with numpy where possible):
     - Sense: sample trail map at 3 forward sensor positions
     - Rotate toward strongest trail signal
     - Move forward by `speed` pixels
     - Deposit trail at new position
     - Wrap positions (toroidal boundary)
  4. Diffuse trail map: `cv2.GaussianBlur(trail_map, (3,3), sigma)`
  5. Decay trail map: `trail_map *= decay_factor`
  6. Convert trail map to BGR overlay (colormap)
  7. Upscale overlay to frame resolution: `cv2.resize`
  8. `out = frame.copy(order='C')`
  9. Blend: `cv2.addWeighted(out, 1 - opacity, overlay, opacity, 0, dst=out)`
  10. Return `out`
- Python fallback: limited to ~2000 agents (still slow, ~15ms)
- C++ version: 10000+ agents, <5ms (see Phase 4)
- Parameters: `num_agents` (int), `sensor_angle` (float radians), `sensor_distance` (float), `turn_speed` (float), `move_speed` (float), `deposit_amount` (float), `decay_factor` (float 0-1), `diffusion_sigma` (float), `opacity` (float 0-1), `colormap` (int cv2 colormap), `sim_scale` (int downscale factor), `enabled` (bool)

#### 2.7 Boids / Flocking Particles (`boids.py`)

**File:** `python/ascii_stream_engine/adapters/processors/filters/boids.py`

```python
class BoidsFilter(BaseFilter):
    name = "boids"
```

Implementation details:
- Stateful: stores `_positions` (N, 2), `_velocities` (N, 2), `_last_shape`
- `reset()`: clears `_positions`, `_velocities`, `_last_shape`
- Resolution change: reinitialize, scatter boids randomly in new frame size
- `apply()` flow:
  1. If first frame or resolution changed, initialize boids randomly
  2. For each boid (vectorized with numpy broadcasting):
     - Compute distances to all other boids (pairwise, O(N^2))
     - Separation: steer away from neighbors within `separation_radius`
     - Alignment: match velocity of neighbors within `alignment_radius`
     - Cohesion: steer toward center of neighbors within `cohesion_radius`
     - Optional attractor: steer toward analysis points (hands, face)
  3. Update velocities: `v += separation * w_s + alignment * w_a + cohesion * w_c + attract * w_t`
  4. Clamp speed to `max_speed`
  5. Update positions: `pos += vel`
  6. Wrap or bounce at frame boundaries
  7. `out = frame.copy(order='C')`
  8. Render boids as small dots or directional triangles using `cv2.circle` or `cv2.fillPoly`
  9. Return `out`
- No-op: if `num_boids == 0`, return `frame`
- Analysis-reactive: if `analysis["hands"]` exists, add attraction force toward hand landmarks
- Parameters: `num_boids` (int, default 200), `max_speed` (float), `separation_radius` (float), `alignment_radius` (float), `cohesion_radius` (float), `separation_weight` (float), `alignment_weight` (float), `cohesion_weight` (float), `boid_size` (int), `boid_color` (tuple), `attract_to_analysis` (bool), `enabled` (bool)

### Deliverables

| File | Filter | Lines (est.) |
|------|--------|-------------|
| `adapters/processors/filters/optical_flow_particles.py` | OpticalFlowParticlesFilter | 120-150 |
| `adapters/processors/filters/stippling.py` | StipplingFilter | 80-100 |
| `adapters/processors/filters/uv_displacement.py` | UVDisplacementFilter | 90-110 |
| `adapters/processors/filters/edge_smooth.py` | EdgeSmoothFilter | 40-60 |
| `adapters/processors/filters/radial_collapse.py` | RadialCollapseFilter | 90-110 |
| `adapters/processors/filters/physarum.py` | PhysarumFilter | 150-200 |
| `adapters/processors/filters/boids.py` | BoidsFilter | 130-160 |

### Acceptance Criteria

- [ ] All 7 filter files exist in `adapters/processors/filters/`
- [ ] Each filter extends `BaseFilter` and sets a unique `name`
- [ ] Each filter has `apply(self, frame, config, analysis=None) -> np.ndarray`
- [ ] No-op paths return `frame` (same reference, 0 copies)
- [ ] Modification paths use `frame.copy(order='C')` then operate in-place
- [ ] Output is always `(H, W, 3)` uint8 BGR, same shape as input
- [ ] Stateful filters (Optical Flow, Physarum, Boids) implement `reset()`
- [ ] Stateful filters handle resolution changes (reinitialize buffers)
- [ ] LUT-cached filters (Stippling, UV Displacement, Radial Collapse) use `_params_dirty` flag
- [ ] LUT-cached filters do NOT recompute tables every frame
- [ ] Analysis-reactive filters guard with `if analysis and "key" in analysis`
- [ ] No filter modifies the `analysis` dict
- [ ] No filter imports from `application/` or `ports/`
- [ ] All filters pass `black --check --line-length 100` and `isort --check`

---

## Phase 3: Unit Tests

**Goal:** Comprehensive unit tests for all 7 filters, following existing test patterns in `python/ascii_stream_engine/tests/test_filters.py`.

### Test File

**File:** `python/ascii_stream_engine/tests/test_new_filters.py`

### Tasks

#### 3.1 Core contract tests (all 7 filters)

For EACH of the 7 filters, write these mandatory tests:

```python
# Pattern: test_{filtername}_noop_returns_same_ref
def test_optical_flow_particles_noop():
    """No-op condition returns same frame reference (0 copies)."""
    f = OpticalFlowParticlesFilter(max_particles=0, enabled=True)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    config = EngineConfig()
    result = f.apply(frame, config)
    assert result is frame

# Pattern: test_{filtername}_output_shape_dtype
def test_optical_flow_particles_output_shape_dtype():
    """Output preserves (H, W, 3) uint8 shape and dtype."""
    f = OpticalFlowParticlesFilter()
    frame = np.random.randint(0, 255, (120, 160, 3), dtype=np.uint8)
    config = EngineConfig()
    # Need two frames for optical flow
    f.apply(frame, config)  # first frame (stores prev)
    frame2 = np.random.randint(0, 255, (120, 160, 3), dtype=np.uint8)
    result = f.apply(frame2, config)
    assert result.shape == frame2.shape
    assert result.dtype == np.uint8

# Pattern: test_{filtername}_c_contiguous
def test_optical_flow_particles_c_contiguous():
    """Output is C-contiguous."""
    # ... apply filter ...
    assert result.flags['C_CONTIGUOUS']
```

#### 3.2 Stateful filter tests

For OpticalFlowParticlesFilter, PhysarumFilter, BoidsFilter:

```python
# test_{filtername}_reset_clears_state
def test_optical_flow_particles_reset():
    """reset() clears internal state completely."""
    f = OpticalFlowParticlesFilter()
    frame = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    config = EngineConfig()
    f.apply(frame, config)
    assert f._prev_gray is not None  # state exists
    f.reset()
    assert f._prev_gray is None
    assert f._particles is None

# test_{filtername}_resolution_change
def test_optical_flow_particles_resolution_change():
    """Resolution change mid-stream reinitializes buffers."""
    f = OpticalFlowParticlesFilter()
    config = EngineConfig()
    frame_small = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    f.apply(frame_small, config)
    frame_large = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
    result = f.apply(frame_large, config)
    assert result.shape == (200, 300, 3)

# test_{filtername}_multiple_frames_accumulate
def test_physarum_multiple_frames():
    """Stateful filter evolves over multiple frames."""
    f = PhysarumFilter(num_agents=100, sim_scale=4)
    config = EngineConfig()
    frame = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    result1 = f.apply(frame, config)
    result2 = f.apply(frame, config)
    # Trail map should evolve: results should differ
    assert not np.array_equal(result1, result2)
```

#### 3.3 LUT cache invalidation tests

For StipplingFilter, UVDisplacementFilter, RadialCollapseFilter:

```python
# test_{filtername}_lut_cache_hit
def test_uv_displacement_lut_cache_hit():
    """Same params reuse cached maps (no rebuild)."""
    f = UVDisplacementFilter(amplitude=10.0, frequency=2.0)
    config = EngineConfig()
    frame = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    f.apply(frame, config)
    assert f._params_dirty is False
    map_x_id = id(f._map_x)
    f.apply(frame, config)
    assert id(f._map_x) == map_x_id  # same object, not rebuilt

# test_{filtername}_lut_cache_invalidation
def test_uv_displacement_param_change_invalidates():
    """Changing a parameter sets _params_dirty and rebuilds maps."""
    f = UVDisplacementFilter(amplitude=10.0, frequency=2.0)
    config = EngineConfig()
    frame = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    f.apply(frame, config)
    f.amplitude = 20.0  # property setter triggers dirty flag
    assert f._params_dirty is True
    f.apply(frame, config)
    assert f._params_dirty is False

# test_{filtername}_resolution_change_rebuilds_lut
def test_radial_collapse_resolution_change_rebuilds():
    """Resolution change forces LUT rebuild."""
    f = RadialCollapseFilter(strength=0.5)
    config = EngineConfig()
    small = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    f.apply(small, config)
    large = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
    result = f.apply(large, config)
    assert result.shape == (200, 300, 3)
```

#### 3.4 Analysis dict interaction tests

```python
# test_filter_with_analysis_dict
def test_radial_collapse_follows_face():
    """follow_face mode reads analysis['face'] safely."""
    f = RadialCollapseFilter(follow_face=True, strength=0.5)
    config = EngineConfig()
    frame = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    analysis = {"face": {"points": np.array([[0.5, 0.5]])}}
    result = f.apply(frame, config, analysis=analysis)
    assert result.shape == frame.shape

# test_filter_with_none_analysis
def test_optical_flow_particles_no_analysis():
    """Filter works when analysis=None."""
    f = OpticalFlowParticlesFilter()
    config = EngineConfig()
    frame = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    result = f.apply(frame, config, analysis=None)
    assert result.shape == frame.shape

# test_filter_does_not_modify_analysis
def test_boids_does_not_modify_analysis():
    """Filter never writes to analysis dict."""
    f = BoidsFilter(num_boids=50, attract_to_analysis=True)
    config = EngineConfig()
    frame = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    analysis = {"hands": {"left": np.array([[0.3, 0.4]])}}
    analysis_copy = {"hands": {"left": analysis["hands"]["left"].copy()}}
    f.apply(frame, config, analysis=analysis)
    np.testing.assert_array_equal(analysis["hands"]["left"], analysis_copy["hands"]["left"])
```

#### 3.5 Edge case tests

```python
# test_filter_with_tiny_frame
def test_stippling_tiny_frame():
    """Filter handles tiny frames gracefully."""
    f = StipplingFilter(density=0.5)
    frame = np.random.randint(0, 255, (2, 2, 3), dtype=np.uint8)
    config = EngineConfig()
    result = f.apply(frame, config)
    assert result.shape == (2, 2, 3)

# test_filter_with_large_frame
def test_edge_smooth_large_frame():
    """Filter handles large frames within budget."""
    f = EdgeSmoothFilter()
    frame = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
    config = EngineConfig()
    result = f.apply(frame, config)
    assert result.shape == frame.shape

# test_disabled_filter
def test_physarum_disabled():
    """Disabled filter should not be applied by pipeline (but apply() still works if called)."""
    f = PhysarumFilter(enabled=False)
    assert f.enabled is False
```

### Deliverables

| File | Tests (est.) |
|------|-------------|
| `python/ascii_stream_engine/tests/test_new_filters.py` | 35-45 tests |

### Acceptance Criteria

- [ ] Test file exists at `python/ascii_stream_engine/tests/test_new_filters.py`
- [ ] Every filter has at least: noop test, shape/dtype test, C-contiguous test
- [ ] Stateful filters have: reset test, resolution change test, multi-frame test
- [ ] LUT-cached filters have: cache hit test, invalidation test, resolution rebuild test
- [ ] Analysis dict tests: with data, with None, no mutation
- [ ] Edge cases: tiny frame, large frame, disabled flag
- [ ] All tests pass: `PYTHONPATH=python:cpp/build python -m pytest python/ascii_stream_engine/tests/test_new_filters.py -v`
- [ ] Tests use `@unittest.skipUnless(has_module("cv2") and has_module("numpy"), ...)` guards
- [ ] Tests use `DummyConfig` or `EngineConfig()` for config parameter

---

## Phase 4: C++ Implementation

**Goal:** Implement performance-critical filters in C++ with pybind11 bindings and Python wrappers.

### Tasks

#### 4.1 Physarum simulation C++ core

**Files:**
- `cpp/src/filters/physarum.cpp` -- Core simulation logic
- `cpp/include/filters/physarum.hpp` -- Header with state struct declarations

Implementation:
- `PhysarumSimulation` class (NOT extending `Filter` -- this is stateful, needs persistent state)
- State: `std::vector<Agent>` (position, angle), `std::vector<float>` trail_map (preallocated)
- `void init(int sim_w, int sim_h, int num_agents)` -- allocate once
- `void step(const uint8_t* luminance, int sim_w, int sim_h, float sensor_angle, float sensor_dist, float turn_speed, float move_speed, float deposit, float decay, float diffuse_sigma)` -- one simulation step
- `const float* trail_data() const` -- pointer to trail map for Python to read
- `void reset()` -- clear agents and trail
- Agent loop: for each agent, sense (3 forward samples), rotate, move, deposit
- Diffusion: 3x3 box blur on trail map (avoid cv2 dependency in C++)
- Decay: `trail[i] *= decay`
- **No heap allocation per step** -- all vectors preallocated in `init()`
- Use `py::gil_scoped_release` around `step()` call

Free function API for pybind:
```cpp
namespace filters {
    void physarum_init(int sim_w, int sim_h, int num_agents);
    void physarum_step(const uint8_t* luminance, int sim_w, int sim_h, /* params */);
    const float* physarum_trail_data();
    void physarum_reset();
}
```

#### 4.2 Optical Flow particle update C++ (optional)

**File:** `cpp/src/filters/particle_update.cpp`

Implementation:
- `void update_particles(float* positions, float* velocities, int* lifetimes, int num_particles, const float* flow_x, const float* flow_y, int flow_w, int flow_h)` -- in-place update
- For each particle: sample flow at position, add to velocity, update position, decrement lifetime
- Pure computation, no OpenCV dependency
- **Optional:** Only implement if Python version exceeds budget

#### 4.3 Boids update C++ (optional)

**File:** `cpp/src/filters/boids_update.cpp`

Implementation:
- `void update_boids(float* positions, float* velocities, int num_boids, float separation_radius, float alignment_radius, float cohesion_radius, float* weights, float max_speed, int frame_w, int frame_h)` -- in-place update
- Naive O(N^2) but in C++ with tight loop (~500 boids in <1ms)
- Optional spatial hashing for >1000 boids
- **Optional:** Only implement if Python version exceeds budget

#### 4.4 Pybind11 bindings

**File:** `cpp/src/bridge/pybind_filters.cpp` (append to existing)

Add bindings:

```cpp
// Physarum (stateful, uses class-level state)
m.def("physarum_init", &filters::physarum_init,
    py::arg("sim_w"), py::arg("sim_h"), py::arg("num_agents"),
    "Initialize physarum simulation.");
m.def("physarum_step", [](py::array_t<uint8_t> luminance, /* params */) {
    py::buffer_info buf = luminance.request();
    {
        py::gil_scoped_release release;
        filters::physarum_step(static_cast<uint8_t*>(buf.ptr), /* ... */);
    }
}, "Run one physarum simulation step.");
m.def("physarum_get_trail", []() -> py::array_t<float> {
    // Return numpy view of trail data (no copy)
    // ...
}, "Get current trail map as numpy array.");
m.def("physarum_reset", &filters::physarum_reset, "Reset simulation.");

// Optional: particle_update, boids_update (if implemented)
```

#### 4.5 Python C++ wrappers

**File:** `python/ascii_stream_engine/adapters/processors/filters/cpp_physarum.py`

```python
class CppPhysarumFilter(BaseFilter):
    name = "cpp_physarum"
```

Pattern: follows `cpp_invert.py` exactly.
- `try: import filters_cpp` with `_CPP_AVAILABLE` flag
- `cpp_available` property
- `apply()`: if not `_CPP_AVAILABLE`, delegate to Python `PhysarumFilter` (fallback)
- If C++ available: call `filters_cpp.physarum_init()` on first frame, `physarum_step()` each frame, read trail, overlay
- `reset()`: call `filters_cpp.physarum_reset()`

**Optionally** (if implemented): `cpp_optical_flow_particles.py`, `cpp_boids.py`

#### 4.6 CMakeLists.txt update

**File:** `cpp/CMakeLists.txt`

Add new source files to `FILTERS_SOURCES`:
```cmake
set(FILTERS_SOURCES
  # ... existing ...
  src/filters/physarum.cpp
  # src/filters/particle_update.cpp  # if implemented
  # src/filters/boids_update.cpp     # if implemented
)
```

#### 4.7 Build and verify

```bash
cd cpp && ./build.sh
PYTHONPATH=python:cpp/build python -c "import filters_cpp; print(dir(filters_cpp))"
```

Verify new functions appear: `physarum_init`, `physarum_step`, `physarum_get_trail`, `physarum_reset`.

### Deliverables

| File | Description |
|------|------------|
| `cpp/src/filters/physarum.cpp` | Physarum simulation core (mandatory) |
| `cpp/include/filters/physarum.hpp` | Physarum header (mandatory) |
| `cpp/src/filters/particle_update.cpp` | Particle update loop (optional) |
| `cpp/src/filters/boids_update.cpp` | Boids update loop (optional) |
| `cpp/src/bridge/pybind_filters.cpp` | Updated bindings (mandatory) |
| `cpp/include/filters/filters_api.hpp` | Updated API declarations (mandatory) |
| `cpp/CMakeLists.txt` | Updated source list (mandatory) |
| `adapters/processors/filters/cpp_physarum.py` | Python C++ wrapper (mandatory) |

### Acceptance Criteria

- [ ] `cpp/build.sh` compiles without errors
- [ ] `import filters_cpp` exposes physarum functions
- [ ] `CppPhysarumFilter` works when C++ is available
- [ ] `CppPhysarumFilter` falls back gracefully when C++ is unavailable (ImportError path)
- [ ] No heap allocation per `physarum_step()` call
- [ ] `py::gil_scoped_release` wraps the simulation step
- [ ] Physarum simulation runs 10000 agents in <5ms (measured with `time.perf_counter()`)
- [ ] C++ code compiles with C++17, no warnings with `-Wall -Wextra`

---

## Phase 5: Integration Tests

**Goal:** Test filters working together in realistic pipeline scenarios.

### Test File

**File:** `python/ascii_stream_engine/tests/test_new_filters_integration.py`

### Tasks

#### 5.1 Filter chain tests

```python
@pytest.mark.integration
def test_multiple_new_filters_in_chain():
    """Multiple new filters applied sequentially produce valid output."""
    filters = [
        EdgeSmoothFilter(strength=0.5),
        StipplingFilter(density=0.3),
        UVDisplacementFilter(amplitude=5.0),
    ]
    config = EngineConfig()
    frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
    result = frame
    for f in filters:
        result = f.apply(result, config)
    assert result.shape == frame.shape
    assert result.dtype == np.uint8

@pytest.mark.integration
def test_stateful_filters_in_chain():
    """Stateful filters chain correctly over multiple frames."""
    filters = [
        OpticalFlowParticlesFilter(max_particles=100),
        BoidsFilter(num_boids=50),
    ]
    config = EngineConfig()
    for _ in range(5):
        frame = np.random.randint(0, 255, (120, 160, 3), dtype=np.uint8)
        result = frame
        for f in filters:
            result = f.apply(result, config)
        assert result.shape == frame.shape
```

#### 5.2 Interaction with analysis dict

```python
@pytest.mark.integration
def test_filters_with_perception_data():
    """Filters correctly use perception analysis dict."""
    analysis = {
        "face": {"points": np.random.rand(468, 2).astype(np.float32)},
        "hands": {
            "left": np.random.rand(21, 2).astype(np.float32),
            "right": np.random.rand(21, 2).astype(np.float32),
        },
        "pose": {"joints": np.random.rand(17, 2).astype(np.float32)},
    }
    filters = [
        RadialCollapseFilter(follow_face=True, strength=0.3),
        OpticalFlowParticlesFilter(max_particles=100),
        BoidsFilter(num_boids=50, attract_to_analysis=True),
    ]
    config = EngineConfig()
    frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
    for f in filters:
        frame = f.apply(frame, config, analysis=analysis)
    assert frame.shape == (240, 320, 3)

@pytest.mark.integration
def test_filters_with_empty_analysis():
    """All filters handle empty analysis gracefully."""
    filters = [
        RadialCollapseFilter(follow_face=True),
        OpticalFlowParticlesFilter(),
        BoidsFilter(attract_to_analysis=True),
    ]
    config = EngineConfig()
    frame = np.random.randint(0, 255, (120, 160, 3), dtype=np.uint8)
    for f in filters:
        frame = f.apply(frame, config, analysis={})
    assert frame.shape == (120, 160, 3)
```

#### 5.3 Resolution change mid-stream

```python
@pytest.mark.integration
def test_resolution_change_all_filters():
    """All filters handle resolution change without crashing."""
    filters = [
        OpticalFlowParticlesFilter(),
        StipplingFilter(density=0.3),
        UVDisplacementFilter(amplitude=5.0),
        EdgeSmoothFilter(),
        RadialCollapseFilter(strength=0.3),
        PhysarumFilter(num_agents=100, sim_scale=2),
        BoidsFilter(num_boids=50),
    ]
    config = EngineConfig()
    # Run at 320x240
    for _ in range(3):
        frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
        for f in filters:
            frame = f.apply(frame, config)
    # Switch to 640x480
    for _ in range(3):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        for f in filters:
            frame = f.apply(frame, config)
        assert frame.shape == (480, 640, 3)
```

#### 5.4 Combined latency test

```python
@pytest.mark.integration
@pytest.mark.slow
def test_combined_filter_latency():
    """All 7 filters combined stay within budget (5ms target, 8ms p95 max)."""
    import time
    filters = [
        OpticalFlowParticlesFilter(max_particles=500),
        StipplingFilter(density=0.3),
        UVDisplacementFilter(amplitude=5.0),
        EdgeSmoothFilter(),
        RadialCollapseFilter(strength=0.3),
        PhysarumFilter(num_agents=500, sim_scale=4),
        BoidsFilter(num_boids=100),
    ]
    config = EngineConfig()
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    # Warm up (build LUTs, init state)
    for _ in range(5):
        result = frame.copy()
        for f in filters:
            result = f.apply(result, config)
    # Measure
    times = []
    for _ in range(20):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        t0 = time.perf_counter()
        result = frame
        for f in filters:
            result = f.apply(result, config)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)
    median = sorted(times)[len(times) // 2]
    p95 = sorted(times)[int(len(times) * 0.95)]
    # Log results (not strict assert -- depends on hardware)
    print(f"Filter chain: median={median:.1f}ms, p95={p95:.1f}ms")
    # Soft assert: p95 should be under 50ms even in Python-only mode
    assert p95 < 50, f"Combined filter latency p95={p95:.1f}ms exceeds 50ms"
```

### Deliverables

| File | Tests (est.) |
|------|-------------|
| `python/ascii_stream_engine/tests/test_new_filters_integration.py` | 10-15 tests |

### Acceptance Criteria

- [ ] All integration tests pass
- [ ] Filter chain produces valid `(H, W, 3)` uint8 output at every step
- [ ] Analysis dict is never mutated by any filter
- [ ] Resolution change mid-stream does not crash any filter
- [ ] Combined latency is measured and logged
- [ ] Tests marked with `@pytest.mark.integration`
- [ ] Slow tests marked with `@pytest.mark.slow`

---

## Phase 6: Performance Validation

**Goal:** Profile each filter individually and in combination, optimize to meet the 5ms combined budget.

### Tasks

#### 6.1 Individual filter profiling

Profile each filter at 640x480 resolution using `time.perf_counter()`:

| Filter | Target (ms) | Method |
|--------|-------------|--------|
| Optical Flow Particles | <3ms | Farneback is ~2ms at 640x480; particle render <1ms |
| Stippling / Pointillism | <1ms (cache hit), <3ms (rebuild) | Grid is cached; color sampling is vectorized |
| UV Math Displacement | <2ms (cache hit) | cv2.remap is fast; phase offset is a float add |
| Edge-Aware Smoothing | <4ms | cv2.bilateralFilter with d=9 |
| Radial Collapse / Singularity | <2ms (cache hit) | cv2.remap; maps cached |
| Physarum Simulation | <5ms (C++), <20ms (Python) | C++ mandatory for production |
| Boids / Flocking Particles | <3ms (200 boids Python), <1ms (C++) | Vectorized numpy for Python |

#### 6.2 Heavy filter optimization strategies

For filters exceeding budget:

1. **Reduced simulation resolution**
   - Physarum: simulate at `frame_size / sim_scale` (default 4x)
   - Optical Flow: compute flow at half resolution, interpolate
   - Document `sim_scale` parameter in docstring

2. **LUT cache hit rate validation**
   - Add `_cache_hits` and `_cache_misses` counters (debug only)
   - Verify cache hit rate >95% during steady-state operation
   - Log cache rebuild triggers (param change, resolution change)

3. **Memory usage for stateful filters**
   - Optical Flow: `_prev_gray` = H*W bytes, `_particles` = N*20 bytes
   - Physarum: `_trail_map` = (H/s)*(W/s)*4 bytes, `_agents` = N*12 bytes
   - Boids: `_positions` = N*8 bytes, `_velocities` = N*8 bytes
   - Document memory usage in class docstring

4. **Frame copy audit**
   - Verify each filter makes exactly 0 or 1 copies
   - Use `np.shares_memory(input, output)` to detect unexpected copies
   - No filter should copy in a no-op path

#### 6.3 Profiling script

**File:** `python/ascii_stream_engine/tests/profile_new_filters.py` (not a test, a utility script)

```python
"""Profile new filters individually and combined.

Usage: PYTHONPATH=python:cpp/build python python/ascii_stream_engine/tests/profile_new_filters.py
"""
```

Output: table of per-filter median/p95 latency at 640x480, plus combined chain latency.

#### 6.4 Optimization pass

Based on profiling results, apply optimizations:
- Move hot loops to numpy vectorized operations
- Replace `cv2.circle` loops with pre-rendered sprite blitting
- Use `cv2.remap` with `INTER_NEAREST` for non-quality-critical remaps
- Reduce default parameter values (fewer particles, lower density)
- Ensure LUT rebuilds are amortized over many frames

### Deliverables

| File | Description |
|------|------------|
| `python/ascii_stream_engine/tests/profile_new_filters.py` | Profiling utility script |
| Updated filter files | Optimizations applied based on profiling |

### Acceptance Criteria

- [ ] Every filter individually measured at 640x480
- [ ] Physarum C++ version: <5ms for 10000 agents
- [ ] LUT-cached filters: cache hit latency <1ms
- [ ] Combined chain (all 7 active, moderate params): median <15ms Python, <8ms with C++
- [ ] No filter exceeds 0-1 frame copies (verified)
- [ ] Memory usage documented in docstrings for stateful filters
- [ ] Profiling script runnable with `PYTHONPATH=python:cpp/build python <script>`
- [ ] Heavy filters document reduced-resolution strategy in docstring

---

## Phase 7: PR Preparation

**Goal:** Register all filters, update documentation, and submit a clean PR to `develop`.

### Tasks

#### 7.1 Register filters in `__init__.py`

**File:** `python/ascii_stream_engine/adapters/processors/filters/__init__.py`

Add imports and `__all__` entries for all 7 new Python filters + C++ wrappers:

```python
from .optical_flow_particles import OpticalFlowParticlesFilter
from .stippling import StipplingFilter
from .uv_displacement import UVDisplacementFilter
from .edge_smooth import EdgeSmoothFilter
from .radial_collapse import RadialCollapseFilter
from .physarum import PhysarumFilter
from .boids import BoidsFilter
from .cpp_physarum import CppPhysarumFilter
# Optional: CppOpticalFlowParticlesFilter, CppBoidsFilter

__all__ = [
    # ... existing ...
    "OpticalFlowParticlesFilter",
    "StipplingFilter",
    "UVDisplacementFilter",
    "EdgeSmoothFilter",
    "RadialCollapseFilter",
    "PhysarumFilter",
    "BoidsFilter",
    "CppPhysarumFilter",
]
```

**File:** `python/ascii_stream_engine/adapters/processors/__init__.py` -- Add re-exports if needed.

**File:** `python/ascii_stream_engine/__init__.py` -- Add to top-level `__all__` if public API.

**NEVER modify `FilterPipeline`** (`application/pipeline/filter_pipeline.py`).

#### 7.2 Update CHANGELOG.md

**File:** `CHANGELOG.md`

Under `[Unreleased]`, add:

```markdown
### Added
- Optical Flow Particles filter: motion-reactive particle system (stateful)
- Stippling / Pointillism filter: LUT-cached dot placement effect
- UV Math Displacement filter: parametric math-based remap distortion
- Edge-Aware Smoothing filter: bilateral filter with blend control
- Radial Collapse / Singularity filter: polar coordinate remap distortion
- Physarum Simulation Overlay filter: slime mold simulation (C++ accelerated)
- Boids / Flocking Particles filter: flocking particle system (stateful)
- C++ Physarum simulation core (`cpp/src/filters/physarum.cpp`)
```

#### 7.3 Update progress.md

**File:** `.claude/orchestration/teams/filters/progress.md`

Document:
- Completion status for each phase
- Per-filter implementation status
- Test results summary
- Latency measurements
- Known issues or limitations

#### 7.4 Update findings.md

**File:** `.claude/orchestration/teams/filters/findings.md`

Document:
- Algorithm choices and rationale
- Performance measurements vs. estimates
- LUT cache hit rates observed
- C++ vs. Python performance comparison for Physarum
- Lessons learned

#### 7.5 Code quality checks

Run before PR submission:

```bash
# Format
make format

# Lint
make lint

# All tests pass
make test

# Specific new filter tests
PYTHONPATH=python:cpp/build python -m pytest python/ascii_stream_engine/tests/test_new_filters.py -v
PYTHONPATH=python:cpp/build python -m pytest python/ascii_stream_engine/tests/test_new_filters_integration.py -v

# C++ build (if applicable)
cd cpp && ./build.sh
```

#### 7.6 Create PR to develop

Branch: `feature/filters-wave2` (or team branch from orchestration)
Target: `develop`

PR title: `feat(filters): add 7 new creative image filters`

PR description should include:
- Summary of all 7 filters with categories
- Latency measurements table
- C++ acceleration details (Physarum)
- Test coverage summary
- Breaking changes: none (additive only)

### Deliverables

| File | Action |
|------|--------|
| `adapters/processors/filters/__init__.py` | Updated with 8 new imports |
| `CHANGELOG.md` | Updated `[Unreleased]` section |
| `.claude/orchestration/teams/filters/progress.md` | Final status report |
| `.claude/orchestration/teams/filters/findings.md` | Research findings and measurements |
| PR to `develop` | Created via `gh pr create` |

### Acceptance Criteria

- [ ] All 7 filters + 1 C++ wrapper registered in `__init__.py`
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] `make format` passes (no changes)
- [ ] `make lint` passes (no warnings)
- [ ] `make test` passes (all existing + new tests green)
- [ ] C++ builds without errors (`cpp/build.sh`)
- [ ] PR created targeting `develop` branch
- [ ] PR description includes latency measurements
- [ ] No files modified in `application/`, `ports/`, or `domain/`
- [ ] Conventional commit message: `feat(filters): ...`
- [ ] `progress.md` reflects final status
- [ ] `findings.md` contains research documentation

---

## Dependency Graph

```
Phase 1 (Research)
    |
    v
Phase 2 (Python Implementation)
    |
    +---> Phase 3 (Unit Tests)        -- can start as filters are written
    |         |
    v         v
Phase 4 (C++ Implementation)         -- depends on Phase 2 for interface design
    |
    v
Phase 5 (Integration Tests)          -- depends on Phase 2 + Phase 4
    |
    v
Phase 6 (Performance Validation)     -- depends on Phase 2 + Phase 4 + Phase 5
    |
    v
Phase 7 (PR Preparation)             -- depends on all prior phases
```

**Parallelization opportunities:**
- Phase 3 (unit tests) can start as soon as each filter in Phase 2 is complete
- Phase 4 (C++) can start once Phase 2 establishes the Python interface for Physarum
- Filters within Phase 2 are independent and can be implemented in any order

## Summary

| Phase | Duration (est.) | Key Outputs |
|-------|----------------|-------------|
| 1. Research & Design | 1 session | `findings.md`, algorithm designs, classification table |
| 2. Python Implementation | 2-3 sessions | 7 new filter `.py` files (~700-900 lines total) |
| 3. Unit Tests | 1-2 sessions | `test_new_filters.py` (~35-45 tests) |
| 4. C++ Implementation | 1-2 sessions | `physarum.cpp`, updated pybind, `cpp_physarum.py` |
| 5. Integration Tests | 1 session | `test_new_filters_integration.py` (~10-15 tests) |
| 6. Performance Validation | 1 session | `profile_new_filters.py`, optimized filters |
| 7. PR Preparation | 1 session | Updated `__init__.py`, `CHANGELOG.md`, PR created |

**Total: 8-11 sessions**
