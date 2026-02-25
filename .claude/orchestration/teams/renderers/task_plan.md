# Renderers Team -- 7-Phase Task Plan

**Team scope:** Build 5 new renderers that implement the `FrameRenderer` protocol.
**Skill reference:** `.claude/skills/renderer-development/SKILL.md`
**Branch:** `feature/renderers-*` (one branch per renderer, rebased on `develop`)

---

## Renderers to Deliver

| # | Renderer | Key Challenge |
|---|---|---|
| 1 | Heatmap Overlay Renderer | Gaussian kernel accumulation from analysis density |
| 2 | Optical Flow Visualization Renderer | Frame-to-frame motion vectors as colored arrows |
| 3 | Deformed Grid Renderer (C++) | C++ mesh deformation with Python fallback |
| 4 | Segmentation Mask Overlay | Colored regions blended from segmentation analysis |
| 5 | Multi-View Renderer | Tile multiple render modes into a single output |

---

## Phase 1: Protocol Audit and Base Scaffold

**Goal:** Verify the `FrameRenderer` protocol contract, create file scaffolds for all 5 renderers, and establish the shared test harness.

### Deliverables

1. **Audit the protocol and domain types** -- read and confirm understanding of:
   - `python/ascii_stream_engine/ports/renderers.py` -- `FrameRenderer` protocol
   - `python/ascii_stream_engine/domain/types.py` -- `RenderFrame` dataclass
   - `python/ascii_stream_engine/domain/config.py` -- `EngineConfig` fields used by renderers (`raw_width`, `raw_height`, `render_mode`)

2. **Create 5 renderer source files** (empty scaffolds with correct imports, class stubs, and docstrings):
   - `python/ascii_stream_engine/adapters/renderers/heatmap_overlay_renderer.py`
   - `python/ascii_stream_engine/adapters/renderers/optical_flow_renderer.py`
   - `python/ascii_stream_engine/adapters/renderers/deformed_grid_renderer.py`
   - `python/ascii_stream_engine/adapters/renderers/segmentation_mask_renderer.py`
   - `python/ascii_stream_engine/adapters/renderers/multi_view_renderer.py`

3. **Create shared test file:**
   - `python/ascii_stream_engine/tests/test_renderers_new.py`
   - Include a `BaseRendererTestMixin` with the 4 mandatory tests from the skill reference:
     - `test_produces_renderframe` -- output is `RenderFrame` with `PIL.Image.Image` in RGB mode
     - `test_output_size_matches_render` -- `output_size()` matches `result.image.size`
     - `test_grayscale_input` -- handles `(H, W)` uint8 without error
     - `test_with_analysis` -- handles analysis dict without error

4. **Do NOT register in `__init__.py` yet** -- registration happens in Phase 6.

### Acceptance Criteria

- [ ] All 5 `.py` files exist with valid Python syntax (importable, no runtime errors)
- [ ] Each class has `output_size` and `render` method stubs that raise `NotImplementedError`
- [ ] Test file is importable; tests are skipped or xfail against stubs
- [ ] No files in `ports/`, `domain/`, or `application/` are modified
- [ ] `make lint` passes on all new files

---

## Phase 2: Heatmap Overlay Renderer

**Goal:** Implement a renderer that visualizes analysis point density as a color heatmap overlaid on the source frame.

### File

`python/ascii_stream_engine/adapters/renderers/heatmap_overlay_renderer.py`

### Design

```
class HeatmapOverlayRenderer:
    __init__(self, inner=None, colormap=cv2.COLORMAP_JET, alpha=0.4, kernel_size=31)
    output_size(self, config) -> (w, h)
    render(self, frame, config, analysis=None) -> RenderFrame
```

