# Outputs Team -- 7-Phase Task Plan

## Team Mission

Build five new output sinks that implement the `OutputSink` protocol, enabling the engine to deliver rendered frames over RTSP, WebRTC, OSC, video recording, and NDI. Every sink follows the patterns established in `.claude/skills/output-development/SKILL.md` and satisfies the 3ms output-stage latency budget defined in `rules/LATENCY_BUDGET.md`.

## Reference Files (Read-Only -- Never Modify)

| File | Purpose |
|---|---|
| `python/ascii_stream_engine/ports/outputs.py` | `OutputSink` protocol definition |
| `python/ascii_stream_engine/ports/output_capabilities.py` | `OutputCapabilities`, `OutputCapability`, `OutputQuality` |
| `python/ascii_stream_engine/domain/types.py` | `RenderFrame` dataclass |
| `python/ascii_stream_engine/domain/config.py` | `EngineConfig` |
| `.claude/skills/output-development/SKILL.md` | Canonical development skill for output sinks |
| `rules/PIPELINE_EXTENSION_RULES.md` | Extension rules (Section 3: Adding a New Output Sink) |
| `rules/LATENCY_BUDGET.md` | 3ms output budget, 33.3ms total frame budget |

## Existing Implementations to Study

| Sink | File | Pattern |
|---|---|---|
| `FfmpegUdpOutput` | `adapters/outputs/udp.py` | ffmpeg subprocess, rawvideo piping |
| `FfmpegRtspSink` | `adapters/outputs/rtsp/rtsp_sink.py` | ffmpeg subprocess, RTSP output (partial -- needs completion) |
| `WebRTCOutput` | `adapters/outputs/webrtc/webrtc_sink.py` | aiortc, async event loop, signaling server (partial -- needs completion) |
| `NdiOutputSink` | `adapters/outputs/ndi/ndi_sink.py` | ndi-python, BGRA conversion, thread lock (partial -- needs completion) |
| `AsciiFrameRecorder` | `adapters/outputs/ascii_recorder.py` | File I/O, text-based recording |
| `CompositeOutputSink` | `adapters/outputs/composite.py` | Fan-out pattern |
| `PreviewSink` | `adapters/outputs/preview_sink.py` | OpenCV window display |
| `NotebookPreviewSink` | `adapters/outputs/notebook_preview_sink.py` | ipywidgets JPEG display |

## Sinks to Build

| # | Sink Class | File Path | Protocol | Key Dependency |
|---|---|---|---|---|
| 1 | `FfmpegRtspSink` | `adapters/outputs/rtsp/rtsp_sink.py` | RTSP via ffmpeg | ffmpeg with RTSP muxer |
| 2 | `WebRTCOutput` | `adapters/outputs/webrtc/webrtc_sink.py` | WebRTC via aiortc | `aiortc`, `aiohttp`, `av` |
| 3 | `OscOutputSink` | `adapters/outputs/osc/osc_sink.py` | OSC over UDP | `python-osc` |
| 4 | `VideoRecorderSink` | `adapters/outputs/recorder/video_recorder_sink.py` | MP4/AVI via ffmpeg | ffmpeg |
| 5 | `NdiOutputSink` | `adapters/outputs/ndi/ndi_sink.py` | NDI | `ndi-python`, NDI SDK |

---

## Phase 1: Audit, Gap Analysis, and Shared Utilities

**Goal:** Understand the current state of all existing and partial sinks, identify what is missing or broken, and extract shared patterns into reusable helpers.

### Tasks

1.1. **Audit existing partial implementations.** Read and analyze the current state of:
   - `adapters/outputs/rtsp/rtsp_sink.py` -- Missing: `is_open()`, `get_capabilities()`, `get_estimated_latency_ms()`, `supports_multiple_clients()`. The `close()` method lacks the `self._is_open = False` assignment after cleanup.
   - `adapters/outputs/webrtc/webrtc_sink.py` -- Missing: `get_capabilities()`, `get_estimated_latency_ms()`, `supports_multiple_clients()`. The `close()` method is not fully idempotent (early returns if `not self._is_open`).
   - `adapters/outputs/ndi/ndi_sink.py` -- Missing: `get_capabilities()`, `get_estimated_latency_ms()`, `supports_multiple_clients()`. Uses `__del__` which is fragile; needs explicit lifecycle.
   - `adapters/outputs/__init__.py` -- Missing registration for `NdiOutputSink`, `OscOutputSink`, `VideoRecorderSink`.

