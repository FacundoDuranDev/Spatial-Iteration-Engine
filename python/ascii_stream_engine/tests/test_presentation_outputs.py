"""Tests for Phase 4B: Output Manager Panel."""

import unittest
from unittest.mock import MagicMock, patch

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.tests import has_module


class MockSink:
    def __init__(self, name="MockSink"):
        self._name = name

    def is_open(self):
        return True


class MockEngine:
    def __init__(self):
        self._config = EngineConfig()
        self._sink = MockSink()
        self.is_running = False

    def get_config(self):
        return self._config

    def get_sink(self):
        return self._sink

    def set_sink(self, sink):
        self._sink = sink

    def stop(self):
        self.is_running = False

    def start(self):
        self.is_running = True


@unittest.skipUnless(has_module("ipywidgets"), "ipywidgets not available")
@unittest.skipUnless(has_module("IPython"), "IPython not available")
class TestOutputManagerPanel(unittest.TestCase):
    @patch("IPython.display.display")
    def test_returns_expected_keys(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_output_manager_panel,
        )

        engine = MockEngine()
        result = build_output_manager_panel(engine)

        expected_keys = {
            "panel",
            "current_sinks_html",
            "sink_type_dd",
            "sink_config",
            "add_sink_btn",
            "sink_controls",
            "refresh_btn",
            "status",
        }
        self.assertTrue(expected_keys.issubset(set(result.keys())))

    @patch("IPython.display.display")
    def test_none_engine_no_crash(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_output_manager_panel,
        )

        result = build_output_manager_panel(engine=None)
        self.assertIn("panel", result)

    @patch("IPython.display.display")
    def test_shows_current_sink(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_output_manager_panel,
        )

        engine = MockEngine()
        result = build_output_manager_panel(engine)
        html = result["current_sinks_html"].value
        self.assertIn("MockSink", html)

    @patch("IPython.display.display")
    def test_sink_type_dropdown_has_options(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_output_manager_panel,
        )

        result = build_output_manager_panel(MockEngine())
        dd = result["sink_type_dd"]
        self.assertIn("NotebookPreviewSink", dd.options)

    @patch("IPython.display.display")
    def test_all_imports_guarded(self, mock_display) -> None:
        """Output manager should not crash even if optional sinks are missing."""
        from ascii_stream_engine.presentation.notebook_api import (
            build_output_manager_panel,
        )

        result = build_output_manager_panel(MockEngine())
        self.assertIsNotNone(result["panel"])


if __name__ == "__main__":
    unittest.main()
