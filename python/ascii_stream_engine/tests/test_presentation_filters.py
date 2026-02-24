"""Tests for Phase 4A: Filter Designer Panel."""

import unittest
from unittest.mock import MagicMock, patch

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.tests import has_module


class MockFilterPipeline:
    def __init__(self):
        self.filters = []

    def replace(self, filters):
        self.filters = list(filters)


class MockEngine:
    def __init__(self):
        self._config = EngineConfig()
        self.filter_pipeline = MockFilterPipeline()
        self.is_running = False

    def get_config(self):
        return self._config


class FakeEdgeFilter:
    name = "Edges"

    def __init__(self, low=60, high=120):
        self.low_threshold = low
        self.high_threshold = high

    def apply(self, frame, analysis=None):
        return frame


class FakeBrightnessFilter:
    name = "Brightness/Contrast"

    def __init__(self):
        self.alpha = 1.0
        self.beta = 0

    def apply(self, frame, analysis=None):
        return frame


@unittest.skipUnless(has_module("ipywidgets"), "ipywidgets not available")
@unittest.skipUnless(has_module("IPython"), "IPython not available")
class TestFilterDesignerPanel(unittest.TestCase):
    @patch("IPython.display.display")
    def test_returns_expected_keys(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_filter_designer_panel,
        )

        engine = MockEngine()
        filters = {
            "Edges": FakeEdgeFilter(),
            "Brightness/Contrast": FakeBrightnessFilter(),
        }
        result = build_filter_designer_panel(engine, filters)

        expected_keys = {
            "panel",
            "filter_cards",
            "active_summary_html",
            "clear_all_btn",
            "status",
        }
        self.assertTrue(expected_keys.issubset(set(result.keys())))

    @patch("IPython.display.display")
    def test_filter_cards_present(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_filter_designer_panel,
        )

        filters = {
            "Edges": FakeEdgeFilter(),
            "Brightness/Contrast": FakeBrightnessFilter(),
        }
        result = build_filter_designer_panel(MockEngine(), filters)
        self.assertIn("Edges", result["filter_cards"])
        self.assertIn("Brightness/Contrast", result["filter_cards"])

    @patch("IPython.display.display")
    def test_edge_filter_has_sliders(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_filter_designer_panel,
        )

        filters = {"Edges": FakeEdgeFilter()}
        result = build_filter_designer_panel(MockEngine(), filters)
        edge_card = result["filter_cards"]["Edges"]
        self.assertIn("low_threshold", edge_card["params"])
        self.assertIn("high_threshold", edge_card["params"])

    @patch("IPython.display.display")
    def test_enable_checkbox_applies_filter(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_filter_designer_panel,
        )

        engine = MockEngine()
        edge = FakeEdgeFilter()
        filters = {"Edges": edge}
        result = build_filter_designer_panel(engine, filters)
        result["filter_cards"]["Edges"]["enabled_cb"].value = True
        self.assertEqual(len(engine.filter_pipeline.filters), 1)
        self.assertIs(engine.filter_pipeline.filters[0], edge)

    @patch("IPython.display.display")
    def test_clear_all_disables_filters(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_filter_designer_panel,
        )

        engine = MockEngine()
        filters = {"Edges": FakeEdgeFilter()}
        result = build_filter_designer_panel(engine, filters)
        result["filter_cards"]["Edges"]["enabled_cb"].value = True
        result["clear_all_btn"].click()
        self.assertFalse(result["filter_cards"]["Edges"]["enabled_cb"].value)

    @patch("IPython.display.display")
    def test_slider_changes_filter_param(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_filter_designer_panel,
        )

        edge = FakeEdgeFilter()
        filters = {"Edges": edge}
        result = build_filter_designer_panel(MockEngine(), filters)
        # Change slider
        result["filter_cards"]["Edges"]["params"]["low_threshold"].value = 100
        self.assertEqual(edge.low_threshold, 100)

    @patch("IPython.display.display")
    def test_none_engine_no_crash(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_filter_designer_panel,
        )

        result = build_filter_designer_panel(engine=None, filters={"Edges": FakeEdgeFilter()})
        self.assertIn("panel", result)


if __name__ == "__main__":
    unittest.main()