**Algorithm:**
1. If `inner` renderer is provided, delegate to it first (decorator pattern per `LandmarksOverlayRenderer`). Convert inner PIL RGB back to BGR numpy for cv2 drawing.
2. If no inner, copy the frame (`img = frame.copy()`). Handle grayscale: `cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)`.
3. Build a density map from analysis coordinates:
   - Extract all normalized point arrays from `analysis` keys (`face.points`, `hands.left`, `hands.right`, `pose.joints`).
   - For each point `(nx, ny)`, increment a float32 accumulator at `(int(ny * h), int(nx * w))`.
   - Apply `cv2.GaussianBlur` with `kernel_size` to spread density.
   - Normalize to 0-255, apply `cv2.applyColorMap` with the configured colormap.
4. Blend heatmap onto `img` using `cv2.addWeighted(img, 1.0 - alpha, heatmap_bgr, alpha, 0)`.
5. Convert BGR to RGB: `cv2.cvtColor(img, cv2.COLOR_BGR2RGB)`.
6. Return `RenderFrame(image=Image.fromarray(rgb), metadata={"source": "heatmap_overlay"})`.

**Performance:**
- Preallocate the `_density_map` buffer as a class attribute; reuse with `fill(0)` each frame.
- Only rebuild when frame shape changes (dirty flag on `(h, w)`).
- Gaussian blur is the hot operation; use small kernel (31x31 default).
- Total budget: < 3ms. GaussianBlur on 640x480 float32 at kernel 31 is ~0.8ms.

### Tests (in `test_renderers_new.py`)

- `TestHeatmapOverlayRenderer` inherits `BaseRendererTestMixin`
- `test_heatmap_no_analysis` -- produces valid output even with `analysis=None`
- `test_heatmap_with_face_points` -- given face points, output image differs from passthrough (pixel comparison)
- `test_heatmap_decorator_wraps_inner` -- wrapping a `PassthroughRenderer` produces valid output
- `test_heatmap_colormap_configurable` -- different colormaps produce different outputs
- `test_heatmap_buffer_reuse` -- rendering twice with same frame shape reuses the density buffer (check `id(renderer._density_map)` is stable)

### Acceptance Criteria

- [ ] All `BaseRendererTestMixin` tests pass
- [ ] All heatmap-specific tests pass
- [ ] Handles empty analysis gracefully (returns frame without heatmap)
- [ ] Handles analysis with only some keys present (e.g., only `face`, no `hands`)
- [ ] Single frame copy (the `addWeighted` blend operates in-place on the copy)
- [ ] Latency < 3ms on 640x480 frame (measure with `time.perf_counter()` in test)
- [ ] `make lint` passes

---

## Phase 3: Optical Flow Visualization Renderer

**Goal:** Implement a renderer that computes frame-to-frame optical flow and visualizes motion vectors as colored arrows on the frame.

### File

`python/ascii_stream_engine/adapters/renderers/optical_flow_renderer.py`

### Design

```
class OpticalFlowRenderer:
    __init__(self, inner=None, arrow_scale=3.0, grid_step=16, arrow_color_mode="direction")
    output_size(self, config) -> (w, h)
    render(self, frame, config, analysis=None) -> RenderFrame
```

**Algorithm:**
1. Maintain `_prev_gray` buffer (previous frame in grayscale) as instance state.
2. Convert current frame to grayscale: `gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)` (or use directly if `ndim == 2`).
3. If `_prev_gray` is None (first frame), store `gray.copy()`, return passthrough render.
4. Compute dense optical flow: `flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)`.
5. If inner renderer provided, delegate and convert back to BGR. Otherwise, `img = frame.copy()` (handle grayscale).
6. Sample flow at grid positions (every `grid_step` pixels):
   - For each grid point `(x, y)`, get `(dx, dy) = flow[y, x]`.
   - Compute arrow endpoint: `(x + dx * arrow_scale, y + dy * arrow_scale)`.
   - Color by direction: convert `atan2(dy, dx)` to hue in HSV, then to BGR.
   - Draw with `cv2.arrowedLine(img, start, end, color, thickness=1, tipLength=0.3)`.
7. Update `_prev_gray = gray.copy()`.
8. Convert BGR to RGB, return `RenderFrame`.

