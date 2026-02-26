# Outputs Team — Findings

## API Contracts

All sinks implement the `OutputSink` protocol: `open(config, output_size)`, `write(frame)`, `close()`, `is_open()`, `get_capabilities()`, `supports_multiple_clients()`.

### OscOutputSink (`adapters/outputs/osc/osc_sink.py`)

```python
OscOutputSink(
    host="127.0.0.1", port=9000, address_prefix="/spatial",
    send_image_info=True, send_analysis=True, send_metadata=True,
)
```

Sends perception/analysis data as OSC messages over UDP. Does NOT transmit pixel data.

**OSC addresses** (with default prefix `/spatial`):
- `/spatial/frame/size` — `[width, height]`
- `/spatial/frame/index` — `int`
- `/spatial/analysis/face/points` — flat float list
- `/spatial/analysis/hands/left` / `right` — flat float list
- `/spatial/analysis/pose/joints` — flat float list
- `/spatial/metadata/<key>` — scalar values

**Capabilities:** `STREAMING | UDP | LOW_LATENCY | ULTRA_LOW_LATENCY`. Protocol: `"OSC/UDP"`. Multi-client: Yes. Dependency: `python-osc` (hard-fail on import).

### VideoRecorderSink (`adapters/outputs/recorder/video_recorder_sink.py`)

```python
VideoRecorderSink(
    output_path="output.mp4", codec="libx264", bitrate="2000k",
    preset="medium", container_format=None, pixel_format="yuv420p",
)
```

Records to video files via ffmpeg subprocess. Supports `.mp4`, `.avi`, `.mkv`, `.mov`, `.webm`.

**Capabilities:** `RECORDING | HIGH_QUALITY | CUSTOM_BITRATE`. Protocol: `"File (Video)"`. Multi-client: No. Context manager: Yes.

### FfmpegRtspSink (`adapters/outputs/rtsp/rtsp_sink.py`)

```python
FfmpegRtspSink(
    rtsp_url=None, bitrate=None, codec=None, preset=None,
    tune=None, rtsp_transport=None, max_clients=None,
)
```

Streams over RTSP via ffmpeg. Defaults: `libx264`, `ultrafast`, `zerolatency`, `tcp`. Auto-builds URL from config if `rtsp_url=None`.

**Capabilities:** `STREAMING | RTSP | TCP | LOW_LATENCY | CUSTOM_BITRATE | MULTI_CLIENT`. Protocol: `"RTSP/H.264"`. Multi-client: Yes (default 10). Context manager: Yes.

### NdiOutputSink (`adapters/outputs/ndi/ndi_sink.py`)

```python
NdiOutputSink(
    source_name=None, groups=None, clock_video=True, clock_audio=False,
)
```

Streams via NDI for zero-config LAN discovery. Pre-allocates BGRA frame buffer for reuse.

**Capabilities:** `STREAMING | NDI | LOW_LATENCY | MULTI_CLIENT | HIGH_QUALITY | ADAPTIVE_QUALITY`. Protocol: `"NDI"`. Multi-client: Yes (unlimited). Thread-safe: `RLock`. Dependency: `ndi-python` (hard-fail on import). Context manager: Yes.

### Existing Sinks (unchanged)

| Sink | Protocol | Multi-client | Notes |
|------|----------|-------------|-------|
| `FfmpegUdpOutput` | `UDP/MPEG-TS` | Yes (broadcast) | Older pattern, no `cleanup_subprocess`. |
| `PreviewSink` | `OpenCV Preview` | No | `cv2.imshow` + `cv2.waitKey(1)`. |
| `NotebookPreviewSink` | In-process | No | IPython display. |
| `AsciiRecorderSink` | File | No | Text recording. |
| `CompositeOutputSink` | Dynamic | Dynamic | Fan-out to multiple sinks. `add_sink`/`remove_sink` only when closed. |

### Subprocess Utilities (`adapters/outputs/_subprocess_utils.py`)

```python
cleanup_subprocess(proc: Optional[Popen], timeout: int = 1) -> None
```

4-step escalation: close stdin → `wait(timeout)` → `terminate()` + `wait` → `kill()`. Used by `VideoRecorderSink` and `FfmpegRtspSink`.

## Discovered Patterns

1. **Subprocess evolution**: `FfmpegUdpOutput` (older) inlines terminate/kill in `close()`. Newer sinks delegate to `cleanup_subprocess()` for safer teardown.

2. **Context manager support**: `VideoRecorderSink`, `FfmpegRtspSink`, `NdiOutputSink` support `with` syntax. Older sinks do not.

3. **Thread safety**: Only `NdiOutputSink` uses locking (`RLock`). All others are single-threaded.

4. **Optional dependency handling**: `OscOutputSink` and `NdiOutputSink` check dependencies at `__init__` time with `ImportError`. Module-level guards prevent crash on import.

5. **Frame format**: All ffmpeg-based sinks convert `RenderFrame.image` (PIL) to RGB bytes via `tobytes()`. `NdiOutputSink` converts to BGRA (4-channel) via `cv2.cvtColor` or numpy fallback.

6. **Capabilities flags unique per sink**: OSC→`ULTRA_LOW_LATENCY`, Recorder→`RECORDING`, RTSP→`RTSP|TCP`, NDI→`NDI|ADAPTIVE_QUALITY`, UDP→`BROADCAST`.

## Dependencies on Other Teams

- `EngineConfig` from `domain/config.py` — fps, host, port, bitrate, pkt_size
- `RenderFrame` from `domain/types.py` — `.image` (PIL Image), `.text`, `.metadata`
- `OutputCapabilities` / `OutputCapability` from `domain/types.py` — capability flags
- External binaries: `ffmpeg` (UDP, RTSP, Recorder), NDI SDK, `python-osc` lib

## Provided to Other Teams

- 4 new output sinks: `OscOutputSink`, `VideoRecorderSink`, `FfmpegRtspSink`, `NdiOutputSink`
- `cleanup_subprocess` utility for safe ffmpeg process teardown
- All sinks registered in `adapters/outputs/__init__.py`
