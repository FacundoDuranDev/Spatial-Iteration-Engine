"""Tests for Phase 7: Integration and Full Dashboard."""

import unittest
from unittest.mock import MagicMock, patch

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.tests import has_module


class MockAnalyzer:
    def __init__(self, name, enabled=False):
        self.name = name
        self.enabled = enabled
        self.confidence_threshold = 0.5


class MockAnalyzerPipeline:
    def __init__(self):
        self.analyzers = [
            MockAnalyzer("face"),
            MockAnalyzer("hands"),
            MockAnalyzer("pose"),
        ]

    def has_any(self):
        return True

    def set_enabled(self, name, enabled):
        for a in self.analyzers:
            if a.name == name:
                a.enabled = enabled


class MockFilterPipeline:
    def __init__(self):
        self.filters = []

    def replace(self, filters):
        self.filters = list(filters)


class MockProfiler:
    def __init__(self):
        self.enabled = False


class MockMetrics:
    def get_fps(self):
        return 0.0

    def get_errors(self):
        return {}

    def get_summary(self):
        return {
            "fps": 0.0,
            "frames_processed": 0,
            "total_errors": 0,
            "errors_by_component": {},
            "latency_avg": 0.0,
            "latency_min": 0.0,
            "latency_max": 0.0,
            "uptime": 0.0,
        }


class MockSink:
    def is_open(self):
        return False


class MockSource:
    def set_camera_index(self, idx):
        pass


class MockEngine:
    """Full mock engine with all public APIs the presentation layer uses."""

    def __init__(self):
        self._config = EngineConfig()
        self.analyzer_pipeline = MockAnalyzerPipeline()
        self.filter_pipeline = MockFilterPipeline()
        self.filters = []
        self.profiler = MockProfiler()
        self.metrics = MockMetrics()
        self.is_running = False
        self._sink = MockSink()
        self._source = MockSource()
        self._renderer = MagicMock()

    def get_config(self):
        return self._config

    def update_config(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self._config, k):
                setattr(self._config, k, v)

    def get_source(self):
        return self._source

    def get_sink(self):
        return self._sink

    def set_sink(self, s):
        self._sink = s

    def get_renderer(self):
        return self._renderer

    def set_renderer(self, r):
        self._renderer = r

    def get_last_analysis(self):
        return {}

    def get_profiling_stats(self):
        return {}

    def get_profiling_report(self):
        return ""

    def start(self, blocking=False):
        self.is_running = True

    def stop(self):
        self.is_running = False


@unittest.skipUnless(has_module("ipywidgets"), "ipywidgets not available")
@unittest.skipUnless(has_module("IPython"), "IPython not available")
class TestBuildFullDashboard(unittest.TestCase):
    @patch("IPython.display.display")
    def test_returns_all_top_level_keys(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_full_dashboard,
        )

        engine = MockEngine()
        result = build_full_dashboard(engine)

        expected_keys = {
            "tabs",
            "control",
            "diagnostics",
            "perception",
            "filters",
            "outputs",
            "performance",
            "presets",
        }
        self.assertEqual(expected_keys, set(result.keys()))

    @patch("IPython.display.display")
    def test_sub_panels_have_expected_keys(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_full_dashboard,
        )

        engine = MockEngine()
        result = build_full_dashboard(engine)

        # Diagnostics sub-panel
        self.assertIn("profiler_html", result["diagnostics"])
        self.assertIn("memory_html", result["diagnostics"])

        # Perception sub-panel
        self.assertIn("analyzers", result["perception"])
        self.assertIn("viz_mode", result["perception"])

        # Filters sub-panel
        self.assertIn("filter_cards", result["filters"])

        # Outputs sub-panel
        self.assertIn("current_sinks_html", result["outputs"])

        # Performance sub-panel
        self.assertIn("budget_chart_html", result["performance"])
        self.assertIn("fps_gauge_html", result["performance"])

        # Presets sub-panel
        self.assertIn("preset_dropdown", result["presets"])
        self.assertIn("save_btn", result["presets"])

    @patch("IPython.display.display")
    def test_none_engine_no_crash(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_full_dashboard,
        )

        result = build_full_dashboard(engine=None)
        self.assertIn("tabs", result)

    @patch("IPython.display.display")
    def test_tabs_widget_has_7_children(self, mock_display) -> None:
        import ipywidgets as widgets

        from ascii_stream_engine.presentation.notebook_api import (
            build_full_dashboard,
        )

        engine = MockEngine()
        result = build_full_dashboard(engine)
        tabs = result["tabs"]
        self.assertIsInstance(tabs, widgets.Tab)
        self.assertEqual(len(tabs.children), 7)

    @patch("IPython.display.display")
    def test_no_private_attribute_access(self, mock_display) -> None:
        """Verify we can build the dashboard using only public API."""
        from ascii_stream_engine.presentation.notebook_api import (
            build_full_dashboard,
        )

        engine = MockEngine()
        # If the code tried to access engine._private_attr, MockEngine
        # would not have it and it would raise AttributeError
        result = build_full_dashboard(engine)
        self.assertIsNotNone(result)


@unittest.skipUnless(has_module("ipywidgets"), "ipywidgets not available")
@unittest.skipUnless(has_module("IPython"), "IPython not available")
class TestNewPanelImports(unittest.TestCase):
    """Verify all new panel functions are importable."""

    def test_all_build_functions_importable(self) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_advanced_diagnostics_panel,
            build_filter_designer_panel,
            build_full_dashboard,
            build_output_manager_panel,
            build_perception_control_panel,
            build_performance_monitor_panel,
            build_preset_manager_panel,
        )

        # All should be callable
        for fn in [
            build_advanced_diagnostics_panel,
            build_perception_control_panel,
            build_filter_designer_panel,
            build_output_manager_panel,
            build_performance_monitor_panel,
            build_preset_manager_panel,
            build_full_dashboard,
        ]:
            self.assertTrue(callable(fn))


if __name__ == "__main__":
    unittest.main()