1.2. **Document the gap matrix.** For each sink, create a checklist of all 7 `OutputSink` protocol methods and whether they exist, are correct, or need work.

1.3. **Extract DummyProc test helper.** The test files `test_outputs.py`, `test_outputs_rtsp.py` each define identical `DummyProc` classes inline. Extract a shared `DummyProc` fixture into `tests/conftest.py` or `tests/helpers.py` for reuse across all ffmpeg-subprocess-based sink tests.

1.4. **Create shared subprocess cleanup utility.** The stdin-close / wait / terminate / kill pattern is duplicated in `udp.py` and `rtsp_sink.py`. Extract a `_cleanup_subprocess(proc, timeout=1)` helper function into `adapters/outputs/_subprocess_utils.py` that both sinks (and the new `VideoRecorderSink`) can import.

### Deliverables

| Deliverable | File Path |
|---|---|
| Gap analysis document | `.claude/orchestration/teams/outputs/gap_analysis.md` |
| Subprocess cleanup utility | `python/ascii_stream_engine/adapters/outputs/_subprocess_utils.py` |
| Shared DummyProc test helper | `python/ascii_stream_engine/tests/helpers/dummy_proc.py` |

### Acceptance Criteria

- [ ] Every partial sink has a documented list of missing or broken protocol methods
- [ ] `_cleanup_subprocess()` is importable and matches the pattern from SKILL.md (close stdin, wait, terminate, kill)
- [ ] `DummyProc` is importable from the shared location and existing tests still pass when refactored to use it
- [ ] `make test` passes with no regressions

---

## Phase 2: Complete RTSP Streaming Sink

**Goal:** Bring `FfmpegRtspSink` to full protocol compliance with all 7 `OutputSink` methods, proper capabilities, and comprehensive tests.

### Tasks

2.1. **Add missing protocol methods to `FfmpegRtspSink`.** Implement the following in `adapters/outputs/rtsp/rtsp_sink.py`:
   - `is_open(self) -> bool` -- Return `True` only when `self._proc` is not None and `self._proc.stdin` is not None.
   - `get_capabilities(self) -> OutputCapabilities` -- Return capabilities with flags: `STREAMING | RTSP | TCP | LOW_LATENCY | CUSTOM_BITRATE | MULTI_CLIENT`. Set `estimated_latency_ms=100.0`, `protocol_name="RTSP/H.264"`, `max_clients` from `self._max_clients`.
   - `get_estimated_latency_ms(self) -> Optional[float]` -- Return `100.0`.
   - `supports_multiple_clients(self) -> bool` -- Return `True` (RTSP inherently supports multiple consumers via an RTSP server like MediaMTX).

2.2. **Fix `close()` idempotency.** Ensure `self._is_open` is set (add `self._is_open = False` -- currently the attribute does not exist at all). Add `self._output_size = None` reset. Ensure `close()` is safe to call when already closed (no `self._proc` attribute check crash).

2.3. **Fix `open()` to set `self._is_open = True`.** Currently `open()` does not set an `_is_open` flag. Add the flag after the subprocess starts.

2.4. **Use `_cleanup_subprocess()` from Phase 1.** Replace the inline subprocess cleanup code in `close()` with a call to the shared utility.

2.5. **Wrap `write()` in try/except.** The `BrokenPipeError` handler in `write()` sets `self._proc = None` but does not set `self._is_open = False`. Fix so the sink state is consistent.

2.6. **Write comprehensive tests.** Add to `tests/test_outputs_rtsp.py`:
   - `test_rtsp_sink_is_open_lifecycle` -- Verify `is_open()` returns `False` before open, `True` after open, `False` after close.
   - `test_rtsp_sink_capabilities` -- Verify correct capability flags, protocol name, latency.
   - `test_rtsp_sink_close_idempotent` -- Call `close()` twice, no exception.
   - `test_rtsp_sink_write_when_closed` -- `write()` on a closed sink is a no-op.
   - `test_rtsp_sink_open_closes_previous` -- Open twice, verify no resource leak.
   - `test_rtsp_sink_estimated_latency` -- Verify `get_estimated_latency_ms()` returns a float.
   - `test_rtsp_sink_supports_multiple_clients` -- Verify returns `True`.

