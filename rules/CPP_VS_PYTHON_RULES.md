# C++ vs Python Rules

**One-sentence rule**: C++ is for per-pixel math we write ourselves; Python is for everything else — orchestration, config, UI, adapter glue, and any filter whose heavy step is already a call into OpenCV, numpy, PIL, or ONNX Runtime.

This doc answers a single question: *"For each kind of code, should it be written in Python or in C++?"* It links to the other rules (`PERFORMANCE_RULES.md`, `PIPELINE_EXTENSION_RULES.md`, `ARCHITECTURE.md`, `LATENCY_BUDGET.md`, `GRAPH_ARCHITECTURE.md`) rather than duplicating them.

---

## 1. Decision criteria (apply in order, stop at first match)

Run this checklist against the code you are about to write. Stop at the first rule that fires. If no rule fires, **write Python**.

1. **Is it orchestration, config parsing, pipeline wiring, adapter registration, port protocol, domain type, CLI glue, notebook code, or UI?** → Python. Always. See §4.

2. **Does the logic consist entirely of calls into OpenCV, numpy, PIL, or ONNX Runtime?** → Python. `cv2.remap`, `cv2.GaussianBlur`, `cv2.bilateralFilter`, `cv2.Canny`, `cv2.cvtColor`, `cv2.warpAffine`, `np.where` / `np.clip` / broadcasting on full frames — all already vectorized C++ under the hood. Re-implementing them in our own C++ is a negative-value exercise.

3. **Does the filter contain a Python-level `for` loop that iterates over rows, columns, pixels, or a mutable structure whose size grows with frame resolution or particle count, AND cannot be expressed as a numpy/cv2 batch call?** → C++. This is the canonical migration target.

   - The loop bound must be `O(H)`, `O(W)`, `O(H*W)`, or `O(N)` with `N ≥ 500`. A loop bound of `O(segments=6)`, `O(copies=3)`, `O(samples=8)`, `O(mip_levels=6)` is not a hot loop — keep it in Python.
   - A loop over a ≤ 21-slot ring buffer (e.g. `chrono_scan` after the April 2026 fix) is not a hot loop either.

4. **Does the filter perform pixel-level random writes through a mask or scatter (`out[mask] = val`, `np.add.at`, `cv2.circle` in a per-particle loop) with element count > 2000?** → C++ candidate, but try numpy fancy-indexing / batched disk-splat first (see the `optical_flow_particles` fix in `docs/performance/FPS_WINS_2026-04-18.md`). Escalate to C++ only if vectorization is impossible or the measured Python cost exceeds 2 ms per frame.

5. **Does the kernel process each pixel independently with arithmetic only (add, subtract, multiply, clamp, LUT lookup, channel permute, threshold, luma conversion) AND there is NO single-call cv2 equivalent that does the exact same thing?** → C++. This is the sweet spot for OpenMP + SIMD: no temporary arrays, no Python object churn, GIL can be released. Invert, brightness/contrast, grayscale, channel swap, threshold, posterize, gamma, sepia fit here.

   LUT-cached filters (`vignette`, `chromatic_aberration`, `uv_displacement`) do NOT fit: their heavy path is a `cv2.remap` call (already C++) and the LUT rebuild is rare.

6. **Does the filter need a stateful simulation with `num_elements > 1000` updated every frame (particles, agents, cellular automata) AND the per-element update has conditional logic numpy cannot vectorize cleanly?** → C++ candidate. `boids` and `physarum` are borderline today: both are vectorized in numpy and running under budget. Do not migrate until profiling shows >3 ms.

7. **Does it touch `application/`, `ports/`, `domain/`, `infrastructure/`, or `presentation/`?** → Python. No exceptions. See `ARCHITECTURE.md` §6-7 and `GRAPH_ARCHITECTURE.md`.

### Threshold summary (paste into PR reviews)

| Signal | Threshold | Language |
|---|---|---|
| cv2/numpy call does ≥ 80 % of the work | — | Python |
| Python `for` over pixels with no cv2/numpy fallback | any | C++ |
| Python `for` over small parameter (segments, copies, samples) | `N < 32` | Python |
| Particle count with `cv2.circle` per particle | `N > 500` | vectorize first, then C++ |
| Measured per-frame cost | `> 3 ms` AND fits criterion 3 or 5 | C++ |
| Measured per-frame cost | `< 1 ms` | Python, do not touch |
| Kernel fits `py::gil_scoped_release` cleanly | — | C++ bonus |

---

## 2. Language policy by component type

