---
name: filter-development
description: Use when adding, modifying, or debugging image filters in Python or C++ within adapters/processors/filters/ or cpp/src/filters/
---

# Filter Development

> **FIRST:** Read `.claude/skills/shared/AGENT_RULES.md` for build environment, anti-blocking protocol, and communication rules.
> **MANDATORY:** `conda activate spatial-iteration-engine` before ANY C++ build or test.

## Existing Components (DO NOT recreate)

| File | Purpose |
|------|---------|
| `adapters/processors/filters/__init__.py` | Filter registry — add new filters here |
| `adapters/processors/filters/base.py` | BaseFilter — extend this |
| `adapters/processors/filters/brightness.py` | Pure Python brightness (reference pattern) |
| `adapters/processors/filters/edges.py` | Pure Python edge detection (reference pattern) |
| `adapters/processors/filters/detail.py` | Pure Python detail enhancement |
| `adapters/processors/filters/invert.py` | Pure Python color inversion |
| `adapters/processors/filters/conversion_cache.py` | Shared color conversion cache |
| `adapters/processors/filters/cpp_invert.py` | C++ wrapper pattern (COPY THIS for new C++ filters) |
| `adapters/processors/filters/cpp_brightness_contrast.py` | C++ brightness/contrast |
| `adapters/processors/filters/cpp_channel_swap.py` | C++ channel swap |
| `adapters/processors/filters/cpp_grayscale.py` | C++ grayscale |
| `cpp/src/filters/` | C++ filter implementations |
| `cpp/src/bridge/pybind_filters.cpp` | pybind11 bridge for filters |

**Pattern:** Copy `edges.py` for Python filters, `cpp_invert.py` for C++ wrappers. Follow the pattern exactly.

## Overview

Develop image filters that modify frames in the pipeline. Filters run AFTER perception and BEFORE rendering. They receive the frame + analysis dict and return a modified frame. Two variants: pure Python (OpenCV) and C++ (pybind11 in-place).

**Core principle:** Filters modify pixels. They copy once if needed, operate in-place on the copy, and return it. They NEVER modify application or pipeline code.

## Scope

**Your files:**
- `python/ascii_stream_engine/adapters/processors/filters/*.py`
- `cpp/src/filters/*.cpp`
- `cpp/include/filters/filter.hpp`
- `cpp/src/bridge/pybind_filters.cpp`

**Read-only (never modify):**
- `ports/processors.py` (Filter protocol)
- `domain/config.py` (EngineConfig)
- `application/pipeline/filter_pipeline.py`

**Never touch:**
- `application/engine.py`
- `application/pipeline/analyzer_pipeline.py`
- Any file in `ports/`, `domain/`, `application/`

## Adding a New Python Filter

Copy from `edges.py` or `brightness.py` and adapt:

```python
import cv2
import numpy as np
from .base import BaseFilter

class MyFilter(BaseFilter):
    name = "myfilter"

    def __init__(self, param: float = 1.0, enabled: bool = True) -> None:
        super().__init__(enabled=enabled)
        self._param = param

    def apply(self, frame, config, analysis=None):
        if self._param == 0:       # no-op: return original, NO copy
            return frame
        out = frame.copy(order="C")  # one copy, then in-place
        # ... modify out ...
        return out
```

**Mandatory:**
- Extend `BaseFilter`
- Set `name` (unique string)
- Signature: `apply(self, frame, config, analysis=None) -> np.ndarray`
- No-op returns `frame` (NOT `frame.copy()`)
- Modification returns `frame.copy(order="C")` then works in-place on copy
- Output: same shape `(H, W, 3)` uint8 BGR as input

## Adding a C++ Filter

### Step 1: C++ implementation

Create `cpp/src/filters/<name>.cpp`:

```cpp
#include "filters/filter.hpp"
#include <cstdint>

namespace filters {

class MyFilter : public Filter {
 public:
  void apply(std::uint8_t* frame, int width, int height, int channels) override {
    const int n = width * height * channels;
    for (int i = 0; i < n; ++i) {
      // modify frame[i] in-place
    }
  }
};

void apply_myfilter_impl(std::uint8_t* data, int w, int h, int c) {
  MyFilter f;
  f.apply(data, w, h, c);
}

}  // namespace filters
```

**C++ interface:** `filters::Filter` with virtual `apply(uint8_t*, w, h, channels)`. Always in-place.

### Step 2: Expose in pybind bridge

Add to `cpp/src/bridge/pybind_filters.cpp`:

```cpp
m.def("apply_myfilter",
    [](py::array_t<std::uint8_t> frame, float param) {
      apply_in_place(frame, [&](std::uint8_t* p, int w, int h, int c) {
        filters::apply_myfilter_impl(p, w, h, c, param);
      });
    },
    py::arg("frame"), py::arg("param") = 1.0,
    "In-place description of what it does.");
```

Uses the existing `apply_in_place()` helper which validates 3D uint8 and requests writable buffer.

### Step 3: Python wrapper

Create `adapters/processors/filters/cpp_<name>.py`:

```python
"""My filter via C++ (filters_cpp)."""
from typing import Optional
import numpy as np
from ....domain.config import EngineConfig
from .base import BaseFilter

try:
    import filters_cpp as _filters_cpp
    _CPP_AVAILABLE = True
except ImportError:
    _filters_cpp = None
    _CPP_AVAILABLE = False

class CppMyFilter(BaseFilter):
    """Description. Delegates to filters_cpp.apply_myfilter."""
    name = "cpp_myfilter"
    enabled = True

    @property
    def cpp_available(self) -> bool:
        return _CPP_AVAILABLE

    def apply(self, frame: np.ndarray, config: EngineConfig,
              analysis: Optional[dict] = None) -> np.ndarray:
        if not _CPP_AVAILABLE:
            return frame.copy()      # fallback: return unmodified copy
        out = np.asarray(frame, dtype=np.uint8).copy(order="C")
        _filters_cpp.apply_myfilter(out)
        return out
```