### Deliverables

| Deliverable | File Path |
|---|---|
| Completed RTSP sink | `python/ascii_stream_engine/adapters/outputs/rtsp/rtsp_sink.py` |
| Expanded tests | `python/ascii_stream_engine/tests/test_outputs_rtsp.py` |

### Acceptance Criteria

- [ ] `FfmpegRtspSink` implements all 7 `OutputSink` protocol methods
- [ ] `close()` is idempotent: calling it on an unopened or already-closed sink does not raise
- [ ] `write()` is a silent no-op when the sink is not open
- [ ] `open()` calls `self.close()` first to prevent resource leaks
- [ ] `get_capabilities()` returns `OutputCapabilities` with `RTSP` and `STREAMING` flags set
- [ ] All new tests pass: `PYTHONPATH=python:cpp/build python -m pytest python/ascii_stream_engine/tests/test_outputs_rtsp.py -v`
- [ ] `make test` passes with no regressions

---

## Phase 3: Complete WebRTC Peer Sink

**Goal:** Bring `WebRTCOutput` to full protocol compliance, fix its async lifecycle, and add missing protocol methods.

### Tasks

3.1. **Add missing protocol methods to `WebRTCOutput`.** Implement in `adapters/outputs/webrtc/webrtc_sink.py`:
   - `get_capabilities(self) -> OutputCapabilities` -- Flags: `STREAMING | WEBRTC | LOW_LATENCY | ADAPTIVE_QUALITY | MULTI_CLIENT`. Set `estimated_latency_ms=50.0`, `protocol_name="WebRTC"`, `max_clients=10`.
   - `get_estimated_latency_ms(self) -> Optional[float]` -- Return `50.0`.
   - `supports_multiple_clients(self) -> bool` -- Return `True`.

3.2. **Fix `close()` idempotency.** The current `close()` returns early with `if not self._is_open: return`. This means a second call after `close()` already ran is safe, but calling `close()` on a never-opened sink also returns early, which is correct. However, the `_loop` reference is not cleaned up, and the `_thread` is not joined. Fix:
   - Always set `self._is_open = False` at the top.
   - Stop the event loop after closing the peer connection.
   - Join the thread with a timeout.
   - Set `self._loop = None` and `self._thread = None`.

3.3. **Fix `FrameVideoTrack` deprecated `loop` parameter.** The `asyncio.Queue(maxsize=2, loop=loop)` pattern uses the deprecated `loop` parameter (removed in Python 3.10). Replace with `asyncio.Queue(maxsize=2)` and handle cross-thread frame injection via `loop.call_soon_threadsafe()`.

3.4. **Add error handling to `write()`.** Currently wraps in try/except, which is correct. Verify it logs but does not raise.

3.5. **Ensure signaling server cleanup.** Verify that `WebRTCSignalingServer.stop()` properly stops the aiohttp runner and cleans up the thread.

3.6. **Write comprehensive tests.** Add to `tests/test_outputs_webrtc.py`:
   - `test_webrtc_output_capabilities` -- Verify capability flags, protocol name, latency.
   - `test_webrtc_output_close_idempotent` -- Call `close()` twice, no exception.
   - `test_webrtc_output_estimated_latency` -- Verify returns 50.0.
   - `test_webrtc_output_supports_multiple_clients` -- Verify returns `True`.
   - `test_webrtc_output_write_image_conversion` -- Verify RGBA images are handled.
   - `test_frame_video_track_put_frame` -- Verify frame queuing works.

### Deliverables

| Deliverable | File Path |
|---|---|
| Completed WebRTC sink | `python/ascii_stream_engine/adapters/outputs/webrtc/webrtc_sink.py` |
| Completed signaling server | `python/ascii_stream_engine/adapters/outputs/webrtc/signaling.py` |
| Expanded tests | `python/ascii_stream_engine/tests/test_outputs_webrtc.py` |

### Acceptance Criteria

- [ ] `WebRTCOutput` implements all 7 `OutputSink` protocol methods
- [ ] `close()` is idempotent and cleans up the async event loop and thread
- [ ] No use of deprecated `loop` parameter in `asyncio.Queue`
- [ ] `write()` is a silent no-op when the sink is not open
- [ ] Signaling server starts and stops cleanly
- [ ] All new tests pass: `PYTHONPATH=python:cpp/build python -m pytest python/ascii_stream_engine/tests/test_outputs_webrtc.py -v`
- [ ] Tests are skipped gracefully when `aiortc`/`aiohttp` are not installed

