# Performance Rules

Rules for maintaining real-time performance in the pipeline.
All agents and developers MUST follow these constraints.

---

## 1. Frame Copy Budget

Maximum allowed copies per frame through the entire pipeline: **3**.

| Stage | Copies Allowed | Rationale |
|---|---|---|
| Source.read() | 0-1 | Camera drivers may copy internally |
| Analyzer | **0** | Read-only; MUST NOT copy the frame |
| Tracking | 0 | Operates on analysis dict, not frame |
| Transform | 0-1 | May produce a new array (warp/resize) |
| Filter | 0-1 | In-place preferred; copy only if needed |
| Renderer | 1 | Produces RenderFrame (new object) |
| Output | 0 | Writes what it receives |

Rules:

- If a filter needs to modify the frame, it MUST call `frame.copy()` exactly once at the start, then operate in-place on the copy. Never copy inside a loop.
- Analyzers MUST NOT call `frame.copy()`. They receive a read-only view. If they need a resized version for inference, they MUST use a preallocated buffer (see Buffer Reuse below).

---

## 2. Buffer Reuse

### C++ side

Perception modules MUST preallocate inference buffers on first call and reuse them across frames.

Pattern:

- Allocate `input_data` vector once in `load()`, sized to `(1 * 3 * input_size * input_size)`.
- Rewrite contents each frame in `run()`, never reallocate.
- Output vector: use `reserve()` on first call; `clear()` + reuse on subsequent calls.

### Python side

- Analyzers that need a resized frame MUST keep a class-level `_resize_buffer: Optional[np.ndarray]` and reuse it with `cv2.resize(..., dst=self._resize_buffer)`.
- Filters with precomputed LUTs (displacement maps, remap tables) MUST cache them and only recompute when parameters change (dirty flag pattern).

---

## 3. GIL Release Patterns for C++ (pybind11)

All C++ pybind11 functions that do computation MUST release the GIL.

**Current problem:** `pybind_perception.cpp` does NOT release the GIL during ONNX inference (10-50ms), blocking the entire Python interpreter.

Correct pattern:

```cpp
m.def("detect_pose", [](py::array_t<uint8_t> frame) {
    require_3d_uint8(frame);
    py::buffer_info buf = frame.request();
    int h = buf.shape[0], w = buf.shape[1];
    uint8_t* ptr = static_cast<uint8_t*>(buf.ptr);
    std::vector<float> data;
    {
        py::gil_scoped_release release;  // <-- REQUIRED
        data = perception::run_pose(ptr, w, h);
    }
    return landmarks_to_numpy(data);
}, py::arg("frame"));
```

Rules:

- `py::gil_scoped_release` MUST wrap any call that takes > 0.1ms.
- NEVER access Python objects (`py::*`, `buf.*`) inside the release block.
- NEVER store pointers to numpy buffer data beyond the GIL release block; the buffer may be garbage collected.

---

## 4. Memory Allocation Per Frame

### C++ hot path

- No heap allocation per frame. `std::vector`: use `reserve()` + `clear()`, not fresh construction.
- `std::string`: avoid in per-frame code.
- `OnnxRunner::run()` currently allocates `input_data` each call. This MUST be moved to a member variable.

### Python hot path

- No Python object creation per frame unless it is the output.
- Do not create intermediate dicts, lists, or dataclasses inside `analyze()` unless they are the return value.
- Use module-level or instance-level preallocated structures.

---

## 5. Numpy Array Contracts

All frame arrays passed between pipeline stages MUST be:

- dtype: `np.uint8`
- shape: `(height, width, 3)` -- 3-channel color
- memory layout: C-contiguous (row-major)
- flags.writeable: `True` (for filters), read-only convention (for analyzers)

---

## 6. Config Access in Hot Path

`get_config()` currently performs a deep copy with full `__post_init__` validation (regex, socket operations) every frame. This MUST be replaced with a dirty-flag mechanism:

- Validate only when config changes (via `update_config()`).
- In the main loop, read `self._config` directly (protected by the existing lock for writes).
- Never run validation logic at 30-60fps.

---

## 7. ONNX Runtime Threading

`SetIntraOpNumThreads(1)` in `onnx_runner.cpp:143` wastes CPU cores. Rules:

- Default to `min(4, hardware_concurrency)` for intra-op threads.
- Make it configurable via environment variable `ONNX_NUM_THREADS`.
- When running multiple analyzers in parallel, reduce per-model threads to avoid oversubscription.

---

## 8. Metrics Integrity

Every value reported as a measurement MUST come from an actual measurement. No hardcoded constants disguised as metrics.

### Rules

- **Return `None`, not a magic number.** If you cannot measure something, the method MUST return `None`. Never `return 80.0` or any hardcoded constant from a method named `get_*`, `measure_*`, or `estimate_*`.
- **One source of truth: `LoopProfiler`.** All per-frame timing goes through `LoopProfiler` in `infrastructure/profiling.py`. It instruments the real pipeline stages (capture, analysis, transformation, filtering, rendering, writing). Do not create parallel timing mechanisms in adapters.
- **No timing in the hot path outside LoopProfiler.** Adapters (filters, outputs, renderers) MUST NOT add `time.perf_counter()` calls in their `write()`, `apply()`, or `render()` methods. The orchestrator already wraps these calls with profiler phases.
- **End-to-end latency is not measurable from one side.** Streaming latency (encoder → network → decoder → display) requires receiver-side measurement. Do not pretend to estimate it from the sender.
- **If a metric field is not measurable, do not add it to the interface.** Prefer no field over an optional field that every implementation sets to `None` or a guess.
