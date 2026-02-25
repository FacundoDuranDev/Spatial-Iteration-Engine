"""Tests for Phase 2: Advanced Diagnostics Panel."""

import unittest
from unittest.mock import patch

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.tests import has_module


class MockProfiler:
    def __init__(self):
        self.enabled = True


class MockMetrics:
    def get_fps(self):
        return 25.0

    def get_errors(self):
        return {"capture": 2, "rendering": 1}

    def get_summary(self):
        return {
            "fps": 25.0,
            "frames_processed": 100,
            "total_errors": 3,
            "errors_by_component": {"capture": 2, "rendering": 1},
            "latency_avg": 0.033,
            "latency_min": 0.020,
            "latency_max": 0.050,
            "uptime": 10.0,
        }


class MockEngine:
    def __init__(self):
        self._config = EngineConfig()
        self.profiler = MockProfiler()
        self.metrics = MockMetrics()
        self.is_running = False

    def get_config(self):
        return self._config

    def get_profiling_stats(self):
        return {
            "capture": {
                "count": 100,
                "total_time": 0.15,
                "avg_time": 0.0015,
                "min_time": 0.001,
                "max_time": 0.003,
                "std_dev": 0.0005,
            },
            "analysis": {
                "count": 100,
                "total_time": 1.0,
                "avg_time": 0.010,
                "min_time": 0.005,
                "max_time": 0.020,
                "std_dev": 0.003,
            },
            "total_frame": {
                "count": 100,
                "total_time": 3.0,
                "avg_time": 0.030,
                "min_time": 0.020,
                "max_time": 0.050,
                "std_dev": 0.005,
            },
        }


@unittest.skipUnless(has_module("ipywidgets"), "ipywidgets not available")
@unittest.skipUnless(has_module("IPython"), "IPython not available")
class TestAdvancedDiagnosticsPanel(unittest.TestCase):
    @patch("IPython.display.display")
    def test_returns_expected_keys(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_advanced_diagnostics_panel,
        )

        engine = MockEngine()
        result = build_advanced_diagnostics_panel(engine)

        expected_keys = {
            "panel",
            "profiler_html",
            "memory_html",
            "cpu_html",
            "errors_html",
            "auto_refresh_cb",
            "profiler_enable_cb",
            "refresh_btn",
            "refresh",
            "stop_refresh",
        }
        self.assertTrue(expected_keys.issubset(set(result.keys())))

    @patch("IPython.display.display")
    def test_none_engine_no_crash(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_advanced_diagnostics_panel,
        )

        result = build_advanced_diagnostics_panel(engine=None)
        self.assertIn("panel", result)

    @patch("IPython.display.display")
    def test_profiler_html_contains_table(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_advanced_diagnostics_panel,
        )

        engine = MockEngine()
        result = build_advanced_diagnostics_panel(engine)
        # Trigger refresh
        result["refresh"]()
        html = result["profiler_html"].value
        self.assertIn("capture", html)
        self.assertIn("analysis", html)
        self.assertIn("total_frame", html)

    @patch("IPython.display.display")
    def test_profiler_enable_toggle(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_advanced_diagnostics_panel,
        )

        engine = MockEngine()
        result = build_advanced_diagnostics_panel(engine)
        result["profiler_enable_cb"].value = False
        self.assertFalse(engine.profiler.enabled)
        result["profiler_enable_cb"].value = True
        self.assertTrue(engine.profiler.enabled)

    @patch("IPython.display.display")
    def test_refresh_callable(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_advanced_diagnostics_panel,
        )

        engine = MockEngine()
        result = build_advanced_diagnostics_panel(engine)
        # Should not raise
        result["refresh"]()
        self.assertTrue(callable(result["stop_refresh"]))


if __name__ == "__main__":
    unittest.main()