---

## Phase 4: Build OSC Output Sink (New)

**Goal:** Create a new `OscOutputSink` that extracts metadata, analysis results, and frame dimensions from `RenderFrame` and sends them as OSC messages to VJ tools (TouchDesigner, Resolume, Max/MSP).

### Context

Unlike image-based sinks, the OSC sink does not transmit pixel data. It sends structured analysis data (face landmarks, hand positions, pose joints, frame metadata) as OSC bundles over UDP. This makes it unique among all sinks but it still follows the full `OutputSink` protocol.

### Tasks

4.1. **Create OSC sink module directory.**
   - `adapters/outputs/osc/__init__.py` -- Import and re-export `OscOutputSink`.
   - `adapters/outputs/osc/osc_sink.py` -- Main implementation.

4.2. **Implement `OscOutputSink` class.** In `adapters/outputs/osc/osc_sink.py`:
   ```python
   class OscOutputSink:
       def __init__(
           self,
           host: str = "127.0.0.1",
           port: int = 9000,
           address_prefix: str = "/spatial",
           send_image_info: bool = True,
           send_analysis: bool = True,
           send_metadata: bool = True,
       ) -> None: ...
   ```

   - `open()`: Create `pythonosc.udp_client.SimpleUDPClient(host, port)`. Store config and output_size.
   - `write()`: Extract data from `RenderFrame` and send OSC messages:
     - `/spatial/frame/size` -- `[width, height]` (int, int)
     - `/spatial/frame/index` -- frame counter (int)
     - `/spatial/analysis/face/points` -- Flattened face landmark array (list of floats)
     - `/spatial/analysis/hands/left` -- Flattened left hand landmarks (list of floats)
     - `/spatial/analysis/hands/right` -- Flattened right hand landmarks (list of floats)
     - `/spatial/analysis/pose/joints` -- Flattened pose joints (list of floats)
     - `/spatial/metadata/*` -- Individual metadata key/value pairs
   - `close()`: Set `self._client = None`, `self._is_open = False`. Idempotent.
   - `get_capabilities()`: Flags `STREAMING | UDP | LOW_LATENCY | ULTRA_LOW_LATENCY`. `estimated_latency_ms=1.0`, `protocol_name="OSC/UDP"`, `max_clients=None` (UDP broadcast-capable).
   - `get_estimated_latency_ms()`: Return `1.0`.
   - `supports_multiple_clients()`: Return `True` (UDP can broadcast).

4.3. **Handle missing analysis data gracefully.** If `frame.metadata` is None or does not contain `analysis`, skip sending analysis OSC messages. Never raise.

4.4. **Handle numpy arrays in OSC.** Convert `np.ndarray` landmarks to flat Python `list[float]` before sending via OSC (pythonosc cannot send numpy arrays directly).

4.5. **Register in `adapters/outputs/__init__.py`.** Use try/except pattern:
   ```python
   try:
       from .osc import OscOutputSink
   except ImportError:
       OscOutputSink = None  # type: ignore
   ```
   Add to `__all__` conditionally.

4.6. **Write comprehensive tests.** Create `tests/test_outputs_osc.py`:
   - `test_osc_sink_lifecycle` -- open/write/close cycle works.
   - `test_osc_sink_close_idempotent` -- Double close is safe.
   - `test_osc_sink_write_when_closed` -- No-op, no exception.
   - `test_osc_sink_capabilities` -- Verify flags, protocol name.
   - `test_osc_sink_sends_frame_info` -- Verify frame size and index are sent.
   - `test_osc_sink_sends_analysis_data` -- Verify face/hands/pose data is sent when available in metadata.
   - `test_osc_sink_handles_missing_analysis` -- No error when metadata has no analysis.
   - `test_osc_sink_open_closes_previous` -- Re-open is safe.
   - `test_osc_sink_estimated_latency` -- Returns 1.0.
   - `test_osc_sink_supports_multiple_clients` -- Returns True.

### Deliverables

| Deliverable | File Path |
|---|---|
| OSC sink implementation | `python/ascii_stream_engine/adapters/outputs/osc/osc_sink.py` |
| OSC module init | `python/ascii_stream_engine/adapters/outputs/osc/__init__.py` |
| Updated outputs init | `python/ascii_stream_engine/adapters/outputs/__init__.py` |
| Tests | `python/ascii_stream_engine/tests/test_outputs_osc.py` |