| Component | Directory | Language | Why |
|---|---|---|---|
| Domain types, events, config dataclasses | `domain/` | Python | Declarative, validation via runtime introspection. |
| Ports (protocols, interfaces) | `ports/` | Python | Type signatures only. C++ can't express `Protocol`. |
| Application layer (engine, graph, scheduler, temporal, filter context) | `application/` | Python | Control flow, threading, lifecycle. GIL-bound by design. |
| Infrastructure (event bus, profiler, plugin manager) | `infrastructure/` | Python | Observable, introspectable, test-mockable. |
| Adapter factories / node adapters | `adapters/**`, `application/graph/adapter_nodes/` | Python | Thin glue. Must be readable and hot-editable. |
| Source adapters (camera, file, network) | `adapters/sources/` | Python | I/O bound, delegates to OpenCV / ffmpeg. |
| Output sinks (preview, NDI, RTSP, recorder) | `adapters/outputs/` | Python | I/O bound. Any threading is the adapter's problem. |
| Renderer adapters | `adapters/renderers/` | Python (delegate to C++ only when criterion 3 or 5 fires) | Typically `cv2.resize` + PIL + overlay. |
| Analyzer wrapping mediapipe | `adapters/perception/` | Python wrapping mediapipe | Mediapipe is already native. |
| Analyzer running ONNX inference | `cpp/src/perception/` + Python wrapper | **C++ kernel** + Python wrapper | We own preprocessing + the ORT session. GIL MUST be released. |
| Filter: per-pixel arithmetic kernel | `cpp/src/filters/` + `adapters/processors/filters/cpp_*.py` | **C++ kernel** + Python wrapper | Canonical pattern. See `cpp_invert.py`. |
| Filter: cv2/numpy declarative composition | `adapters/processors/filters/` | Python | cv2 is already C++. |
| Filter: LUT-cached remap | `adapters/processors/filters/` | Python | Heavy path is `cv2.remap`. |
| Filter: temporal buffer | `adapters/processors/filters/` | Python (unless hot) | Dominated by frame copies + `cv2.warpAffine`. |
| Filter: stateful simulation | Python today; C++ on demand | | Migrate only with measured evidence. |
| Filter: overlay rasterization (ASCII, stippling, typography) | `adapters/processors/filters/` | Python | PIL + cv2 glyph blit. |
| Tests | `python/ascii_stream_engine/tests/` | Python | pytest owns the harness. |
| Notebooks, dashboards, run_*.py | repo root, `presentation/` | Python | User-facing glue. |

### Forbidden C++ surfaces

These MUST stay Python, no matter how tempting:

- Everything under `application/graph/**` — scheduler, builder, graph, nodes, ports. Pure control flow; moving to C++ destroys test velocity.
- `domain/config.py` — dataclasses with validation. C++ can't express this cleanly.
- Adapter registration, factory code, `__init__.py`, any import glue.
- `FilterContext` (temporal lazy access).

---

## 3. Classification of existing filters

Three buckets:

- **C++** — a C++ kernel exists or should exist.
- **Python (keep)** — stays in Python forever; cv2/numpy composition or orchestration.
- **Profile first** — re-evaluate after measurement before deciding.

### 3.1 Already in C++ (reference pattern)

Located at `cpp/src/filters/*.cpp` with pybind11 entries in `pybind_filters.cpp` and Python wrappers at `adapters/processors/filters/cpp_<name>.py`.

| Filter | Status | Notes |
|---|---|---|
| `cpp_invert` | Implemented | Reference for new wrappers. |
| `cpp_brightness_contrast` | Implemented | |
| `cpp_grayscale` | Implemented | |
| `cpp_channel_swap` | Implemented | |
| `cpp_physarum` | Implemented (simulation) | |

### 3.2 C++ stubs — policy

All currently no-op. Each has a pybind entrypoint. Policy differs per stub:

| Stub | Finish? | Rationale |
|---|---|---|
| `threshold` | **Yes**, P0 | Useful primitive, trivial to implement. |
| `posterize` | **Yes**, P0 | Building block for `toon_shading` quantization. |
| `blur` | **No** | `cv2.GaussianBlur` already SIMD-optimized; we cannot beat it. |
| `sharpen` | **No** | Express as `cv2.GaussianBlur + addWeighted`. |
| `edge` | **No** | `cv2.Canny` is already C++. Keep `edges.py`. |

The "do not finish" stubs stay as pybind entries so the module keeps compiling, but the impl functions remain no-op. If they're still untouched in 6 months, delete them outright.

### 3.3 Python (stays in Python forever)

Dominated by cv2/numpy calls. Re-implementing in C++ has negative ROI:

