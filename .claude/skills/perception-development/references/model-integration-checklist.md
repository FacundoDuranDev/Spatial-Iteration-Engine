# AI Model Integration Checklist

Complete reference for adding new ONNX models to the perception pipeline.

## Pre-Integration Verification

Before starting:
- [ ] Model is ONNX format (convert TFLite/PyTorch if needed)
- [ ] Input is `(1, 3, H, W)` NCHW float32 normalized 0-1 RGB
- [ ] File size < 50MB preferred (< 200MB max)
- [ ] CPU inference < 20ms at target resolution
- [ ] Source is whitelisted (HuggingFace, ONNX Zoo, Google, Microsoft, Meta, TF Hub, PyTorch Hub, .edu)

## Download Security (from SECURITY_MODEL_DOWNLOAD.md)

**Mandatory verifications:**
1. SHA256 checksum verification
2. ONNX format validation (magic bytes)
3. Non-executable permissions (644)
4. Size check (1KB - 500MB)
5. Suspicious string scan (no embedded scripts)

**Flow:** Download to temp -> verify all checks -> move to `onnx_models/` -> record in audit log

**Prohibited sources:** URL shorteners, generic file hosts (Dropbox, Google Drive), unmaintained repos, undocumented origins.

## 10-Step Integration

### Step 1: Download
```bash
# Example from HuggingFace
curl -L "https://huggingface.co/<org>/<model>/resolve/main/model.onnx" -o /tmp/model.onnx
sha256sum /tmp/model.onnx  # Record this
```

### Step 2: Place model
```bash
cp /tmp/model.onnx onnx_models/mediapipe/<model_name>.onnx
```

### Step 3: Register in MODEL_REGISTRY.md
Add entry with: name, file path, source URL, SHA256, input/output shapes, measured CPU latency, file size, status.

### Step 4: C++ runner
Create `cpp/src/perception/<name>.cpp` using the static OnnxRunner pattern.
See `face_landmarks.cpp` as reference.

### Step 5: Pybind bridge
Add `detect_<name>()` to `cpp/src/bridge/pybind_perception.cpp`.
MUST include `py::gil_scoped_release` and `require_3d_uint8()`.

### Step 6: Python adapter
Create `adapters/perception/<name>.py` extending BaseAnalyzer.
MUST include ImportError fallback and coord normalization to 0-1.

### Step 7: Domain types (if needed)
Add new dataclass to `domain/frame_analysis.py` only if existing types don't fit.

### Step 8: Public API
Add to `__init__.py` exports with conditional import flag.

### Step 9: Architecture docs
Update `rules/ARCHITECTURE.md` module list.

### Step 10: Tests
- Stub mode test (no C++ module)
- Synthetic frame test (if model available)
- Output shape and normalization validation

## Model Requirements Summary

| Requirement | Value |
|---|---|
| Format | ONNX only |
| Input layout | NCHW float32 |
| Input range | [0.0, 1.0] |
| Input color | RGB (C++ converts BGR->RGB) |
| Max file size | 200MB |
| Max CPU latency | 20ms |
| Target CPU latency | <5ms |
| Output coords | Adapter normalizes to 0-1 |