### Acceptance Criteria

- [ ] `OscOutputSink` implements all 7 `OutputSink` protocol methods
- [ ] OSC messages are sent with correct address patterns under the configurable prefix
- [ ] Analysis data (face, hands, pose) is correctly extracted from `RenderFrame.metadata["analysis"]` and converted to flat float lists
- [ ] Missing analysis data does not cause errors
- [ ] `close()` is idempotent
- [ ] `write()` is a no-op when closed
- [ ] Registered in `__init__.py` with try/except for `python-osc` dependency
- [ ] All tests pass: `PYTHONPATH=python:cpp/build python -m pytest python/ascii_stream_engine/tests/test_outputs_osc.py -v`
- [ ] `make test` passes with no regressions (tests skipped if `python-osc` not installed)

---

## Phase 5: Build Video Recorder Sink (New)

**Goal:** Create a `VideoRecorderSink` that records rendered frames to MP4 or AVI video files using an ffmpeg subprocess, following the same subprocess pattern as `FfmpegUdpOutput` and `FfmpegRtspSink`.

### Tasks

5.1. **Create video recorder module directory.**
   - `adapters/outputs/recorder/__init__.py` -- Import and re-export `VideoRecorderSink`.
   - `adapters/outputs/recorder/video_recorder_sink.py` -- Main implementation.

5.2. **Implement `VideoRecorderSink` class.** In `adapters/outputs/recorder/video_recorder_sink.py`:
   ```python
   class VideoRecorderSink:
       def __init__(
           self,
           output_path: str = "output.mp4",
           codec: str = "libx264",
           bitrate: str = "2000k",
           preset: str = "medium",
           container_format: Optional[str] = None,  # auto-detect from extension
           pixel_format: str = "yuv420p",
       ) -> None: ...
   ```

   - `open()`: Call `self.close()` first. Detect container format from file extension if not specified (`.mp4` -> mp4, `.avi` -> avi, `.mkv` -> matroska). Build ffmpeg command:
     ```
     ffmpeg -loglevel error -f rawvideo -pix_fmt rgb24
            -s {W}x{H} -framerate {fps} -i -
            -an -c:v {codec} -b:v {bitrate} -preset {preset}
            -pix_fmt {pixel_format} -f {format} {output_path}
     ```
   - `write()`: Use subprocess stdin pipe pattern. Convert PIL RGB to bytes. Use `_cleanup_subprocess()` shared utility on error.
   - `close()`: Use `_cleanup_subprocess()` from Phase 1. Set `self._is_open = False`, `self._output_size = None`. Ensure output file is properly finalized (ffmpeg flushes moov atom on clean stdin close).
   - `get_capabilities()`: Flags `RECORDING | HIGH_QUALITY | CUSTOM_BITRATE`. `estimated_latency_ms=2.0`, `protocol_name="File (Video)"`, `max_clients=1`.
   - `get_estimated_latency_ms()`: Return `2.0`.
   - `supports_multiple_clients()`: Return `False`.

5.3. **Handle container format detection.** Map file extensions:
   - `.mp4` -> `"mp4"`
   - `.avi` -> `"avi"`
   - `.mkv` -> `"matroska"`
   - `.mov` -> `"mov"`
   - `.webm` -> `"webm"` (with `libvpx` codec override)
   - Default to `"mp4"` if unknown.

5.4. **Register in `adapters/outputs/__init__.py`.** No try/except needed since ffmpeg is already a hard dependency for `FfmpegUdpOutput`. But use the pattern anyway for consistency:
   ```python
   try:
       from .recorder import VideoRecorderSink
   except ImportError:
       VideoRecorderSink = None  # type: ignore
   ```

