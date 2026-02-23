# AI Model Integration Rules

Rules for adding, loading, and running AI models in the pipeline.

---

## 1. ONNX Format Requirements

All AI models used in the pipeline MUST be in ONNX format. Other formats (TFLite, NCNN, OpenVINO IR) MUST be converted to ONNX before integration.

### Input contract

- Tensor name: `"input"` or auto-detected from model metadata
- Shape: `(1, 3, H, W)` -- batch=1, channels=3, NCHW layout
- Dtype: float32
- Value range: `[0.0, 1.0]` (normalized from uint8 / 255.0)
- Color order: RGB (the C++ runner converts BGR->RGB internally)

### Output contract

- Landmarks: flat float32 array, (x,y) or (x,y,z) interleaved
- Detection boxes: (x_center, y_center, w, h, confidence, ...)
- Coordinate space: MUST be documented in the adapter's docstring as one of:
  - `"normalized"` (0.0-1.0, relative to input image)
  - `"pixel"` (absolute pixel coordinates in model input space)
  - `"pixel_original"` (absolute pixel coordinates in original image space)
- The Python adapter is responsible for converting any coordinate space to **normalized (0.0-1.0)** before returning.

---

## 2. Model Registration

Every model MUST be registered in `rules/MODEL_REGISTRY.md` with:

- Model name and version
- Source URL (must be in `SECURITY_MODEL_DOWNLOAD.md` whitelist)
- SHA256 checksum
- Input shape and dtype
- Output shape and semantics
- Expected latency on CPU (measured, not estimated)
- File size

---

## 3. Model Loading

Rules:

- Models MUST be loaded lazily (on first inference call), not at import time.
- Model loading MUST NOT block the pipeline; if the model is not ready, the analyzer returns `{}`.
- Model path MUST be configurable via environment variable, defaulting to `onnx_models/mediapipe/<model_name>.onnx`.
- If the model file does not exist at runtime, log a WARNING **once** (not per frame) and return empty results.

### C++ pattern

```cpp
bool OnnxRunner::load(const std::string& path);
// Returns false if file not found or load failed.
// Caller MUST check return value.
```

### Python adapter pattern

```python
class MyAnalyzer(BaseAnalyzer):
    _model_loaded = False
    _load_attempted = False

    def _ensure_model(self):
        if self._load_attempted:
            return self._model_loaded
        self._load_attempted = True
        # ... load logic ...
        return self._model_loaded

    def analyze(self, frame, config):
        if not self._ensure_model():
            return {}
        # ... inference ...
```

---

## 4. Fallback Behavior (Mandatory)

### C++ module unavailable (ImportError)

- The Python adapter MUST return `{}` (empty dict).
- MUST NOT raise an exception.
- MUST NOT log per-frame warnings (log once at import time).

### ONNX model file missing

- The C++ runner returns empty vector.
- The Python adapter returns `{}`.

### Inference failure (bad input, runtime error)

- Catch the exception inside the adapter.
- Return `{}`.
- Log at DEBUG level (not WARNING) to avoid log spam.

---

## 5. Adding a New AI Model (Checklist)

1. Download model following `SECURITY_MODEL_DOWNLOAD.md`
2. Place in `onnx_models/<provider>/<model_name>.onnx`
3. Register in `rules/MODEL_REGISTRY.md`
4. Create C++ runner in `cpp/src/perception/<name>.cpp`
   - MUST use OnnxRunner (do not create new runtime wrappers)
   - MUST expose `run_<name>(uint8_t*, int, int) -> vector<float>`
5. Add to pybind bridge in `cpp/src/bridge/pybind_perception.cpp`
   - MUST release GIL during inference
   - MUST validate 3D uint8 input
6. Create Python adapter in `adapters/perception/<name>.py`
   - MUST extend BaseAnalyzer
   - MUST follow ImportError fallback pattern
   - MUST normalize output coordinates to 0.0-1.0
7. Add to `domain/frame_analysis.py` if new data structure needed
8. Update `__init__.py` exports if public
9. Update `rules/ARCHITECTURE.md` module list
10. Write at least one test (stub mode + real mode if model present)
