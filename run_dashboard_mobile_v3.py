#!/usr/bin/env python
"""SIE web dashboard v3 — FastAPI + WebSocket + vanilla HTML/CSS/JS.

Mobile-first control surface for the engine. Replaces v1/v2 Gradio.
See `.claude/scratch/ws_protocol.md` for the wire protocol (v=1).

Run:
    python run_dashboard_mobile_v3.py
Open on phone:
    http://<lan-ip>:7861/?t=<token>   (URL + token printed at boot)

Phase A: only start/stop are wired. Filter ops will land in Phase B.
"""
from __future__ import annotations

import logging
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "python"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "cpp", "build"))

import cv2  # noqa: F401  (cv2 import side-effects for camera)
import uvicorn

print("[v3] loading engine...", flush=True)
from ascii_stream_engine.application.engine import StreamEngine
from ascii_stream_engine.adapters.sources.camera import OpenCVCameraSource
from ascii_stream_engine.adapters.renderers.passthrough_renderer import (
    PassthroughRenderer,
)
from ascii_stream_engine.adapters.outputs.preview_sink import PreviewSink
from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.adapters.outputs.web_dashboard import create_app

try:
    import qrcode as _qrcode
except ImportError:
    _qrcode = None


HOST = "0.0.0.0"
PORT = int(os.environ.get("SIE_V3_PORT", "7861"))
CAMERA_INDEX = int(os.environ.get("SIE_CAMERA_INDEX", "2"))


def _lan_ip() -> str:
    """Best-effort LAN IP for printing the QR. Falls back to 127.0.0.1."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def _print_qr(url: str) -> None:
    if _qrcode is None:
        return
    qr = _qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make()
    qr.print_ascii(invert=True)


class StickyPreviewSink(PreviewSink):
    """PreviewSink that survives engine start→stop→start cycles.

    The base PreviewSink:
      - open()  → calls self.close() then cv2.namedWindow() etc.
      - close() → cv2.destroyWindow + cv2.destroyAllWindows().
    Re-creating the cv2 window from a new engine worker thread on the
    second start deadlocks Qt (the second `_run` thread opens the camera
    but never returns from `cv2.namedWindow`).

    Fix: the cv2 window is created exactly ONCE on the very first open.
    Subsequent open/close calls only flip the `_is_open` flag, leaving
    the window alive on the desktop. `write()` already short-circuits
    when `_is_open` is False, so during a "stopped" cycle the window
    just freezes on the last frame.

    v1 / v2 dashboards keep the base PreviewSink behaviour, so this is
    a v3-only fix.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._window_created = False

    def open(self, config, output_size) -> None:
        # First time: create the window. After that: just flip the flag.
        self._output_size = output_size
        self._is_open = True
        if not self._window_created:
            self._is_fullscreen = False
            self._ensure_window()
            self._window_created = True

    def close(self) -> None:
        # Do NOT touch cv2 — keep the window alive between cycles.
        self._is_open = False


def _build_engine() -> StreamEngine:
    """Build StreamEngine with the real camera and a sticky PreviewSink.

    Filters are attached lazily by the bridge on first toggle.
    """
    config = EngineConfig(
        fps=30,
        enable_temporal=True,
        enable_events=True,
        enable_audio_reactive=False,
    )
    source = OpenCVCameraSource(camera_index=CAMERA_INDEX)
    renderer = PassthroughRenderer()
    sink = StickyPreviewSink(
        window_name="Spatial-Iteration-Engine v3 — f=fullscreen · ESC=exit"
    )
    return StreamEngine(
        source=source,
        renderer=renderer,
        sink=sink,
        config=config,
        enable_profiling=False,
    )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    # Boot a dedicated Qt event-pump thread BEFORE any other cv2 calls.
    # Without this, cv2.namedWindow on the second engine start (from a
    # new worker thread) deadlocks waiting for events. With this, the
    # cv2 window can be created/destroyed from any worker thread safely.
    cv2.startWindowThread()

    print("[v3] building engine (camera not opened yet)...", flush=True)
    engine = _build_engine()

    app, token, _bridge = create_app(engine)

    ip = _lan_ip()
    url = f"http://{ip}:{PORT}/?t={token}"
    print()
    print("=" * 60)
    print(f"  SIE web dashboard v3")
    print(f"  URL    : {url}")
    print(f"  Token  : {token}")
    print(f"  Local  : http://127.0.0.1:{PORT}/?t={token}")
    print(f"  Camera : /dev/video{CAMERA_INDEX} (engine NOT started yet —")
    print(f"           tap Iniciar in the UI to open it)")
    print("=" * 60)
    _print_qr(url)
    print()

    uvicorn.run(app, host=HOST, port=PORT, log_level="info", access_log=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