5.5. **Write comprehensive tests.** Create `tests/test_outputs_recorder.py`:
   - `test_recorder_sink_lifecycle` -- open/write/close with DummyProc.
   - `test_recorder_sink_close_idempotent` -- Double close is safe.
   - `test_recorder_sink_write_when_closed` -- No-op, no exception.
   - `test_recorder_sink_capabilities` -- Verify `RECORDING` flag, protocol name.
   - `test_recorder_sink_spawns_ffmpeg_with_correct_args` -- Verify ffmpeg command includes codec, bitrate, output path.
   - `test_recorder_sink_detects_mp4_format` -- Verify `.mp4` extension maps to mp4 format.
   - `test_recorder_sink_detects_avi_format` -- Verify `.avi` extension maps to avi format.
   - `test_recorder_sink_detects_mkv_format` -- Verify `.mkv` extension maps to matroska format.
   - `test_recorder_sink_custom_codec` -- Verify custom codec is passed to ffmpeg.
   - `test_recorder_sink_open_closes_previous` -- Re-open is safe.
   - `test_recorder_sink_handles_image_conversion` -- RGBA images are converted to RGB.
   - `test_recorder_sink_estimated_latency` -- Returns 2.0.

### Deliverables

| Deliverable | File Path |
|---|---|
| Video recorder implementation | `python/ascii_stream_engine/adapters/outputs/recorder/video_recorder_sink.py` |
| Recorder module init | `python/ascii_stream_engine/adapters/outputs/recorder/__init__.py` |
| Updated outputs init | `python/ascii_stream_engine/adapters/outputs/__init__.py` |
| Tests | `python/ascii_stream_engine/tests/test_outputs_recorder.py` |

### Acceptance Criteria

- [ ] `VideoRecorderSink` implements all 7 `OutputSink` protocol methods
- [ ] ffmpeg subprocess is spawned with correct codec, bitrate, format, and output path
- [ ] Container format is auto-detected from file extension
- [ ] `close()` is idempotent and uses the shared `_cleanup_subprocess()` utility
- [ ] `write()` is a no-op when closed
- [ ] Output file is properly finalized on clean close (no corrupt moov atom)
- [ ] Registered in `__init__.py` with try/except
- [ ] All tests pass: `PYTHONPATH=python:cpp/build python -m pytest python/ascii_stream_engine/tests/test_outputs_recorder.py -v`
- [ ] `make test` passes with no regressions

---

## Phase 6: Complete NDI Output Sink

**Goal:** Bring `NdiOutputSink` to full protocol compliance, add missing methods, fix fragile lifecycle patterns, and expand tests.

### Tasks

6.1. **Add missing protocol methods to `NdiOutputSink`.** Implement in `adapters/outputs/ndi/ndi_sink.py`:
   - `get_capabilities(self) -> OutputCapabilities` -- Flags: `STREAMING | NDI | LOW_LATENCY | MULTI_CLIENT | HIGH_QUALITY | ADAPTIVE_QUALITY`. Set `estimated_latency_ms=10.0`, `protocol_name="NDI"`, `max_clients=None` (NDI supports unlimited receivers).
   - `get_estimated_latency_ms(self) -> Optional[float]` -- Return `10.0`.
   - `supports_multiple_clients(self) -> bool` -- Return `True`.

6.2. **Fix `close()` idempotency.** The current `close()` acquires `self._lock` and checks `if self._ndi_send:`. This is correct for idempotency. However, `ndi.destroy()` is called every time `close()` runs, which may crash if NDI was never initialized. Guard with `if self._ndi_send:` before calling `ndi.destroy()`. Also remove the bare `except Exception: pass` on `ndi.destroy()` -- it should at least log.

6.3. **Remove `__del__`.** The `__del__` destructor is fragile and may cause issues with garbage collection ordering. Remove it. Users should call `close()` explicitly or use context manager support.

6.4. **Add context manager support.** Add `__enter__`/`__exit__` methods (same pattern as `FfmpegRtspSink`).

6.5. **Optimize `write()` BGR conversion.** The current implementation creates a separate BGRA array and copies channels one-by-one. Optimize using `cv2.cvtColor` with `COLOR_RGB2BGRA` if OpenCV is available, falling back to the current numpy approach.

6.6. **Register in `adapters/outputs/__init__.py`.** Add:
   ```python
   try:
       from .ndi import NdiOutputSink
   except ImportError:
       NdiOutputSink = None  # type: ignore
   ```
   Add to `__all__` conditionally. Currently `NdiOutputSink` is NOT registered -- this must be added.