**Stateful renderer rules (from `PIPELINE_EXTENSION_RULES.md` stateful filter pattern):**
- Implement `reset(self)` to clear `_prev_gray`.
- Handle shape changes: if `gray.shape != _prev_gray.shape`, reinitialize.
- Never store more than 1 previous frame.

**Performance:**
- `calcOpticalFlowFarneback` is expensive (~5-10ms on 640x480). To stay within 3ms budget:
  - Downsample both frames by 2x before flow computation, then scale vectors back up.
  - Use `pyrScale=0.5, levels=2, winsize=11` (faster parameters).
- Arrow drawing: vectorize grid sampling with numpy slicing, minimize Python loop iterations.
- Preallocate `_prev_gray` buffer.

### Tests

- `TestOpticalFlowRenderer` inherits `BaseRendererTestMixin`
- `test_flow_first_frame_passthrough` -- first frame returns valid output without arrows
- `test_flow_second_frame_has_motion` -- two different frames produce an image with arrow artifacts (pixel diff > 0)
- `test_flow_reset_clears_state` -- after `reset()`, `_prev_gray` is `None`
- `test_flow_shape_change_reinitializes` -- sending a different resolution frame after the first does not crash
- `test_flow_decorator_wraps_inner` -- wrapping `PassthroughRenderer` produces valid output

### Acceptance Criteria

- [ ] All `BaseRendererTestMixin` tests pass
- [ ] All flow-specific tests pass
- [ ] First frame never crashes (graceful passthrough)
- [ ] Resolution change mid-stream does not crash
- [ ] `reset()` method exists and clears state
- [ ] Arrow colors encode motion direction (HSV-based coloring)
- [ ] Latency < 3ms on 640x480 with downsampled flow (document actual measured latency)
- [ ] `make lint` passes

---

## Phase 4: Deformed Grid Renderer (C++ Accelerated)

**Goal:** Implement a mesh deformation renderer with C++ acceleration and a pure-Python fallback.

### Files

- `python/ascii_stream_engine/adapters/renderers/deformed_grid_renderer.py` -- Python adapter with fallback
- `cpp/src/renderers/deformed_grid.cpp` -- C++ mesh deformation core
- `cpp/src/renderers/deformed_grid.h` -- C++ header
- `cpp/src/bridge/pybind_deformed_grid.cpp` -- pybind11 bindings

### Design (Python adapter)

```
class DeformedGridRenderer:
    __init__(self, inner=None, grid_rows=20, grid_cols=20, deform_strength=0.3)
    output_size(self, config) -> (w, h)
    render(self, frame, config, analysis=None) -> RenderFrame
```

**Python fallback algorithm (when C++ unavailable):**
1. Build a regular mesh grid of control points: `np.mgrid[0:h:grid_rows, 0:w:grid_cols]`.
2. Displace control points based on analysis data:
   - Face/hand/pose landmarks push nearby grid vertices outward (repulsion field).
   - Displacement magnitude = `deform_strength * (1.0 / (distance + epsilon))`.
3. Interpolate displaced mesh into a dense remap map using `cv2.remap` with `map_x`, `map_y`.
4. Apply `cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR)` to produce deformed frame.
5. Convert BGR to RGB, return `RenderFrame`.

**C++ accelerated path:**
1. Follow `CppDeformedRenderer` pattern in `cpp_renderer.py`:
   ```python
   try:
       import deformed_grid_cpp as _deformed_grid
       _CPP_AVAILABLE = True
   except ImportError:
       _deformed_grid = None
       _CPP_AVAILABLE = False
   ```
2. C++ receives `(frame: uint8[H,W,3], landmarks: float32[N,2], grid_rows, grid_cols, strength)`.
3. C++ builds mesh, computes displacements, applies `cv::remap` -- all with GIL released.
4. Returns deformed frame as `uint8[H,W,3]`.

