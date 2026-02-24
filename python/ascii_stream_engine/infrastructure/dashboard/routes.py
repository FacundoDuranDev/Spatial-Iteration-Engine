"""Route handler for the dashboard HTTP server.

Defines endpoints: /api/health, /api/metrics, /api/budget,
/api/instances, /api/metrics/history, /stream.
"""

import json
import logging
import time
from http.server import BaseHTTPRequestHandler
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

try:
    import cv2

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for dashboard API endpoints.

    Attributes on the server object (set by DashboardServer):
        metrics_exporter: MetricsExporter instance (optional).
        metrics_collector: MetricsCollector instance (optional).
        frame_buffer: FrameBuffer instance (optional, for MJPEG).
        mjpeg_streamer: MJPEGStreamer instance (optional).
        start_time: Server start time (perf_counter).
    """

    def log_message(self, format, *args):
        """Suppress default HTTP logging to use our logger."""
        logger.debug(f"Dashboard: {format % args}")

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)

        try:
            if path == "/api/health":
                self._handle_health()
            elif path == "/api/metrics":
                self._handle_metrics()
            elif path == "/api/budget":
                self._handle_budget()
            elif path == "/api/instances":
                self._handle_instances()
            elif path == "/api/metrics/history":
                seconds = float(query.get("seconds", [60])[0])
                self._handle_metrics_history(seconds)
            elif path == "/stream":
                self._handle_stream()
            else:
                self._send_json_response(404, {"error": "Not found", "path": self.path})
        except Exception as e:
            logger.error(f"Error handling request {self.path}: {e}", exc_info=True)
            self._send_json_response(500, {"error": str(e)})

    def _handle_health(self):
        """Handle /api/health endpoint."""
        start_time = getattr(self.server, "start_time", time.perf_counter())
        uptime = time.perf_counter() - start_time
        self._send_json_response(200, {"status": "ok", "uptime": round(uptime, 2)})

    def _handle_metrics(self):
        """Handle /api/metrics endpoint."""
        exporter = getattr(self.server, "metrics_exporter", None)
        if exporter is None:
            self._send_json_response(503, {"error": "Metrics exporter not configured"})
            return
        try:
            payload = exporter.get_dashboard_payload()
            self._send_json_response(200, payload)
        except Exception as e:
            self._send_json_response(500, {"error": f"Failed to get metrics: {e}"})

    def _handle_budget(self):
        """Handle /api/budget endpoint."""
        exporter = getattr(self.server, "metrics_exporter", None)
        if exporter is None:
            self._send_json_response(503, {"error": "Metrics exporter not configured"})
            return
        try:
            payload = exporter.get_dashboard_payload()
            budget_data = {
                "budget": payload.get("budget", {}),
                "utilization": payload.get("utilization", {}),
                "violations": payload.get("violations", {}),
                "degradation_recommendation": payload.get("degradation_recommendation"),
            }
            self._send_json_response(200, budget_data)
        except Exception as e:
            self._send_json_response(500, {"error": f"Failed to get budget: {e}"})

    def _handle_instances(self):
        """Handle /api/instances endpoint."""
        collector = getattr(self.server, "metrics_collector", None)
        if collector is None:
            self._send_json_response(200, {"instances": [], "aggregate": {}})
            return
        try:
            all_instances = collector.get_all_instances()
            aggregate = collector.get_aggregate()
            self._send_json_response(200, {"instances": all_instances, "aggregate": aggregate})
        except Exception as e:
            self._send_json_response(500, {"error": f"Failed to get instances: {e}"})

    def _handle_metrics_history(self, seconds: float):
        """Handle /api/metrics/history endpoint.

        Args:
            seconds: Number of seconds of history to return.
        """
        exporter = getattr(self.server, "metrics_exporter", None)
        if exporter is None:
            self._send_json_response(503, {"error": "Metrics exporter not configured"})
            return
        try:
            aggregator = exporter._aggregator
            window = aggregator.get_window(seconds=seconds)
            self._send_json_response(200, {"history": window, "seconds": seconds})
        except Exception as e:
            self._send_json_response(500, {"error": f"Failed to get history: {e}"})

    def _handle_stream(self):
        """Handle /stream MJPEG endpoint."""
        streamer = getattr(self.server, "mjpeg_streamer", None)
        if streamer is None:
            self._send_json_response(503, {"error": "MJPEG stream not configured"})
            return

        if not CV2_AVAILABLE:
            self._send_json_response(
                503, {"error": "cv2 (OpenCV) is not available, MJPEG stream disabled"}
            )
            return

        try:
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=--jpgboundary")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            for frame_data in streamer.generate_frames():
                try:
                    self.wfile.write(b"--jpgboundary\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(frame_data)}\r\n\r\n".encode())
                    self.wfile.write(frame_data)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break
        except Exception as e:
            logger.error(f"Error in MJPEG stream: {e}")

    def _send_json_response(self, status_code: int, data: Any) -> None:
        """Send a JSON response with CORS headers.

        Args:
            status_code: HTTP status code.
            data: Data to serialize as JSON.
        """
        try:
            body = json.dumps(data, indent=2, default=str).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            logger.error(f"Error sending response: {e}")
