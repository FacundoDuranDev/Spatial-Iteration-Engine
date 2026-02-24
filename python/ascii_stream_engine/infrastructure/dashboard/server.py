"""Lightweight HTTP dashboard server using stdlib http.server.

Provides JSON API endpoints for metrics, budget, and instances,
plus an optional MJPEG live preview stream.
"""

import logging
import threading
import time
from http.server import HTTPServer
from typing import Any, Optional

from .mjpeg_stream import MJPEGStreamer
from .routes import DashboardRequestHandler

logger = logging.getLogger(__name__)


class DashboardServer:
    """Lightweight HTTP dashboard server using stdlib http.server.

    Runs in a background daemon thread.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        metrics_exporter: Optional[Any] = None,
        metrics_collector: Optional[Any] = None,
        frame_buffer: Optional[Any] = None,
        mjpeg_target_fps: float = 10.0,
        mjpeg_quality: int = 50,
        mjpeg_max_width: int = 320,
    ) -> None:
        """Initialize the dashboard server.

        Args:
            host: Host to bind to.
            port: Port to bind to.
            metrics_exporter: MetricsExporter instance (optional).
            metrics_collector: MetricsCollector instance (optional).
            frame_buffer: FrameBuffer instance for MJPEG preview (optional).
            mjpeg_target_fps: Target FPS for MJPEG stream.
            mjpeg_quality: JPEG quality for MJPEG stream.
            mjpeg_max_width: Max width for MJPEG stream frames.
        """
        self._host = host
        self._port = port
        self._metrics_exporter = metrics_exporter
        self._metrics_collector = metrics_collector
        self._frame_buffer = frame_buffer

        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._start_time: Optional[float] = None

        # MJPEG streamer
        self._mjpeg_streamer: Optional[MJPEGStreamer] = None
        if frame_buffer:
            self._mjpeg_streamer = MJPEGStreamer(
                frame_buffer=frame_buffer,
                target_fps=mjpeg_target_fps,
                jpeg_quality=mjpeg_quality,
                max_width=mjpeg_max_width,
            )

    def start(self) -> None:
        """Start the dashboard server in a background thread."""
        if self._running:
            logger.warning("DashboardServer already running")
            return

        try:
            self._server = HTTPServer((self._host, self._port), DashboardRequestHandler)
            # Attach context to the server object so handler can access it
            self._server.metrics_exporter = self._metrics_exporter
            self._server.metrics_collector = self._metrics_collector
            self._server.frame_buffer = self._frame_buffer
            self._server.mjpeg_streamer = self._mjpeg_streamer
            self._server.start_time = time.perf_counter()
            self._start_time = self._server.start_time

            self._thread = threading.Thread(
                target=self._server.serve_forever, daemon=True, name="dashboard-server"
            )
            self._thread.start()
            self._running = True
            logger.info(f"DashboardServer started at http://{self._host}:{self._port}")
        except Exception as e:
            logger.error(f"Failed to start DashboardServer: {e}", exc_info=True)
            self._running = False

    def stop(self) -> None:
        """Stop the dashboard server."""
        if not self._running:
            return

        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

        self._running = False
        logger.info("DashboardServer stopped")

    def is_running(self) -> bool:
        """Check if the server is running.

        Returns:
            True if the server is running.
        """
        return self._running

    def get_url(self) -> str:
        """Get the server URL.

        Returns:
            URL string (e.g., "http://127.0.0.1:8080").
        """
        return f"http://{self._host}:{self._port}"

    def __del__(self) -> None:
        """Ensure cleanup on garbage collection."""
        try:
            self.stop()
        except Exception:
            pass