`brightness.py`, `invert.py` (pure-Python twin of `cpp_invert`, fallback), `mosaic.py`, `edges.py`, `edge_smooth.py`, `detail.py`, `infrared.py`, `vignette.py`, `bloom.py`, `bloom_cinematic.py`, `lens_flare.py`, `color_grading.py`, `film_grain.py`, `kuwahara.py`, `toon_shading.py`, `panel_compositor.py`, `kinetic_typography.py`, `geometric_patterns.py`, `ascii.py`, `hand_frame.py`, `chromatic_aberration.py`, `kaleidoscope.py`, `uv_displacement.py`, `radial_collapse.py`, `radial_blur.py`, `motion_blur.py`, `depth_of_field.py`, `double_vision.py`, `glitch_block.py`, `crt_glitch.py`, `hand_spatial_warp.py`, `chromatic_trails.py`, `chrono_scan.py`, `feedback_loop.py`.

### 3.4 Profile first (grey zone)

Migrate only when measurement at 1080p shows Python version exceeds 3 ms per frame AND the rest of the frame budget (`LATENCY_BUDGET.md`) is respected.

| Filter | What to measure | If hot, approach |
|---|---|---|
| `stippling.py` | time per `apply()` at density 0.8, 1080p | batched disk-splat like `optical_flow_particles`, OR C++ scatter-writer |
| `slit_scan.py` | time per `apply()` at 1080p, buffer_size=30 | vectorize with `np.take_along_axis`, or C++ kernel |
| `physarum.py` | time per step at `num_agents=4000`, 1/4 res | C++ with OpenMP on agent update + gaussian diffuse |
| `boids.py` | time at `num_boids ≥ 500` | C++ force computation only if N grows |
| `optical_flow_particles.py` | measured already < 2 ms at 2000 particles ✅ | likely fine |
| `glitch_block.py` | at corruption_rate 0.5 | C++ block scatter |

### 3.5 C++ today by design (new in 2026-04)

| Filter | Rationale |
|---|---|
| `temporal_scan` | Per-pixel angle projection + per-pixel fancy-index from a ring buffer. Exactly criterion 3 + 5. Replaces `slit_scan` + `chrono_scan` with a unified angle-aware version. |

---

## 4. What must stay in Python forever

Hard list. A PR that moves any of these to C++ must be rejected.

1. Everything under `application/` — engine, graph, scheduler, temporal manager, filter context. Control flow, must be editable in seconds. See `GRAPH_ARCHITECTURE.md` §1.
2. Everything under `ports/` — protocol definitions.
3. Everything under `domain/` — dataclasses, enums, config. Validation needs Python runtime introspection.
4. Adapter registries, node factories, `adapter_nodes/**`, `_registry.py`.
5. The `ImportError` fallback in every `cpp_*.py` wrapper — if the C++ module fails to load, the pipeline MUST still run. See `cpp_invert.py` for the canonical shape.
6. Config access, event bus dispatch, plugin manager, metrics aggregation.
7. Notebooks, dashboards, `run_*.py`, tests.
8. Pipeline stage ordering and node types — `PIPELINE_EXTENSION_RULES.md` §6 forbids changes regardless of language.

---

## 5. Migration priority tiers

Ordered by expected FPS payoff vs implementation cost.

### P0 — do soon (high-confidence wins)

1. **`temporal_scan` C++ kernel** — replaces `slit_scan` + `chrono_scan` with a unified angle-aware temporal filter. Unlocks the angle-dial widget and establishes the ring-buffer pattern for future stateful C++ filters.
2. **Finish `threshold` C++ kernel** — trivial `pixel > T ? 255 : 0` with channel broadcast.
3. **Finish `posterize` C++ kernel** — quantize to N levels.
4. **Add `gamma` and `sepia` C++ kernels** — trivial per-pixel. Building blocks for `color_grading`, `film_grain`, `infrared`.
5. **Measure-then-migrate `slit_scan` and `stippling`** — §3.4.

### P1 — later (needs measurement first)

1. `physarum` C++ with OpenMP — unlocks `num_agents > 4000`.
2. `boids` C++ pairwise force — only if N > 500 in use.
3. `optical_flow_particles` C++ splat — only if Python > 2 ms at 2000 particles.

### P2 — maybe never

1. Finishing `blur`, `sharpen`, `edge` stubs. cv2 is already faster. Delete them outright if untouched in 6 months.
2. C++ ports of `invert.py`, `brightness.py`, `mosaic.py` — cv2 handles these at near-C speed.
3. Any filter whose Python version is under 1 ms measured.
4. C++ port of mediapipe Python wrappers. Mediapipe is already native.

---

## 6. Authoring checklist for new code

### 60-second decision for a new filter

