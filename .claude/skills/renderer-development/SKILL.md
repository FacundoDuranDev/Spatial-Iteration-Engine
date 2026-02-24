---
name: renderer-development
description: Use when adding, modifying, or debugging renderers (ASCII, passthrough, landmark overlay, C++ deformed) or the RenderFrame output in adapters/renderers/
---

# Renderer Development

> **FIRST:** Read `.claude/skills/shared/AGENT_RULES.md` for build environment, anti-blocking protocol, and communication rules.
> **MANDATORY:** `conda activate spatial-iteration-engine` before ANY C++ build or test.

## Existing Components (DO NOT recreate)

| File | Purpose |
|------|---------|
| `adapters/renderers/__init__.py` | Renderer registry — add new renderers here |
| `adapters/renderers/passthrough_renderer.py` | Simplest renderer (COPY THIS for new renderers) |
| `adapters/renderers/ascii.py` | ASCII art renderer (complex, reference for caching patterns) |
| `adapters/renderers/landmarks_overlay_renderer.py` | Overlay decorator (COPY THIS for overlay renderers) |
| `adapters/renderers/cpp_renderer.py` | C++ render_bridge wrapper |
| `ports/renderers.py` | FrameRenderer protocol (READ-ONLY) |
| `domain/types.py` | RenderFrame dataclass (READ-ONLY) |

**Pattern:** Copy `passthrough_renderer.py` for basic renderers, `landmarks_overlay_renderer.py` for overlays.

## Overview

Develop renderers that convert a processed frame into a `RenderFrame` (PIL Image + optional text/lines). Renderers are the second-to-last pipeline stage: they receive filtered frames + analysis dict and produce the visual output that sinks consume.

**Core principle:** A renderer's job is `frame (numpy BGR) -> RenderFrame (PIL RGB Image)`. It produces exactly 1 frame copy. It never modifies the pipeline source frame.

## Scope

**Your files:**
- `python/ascii_stream_engine/adapters/renderers/ascii.py`
- `python/ascii_stream_engine/adapters/renderers/passthrough_renderer.py`
- `python/ascii_stream_engine/adapters/renderers/landmarks_overlay_renderer.py`
- `python/ascii_stream_engine/adapters/renderers/cpp_renderer.py`
- `cpp/src/bridge/deformed_render.cpp` (stub, future)
- `cpp/src/bridge/pybind_bridge.cpp`

**Read-only (never modify):**
- `ports/renderers.py` — `FrameRenderer` protocol
- `domain/types.py` — `RenderFrame` dataclass
- `domain/config.py` — `EngineConfig`

**Never touch:**
- `application/engine.py`, `application/pipeline/`, `ports/`, `domain/`

## The FrameRenderer Protocol

```python
class FrameRenderer(Protocol):
    def output_size(self, config: EngineConfig) -> Tuple[int, int]:
        ...

    def render(self, frame: np.ndarray, config: EngineConfig,
               analysis: Optional[dict] = None) -> RenderFrame:
        ...
```

## The RenderFrame Dataclass

```python
@dataclass
class RenderFrame:
    image: Image.Image              # PIL RGB Image (REQUIRED)
    text: Optional[str] = None      # Full text (ASCII mode)
    lines: Optional[List[str]] = None  # Line-by-line (ASCII mode)
    metadata: Optional[Dict] = None # Arbitrary metadata
```

Every renderer MUST produce a `RenderFrame` with at least `image` set. Sinks depend on `image` being a valid `PIL.Image.Image` in RGB mode.

## Existing Renderers

| Renderer | Purpose | Image | Text/Lines |
|---|---|---|---|
| `PassthroughRenderer` | Raw video, no transformation | BGR→RGB→PIL | None |
| `AsciiRenderer` | ASCII art rendering | PIL with drawn text | Yes |
| `LandmarksOverlayRenderer` | Draws perception points on frame | BGR→draw→RGB→PIL | None |
| `CppDeformedRenderer` | C++ render_bridge (stub) | C++ output→PIL | None |

## Adding a New Renderer

```python
"""My renderer description."""
from typing import Optional, Tuple
import cv2
import numpy as np
from PIL import Image
from ...domain.config import EngineConfig
from ...domain.types import RenderFrame

class MyRenderer:
    """Description of what this renderer produces."""

    def output_size(self, config: EngineConfig) -> Tuple[int, int]:
        # Return (width, height) of the output image
        w = getattr(config, "raw_width", None) or 640
        h = getattr(config, "raw_height", None) or 480
        return int(w), int(h)

    def render(self, frame: np.ndarray, config: EngineConfig,
               analysis: Optional[dict] = None) -> RenderFrame:
        # 1. Handle grayscale input
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

        # 2. Your rendering logic (operate on a copy if modifying)
        img = frame.copy()
        # ... modify img ...

        # 3. Convert BGR -> RGB -> PIL (mandatory)
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)

        # 4. Return RenderFrame
        return RenderFrame(image=pil_img, metadata={"source": "myrenderer"})
```

## Color Space Rules

This is the most common source of bugs in renderers:

```
Input frame:     BGR uint8 (OpenCV convention)
cv2 drawing:     BGR (circles, text, lines)
PIL Image:       RGB
RenderFrame:     RGB (PIL Image)
```

**Conversion flow:**
```
frame (BGR) → copy → draw with cv2 (BGR) → cvtColor BGR2RGB → Image.fromarray → RenderFrame
```

