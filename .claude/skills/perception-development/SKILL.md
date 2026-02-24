---
name: perception-development
description: Use when adding, modifying, or debugging AI analyzers, ONNX models, C++ perception runners, or Python perception adapters in adapters/perception/ or cpp/src/perception/
---

# Perception Development

> **FIRST:** Read `.claude/skills/shared/AGENT_RULES.md` for build environment, anti-blocking protocol, and communication rules.
> **MANDATORY:** `conda activate spatial-iteration-engine` before ANY C++ build or test.

## Existing Components (DO NOT recreate)

| File | Purpose |
|------|---------|
| `adapters/perception/__init__.py` | Analyzer registry — add new analyzers here |
| `adapters/perception/face.py` | Face landmarks analyzer (working) |
| `adapters/perception/hands.py` | Hand landmarks analyzer (working) |
| `adapters/perception/pose.py` | Pose detection analyzer (working) |
| `adapters/processors/analyzers/base.py` | BaseAnalyzer — extend this |
| `cpp/src/perception/onnx_runner.cpp` | Shared ONNX inference engine |
| `cpp/src/perception/face_landmarks.cpp` | Face C++ runner |
| `cpp/src/perception/hand_landmarks.cpp` | Hand C++ runner |
| `cpp/src/perception/pose_landmarks.cpp` | Pose C++ runner |
| `cpp/src/bridge/pybind_perception.cpp` | pybind11 bridge |

**Pattern:** Copy `face.py` for Python, `face_landmarks.cpp` for C++. Follow the pattern exactly.

## Overview

Develop AI perception analyzers (face, hands, pose) that run ONNX models in C++ and expose results to Python. Analyzers MUST NOT modify the frame. They return normalized 0-1 coordinates via a dict.

**Core principle:** C++ owns inference (OnnxRunner), Python owns normalization and fallback. The pipeline never breaks if perception fails.

## Scope

**Your files:**
- `python/ascii_stream_engine/adapters/perception/{face,hands,pose}.py`
- `cpp/src/perception/{face_landmarks,hand_landmarks,pose_landmarks,onnx_runner}.cpp`
- `cpp/include/perception/onnx_runner.hpp`
- `cpp/src/bridge/pybind_perception.cpp`
- `onnx_models/` (model files)
- `rules/MODEL_REGISTRY.md` (registration)

**Read-only (never modify):**
- `ports/processors.py` (Analyzer protocol)
- `domain/frame_analysis.py` (data structures)
- `application/pipeline/analyzer_pipeline.py`

**Never touch:**
- `application/engine.py`
- `pipeline/filter_pipeline.py`
- Any file in `ports/`, `domain/`, `application/`

## Adding a New Analyzer (10-Step Checklist)

1. Download model per `rules/SECURITY_MODEL_DOWNLOAD.md` (whitelisted sources only)
2. Place in `onnx_models/<provider>/<model_name>.onnx`
3. Register in `rules/MODEL_REGISTRY.md` with SHA256, input/output shapes, measured latency
4. Create C++ runner: `cpp/src/perception/<name>.cpp` using `OnnxRunner`
5. Add to pybind bridge: `cpp/src/bridge/pybind_perception.cpp` with GIL release
6. Create Python adapter: `adapters/perception/<name>.py` extending `BaseAnalyzer`
7. Add to `domain/frame_analysis.py` if new data structure needed
8. Update `__init__.py` exports
9. Update `rules/ARCHITECTURE.md`
10. Write tests (stub + real mode)

## C++ Runner Pattern

Every runner follows this exact pattern (copy from `face_landmarks.cpp`):

```cpp
#include "perception/perception_common.hpp"
#include "perception/onnx_runner.hpp"

namespace perception {
namespace {
std::string get_model_path() {
  const char* env = std::getenv("ONNX_MODELS_DIR");
  std::string dir = (env && env[0]) ? env : "onnx_models/mediapipe";
  return dir + "/my_model.onnx";
}
}  // namespace

std::vector<float> run_mymodel(std::uint8_t* image, int width, int height) {
#ifdef USE_ONNXRUNTIME
  static OnnxRunner runner;
  if (!runner.is_loaded() && !runner.load(get_model_path()))
    return {};
  return runner.run(image, width, height);
#else
  (void)image; (void)width; (void)height;
  return {};
#endif
}
}  // namespace perception
```

**Rules:**
- `static OnnxRunner` = lazy load on first call, singleton per model
- `#ifdef USE_ONNXRUNTIME` = compiles without ONNX RT as stub
- Return `{}` on any failure, never throw

## Pybind Bridge Pattern

Add to `pybind_perception.cpp` following existing entries:

```cpp
m.def("detect_mymodel",
    [](py::array_t<std::uint8_t> frame) {
      require_3d_uint8(frame);               // validate input
      py::buffer_info buf = frame.request();
      int h = static_cast<int>(buf.shape[0]);
      int w = static_cast<int>(buf.shape[1]);
      std::uint8_t* ptr = static_cast<std::uint8_t*>(buf.ptr);
      std::vector<float> data;
      {
        py::gil_scoped_release release;      // MANDATORY for >0.1ms
        data = perception::run_mymodel(ptr, w, h);
      }
      return landmarks_to_numpy(data);       // -> (N,2) float32
    },
    py::arg("frame"), "Detect mymodel landmarks.");
```

