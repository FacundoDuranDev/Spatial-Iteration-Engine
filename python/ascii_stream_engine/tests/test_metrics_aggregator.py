"""Tests for MetricsAggregator and MetricsExporter."""

import json
import os
import tempfile
import time

import pytest

from ascii_stream_engine.infrastructure.performance.budget_tracker import BudgetTracker
from ascii_stream_engine.infrastructure.performance.metrics_aggregator import MetricsAggregator
from ascii_stream_engine.infrastructure.performance.metrics_exporter import MetricsExporter


def make_metrics_summary(fps=30.0, frames=100, latency=0.033):
    """Helper to create a metrics summary dict."""
    return {
        "fps": fps,
        "frames_processed": frames,
        "total_errors": 0,
        "errors_by_component": {},
        "latency_avg": latency,
        "latency_min": latency * 0.5,
        "latency_max": latency * 2.0,
        "uptime": 10.0,
    }


def make_profiler_summary():
    """Helper to create a profiler summary dict."""
    return {
        "capture": {
            "count": 100,
            "total_time": 0.1,
            "avg_time": 0.001,
            "min_time": 0.0005,
            "max_time": 0.003,
            "std_dev": 0.0003,
        },
        "analysis": {
            "count": 100,
            "total_time": 1.0,
            "avg_time": 0.010,
            "min_time": 0.005,
            "max_time": 0.020,
            "std_dev": 0.003,
        },
    }


class TestMetricsAggregator:
    """Tests for MetricsAggregator."""

    def test_initial_state(self):
        """No snapshots initially."""
        agg = MetricsAggregator()
        assert agg.get_latest() is None
        assert agg.get_snapshot_count() == 0

    def test_record_snapshot(self):
        """Recording a snapshot stores it."""
        agg = MetricsAggregator(sample_interval=0.0)
        agg.record_snapshot(make_metrics_summary(), make_profiler_summary())
        assert agg.get_snapshot_count() == 1

    def test_get_latest(self):
        """get_latest returns the most recent snapshot."""
        agg = MetricsAggregator(sample_interval=0.0)
        agg.record_snapshot(make_metrics_summary(fps=25.0), make_profiler_summary())
        agg.record_snapshot(make_metrics_summary(fps=30.0), make_profiler_summary())
        latest = agg.get_latest()
        assert latest is not None
        assert latest["fps"] == 30.0

    def test_snapshot_contains_phases(self):
        """Snapshot contains per-phase timing data."""
        agg = MetricsAggregator(sample_interval=0.0)
        agg.record_snapshot(make_metrics_summary(), make_profiler_summary())
        latest = agg.get_latest()
        assert "phases" in latest
        assert "capture" in latest["phases"]
        assert "avg_ms" in latest["phases"]["capture"]

    def test_bounded_storage(self):
        """Snapshots are bounded by max_windows."""
        agg = MetricsAggregator(max_windows=5, sample_interval=0.0)
        for _ in range(10):
            agg.record_snapshot(make_metrics_summary(), make_profiler_summary())
        assert agg.get_snapshot_count() == 5

    def test_sample_interval_enforced(self):
        """Snapshots within sample_interval are dropped."""
        agg = MetricsAggregator(sample_interval=1.0)
        agg.record_snapshot(make_metrics_summary(), make_profiler_summary())
        agg.record_snapshot(make_metrics_summary(), make_profiler_summary())  # Too fast
        assert agg.get_snapshot_count() == 1

    def test_get_window(self):
        """get_window returns snapshots within time range."""
        agg = MetricsAggregator(sample_interval=0.0)
        agg.record_snapshot(make_metrics_summary(), make_profiler_summary())
        time.sleep(0.01)
        agg.record_snapshot(make_metrics_summary(), make_profiler_summary())
        window = agg.get_window(seconds=10.0)
        assert len(window) == 2

    def test_get_trend(self):
        """get_trend returns time-series for a metric key."""
        agg = MetricsAggregator(sample_interval=0.0)
        agg.record_snapshot(make_metrics_summary(fps=25.0), make_profiler_summary())
        time.sleep(0.01)
        agg.record_snapshot(make_metrics_summary(fps=30.0), make_profiler_summary())
        trend = agg.get_trend("fps", seconds=10.0)
        assert len(trend) == 2
        assert trend[0][1] == 25.0
        assert trend[1][1] == 30.0

    def test_reset(self):
        """Reset clears all snapshots."""
        agg = MetricsAggregator(sample_interval=0.0)
        agg.record_snapshot(make_metrics_summary(), make_profiler_summary())
        agg.reset()
        assert agg.get_snapshot_count() == 0
        assert agg.get_latest() is None


class TestMetricsExporter:
    """Tests for MetricsExporter."""

    def test_export_snapshot_valid_json(self):
        """export_snapshot produces valid JSON."""
        agg = MetricsAggregator(sample_interval=0.0)
        tracker = BudgetTracker()
        agg.record_snapshot(make_metrics_summary(), make_profiler_summary())
        exporter = MetricsExporter(agg, tracker)
        json_str = exporter.export_snapshot()
        data = json.loads(json_str)
        assert "timestamp" in data
        assert "current" in data
        assert "budget" in data

    def test_export_to_file(self):
        """export_to_file writes valid JSON file."""
        agg = MetricsAggregator(sample_interval=0.0)
        tracker = BudgetTracker()
        agg.record_snapshot(make_metrics_summary(), make_profiler_summary())
        exporter = MetricsExporter(agg, tracker)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            exporter.export_to_file(path)
            with open(path, "r") as f:
                data = json.load(f)
            assert "current" in data
        finally:
            os.unlink(path)

    def test_dashboard_payload_structure(self):
        """Dashboard payload has expected keys."""
        agg = MetricsAggregator(sample_interval=0.0)
        tracker = BudgetTracker()
        agg.record_snapshot(make_metrics_summary(), make_profiler_summary())
        tracker.record_phase("analysis", 0.025)
        tracker.record_frame(0.050)
        exporter = MetricsExporter(agg, tracker)

        payload = exporter.get_dashboard_payload()
        assert "timestamp" in payload
        assert "current" in payload
        assert "budget" in payload
        assert "utilization" in payload
        assert "violations" in payload
        assert "degradation_recommendation" in payload

    def test_dashboard_payload_no_data(self):
        """Dashboard payload works with no data."""
        agg = MetricsAggregator()
        tracker = BudgetTracker()
        exporter = MetricsExporter(agg, tracker)
        payload = exporter.get_dashboard_payload()
        assert payload["current"] is None
        assert payload["degradation_recommendation"] is None