**Common bug:** Forgetting BGR→RGB conversion produces blue-shifted output.

## Decorator/Wrapper Pattern (LandmarksOverlayRenderer)

The overlay renderer wraps an inner renderer and draws on top:

```python
class OverlayRenderer:
    def __init__(self, inner: Optional[FrameRenderer] = None):
        self._inner = inner

    def render(self, frame, config, analysis=None):
        if self._inner:
            inner_result = self._inner.render(frame, config, analysis)
            # Convert inner PIL (RGB) back to numpy BGR for cv2 drawing
            img = cv2.cvtColor(np.array(inner_result.image), cv2.COLOR_RGB2BGR)
        else:
            img = frame.copy()

        # Draw overlays on img (BGR)...

        # Convert back to RGB PIL
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return RenderFrame(image=Image.fromarray(rgb))
```

**Key:** The inner renderer returns RGB PIL. To draw with cv2, convert back to BGR numpy, draw, then convert to RGB PIL again.

## Reading the Analysis Dict

Renderers can use perception results for visualization:

```python
if analysis:
    # Face: green dots
    face = analysis.get("face", {})
    if face.get("points") is not None:
        _draw_points(img, face["points"], (0, 255, 0))  # BGR green

    # Hands: left=red, right=blue
    hands = analysis.get("hands", {})
    if hands.get("left") is not None:
        _draw_points(img, hands["left"], (0, 0, 255))   # BGR red
    if hands.get("right") is not None:
        _draw_points(img, hands["right"], (255, 0, 0))   # BGR blue

    # Pose: yellow
    pose = analysis.get("pose", {})
    if pose.get("joints") is not None:
        _draw_points(img, pose["joints"], (0, 255, 255)) # BGR yellow
```

All coordinates are normalized 0-1. Scale by `(w, h)` to get pixel positions:

```python
h, w = img.shape[:2]
px = int(point[0] * w)
py = int(point[1] * h)
```

## Performance Patterns

**PIL Image caching** (from AsciiRenderer):
```python
# Reuse PIL image when size unchanged
if self._cached_image is not None and self._cached_size == (out_w, out_h):
    img = self._cached_image
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (out_w, out_h)], fill=(0, 0, 0))
else:
    img = Image.new("RGB", (out_w, out_h), color=(0, 0, 0))
    self._cached_image = img
    self._cached_size = (out_w, out_h)
```

**Skip resize when unnecessary:**
```python
h, w = rgb.shape[:2]
if (w, h) != output_size:
    rgb = cv2.resize(rgb, output_size, interpolation=cv2.INTER_AREA)
```

## Contracts

| Contract | Rule |
|---|---|
| Input frame | `(H, W, 3)` BGR uint8 or `(H, W)` grayscale uint8 |
| Output | `RenderFrame` with `.image` as PIL RGB Image |
| Frame copies | **1** maximum. The conversion to PIL is the copy. |
| Latency budget | **3ms** |
| analysis dict | Read-only. Coords normalized 0-1. |
| Grayscale input | Handle `frame.ndim == 2` gracefully |
| C++ bridge | ImportError fallback to passthrough |

## Testing

```python
def test_myrenderer_produces_renderframe():
    """Output is valid RenderFrame with PIL Image."""
    r = MyRenderer()
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    result = r.render(frame, config)
    assert isinstance(result, RenderFrame)
    assert isinstance(result.image, Image.Image)
    assert result.image.mode == "RGB"

def test_myrenderer_output_size():
    """output_size matches actual render dimensions."""
    r = MyRenderer()
    expected = r.output_size(config)
    result = r.render(frame, config)
    assert result.image.size == expected

def test_myrenderer_grayscale_input():
    """Handles grayscale frames without error."""
    r = MyRenderer()
    gray = np.random.randint(0, 255, (480, 640), dtype=np.uint8)
    result = r.render(gray, config)
    assert isinstance(result.image, Image.Image)

def test_myrenderer_with_analysis():
    """Handles analysis dict without error."""
    r = MyRenderer()
    analysis = {"face": {"points": np.array([[0.5, 0.5]])}}
    result = r.render(frame, config, analysis=analysis)
    assert isinstance(result.image, Image.Image)
```

## Red Flags

**Stop immediately if you catch yourself:**
- Returning a numpy array instead of `RenderFrame`
- Returning a PIL Image in BGR mode (must be RGB)
- Modifying the input frame directly (always copy first)
- Forgetting `cvtColor(BGR2RGB)` before `Image.fromarray()`
- Importing from `application/` or `pipeline/`
- Modifying `ports/renderers.py` or `domain/types.py`
- Creating more than 1 frame copy
- Ignoring grayscale input (`frame.ndim == 2`)
- Hardcoding output size instead of reading from config

## Common Mistakes

| Mistake | Fix |
|---|---|
| Blue-shifted output | Missing `cv2.cvtColor(img, cv2.COLOR_BGR2RGB)` before PIL |
| Crash on grayscale frame | Check `frame.ndim == 2` and convert with `COLOR_GRAY2BGR` |
| PIL Image wrong size | Use `output_size()` consistently, resize if needed |
| Overlay on ASCII text-only result | Fall back to raw frame when `inner_result.image` produces text-only |
| Landmarks scaled wrong | Coords are 0-1, multiply by `(w, h)` for pixel position |
| Memory leak in cached images | Clear/reuse cache, don't accumulate |
| C++ renderer crash | ImportError fallback to passthrough, never crash pipeline |