**C++ implementation details:**
- GIL release during mesh computation and remap (follows `rules/PERFORMANCE_RULES.md` section 3).
- Buffer reuse: preallocate `map_x`, `map_y` as member variables, only reallocate on shape change.
- pybind11: expose `deform_grid(frame, landmarks, grid_rows, grid_cols, strength) -> ndarray`.

**Remap cache (LUT pattern from `PIPELINE_EXTENSION_RULES.md`):**
- Cache the remap tables (`map_x`, `map_y`) as instance attributes.
- Only recompute when analysis landmarks change significantly (L2 norm of landmark delta > threshold).
- Use `_params_dirty` flag pattern.

### Tests

- `TestDeformedGridRenderer` inherits `BaseRendererTestMixin`
- `test_deformed_no_analysis_passthrough` -- without analysis, frame passes through undeformed
- `test_deformed_with_landmarks` -- with face points, output differs from input (pixel comparison)
- `test_deformed_python_fallback` -- force `_CPP_AVAILABLE = False`, verify fallback works
- `test_deformed_grid_params` -- different `grid_rows`/`grid_cols` produce different results
- `test_deformed_remap_cache` -- consecutive calls with same landmarks reuse cached remap (check `_params_dirty`)
- `test_deformed_cpp_import_fallback` -- mock `ImportError` on the C++ module, verify graceful fallback

### Acceptance Criteria

- [ ] All `BaseRendererTestMixin` tests pass
- [ ] Python fallback works without any C++ module compiled
- [ ] C++ path works when module is compiled (integration test, may be skipped in CI)
- [ ] `ImportError` fallback is graceful (no crash, passthrough behavior)
- [ ] Remap tables are cached and reused when landmarks are stable
- [ ] GIL is released during C++ computation
- [ ] C++ buffers are preallocated and reused (no per-frame heap allocation)
- [ ] Latency < 3ms with C++ path on 640x480; Python fallback documented (may exceed budget)
- [ ] `make lint` passes; C++ compiles with `make cpp-build`

---

## Phase 5: Segmentation Mask Overlay Renderer

**Goal:** Implement a renderer that blends colored segmentation regions from analysis onto the frame.

### File

`python/ascii_stream_engine/adapters/renderers/segmentation_mask_renderer.py`

### Design

```
class SegmentationMaskRenderer:
    __init__(self, inner=None, alpha=0.5, class_colors=None)
    output_size(self, config) -> (w, h)
    render(self, frame, config, analysis=None) -> RenderFrame
```

**Expected analysis dict keys:**
```python
analysis = {
    "segmentation": {
        "mask": np.ndarray,      # (H, W) uint8, class IDs per pixel (0=background)
        "class_names": list,     # ["background", "person", "car", ...] (optional)
        "num_classes": int,      # total number of classes
    },
    # Also supports the existing silhouette_segmentation key:
    "silhouette_segmentation": {
        "person_mask": np.ndarray,  # (H, W) uint8, 0=bg, 255=person
    },
}
```

**Algorithm:**
1. If inner renderer provided, delegate and convert back to BGR. Otherwise, `img = frame.copy()` (handle grayscale).
2. Extract segmentation data from analysis:
   - Primary: `analysis.get("segmentation", {}).get("mask")` -- multi-class mask.
   - Fallback: `analysis.get("silhouette_segmentation", {}).get("person_mask")` -- binary mask.
3. If no mask found, return frame as-is (passthrough).
4. Generate class-to-color mapping:
   - Use `class_colors` if provided (dict mapping class_id to BGR tuple).
   - Default: generate distinct colors using HSV spacing: `hue = (class_id * 137.508) % 360` (golden angle for max separation).
   - Class 0 (background) is always transparent (no overlay).
5. Build a colored overlay:
   - Create `overlay = np.zeros_like(img)`.
   - For each class_id > 0: `overlay[mask == class_id] = class_colors[class_id]`.
   - For binary mask (silhouette): `overlay[person_mask > 127] = class_colors[1]`.