**Mandatory:** ImportError fallback returns `frame.copy()` (not `frame`).

### Step 4: Register

1. Add import to `adapters/processors/filters/__init__.py`
2. Add to `__all__` list
3. Add to top-level `__init__.py` if public

**NEVER modify `FilterPipeline`** (in `application/pipeline/`).

## Using the Analysis Dict

Filters can read perception results via the `analysis` parameter:

```python
def apply(self, frame, config, analysis=None):
    if analysis and "face" in analysis:
        points = analysis["face"]["points"]  # (N, 2) normalized 0-1
        h, w = frame.shape[:2]
        # Convert to pixel coords for drawing
        px = (points[:, 0] * w).astype(int)
        py = (points[:, 1] * h).astype(int)
    # ...
```

Analysis dict keys: `face.points`, `hands.{left,right}`, `pose.joints`. All coords normalized 0-1.

## Stateful Filters

Filters with internal state (feedback, slit scan, particles):

```python
class StatefulFilter(BaseFilter):
    name = "stateful"

    def __init__(self, enabled=True):
        super().__init__(enabled=enabled)
        self._buffer = None
        self._last_shape = None

    def reset(self):
        """Clear internal state. Called on pipeline reset."""
        self._buffer = None
        self._last_shape = None

    def apply(self, frame, config, analysis=None):
        h, w = frame.shape[:2]
        if (h, w) != self._last_shape:
            self._buffer = np.zeros((h, w, 3), dtype=np.uint8)
            self._last_shape = (h, w)
        # ... use self._buffer ...
```

**Mandatory:** Implement `reset()`. Handle resolution changes by reinitializing buffers.

## LUT-Cached Filters

Filters with precomputed tables (remap, distortion):

```python
class LUTFilter(BaseFilter):
    name = "lut"

    def __init__(self, strength=1.0, enabled=True):
        super().__init__(enabled=enabled)
        self._strength = strength
        self._lut = None
        self._params_dirty = True

    @property
    def strength(self):
        return self._strength

    @strength.setter
    def strength(self, value):
        self._strength = value
        self._params_dirty = True   # recompute on next frame

    def apply(self, frame, config, analysis=None):
        if self._params_dirty:
            self._lut = self._compute_lut()
            self._params_dirty = False
        return cv2.LUT(frame, self._lut)
```

**Mandatory:** Dirty flag pattern. Never recompute LUTs every frame.

## Conversion Cache

Use `get_cached_conversion()` for shared color conversions:

```python
from .conversion_cache import get_cached_conversion

def apply(self, frame, config, analysis=None):
    gray = get_cached_conversion(frame, cv2.COLOR_BGR2GRAY)  # cached per frame
    # ...
```

Multiple filters requesting BGR2GRAY on the same frame only compute it once.

## Contracts

| Contract | Rule |
|---|---|
| Input frame | `(H, W, 3)` BGR uint8 C-contiguous |
| Output frame | Same shape and dtype as input |
| Frame copies | **0-1** per filter. No-op = 0. Modification = 1 copy then in-place. |
| Combined latency | **5ms** for ALL filters combined |
| Pipeline order | Filters run AFTER perception+tracking+transform, BEFORE renderer |
| Analysis dict | Read-only. Coords are 0-1. Keys: face, hands, pose, tracking |
| Registration | `__init__.py` in filters/ only. NEVER modify FilterPipeline. |

## Testing

```python
def test_myfilter_noop():
    """No-op returns same reference (no unnecessary copy)."""
    f = MyFilter(param=0)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    result = f.apply(frame, config)
    assert result is frame  # same object

def test_myfilter_modifies():
    """Filter produces valid output."""
    f = MyFilter(param=1.0)
    frame = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    result = f.apply(frame, config)
    assert result.shape == frame.shape
    assert result.dtype == np.uint8
    assert not np.array_equal(result, frame)

def test_cpp_myfilter_fallback():
    """Graceful fallback when C++ unavailable."""
    f = CppMyFilter()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    result = f.apply(frame, config)
    assert result.shape == frame.shape
```

## Red Flags

**Stop immediately if you catch yourself:**
- Modifying `FilterPipeline` or any file in `application/`
- Modifying `ports/processors.py`
- Copying the frame more than once per filter
- Returning `frame.copy()` in a no-op path (return `frame`)
- Creating heap allocations per frame in C++ (no `new`, no fresh vectors)
- Writing a filter that modifies `analysis` dict (read-only)
- Recomputing LUTs every frame (use dirty flag)
- Forgetting to register in `__init__.py`
- Forgetting `ImportError` fallback in C++ wrapper
- Returning a frame with different shape/dtype than input

## Common Mistakes

| Mistake | Fix |
|---|---|
| No-op path copies frame | Return `frame` directly (same reference) |
| C++ filter not in-place | Use `frame.request(true)` for writable buffer, operate in-place |
| Filter output is grayscale | Convert back to BGR `(H,W,3)` before returning |
| Missing `order="C"` on copy | Always `frame.copy(order="C")` for C-contiguous |
| Filter exceeds 5ms combined budget | Move to C++, use SIMD, or mark as "heavy" filter |
| C++ wrapper missing `_CPP_AVAILABLE` guard | Copy pattern from `cpp_invert.py` exactly |
| Stateful filter breaks on resolution change | Check shape, reinitialize buffers in `apply()` |
