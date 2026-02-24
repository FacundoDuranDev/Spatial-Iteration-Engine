"""Metrics collector that receives and aggregates metrics from multiple engine instances.

Listens on a UDP port for MetricsMessage datagrams from MetricsReporter
instances and provides aggregated views.
"""

import logging
import socket
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional

from .protocol import MetricsMessage

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Receives and aggregates metrics from multiple engine instances.

    Thread-safe. Runs a background UDP listener thread.
    """

    def __init__(
        self,
        listen_host: str = "0.0.0.0",
        listen_port: int = 9876,
        max_instances: int = 20,
        stale_timeout: float = 30.0,
        max_history_per_instance: int = 100,
    ) -> None:
        """Initialize the metrics collector.

        Args:
            listen_host: Host to bind the UDP listener.
            listen_port: Port to bind the UDP listener.
            max_instances: Maximum number of tracked instances.
            stale_timeout: Seconds after which an instance is considered stale.
            max_history_per_instance: Max snapshots stored per instance.
        """
        self._listen_host = listen_host
        self._listen_port = listen_port
        self._max_instances = max_instances
        self._stale_timeout = stale_timeout
        self._max_history = max_history_per_instance

        self._lock = threading.Lock()
        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

        # instance_id -> deque of (timestamp, metrics_dict)
        self._instances: Dict[str, deque] = {}
        # instance_id -> last_seen (perf_counter)
        self._last_seen: Dict[str, float] = {}

    def start(self) -> None:
        """Start the background UDP listener thread."""
        with self._lock:
            if self._running:
                logger.warning("MetricsCollector already running")
                return

            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind((self._listen_host, self._listen_port))
            self._socket.settimeout(1.0)  # 1s timeout for clean shutdown
            self._stop_event.clear()
            self._running = True

            self._thread = threading.Thread(
                target=self._listen_loop, daemon=True, name="metrics-collector"
            )
            self._thread.start()
            logger.info(f"MetricsCollector listening on {self._listen_host}:{self._listen_port}")

    def stop(self) -> None:
        """Stop the collector and close the socket."""
        with self._lock:
            if not self._running:
                return
            self._stop_event.set()
            self._running = False

        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

        with self._lock:
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None

        logger.info("MetricsCollector stopped")

    def get_instance_ids(self) -> List[str]:
        """Get list of tracked instance IDs.

        Returns:
            List of instance ID strings.
        """
        with self._lock:
            return list(self._instances.keys())

    def get_instance_metrics(self, instance_id: str) -> Optional[Dict]:
        """Get the latest metrics for an instance.

        Args:
            instance_id: Instance ID.

        Returns:
            Latest metrics dict or None if not found.
        """
        with self._lock:
            history = self._instances.get(instance_id)
            if not history:
                return None
            ts, metrics = history[-1]
            return {"timestamp": ts, "metrics": metrics, "instance_id": instance_id}

    def get_all_instances(self) -> Dict[str, Dict]:
        """Get latest metrics for all tracked instances.

        Returns:
            Dict of instance_id -> latest metrics.
        """
        with self._lock:
            result = {}
            for instance_id, history in self._instances.items():
                if history:
                    ts, metrics = history[-1]
                    result[instance_id] = {
                        "timestamp": ts,
                        "metrics": metrics,
                        "instance_id": instance_id,
                    }
            return result

    def get_aggregate(self) -> Dict[str, Any]:
        """Compute aggregate metrics across all instances.

        Returns:
            Dict with mean_fps, total_frames, total_errors, instance_count.
        """
        with self._lock:
            if not self._instances:
                return {
                    "mean_fps": 0.0,
                    "total_frames": 0,
                    "total_errors": 0,
                    "instance_count": 0,
                }

            fps_values = []
            total_frames = 0
            total_errors = 0

            for instance_id, history in self._instances.items():
                if not history:
                    continue
                _, metrics = history[-1]
                fps_values.append(metrics.get("fps", 0.0))
                total_frames += metrics.get("frames_processed", 0)
                total_errors += metrics.get("total_errors", 0)

            mean_fps = sum(fps_values) / len(fps_values) if fps_values else 0.0

            return {
                "mean_fps": mean_fps,
                "total_frames": total_frames,
                "total_errors": total_errors,
                "instance_count": len(self._instances),
            }

    def prune_stale(self) -> int:
        """Remove instances that haven't reported within stale_timeout.

        Returns:
            Number of instances removed.
        """
        now = time.perf_counter()
        pruned = 0
        with self._lock:
            stale_ids = [
                iid for iid, last in self._last_seen.items() if (now - last) > self._stale_timeout
            ]
            for iid in stale_ids:
                self._instances.pop(iid, None)
                self._last_seen.pop(iid, None)
                pruned += 1
                logger.info(f"Pruned stale instance: {iid}")
        return pruned

    def _listen_loop(self) -> None:
        """Background loop listening for UDP datagrams."""
        while not self._stop_event.is_set():
            try:
                data, addr = self._socket.recvfrom(65535)
                self._handle_message(data)
            except socket.timeout:
                # Expected when no data arrives within timeout
                continue
            except OSError:
                # Socket closed during shutdown
                if self._stop_event.is_set():
                    break
                logger.error("Socket error in collector listen loop")
            except Exception as e:
                logger.error(f"Error in collector listen loop: {e}")

    def _handle_message(self, data: bytes) -> None:
        """Process a received UDP message.

        Args:
            data: Raw bytes received.
        """
        try:
            msg = MetricsMessage.deserialize(data)
        except ValueError as e:
            logger.warning(f"Invalid metrics message received: {e}")
            return

        now = time.perf_counter()
        instance_id = msg.instance_id

        with self._lock:
            # Enforce max_instances limit
            if instance_id not in self._instances:
                if len(self._instances) >= self._max_instances:
                    logger.warning(
                        f"Max instances ({self._max_instances}) reached, "
                        f"rejecting instance {instance_id}"
                    )
                    return
                self._instances[instance_id] = deque(maxlen=self._max_history)

            self._instances[instance_id].append((now, msg.metrics))
            self._last_seen[instance_id] = now

    def __del__(self) -> None:
        """Ensure cleanup on garbage collection."""
        try:
            self.stop()
        except Exception:
            pass