6. Blend: `cv2.addWeighted(img, 1.0, overlay, alpha, 0, dst=img)` (in-place on copy).
7. Resize mask to frame dimensions if shapes differ: `cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)`.
8. Convert BGR to RGB, return `RenderFrame(image=..., metadata={"source": "segmentation_mask", "num_classes": ...})`.

**Performance:**
- Precompute the `_color_lut` (lookup table: class_id -> BGR color) once on init or when `num_classes` changes.
- Use vectorized numpy for overlay construction: `overlay = color_lut[mask]` (index an (N, 3) array by the mask).
- Avoid Python loops over pixels.
- Mask resize uses `INTER_NEAREST` to preserve class IDs.

### Tests

- `TestSegmentationMaskRenderer` inherits `BaseRendererTestMixin`
- `test_segmentation_no_analysis` -- returns valid output without segmentation data
- `test_segmentation_multiclass_mask` -- with a 3-class mask, output has colored regions
- `test_segmentation_binary_mask` -- with `silhouette_segmentation.person_mask`, overlay is applied
- `test_segmentation_custom_colors` -- custom `class_colors` dict produces expected BGR values in output
- `test_segmentation_mask_resize` -- mask at different resolution than frame is resized correctly
- `test_segmentation_background_transparent` -- class 0 pixels are not colored
- `test_segmentation_decorator_wraps_inner` -- wrapping `PassthroughRenderer` works

### Acceptance Criteria

- [ ] All `BaseRendererTestMixin` tests pass
- [ ] All segmentation-specific tests pass
- [ ] Handles missing segmentation data gracefully (passthrough)
- [ ] Handles both multi-class mask and binary person mask
- [ ] Mask resolution mismatch handled with `INTER_NEAREST` resize
- [ ] Background (class 0) is never colored
- [ ] Color LUT is vectorized (no per-pixel Python loop)
- [ ] Latency < 3ms on 640x480 frame with 10-class mask
- [ ] `make lint` passes

---

## Phase 6: Multi-View Renderer

**Goal:** Implement a renderer that tiles the output of multiple inner renderers into a single composite image.

### File

`python/ascii_stream_engine/adapters/renderers/multi_view_renderer.py`

### Design

```
class MultiViewRenderer:
    __init__(self, renderers: List[FrameRenderer], layout="auto", border_width=2, border_color=(40, 40, 40))
    output_size(self, config) -> (w, h)
    render(self, frame, config, analysis=None) -> RenderFrame
```

**Parameters:**
- `renderers` -- list of `FrameRenderer` instances to tile. Minimum 1, maximum 9.
- `layout` -- `"auto"` (compute grid), `"2x1"`, `"1x2"`, `"2x2"`, `"3x1"`, `"1x3"`, `"3x3"`, or `"NxM"` string.
- `border_width` -- pixel width of border between tiles.
- `border_color` -- BGR color of border.

**Algorithm:**
1. Determine grid layout:
   - `"auto"`: compute `cols = ceil(sqrt(n))`, `rows = ceil(n / cols)`.
   - `"NxM"`: parse N columns, M rows.
   - Validate: `rows * cols >= len(renderers)`.
2. Compute per-tile size: `tile_w = (total_w - (cols - 1) * border_width) // cols`, same for height.
3. Compute total output size: `total_w = tile_w * cols + (cols - 1) * border_width`, same for height. Derive from `config` base size.
4. Create output canvas: `canvas = np.full((total_h, total_w, 3), border_color, dtype=np.uint8)` in BGR.
5. For each renderer in the list:
   - Call `renderer.render(frame, config, analysis)`.
   - Convert the returned PIL RGB image back to BGR numpy.
   - Resize to `(tile_w, tile_h)` if needed.
   - Place into canvas at the correct grid position.
6. Empty grid cells (when `len(renderers) < rows * cols`) are left as border color.
7. Convert BGR to RGB, return `RenderFrame(image=..., metadata={"source": "multi_view", "layout": f"{cols}x{rows}", "renderer_count": len(renderers)})`.