1. Kernel is a sequence of cv2/numpy/PIL/ORT calls? → **Python**, write at `adapters/processors/filters/<name>.py`. Follow `PIPELINE_EXTENSION_RULES.md` §1.
2. Has a Python `for` loop over pixels that numpy can't replace? → **C++**. Write at `cpp/src/filters/<name>.cpp`, bind in `pybind_filters.cpp`, wrap at `adapters/processors/filters/cpp_<name>.py` copying `cpp_invert.py` verbatim (for stateless) or `cpp_temporal_scan.py` (for stateful).
3. Lives under `application/`, `ports/`, `domain/`, or `infrastructure/`? → **Python**. Stop.

### C++ filter PR checklist (paste into the PR)

```
[ ] cpp/src/filters/<name>.cpp defines apply_<name>_impl(...) for stateless
    kernels, or a class for stateful ones.
[ ] cpp/src/bridge/pybind_filters.cpp exposes the function / class; the
    wrapper releases the GIL via py::gil_scoped_release for the kernel.
[ ] Python wrapper cpp_<name>.py follows the cpp_invert.py pattern for
    stateless or cpp_temporal_scan.py for stateful:
    try import filters_cpp, _CPP_AVAILABLE flag, fallback path.
[ ] A Python fallback exists (pure-Python twin OR the wrapper falls back
    to a passthrough). The pipeline MUST still run on a machine where
    filters_cpp failed to build.
[ ] Benchmark: ≥ 30 % faster than the Python equivalent at 1080p, or the
    Python equivalent exceeds 3 ms and the C++ one is ≤ 1.5 ms.
[ ] Unit tests verify both the C++ path (bit-for-bit or ±1 uint8 vs the
    Python reference) and the ImportError fallback path.
[ ] No heap allocation per frame inside the kernel (PERFORMANCE_RULES.md §4).
[ ] Registered in adapters/processors/filters/__init__.py and, if used
    as a graph node, a ProcessorNode adapter exists.
[ ] No touch to application/, ports/, domain/, infrastructure/.
```

### Python filter PR checklist

```
[ ] Extends BaseFilter, declares temporal needs as class attributes.
[ ] If kernel uses cv2: verified the cv2 call is the natural choice
    (don't reinvent cv2 primitives in Python loops).
[ ] LUT/mask precomputation is cached with a _params_dirty flag.
[ ] Stateful filters implement reset() and handle resolution change.
[ ] No Python for-loop with frame-size bound unless ≤ max_delay or
    a small constant (mip depth, sample count).
[ ] Under 5 ms measured at 1080p, or documented as "heavy".
[ ] No touch to application/, ports/, domain/.
```

---

## 7. Acceptance bar for a Python → C++ migration

A PR that migrates a filter from Python to C++ MUST show, in the PR description:

1. **Measured Python baseline** at 1080p, 30 FPS loop, with profiler output.
2. **Measured C++ runtime** under the same conditions.
3. **Wall-clock improvement**: at minimum a 2× speedup, OR an absolute saving of 1.5 ms per frame at 1080p. Less than that isn't worth the binary size, build complexity, and bindings overhead.
4. **Parity test**: output matches the Python version within ±1 uint8 per pixel on a reference image set (deterministic filters) or ±3 uint8 (LUT/interpolation filters).
5. **Fallback preserved**: pure-Python version remains available. Either keep both registered (`invert` and `cpp_invert` as siblings), or the `cpp_<name>.py` wrapper falls back to the Python twin on ImportError.
6. **No new runtime dependency** beyond what `filters_cpp` already links. Adding OpenMP or SIMD intrinsics is fine; adding a new external library is not.

If any one of these fails, the PR is Python.

---

## 8. Relation to the other rules

- **`ARCHITECTURE.md`** — what modules exist and where. When in doubt about where a new file goes, read that first.
- **`GRAPH_ARCHITECTURE.md`** — the graph is sole execution path. Every filter, whether Python or C++, ends up as a `ProcessorNode` in the DAG.
- **`PERFORMANCE_RULES.md`** — frame copy budget (§1), buffer reuse (§2), GIL release (§3), no-alloc hot path (§4). Every C++ kernel authored under this rule must obey §3 and §4.
- **`PIPELINE_EXTENSION_RULES.md`** — how to register a new filter.
- **`LATENCY_BUDGET.md`** — the 5 ms combined-filter budget. A Python filter busting the budget is the canonical C++ migration candidate.
- **`AI_AGENT_RULES.md`** §3 — follow existing patterns; copy `cpp_invert.py` verbatim for new stateless wrappers.
- **`docs/performance/FPS_WINS_2026-04-18.md`** — record of what we already squeezed out of Python. Read before migrating: the Python version may already be fast enough.

---

## 9. One-sentence reminders

- "Is cv2 already doing this? Then Python."
- "Am I writing a for loop over pixels? Then C++."
- "Am I touching the graph, scheduler, or domain? Then Python, no discussion."
- "Did I measure? If not, no migration."
- "Does the fallback path still work without the C++ module? If not, the PR is wrong."
