---
name: output-development
description: Use when adding, modifying, or debugging output sinks (UDP, RTSP, WebRTC, NDI, preview, notebook, recorder, composite) in adapters/outputs/
---

# Output Development

> **FIRST:** Read `.claude/skills/shared/AGENT_RULES.md` for build environment, anti-blocking protocol, and communication rules.

## Existing Components (DO NOT recreate)

| File | Purpose |
|------|---------|
| `adapters/outputs/__init__.py` | Output registry — add new sinks here |
| `adapters/outputs/udp.py` | FfmpegUdpOutput (COPY subprocess pattern from this) |
| `adapters/outputs/preview_sink.py` | PreviewSink (cv2.imshow, reference for simple sinks) |
| `adapters/outputs/notebook_preview_sink.py` | NotebookPreviewSink (JPEG encoding pattern) |
| `adapters/outputs/ascii_recorder.py` | AsciiFrameRecorder (file-based text sink) |
| `adapters/outputs/composite.py` | CompositeOutputSink (fan-out pattern) |
| `ports/outputs.py` | OutputSink protocol (READ-ONLY) |
| `ports/output_capabilities.py` | OutputCapabilities, flags (READ-ONLY) |

**Pattern:** Copy `udp.py` for subprocess/streaming sinks, `preview_sink.py` for simple sinks.

## Overview

Develop output sinks that consume `RenderFrame` objects and deliver them to destinations (network streams, display windows, files, notebooks). Sinks are the final pipeline stage: they receive the rendered frame and write it out.

**Core principle:** A sink's job is `RenderFrame -> destination`. It opens a connection/resource, writes frames, and closes cleanly. It never modifies the pipeline frame. It never touches application or pipeline code.

## Scope

**Your files:**
- `python/ascii_stream_engine/adapters/outputs/udp.py`
- `python/ascii_stream_engine/adapters/outputs/preview_sink.py`
- `python/ascii_stream_engine/adapters/outputs/notebook_preview_sink.py`
- `python/ascii_stream_engine/adapters/outputs/ascii_recorder.py`
- `python/ascii_stream_engine/adapters/outputs/composite.py`
- `python/ascii_stream_engine/adapters/outputs/rtsp.py` (planned, not yet created)
- `python/ascii_stream_engine/adapters/outputs/webrtc.py` (planned, not yet created)

**Read-only (never modify):**
- `ports/outputs.py` — `OutputSink` protocol
- `ports/output_capabilities.py` — `OutputCapabilities`, `OutputCapability`, `OutputQuality`
- `domain/types.py` — `RenderFrame` dataclass
- `domain/config.py` — `EngineConfig`

**Never touch:**
- `application/engine.py`, `application/pipeline/`, `ports/`, `domain/`

## The OutputSink Protocol

```python
class OutputSink(Protocol):
    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None: ...
    def write(self, frame: RenderFrame) -> None: ...
    def close(self) -> None: ...
    def get_capabilities(self) -> OutputCapabilities: ...
    def is_open(self) -> bool: ...
    def get_estimated_latency_ms(self) -> Optional[float]: ...
    def supports_multiple_clients(self) -> bool: ...
```

## The RenderFrame Input

```python
@dataclass
class RenderFrame:
    image: Image.Image              # PIL RGB Image (ALWAYS present)
    text: Optional[str] = None      # Full text (ASCII mode)
    lines: Optional[List[str]] = None  # Line-by-line (ASCII mode)
    metadata: Optional[Dict] = None # Arbitrary metadata
```

Sinks receive `RenderFrame`. The `.image` field is always a valid `PIL.Image.Image` in **RGB** mode. Text-based sinks (like `AsciiFrameRecorder`) may use `.text` instead.

## OutputCapabilities System

Every sink MUST implement `get_capabilities()` returning `OutputCapabilities`:

```python
from ...ports.output_capabilities import (
    OutputCapabilities,
    OutputCapability,
    OutputQuality,
)

def get_capabilities(self) -> OutputCapabilities:
    return OutputCapabilities(
        capabilities=OutputCapability.STREAMING | OutputCapability.LOW_LATENCY,
        estimated_latency_ms=50.0,
        supported_qualities=[OutputQuality.LOW, OutputQuality.MEDIUM, OutputQuality.HIGH],
        max_clients=1,
        protocol_name="My Protocol",
        metadata={"key": "value"},
    )
```

**Available capability flags:**
- `STREAMING`, `RECORDING`, `MULTI_CLIENT`, `BROADCAST`
- `HIGH_QUALITY`, `ADAPTIVE_QUALITY`, `CUSTOM_BITRATE`
- `LOW_LATENCY`, `ULTRA_LOW_LATENCY`
- `UDP`, `TCP`, `HTTP`, `RTSP`, `NDI`, `WEBRTC`