**PIL Image caching:**
- Cache the output PIL Image when size is unchanged (same pattern as `AsciiRenderer`):
  ```python
  if self._cached_image is not None and self._cached_size == (total_w, total_h):
      # Reuse
  ```

### Tests

- `TestMultiViewRenderer` inherits `BaseRendererTestMixin`
- `test_multi_view_single_renderer` -- 1 renderer fills the entire canvas
- `test_multi_view_two_renderers` -- 2 renderers tile as `1x2` or `2x1`
- `test_multi_view_four_renderers_2x2` -- 4 renderers in a `2x2` grid
- `test_multi_view_auto_layout` -- `"auto"` with 3 renderers produces `2x2` grid with one empty cell
- `test_multi_view_custom_layout` -- explicit `"3x1"` layout with 3 renderers
- `test_multi_view_border` -- border pixels are the configured `border_color`
- `test_multi_view_mixed_renderers` -- mixing `PassthroughRenderer` and `HeatmapOverlayRenderer` works
- `test_multi_view_output_size_consistent` -- `output_size()` matches the rendered image dimensions
- `test_multi_view_empty_renderers_list` -- raises `ValueError` if renderers list is empty

### Acceptance Criteria

- [ ] All `BaseRendererTestMixin` tests pass
- [ ] All multi-view-specific tests pass
- [ ] Grid layout is computed correctly for 1-9 renderers
- [ ] Custom layout strings (`"NxM"`) are parsed and validated
- [ ] Border between tiles is the configured color and width
- [ ] Empty cells are filled with border color (not black, not garbage)
- [ ] Each inner renderer receives the same `frame`, `config`, and `analysis`
- [ ] PIL Image caching is implemented for repeated same-size renders
- [ ] Latency scales linearly with renderer count (document per-tile overhead)
- [ ] `make lint` passes

---

## Phase 7: Integration, Registration, and Documentation

**Goal:** Register all 5 renderers, run full test suite, verify integration with the engine, and document.

### Deliverables

1. **Register all renderers in `__init__.py`:**

   Update `python/ascii_stream_engine/adapters/renderers/__init__.py`:
   ```python
   from .heatmap_overlay_renderer import HeatmapOverlayRenderer
   from .optical_flow_renderer import OpticalFlowRenderer
   from .deformed_grid_renderer import DeformedGridRenderer
   from .segmentation_mask_renderer import SegmentationMaskRenderer
   from .multi_view_renderer import MultiViewRenderer

   __all__ = [
       "AsciiRenderer",
       "CppDeformedRenderer",
       "DeformedGridRenderer",
       "FrameRenderer",
       "HeatmapOverlayRenderer",
       "LandmarksOverlayRenderer",
       "MultiViewRenderer",
       "OpticalFlowRenderer",
       "PassthroughRenderer",
       "SegmentationMaskRenderer",
   ]
   ```

2. **Register in top-level `__init__.py`:**

   Add all 5 new renderers to `python/ascii_stream_engine/__init__.py` `__all__` list.

3. **Run the full test suite:**
   ```bash
   make test
   ```
   All existing tests must continue to pass. All new tests must pass.

4. **Run lint and format checks:**
   ```bash
   make check
   ```

5. **Integration smoke test** (manual or notebook):
   - Instantiate `StreamEngine` with each new renderer.
   - Feed 10 frames from `DummySource`.
   - Verify no crashes, valid `RenderFrame` output at each step.
   - Test `MultiViewRenderer` wrapping all 4 other new renderers.

6. **Latency benchmark:**
   - For each renderer, measure p50 and p95 latency over 100 frames on 640x480 input.
   - Record results in the test file as comments or in renderer docstrings.
   - All renderers must be < 3ms p50 on 640x480 (except Python-fallback Deformed Grid, which must document its actual latency).

7. **Verify decorator stacking:**
   - `MultiViewRenderer([HeatmapOverlayRenderer(PassthroughRenderer()), OpticalFlowRenderer(), SegmentationMaskRenderer(PassthroughRenderer())])` produces valid output.
   - Nested decorators do not exceed the frame copy budget.

