# C++ Filter Development Guide

## Architecture

```
cpp/
├── include/filters/filter.hpp         # Virtual interface: Filter::apply()
├── src/filters/
│   ├── brightness_contrast.cpp        # Working
│   ├── invert.cpp                     # Working
│   ├── grayscale.cpp                  # Working
│   ├── channel_swap.cpp               # Working
│   ├── threshold.cpp                  # Phase 2
│   ├── edge.cpp                       # Phase 2
│   ├── blur.cpp                       # Phase 2
│   ├── posterize.cpp                  # Phase 2
│   └── sharpen.cpp                    # Phase 2
└── src/bridge/pybind_filters.cpp      # Python bindings
```

## Interface

```cpp
// filters/filter.hpp
namespace filters {
class Filter {
 public:
  virtual ~Filter() = default;
  virtual void apply(std::uint8_t* frame, int width, int height, int channels) = 0;
};
}
```

All filters operate in-place on the raw buffer. Python side provides a writable copy.

## Pybind Helper

The bridge uses `apply_in_place()` which:
1. Validates 3D uint8 (`require_3d_uint8`)
2. Requests writable buffer (`frame.request(true)`)
3. Extracts (h, w, c) dimensions
4. Calls the implementation function

```cpp
static void apply_in_place(py::array_t<std::uint8_t> frame,
                           std::function<void(std::uint8_t*, int, int, int)> f) {
  require_3d_uint8(frame);
  py::buffer_info buf = frame.request(true);
  int h = static_cast<int>(buf.shape[0]);
  int w = static_cast<int>(buf.shape[1]);
  int c = static_cast<int>(buf.shape[2]);
  f(static_cast<std::uint8_t*>(buf.ptr), w, h, c);
}
```

Note: dimensions are passed as `(width, height, channels)` to the impl function, matching the Filter interface.

## Adding a New C++ Filter (Step by Step)

### 1. Create implementation

`cpp/src/filters/myfilter.cpp`:

```cpp
#include "filters/filter.hpp"
#include <cstdint>

namespace filters {

class MyFilter : public Filter {
 public:
  void apply(std::uint8_t* frame, int width, int height, int channels) override {
    const int n = width * height * channels;
    for (int i = 0; i < n; ++i) {
      // operate on frame[i]
    }
  }
};

void apply_myfilter_impl(std::uint8_t* data, int w, int h, int c, float param) {
  // Use param to configure, then apply
  MyFilter f;
  f.apply(data, w, h, c);
}

}  // namespace filters
```

### 2. Declare in header

Add to `cpp/include/filters/filters_api.hpp`:

```cpp
void apply_myfilter_impl(std::uint8_t* data, int w, int h, int c, float param);
```

### 3. Add to CMakeLists.txt

Add source file to the `filters_cpp` target source list.

### 4. Add pybind binding

In `pybind_filters.cpp`:

```cpp
m.def("apply_myfilter",
    [](py::array_t<std::uint8_t> frame, float param) {
      apply_in_place(frame, [&](std::uint8_t* p, int w, int h, int c) {
        filters::apply_myfilter_impl(p, w, h, c, param);
      });
    },
    py::arg("frame"), py::arg("param") = 1.0,
    "In-place: description.");
```

### 5. Build and test

```bash
cd cpp && ./build.sh
PYTHONPATH=python:cpp/build python -c "import filters_cpp; print(dir(filters_cpp))"
```

## Performance Rules

- **No heap allocation in `apply()`**. Pre-allocate if needed.
- **No `std::string` in hot path.**
- Pixel loops: iterate linearly `[0, w*h*c)` for cache friendliness.
- For SIMD potential: process 4/8/16 pixels at a time, keep data aligned.
- Total filter budget: 5ms combined for ALL filters.

## Existing Implementations Reference

| Filter | File | Parameters |
|---|---|---|
| brightness_contrast | `brightness_contrast.cpp` | `brightness_delta: int`, `contrast_factor: double` |
| invert | `invert.cpp` | none |
| grayscale | `grayscale.cpp` | none (outputs 3-channel gray) |
| channel_swap | `channel_swap.cpp` | `dst_for_b, dst_for_g, dst_for_r: int` |
| threshold | `threshold.cpp` | `threshold: uint8` |
| edge | `edge.cpp` | none |
| blur | `blur.cpp` | `kernel_size: int` |
| posterize | `posterize.cpp` | `levels: int` |
| sharpen | `sharpen.cpp` | `strength: double` |