## Existing Sinks

| Sink | Purpose | Input used | Latency | Multi-client |
|---|---|---|---|---|
| `FfmpegUdpOutput` | UDP streaming via ffmpeg subprocess | `.image` (RGB PIL) | ~80ms | Yes (broadcast) |
| `PreviewSink` | Local OpenCV window (`cv2.imshow`) | `.image` -> BGR numpy | ~16ms | No |
| `NotebookPreviewSink` | Jupyter widget (`ipywidgets.Image`) | `.image` -> JPEG/PNG bytes | ~50ms | No |
| `AsciiFrameRecorder` | Text file recording | `.text` only | N/A | No |
| `CompositeOutputSink` | Fan-out to multiple sinks | Delegates to children | Max of children | If any child does |
| `FfmpegRtspSink` | RTSP streaming (planned) | — | — | — |
| `WebRTCOutput` | WebRTC peer (planned) | — | — | — |

## Adding a New Sink

```python
"""My output sink description."""
from typing import Optional, Tuple
from PIL import Image
from ...domain.config import EngineConfig
from ...domain.types import RenderFrame
from ...ports.output_capabilities import (
    OutputCapabilities,
    OutputCapability,
    OutputQuality,
)


class MySink:
    """Description of what this sink does."""

    def __init__(self, param: str = "default") -> None:
        self._param = param
        self._is_open = False
        self._output_size: Optional[Tuple[int, int]] = None

    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        self.close()  # idempotent: close previous if any
        self._output_size = output_size
        # ... open connection/file/resource ...
        self._is_open = True

    def write(self, frame: RenderFrame) -> None:
        if not self._is_open:
            return
        image = frame.image
        if isinstance(image, Image.Image):
            if image.mode != "RGB":
                image = image.convert("RGB")
        # ... send/write image bytes ...

    def close(self) -> None:
        # MUST be idempotent (safe to call twice)
        # ... close connection/file/resource ...
        self._is_open = False
        self._output_size = None

    def get_capabilities(self) -> OutputCapabilities:
        return OutputCapabilities(
            capabilities=OutputCapability.STREAMING | OutputCapability.LOW_LATENCY,
            estimated_latency_ms=50.0,
            supported_qualities=[OutputQuality.LOW, OutputQuality.MEDIUM, OutputQuality.HIGH],
            max_clients=1,
            protocol_name="My Protocol",
            metadata={},
        )

    def is_open(self) -> bool:
        return self._is_open

    def get_estimated_latency_ms(self) -> Optional[float]:
        return 50.0

    def supports_multiple_clients(self) -> bool:
        return False
```

## Registration

1. Add import to `adapters/outputs/__init__.py`
2. Add to `__all__` list
3. If optional dependency, use try/except pattern:

```python
# In __init__.py
try:
    from .mysink import MySink
except ImportError:
    MySink = None  # type: ignore

__all__ = [...]
if MySink is not None:
    __all__.append("MySink")
```

**NEVER modify the engine or pipeline to register a new sink.**

## Image Extraction Patterns

Sinks receive `RenderFrame`, not raw images. Extract the image correctly:

**For image-based sinks (most cases):**
```python
image = frame.image  # PIL RGB Image
if image.mode != "RGB":
    image = image.convert("RGB")
```

**For sinks that need raw bytes (network streaming):**
```python
# RGB bytes for ffmpeg rawvideo
image.tobytes()

# JPEG compressed for web/notebook
import io
buf = io.BytesIO()
image.save(buf, format="JPEG", quality=85)
jpeg_bytes = buf.getvalue()
```

**For sinks that need numpy BGR (OpenCV display):**
```python
import numpy as np
import cv2
arr = np.asarray(image, dtype=np.uint8)
bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
cv2.imshow("window", bgr)
```

**For text-based sinks (ASCII recorder):**
```python
text = frame.text  # May be None
if not text:
    return  # Skip frames without text
```

## Subprocess Sinks (ffmpeg pattern)

For sinks that pipe to external processes (UDP, RTSP):

```python
import subprocess

def open(self, config, output_size):
    self.close()
    cmd = ["ffmpeg", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{output_size[0]}x{output_size[1]}",
           "-framerate", str(config.fps),
           "-i", "-",
           # ... output codec/format/url ...
           ]
    self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    self._is_open = True

def write(self, frame):
    if not self._proc or not self._proc.stdin:
        return
    image = frame.image
    if isinstance(image, Image.Image):
        if image.mode != "RGB":
            image = image.convert("RGB")
        self._proc.stdin.write(image.tobytes())

def close(self):
    if self._proc and self._proc.stdin:
        try:
            self._proc.stdin.close()
        except Exception:
            pass
    if self._proc:
        try:
            self._proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()
        self._proc = None
    self._is_open = False
```