6.7. **Write comprehensive tests.** Expand `tests/test_outputs_ndi.py`:
   - `test_ndi_output_capabilities` -- Verify flags include `NDI`, `STREAMING`, `MULTI_CLIENT`.
   - `test_ndi_output_close_idempotent` -- Call `close()` twice, no exception.
   - `test_ndi_output_estimated_latency` -- Returns 10.0.
   - `test_ndi_output_supports_multiple_clients` -- Returns True.
   - `test_ndi_output_context_manager` -- Verify `with NdiOutputSink() as sink:` works.
   - `test_ndi_output_open_closes_previous` -- Re-open calls close first.
   - `test_ndi_output_handles_rgba_image` -- RGBA images are handled without error.

### Deliverables

| Deliverable | File Path |
|---|---|
| Completed NDI sink | `python/ascii_stream_engine/adapters/outputs/ndi/ndi_sink.py` |
| Updated outputs init | `python/ascii_stream_engine/adapters/outputs/__init__.py` |
| Expanded tests | `python/ascii_stream_engine/tests/test_outputs_ndi.py` |

### Acceptance Criteria

- [ ] `NdiOutputSink` implements all 7 `OutputSink` protocol methods
- [ ] `__del__` removed, context manager (`__enter__`/`__exit__`) added
- [ ] `close()` is idempotent and does not crash when NDI was never initialized
- [ ] `write()` is a no-op when closed
- [ ] `get_capabilities()` returns `OutputCapabilities` with `NDI` and `MULTI_CLIENT` flags
- [ ] Registered in `__init__.py` with try/except for `ndi-python` dependency
- [ ] All tests pass: `PYTHONPATH=python:cpp/build python -m pytest python/ascii_stream_engine/tests/test_outputs_ndi.py -v`
- [ ] Tests are skipped gracefully when `ndi-python` is not installed

---

## Phase 7: Integration, CompositeOutputSink Verification, and Documentation

**Goal:** Verify all five sinks work together through `CompositeOutputSink`, ensure `__init__.py` registration is complete and correct, run full test suite, and document the outputs for the project.

### Tasks

7.1. **Verify `adapters/outputs/__init__.py` final state.** Ensure all five sinks are registered with proper try/except and conditional `__all__`:
   ```python
   from .ascii_recorder import AsciiFrameRecorder
   from .composite import CompositeOutputSink
   from .notebook_preview_sink import NotebookPreviewSink
   from .preview_sink import PreviewSink
   from .udp import FfmpegUdpOutput
   from ...ports.outputs import OutputSink

   try:
       from .rtsp import FfmpegRtspSink
   except ImportError:
       FfmpegRtspSink = None

   try:
       from .webrtc import WebRTCOutput
   except ImportError:
       WebRTCOutput = None

   try:
       from .osc import OscOutputSink
   except ImportError:
       OscOutputSink = None

   try:
       from .recorder import VideoRecorderSink
   except ImportError:
       VideoRecorderSink = None

   try:
       from .ndi import NdiOutputSink
   except ImportError:
       NdiOutputSink = None

   __all__ = [
       "AsciiFrameRecorder",
       "CompositeOutputSink",
       "FfmpegUdpOutput",
       "NotebookPreviewSink",
       "OutputSink",
       "PreviewSink",
   ]
   for _cls_name, _cls in [
       ("FfmpegRtspSink", FfmpegRtspSink),
       ("WebRTCOutput", WebRTCOutput),
       ("OscOutputSink", OscOutputSink),
       ("VideoRecorderSink", VideoRecorderSink),
       ("NdiOutputSink", NdiOutputSink),
   ]:
       if _cls is not None:
           __all__.append(_cls_name)
   ```

7.2. **Write CompositeOutputSink integration tests.** Add to `tests/test_outputs.py`:
   - `test_composite_with_recorder_and_osc` -- Compose a `VideoRecorderSink` + `OscOutputSink` in a `CompositeOutputSink`, verify both receive frames.
   - `test_composite_capabilities_combined` -- Verify OR-combined capabilities include `RECORDING | STREAMING | UDP | OSC`.
   - `test_composite_latency_is_max` -- Verify estimated latency is the maximum of all children.
   - `test_composite_handles_partial_failures` -- One sink fails to open, others continue.

7.3. **Write cross-sink protocol conformance test.** Create `tests/test_outputs_protocol_conformance.py`:
   - Parameterized test that instantiates each sink class (with mocked dependencies where needed) and verifies:
     - `is_open()` returns `False` before `open()`
     - `get_capabilities()` returns a valid `OutputCapabilities` instance
     - `get_estimated_latency_ms()` returns `None` or a positive float
     - `supports_multiple_clients()` returns a bool
     - `close()` can be called twice without raising
     - `write()` on a closed sink does not raise

