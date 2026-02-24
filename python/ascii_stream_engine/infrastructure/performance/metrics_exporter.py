"""Metrics exporter for dashboard consumption.

Exports aggregated metrics as JSON snapshots from MetricsAggregator
and BudgetTracker.
"""

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MetricsExporter:
    """Exports aggregated metrics as JSON for dashboard consumption.

    Thread-safe. Uses time.perf_counter() for all timing.
    """

    def __init__(self, aggregator: Any, budget_tracker: Any) -> None:
        """Initialize the metrics exporter.

        Args:
            aggregator: MetricsAggregator instance.
            budget_tracker: BudgetTracker instance.
        """
        self._aggregator = aggregator
        self._budget_tracker = budget_tracker
        self._lock = threading.Lock()

    def export_snapshot(self) -> str:
        """Export current state as a JSON string.

        Returns:
            JSON string of current metrics state.
        """
        payload = self.get_dashboard_payload()
        return json.dumps(payload, indent=2, default=str)

    def export_to_file(self, path: str) -> None:
        """Write a metrics snapshot to a file.

        Args:
            path: Output file path.
        """
        with self._lock:
            json_str = self.export_snapshot()
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(json_str)
            logger.debug(f"Metrics exported to {path}")

    def get_dashboard_payload(self) -> Dict[str, Any]:
        """Get structured metrics dict for dashboard/HTTP response.

        Returns:
            Dict with latest metrics, budget status, and history.
        """
        with self._lock:
            payload: Dict[str, Any] = {
                "timestamp": time.perf_counter(),
            }

            # Latest aggregated metrics
            latest = self._aggregator.get_latest()
            if latest:
                payload["current"] = {
                    "fps": latest.get("fps", 0.0),
                    "frame_time_ms": latest.get("frame_time_ms", 0.0),
                    "frames_processed": latest.get("frames_processed", 0),
                    "total_errors": latest.get("total_errors", 0),
                    "phases": latest.get("phases", {}),
                }
            else:
                payload["current"] = None

            # Budget status
            budget_summary = self._budget_tracker.get_summary()
            payload["budget"] = budget_summary

            # Budget utilization
            payload["utilization"] = self._budget_tracker.get_budget_utilization()

            # Violations
            violations = self._budget_tracker.get_violations()
            payload["violations"] = {
                phase: {
                    "budget_ms": v.budget_ms,
                    "actual_ms": round(v.actual_ms, 3),
                    "p95_ms": round(v.p95_ms, 3),
                    "violation_count": v.violation_count,
                }
                for phase, v in violations.items()
            }

            # Degradation recommendation
            recommendation = self._budget_tracker.get_degradation_recommendation()
            payload["degradation_recommendation"] = recommendation

            return payload
