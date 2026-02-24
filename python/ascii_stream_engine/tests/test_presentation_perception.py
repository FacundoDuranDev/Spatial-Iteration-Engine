"""Tests for Phase 3: Perception Control Panel."""

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
    def __init__(self, analyzers=None):
        self.analyzers = analyzers or []

    def has_any(self):
        return len(self.analyzers) > 0

    def set_enabled(self, name, enabled):
        for a in self.analyzers:
            if a.name == name:
                a.enabled = enabled


class MockEngine:
    def __init__(self, with_analyzers=True):
        self._config = EngineConfig()
        self.is_running = False
        if with_analyzers:
            self.analyzer_pipeline = MockAnalyzerPipeline(
                [
                    MockAnalyzer("face"),
                    MockAnalyzer("hands"),
                    MockAnalyzer("pose"),
                ]
            )
        else:
            self.analyzer_pipeline = MockAnalyzerPipeline([])

    def get_config(self):
        return self._config

    def get_last_analysis(self):
        return {}

    def get_renderer(self):
        return MagicMock()

    def set_renderer(self, r):
        pass

    def stop(self):
        self.is_running = False

    def start(self):
        self.is_running = True


@unittest.skipUnless(has_module("ipywidgets"), "ipywidgets not available")
@unittest.skipUnless(has_module("IPython"), "IPython not available")
class TestPerceptionControlPanel(unittest.TestCase):
    @patch("IPython.display.display")
    def test_returns_expected_keys(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_perception_control_panel,
        )

        engine = MockEngine()
        result = build_perception_control_panel(engine)

        expected_keys = {
            "panel",
            "analyzers",
            "model_info_html",
            "viz_mode",
            "analysis_html",
            "refresh_btn",
            "apply_viz_btn",
            "status",
        }
        self.assertTrue(expected_keys.issubset(set(result.keys())))

    @patch("IPython.display.display")
    def test_analyzer_widgets_present(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_perception_control_panel,
        )

        engine = MockEngine()
        result = build_perception_control_panel(engine)
        analyzers = result["analyzers"]
        for name in ("face", "hands", "pose"):
            self.assertIn(name, analyzers)
            self.assertIn("enabled_cb", analyzers[name])
            self.assertIn("confidence", analyzers[name])
            self.assertIn("status_html", analyzers[name])

    @patch("IPython.display.display")
    def test_no_pipeline_no_crash(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_perception_control_panel,
        )

        engine = MockEngine(with_analyzers=False)
        result = build_perception_control_panel(engine)
        self.assertIn("panel", result)

    @patch("IPython.display.display")
    def test_none_engine_no_crash(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_perception_control_panel,
        )

        result = build_perception_control_panel(engine=None)
        self.assertIn("panel", result)

    @patch("IPython.display.display")
    def test_toggle_enables_analyzer(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_perception_control_panel,
        )

        engine = MockEngine()
        result = build_perception_control_panel(engine)
        # Enable face
        result["analyzers"]["face"]["enabled_cb"].value = True
        face_analyzer = engine.analyzer_pipeline.analyzers[0]
        self.assertTrue(face_analyzer.enabled)

    @patch("IPython.display.display")
    def test_confidence_disabled_when_no_attr(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_perception_control_panel,
        )

        # Remove confidence_threshold from analyzers
        engine = MockEngine()
        for a in engine.analyzer_pipeline.analyzers:
            if hasattr(a, "confidence_threshold"):
                delattr(a, "confidence_threshold")
        result = build_perception_control_panel(engine)
        # All confidence sliders should be disabled
        for name in ("face", "hands", "pose"):
            self.assertTrue(result["analyzers"][name]["confidence"].disabled)


if __name__ == "__main__":
    unittest.main()