**Key:** Always close stdin first, then wait, then terminate, then kill. Never leave zombie processes.

## CompositeOutputSink Pattern

The composite sink fans out to multiple sinks. Key behaviors:
- `open()`: Opens all children; logs errors but continues if some fail
- `write()`: Writes to all open children; logs errors but continues
- `close()`: Closes all children; always idempotent
- Capabilities: OR-combined from children, latency = max of children
- `add_sink()`/`remove_sink()`: Only when closed

```python
composite = CompositeOutputSink([
    FfmpegUdpOutput(host="127.0.0.1", port=1234),
    PreviewSink(),
    AsciiFrameRecorder("output.txt"),
])
```

## Contracts

| Contract | Rule |
|---|---|
| Input | `RenderFrame` with `.image` as PIL RGB Image |
| `open()` | Receives `EngineConfig` + `(width, height)` tuple |
| `close()` | **Idempotent**. Safe to call multiple times. |
| `write()` | Silent return if not open. Never raise on write failure for streaming sinks. |
| Latency budget | **3ms** for output stage |
| Threading | Sink handles its own threading if needed |
| Resource cleanup | MUST release all resources in `close()` (sockets, files, processes) |
| Capabilities | MUST implement `get_capabilities()` with accurate flags |
| Frame modification | **NEVER** modify the RenderFrame or its image |

## Testing

```python
def test_mysink_lifecycle():
    """Open, write, close lifecycle works."""
    sink = MySink()
    assert not sink.is_open()
    sink.open(config, (640, 480))
    assert sink.is_open()
    frame = RenderFrame(image=Image.new("RGB", (640, 480)))
    sink.write(frame)
    sink.close()
    assert not sink.is_open()

def test_mysink_close_idempotent():
    """close() can be called multiple times safely."""
    sink = MySink()
    sink.open(config, (640, 480))
    sink.close()
    sink.close()  # Must not raise

def test_mysink_write_when_closed():
    """write() on closed sink is a no-op, not an error."""
    sink = MySink()
    frame = RenderFrame(image=Image.new("RGB", (640, 480)))
    sink.write(frame)  # Must not raise

def test_mysink_capabilities():
    """Capabilities are correctly reported."""
    sink = MySink()
    caps = sink.get_capabilities()
    assert isinstance(caps, OutputCapabilities)
    assert caps.protocol_name is not None

def test_mysink_open_closes_previous():
    """Opening again closes previous connection first."""
    sink = MySink()
    sink.open(config, (640, 480))
    sink.open(config, (320, 240))  # Must not leak resources
    sink.close()
```

## Planned Sinks (MVP_04)

| Sink | Protocol | Status | Key dependency |
|---|---|---|---|
| `FfmpegRtspSink` | RTSP via ffmpeg | Planned | ffmpeg with RTSP support |
| `WebRTCOutput` | WebRTC via aiortc | Planned | `aiortc` package |
| NDI Output | NDI via ndi-python | Future | `ndi-python` package |

All planned sinks MUST follow the try/except import pattern in `__init__.py`.

## Red Flags

**Stop immediately if you catch yourself:**
- Modifying `engine.py` or any file in `application/`
- Modifying `ports/outputs.py` or `ports/output_capabilities.py`
- Making `close()` non-idempotent (must survive double-close)
- Raising exceptions in `write()` for transient failures (log and continue)
- Leaving subprocesses without proper cleanup (stdin close -> wait -> terminate -> kill)
- Modifying the `RenderFrame` or its `.image` in `write()`
- Forgetting `self.close()` at the start of `open()` (resource leak)
- Importing from `application/` or `pipeline/`
- Hardcoding network addresses instead of reading from `EngineConfig`

## Common Mistakes

| Mistake | Fix |
|---|---|
| Zombie ffmpeg process | Close stdin, wait with timeout, terminate, kill |
| write() crashes pipeline | Wrap in try/except, log error, return silently |
| close() called twice raises | Add `if self._is_open:` guard or make operations idempotent |
| Image mode not RGB | Always `image.convert("RGB")` before `.tobytes()` |
| Missing capabilities | Copy from existing sink, adjust flags and latency |
| Leaked file handle | Use try/finally or ensure `close()` covers all paths |
| Network sink blocks pipeline | Consider threading or async for high-latency destinations |
| Forgot __init__.py registration | Add import + `__all__` entry, use try/except for optional deps |
