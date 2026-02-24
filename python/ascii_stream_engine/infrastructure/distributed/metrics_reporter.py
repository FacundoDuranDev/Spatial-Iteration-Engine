"""Metrics reporter that sends periodic snapshots to a collector via UDP.

Designed for multi-instance monitoring where several StreamEngine
processes report to a central collector.
"""

import logging
import socket
import threading
import time
from typing import Any, Dict, Optional

from .protocol import MetricsMessage

logger = logging.getLogger(__name__)


class MetricsReporter:
    """Sends periodic metric snapshots to a collector via UDP.

    Thread-safe. Uses a background daemon thread for periodic reporting.
    """

    def __init__(
        self,
        instance_id: str,
        collector_host: str = "127.0.0.1",
        collector_port: int = 9876,
        report_interval: float = 5.0,
        metrics: Optional[Any] = None,
        profiler: Optional[Any] = None,
    ) -> None:
        """Initialize the metrics reporter.

        Args:
            instance_id: Unique identifier for this engine instance.
            collector_host: Collector hostname or IP.
            collector_port: Collector UDP port.
            report_interval: Seconds between reports.
            metrics: EngineMetrics instance (optional).
            profiler: LoopProfiler instance (optional).
        """
        self._instance_id = instance_id
        self._collector_host = collector_host
        self._collector_port = collector_port
        self._report_interval = report_interval
        self._metrics = metrics
        self._profiler = profiler

        self._socket: Optional[socket.socket] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._running = False

    def start(self) -> None:
        """Start the background reporting thread."""
        with self._lock:
            if self._running:
                logger.warning("MetricsReporter already running")
                return

            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setblocking(False)
            self._stop_event.clear()
            self._running = True

            self._thread = threading.Thread(
                target=self._report_loop, daemon=True, name="metrics-reporter"
            )
            self._thread.start()
            logger.info(
                f"MetricsReporter started: {self._instance_id} -> "
                f"{self._collector_host}:{self._collector_port}"
            )

    def stop(self) -> None:
        """Stop the reporting thread and close the socket."""
        with self._lock:
            if not self._running:
                return
            self._stop_event.set()
            self._running = False

        if self._thread:
            self._thread.join(timeout=self._report_interval + 2.0)
            self._thread = None

        with self._lock:
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None

        logger.info(f"MetricsReporter stopped: {self._instance_id}")

    def report_now(self) -> None:
        """Send an immediate one-shot report."""
        metrics_data = self._collect_metrics()
        msg = MetricsMessage.create_now(self._instance_id, metrics_data)
        self._send_message(msg)

    def is_running(self) -> bool:
        """Check if the reporter is running.

        Returns:
            True if the background thread is active.
        """
        with self._lock:
            return self._running

    def _report_loop(self) -> None:
        """Background loop that sends reports at the configured interval."""
        while not self._stop_event.is_set():
            try:
                self.report_now()
            except Exception as e:
                logger.error(f"Error sending metrics report: {e}")

            # Wait for the interval or until stop is requested
            self._stop_event.wait(timeout=self._report_interval)

    def _collect_metrics(self) -> Dict[str, Any]:
        """Collect current metrics from EngineMetrics and LoopProfiler.

        Returns:
            Dict of metrics data.
        """
        data: Dict[str, Any] = {}

        if self._metrics:
            try:
                summary = self._metrics.get_summary()
                data["fps"] = summary.get("fps", 0.0)
                data["frames_processed"] = summary.get("frames_processed", 0)
                data["total_errors"] = summary.get("total_errors", 0)
                data["errors"] = summary.get("errors_by_component", {})
                data["latency_avg"] = summary.get("latency_avg", 0.0)
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")

        if self._profiler:
            try:
                profiler_summary = self._profiler.get_summary_dict()
                data["phases"] = {}
                for phase, stats in profiler_summary.items():
                    data["phases"][phase] = {
                        "avg_ms": stats.get("avg_time", 0.0) * 1000.0,
                        "count": stats.get("count", 0),
                    }
            except Exception as e:
                logger.error(f"Error collecting profiler data: {e}")

        return data

    def _send_message(self, msg: MetricsMessage) -> None:
        """Send a message via UDP.

        Args:
            msg: MetricsMessage to send.
        """
        with self._lock:
            if not self._socket:
                return
            try:
                data = msg.serialize()
                self._socket.sendto(data, (self._collector_host, self._collector_port))
            except BlockingIOError:
                pass  # Non-blocking socket, skip if would block
            except Exception as e:
                logger.error(f"Error sending UDP message: {e}")

    def __del__(self) -> None:
        """Ensure cleanup on garbage collection."""
        try:
            self.stop()
        except Exception:
            pass