### Acceptance Criteria

- [ ] All 5 renderers are importable from `ascii_stream_engine.adapters.renderers`
- [ ] All 5 renderers are importable from `ascii_stream_engine` top-level
- [ ] `make test` passes with 0 failures
- [ ] `make check` passes (format + lint + tests)
- [ ] No files in `ports/`, `domain/`, or `application/` were modified across all phases
- [ ] Each renderer's docstring documents: purpose, analysis keys consumed, latency budget
- [ ] Decorator pattern works: any renderer can wrap any other renderer
- [ ] `MultiViewRenderer` successfully tiles all 4 other new renderers
- [ ] Latency benchmarks documented (p50 < 3ms on 640x480 for all except documented exceptions)
- [ ] C++ deformed grid compiles with `make cpp-build` (or gracefully skipped if C++ toolchain unavailable)
- [ ] Conventional commit per phase: `feat(renderers): <description>`

---

## File Summary

### New files to create

| Phase | File | Purpose |
|---|---|---|
| 1 | `adapters/renderers/heatmap_overlay_renderer.py` | Scaffold |
| 1 | `adapters/renderers/optical_flow_renderer.py` | Scaffold |
| 1 | `adapters/renderers/deformed_grid_renderer.py` | Scaffold |
| 1 | `adapters/renderers/segmentation_mask_renderer.py` | Scaffold |
| 1 | `adapters/renderers/multi_view_renderer.py` | Scaffold |
| 1 | `tests/test_renderers_new.py` | Shared test harness + all renderer tests |
| 4 | `cpp/src/renderers/deformed_grid.cpp` | C++ mesh deformation |
| 4 | `cpp/src/renderers/deformed_grid.h` | C++ header |
| 4 | `cpp/src/bridge/pybind_deformed_grid.cpp` | pybind11 bindings |

### Existing files to modify

| Phase | File | Change |
|---|---|---|
| 7 | `adapters/renderers/__init__.py` | Add imports + `__all__` entries |
| 7 | `ascii_stream_engine/__init__.py` | Add to `__all__` |
| 4 | `cpp/CMakeLists.txt` | Add deformed_grid target (if adding C++ module) |

### Files that must NEVER be modified

- `python/ascii_stream_engine/ports/renderers.py`
- `python/ascii_stream_engine/domain/types.py`
- `python/ascii_stream_engine/domain/config.py`
- `python/ascii_stream_engine/application/engine.py`
- `python/ascii_stream_engine/application/pipeline/*.py`
- Any existing renderer file (unless fixing a bug discovered during integration)

---

## Dependency Graph

```
Phase 1 (scaffolds + test harness)
  |
  +---> Phase 2 (Heatmap Overlay)
  |
  +---> Phase 3 (Optical Flow)
  |
  +---> Phase 4 (Deformed Grid + C++)
  |
  +---> Phase 5 (Segmentation Mask)
  |
  +---> Phase 6 (Multi-View) -- depends on at least 2 renderers from Phases 2-5
  |
  +---> Phase 7 (Integration) -- depends on all of Phases 2-6
```

Phases 2-5 are independent and can be developed in parallel after Phase 1 completes.
Phase 6 requires at least 2 working renderers from Phases 2-5 to test multi-view tiling.
Phase 7 requires all renderers to be complete.

---

## Conventions Checklist (every phase)

- [ ] Read `ports/renderers.py` and `domain/types.py` before writing (skill rule: read before write)
- [ ] BGR input, RGB output in `RenderFrame.image` (color space rule)
- [ ] Handle `frame.ndim == 2` grayscale input
- [ ] Maximum 1 frame copy per render call
- [ ] Normalized coordinates `(0-1)` from analysis scaled by `(w, h)`
- [ ] `output_size()` returns `(width, height)` matching rendered image size
- [ ] No imports from `application/` or `pipeline/`
- [ ] `make lint` passes before committing
- [ ] Conventional commit: `feat(renderers): add <renderer_name>`
- [ ] All code and comments in English
