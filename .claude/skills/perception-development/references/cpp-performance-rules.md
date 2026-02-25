# C++ Performance Rules for Perception

Rules specific to perception C++ modules (`perception_cpp`).

## Buffer Reuse

```cpp
class OnnxRunner {
  std::vector<float> input_data_;  // preallocated in load(), reused in run()
  std::mutex run_mutex_;           // thread safety
};
```

- `input_data_` allocated once in `load()`, sized to `1 * 3 * input_size * input_size`
- Rewritten in-place each frame via `letterbox_and_normalize_nchw()`
- Output vector: `reserve()` on first call, `clear()` + reuse on subsequent calls
- NEVER use `new` or fresh `std::vector` construction per frame

## GIL Release (pybind11)

ALL pybind functions that call inference MUST release the GIL:

```cpp
std::vector<float> data;
{
    py::gil_scoped_release release;  // MANDATORY
    data = perception::run_face(ptr, w, h);
}
// Back under GIL: safe to create Python objects
return landmarks_to_numpy(data);
```

**Rules:**
- `py::gil_scoped_release` for ANY call > 0.1ms
- NEVER access `py::*`, `buf.*`, or numpy buffers inside release block
- NEVER store buffer pointers beyond release block (GC may collect)

## Memory Allocation

**Forbidden in hot path:**
- `new` / `delete`
- Fresh `std::vector` construction (use `clear()` + reuse)
- `std::string` creation
- `std::map` / `std::unordered_map` per frame

**Allowed:**
- `reserve()` + `clear()` on preallocated vectors
- Stack-local primitives
- `std::memset` on preallocated buffers

## Thread Safety

- `OnnxRunner::run()` protected by `std::mutex run_mutex_`
- Each model has its own static `OnnxRunner` instance
- When running multiple analyzers in parallel, reduce `ONNX_NUM_THREADS` to avoid oversubscription

## ONNX Threading

- Default: `min(4, std::thread::hardware_concurrency())`
- Override: `ONNX_NUM_THREADS` env var
- With 3 parallel analyzers: set to 1-2 threads each

## Input Validation (pybind)

Always validate before accessing buffer:

```cpp
static void require_3d_uint8(const py::array_t<uint8_t>& frame) {
    if (frame.ndim() != 3)
        throw std::runtime_error("frame must be 3D (height, width, channels)");
    if (frame.shape(2) != 3)
        throw std::runtime_error("frame must have 3 channels");
}
```
