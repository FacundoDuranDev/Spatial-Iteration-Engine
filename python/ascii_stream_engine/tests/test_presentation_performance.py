"""Tests for Phase 5: Performance Monitor Panel."""

import unittest
from unittest.mock import patch

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.tests import has_module


class MockProfiler:
    def __init__(self):
        self.enabled = True


class MockMetrics:
    def get_fps(self):
        return 28.0


class MockEngine:
    def __init__(self):
        self._config = EngineConfig()
        self.profiler = MockProfiler()
        self.metrics = MockMetrics()
        self.is_running = True

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
                "total_time": 1.2,
                "avg_time": 0.012,
                "min_time": 0.008,
                "max_time": 0.020,
                "std_dev": 0.003,
            },
            "transformation": {
                "count": 100,
                "total_time": 0.10,
                "avg_time": 0.001,
                "min_time": 0.0005,
                "max_time": 0.002,
                "std_dev": 0.0003,
            },
            "filtering": {
                "count": 100,
                "total_time": 0.30,
                "avg_time": 0.003,
                "min_time": 0.001,
                "max_time": 0.006,
                "std_dev": 0.001,
            },
            "rendering": {
                "count": 100,
                "total_time": 0.20,
                "avg_time": 0.002,
                "min_time": 0.001,
                "max_time": 0.004,
                "std_dev": 0.0005,
            },
            "writing": {
                "count": 100,
                "total_time": 0.15,
                "avg_time": 0.0015,
                "min_time": 0.001,
                "max_time": 0.003,
                "std_dev": 0.0005,
            },
            "total_frame": {
                "count": 100,
                "total_time": 2.8,
                "avg_time": 0.028,
                "min_time": 0.020,
                "max_time": 0.045,
                "std_dev": 0.005,
            },
        }


@unittest.skipUnless(has_module("ipywidgets"), "ipywidgets not available")
@unittest.skipUnless(has_module("IPython"), "IPython not available")
class TestPerformanceMonitorPanel(unittest.TestCase):
    @patch("IPython.display.display")
    def test_returns_expected_keys(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_performance_monitor_panel,
        )

        engine = MockEngine()
        result = build_performance_monitor_panel(engine)

        expected_keys = {
            "panel",
            "budget_chart_html",
            "fps_gauge_html",
            "degradation_html",
            "histogram_output",
            "bottleneck_html",
            "auto_refresh_cb",
            "refresh_btn",
            "refresh",
            "stop_refresh",
            "status",
        }
        self.assertTrue(expected_keys.issubset(set(result.keys())))

    @patch("IPython.display.display")
    def test_none_engine_no_crash(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_performance_monitor_panel,
        )

        result = build_performance_monitor_panel(engine=None)
        self.assertIn("panel", result)

    @patch("IPython.display.display")
    def test_budget_chart_has_stages(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_performance_monitor_panel,
        )

        engine = MockEngine()
        result = build_performance_monitor_panel(engine)
        result["refresh"]()
        html = result["budget_chart_html"].value
        self.assertIn("capture", html)
        self.assertIn("analysis", html)
        self.assertIn("total_frame", html)

    @patch("IPython.display.display")
    def test_fps_gauge_shows_values(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_performance_monitor_panel,
        )

        engine = MockEngine()
        result = build_performance_monitor_panel(engine)
        result["refresh"]()
        html = result["fps_gauge_html"].value
        self.assertIn("28.0", html)
        self.assertIn("20", html)  # target FPS from config

    @patch("IPython.display.display")
    def test_degradation_within_budget(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_performance_monitor_panel,
        )

        engine = MockEngine()
        result = build_performance_monitor_panel(engine)
        result["refresh"]()
        html = result["degradation_html"].value
        # Our mock is within budget (28ms < 33.3ms)
        self.assertIn("within budget", html)

    @patch("IPython.display.display")
    def test_bottleneck_identifies_stage(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_performance_monitor_panel,
        )

        engine = MockEngine()
        result = build_performance_monitor_panel(engine)
        result["refresh"]()
        html = result["bottleneck_html"].value
        # analysis should be the bottleneck (12ms out of 28ms)
        self.assertIn("analysis", html)

    @patch("IPython.display.display")
    def test_profiler_disabled_message(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_performance_monitor_panel,
        )

        engine = MockEngine()
        engine.profiler.enabled = False
        # Return empty stats when profiler is disabled
        engine.get_profiling_stats = lambda: {}
        result = build_performance_monitor_panel(engine)
        result["refresh"]()
        html = result["budget_chart_html"].value
        self.assertIn("Enable profiler", html)

    @patch("IPython.display.display")
    def test_auto_refresh_toggle(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_performance_monitor_panel,
        )

        engine = MockEngine()
        result = build_performance_monitor_panel(engine)
        result["auto_refresh_cb"].value = True
        # Stop it immediately
        result["stop_refresh"]()
        self.assertFalse(result["auto_refresh_cb"].value)


if __name__ == "__main__":
    unittest.main()