7.4. **Run full test suite.** Execute `make test` and `make check` to verify no regressions across all test files.

7.5. **Update the SKILL.md planned sinks table.** Update `.claude/skills/output-development/SKILL.md` section "Planned Sinks (MVP_04)" to reflect the completed status of all five sinks and add the OSC and Video Recorder sinks to the "Existing Sinks" table.

7.6. **Update CHANGELOG.md.** Add entries under `[Unreleased]`:
   - `feat(outputs): complete RTSP streaming sink with full protocol compliance`
   - `feat(outputs): complete WebRTC peer sink with signaling server`
   - `feat(outputs): add OSC output sink for VJ tool integration`
   - `feat(outputs): add video recorder sink with MP4/AVI/MKV support`
   - `feat(outputs): complete NDI output sink with full protocol compliance`
   - `refactor(outputs): extract shared subprocess cleanup utility`

### Deliverables

| Deliverable | File Path |
|---|---|
| Final outputs init | `python/ascii_stream_engine/adapters/outputs/__init__.py` |
| Protocol conformance tests | `python/ascii_stream_engine/tests/test_outputs_protocol_conformance.py` |
| Updated composite tests | `python/ascii_stream_engine/tests/test_outputs.py` |
| Updated SKILL.md | `.claude/skills/output-development/SKILL.md` |
| Updated CHANGELOG.md | `CHANGELOG.md` |

### Acceptance Criteria

- [ ] All 5 sinks are registered in `__init__.py` with try/except pattern
- [ ] All 5 sinks pass protocol conformance tests (all 7 methods behave correctly)
- [ ] `CompositeOutputSink` can fan out to any combination of the 5 new sinks
- [ ] `make test` passes with zero failures
- [ ] `make check` passes (format + lint + test)
- [ ] CHANGELOG.md updated with all new features
- [ ] SKILL.md updated with completed sink status

---

## Summary of All Deliverables

| Phase | New/Modified Files | Status |
|---|---|---|
| 1 | `_subprocess_utils.py`, `helpers/dummy_proc.py`, `gap_analysis.md` | Foundation |
| 2 | `rtsp/rtsp_sink.py`, `test_outputs_rtsp.py` | Complete RTSP |
| 3 | `webrtc/webrtc_sink.py`, `webrtc/signaling.py`, `test_outputs_webrtc.py` | Complete WebRTC |
| 4 | `osc/osc_sink.py`, `osc/__init__.py`, `test_outputs_osc.py`, `__init__.py` | New OSC |
| 5 | `recorder/video_recorder_sink.py`, `recorder/__init__.py`, `test_outputs_recorder.py`, `__init__.py` | New Recorder |
| 6 | `ndi/ndi_sink.py`, `test_outputs_ndi.py`, `__init__.py` | Complete NDI |
| 7 | `__init__.py`, `test_outputs_protocol_conformance.py`, `test_outputs.py`, `SKILL.md`, `CHANGELOG.md` | Integration |

## Dependency Graph

```
Phase 1 (Foundation)
   |
   +---> Phase 2 (RTSP) ----+
   |                         |
   +---> Phase 3 (WebRTC) ---+
   |                         |
   +---> Phase 4 (OSC) ------+---> Phase 7 (Integration)
   |                         |
   +---> Phase 5 (Recorder) -+
   |                         |
   +---> Phase 6 (NDI) ------+
```

Phases 2-6 depend on Phase 1 (shared utilities) but are independent of each other and can be worked on in parallel. Phase 7 depends on all prior phases being complete.

## Conventions

- All file paths are relative to `python/ascii_stream_engine/` unless otherwise noted.
- All sinks MUST follow the patterns in `.claude/skills/output-development/SKILL.md`.
- All imports from the project use relative imports within the package (`from ...domain.config import EngineConfig`).
- Tests use `unittest.TestCase` with `unittest.mock.patch` for mocking external dependencies.
- Tests for optional-dependency sinks use `@unittest.skipUnless(has_module("..."), "requires ...")`.
- Commit messages follow conventional commits: `feat(outputs):`, `fix(outputs):`, `refactor(outputs):`, `test(outputs):`.