**Mandatory:** `py::gil_scoped_release` wrapping inference. Never access `py::*` inside release block.

## Python Adapter Pattern

Copy from `face.py` and adapt:

```python
"""My analyzer (C++ perception_cpp). MVP_03."""
from typing import Any, Dict
import numpy as np
from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.adapters.processors.analyzers.base import BaseAnalyzer

try:
    import perception_cpp as _perception_cpp
    _CPP_AVAILABLE = True
except ImportError:
    _perception_cpp = None
    _CPP_AVAILABLE = False

class MyAnalyzer(BaseAnalyzer):
    """Description. Delegates to perception_cpp.detect_mymodel."""
    name = "mymodel"   # used as top-level key in analysis dict
    enabled = True

    def analyze(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, Any]:
        if not _CPP_AVAILABLE or frame is None:
            return {}
        try:
            out = _perception_cpp.detect_mymodel(frame)
            if out is None or out.size == 0:
                return {}
            # C++ returns pixel coords; normalize to 0-1
            h, w = frame.shape[:2]
            if h > 0 and w > 0:
                out[:, 0] /= w
                out[:, 1] /= h
                np.clip(out, 0.0, 1.0, out=out)
            return {"points": out}   # dict keys documented in frame_analysis.py
        except Exception:
            return {}
```

**Mandatory elements:**
- `try/except ImportError` at module level
- `_CPP_AVAILABLE` guard
- Normalize pixel coords to 0-1
- `np.clip(out, 0.0, 1.0, out=out)`
- Return `{}` on ANY failure
- `name` attribute matches analysis dict key

## Contracts

| Contract | Rule |
|---|---|
| Input frame | `(H, W, 3)` BGR uint8 C-contiguous. NEVER modify it. |
| Output | `dict` with analyzer `name` as key. Coordinates normalized 0-1. |
| Failure | Return `{}`. No exceptions leak. Log once, not per frame. |
| Frame copies | **0** allowed for analyzers. Use preallocated buffers. |
| C++ color | BGR input. Runner converts BGR->RGB internally. |
| Latency | 5ms per analyzer, 15ms total. See `references/latency-budget.md` |
| Model format | ONNX only. `(1,3,H,W)` NCHW float32 normalized 0-1 RGB. |

## OnnxRunner Internals

The shared C++ inference engine (`onnx_runner.cpp`):

- **Preprocessing:** Letterbox resize (aspect-ratio preserving, black padding) to model input size, then NCHW float32 0-1
- **Post-processing:** YOLOv8 pose (confidence > 0.5, keypoint confidence > 0.3) or standard landmark (x,y,z) triplets
- **Coordinate mapping:** Undoes letterbox padding to return pixel coords in original image space
- **Thread safety:** `std::mutex run_mutex_` protects inference
- **Buffer reuse:** `input_data_` member preallocated, rewritten each frame
- **Threading:** `ONNX_NUM_THREADS` env var, defaults to `min(4, hw_concurrency)`

## Current Model Status

| Model | Status | Issue |
|---|---|---|
| YOLOv8n-pose (pose) | Working | ~15-25ms CPU |
| face_landmark_qualcomm.onnx (face) | Working | Needs accuracy validation |
| hand_landmark_new.onnx (hands) | Working | Needs accuracy validation |
| face_detection_yunet.onnx | Untracked | Needs integration |

See `rules/MODEL_REGISTRY.md` for full details and candidate models.

## Testing

Every new analyzer needs:

```python
# test_analyzers.py or test_perception_<name>.py

def test_myanalyzer_no_cpp():
    """Verify graceful fallback when C++ module unavailable."""
    analyzer = MyAnalyzer()
    # Mock _CPP_AVAILABLE = False
    result = analyzer.analyze(np.zeros((480, 640, 3), dtype=np.uint8), config)
    assert result == {}

def test_myanalyzer_synthetic_frame():
    """Verify output shape and normalization with synthetic input."""
    analyzer = MyAnalyzer()
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    result = analyzer.analyze(frame, config)
    if result:  # only if model available
        points = result["points"]
        assert points.dtype == np.float32
        assert points.shape[1] == 2
        assert points.min() >= 0.0
        assert points.max() <= 1.0
```

## Red Flags

**Stop immediately if you catch yourself:**
- Modifying the input frame inside `analyze()`
- Importing from `application/` or `pipeline/`
- Creating a new OnnxRunner wrapper (use the existing one)
- Allocating buffers per frame in C++
- Forgetting `py::gil_scoped_release` in pybind
- Returning coordinates outside 0-1 range
- Logging warnings per frame (log once at import/load)
- Adding a model without registering in MODEL_REGISTRY.md
- Skipping ImportError fallback pattern

## Common Mistakes

| Mistake | Fix |
|---|---|
| Coords in pixel space returned to pipeline | Divide by (w,h) and clip to 0-1 in Python adapter |
| Model loads at import time, blocking startup | Use lazy load pattern (static OnnxRunner + is_loaded check) |
| GIL held during 20ms inference | Add `py::gil_scoped_release` block in pybind |
| New heap alloc per frame in C++ | Use `reserve()` + `clear()` on vectors, preallocate `input_data_` |
| Bare `Exception` in ports/domain | Only catch in adapter layer, never in ports or domain |
| Model file hardcoded | Use `ONNX_MODELS_DIR` env var with fallback to `onnx_models/mediapipe` |
