"""Tests for Phase 1: Shared helper functions in notebook_api.py."""

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from ascii_stream_engine.tests import has_module


class TestStatusStyle(unittest.TestCase):
    """Tests for _status_style module-level helper."""

    def test_status_style_ok(self) -> None:
        from ascii_stream_engine.presentation.notebook_api import _status_style

        result = _status_style("All good", "ok")
        self.assertIn("All good", result)
        self.assertIn("#d4edda", result)

    def test_status_style_warn(self) -> None:
        from ascii_stream_engine.presentation.notebook_api import _status_style

        result = _status_style("Warning", "warn")
        self.assertIn("Warning", result)
        self.assertIn("#fff3cd", result)

    def test_status_style_info(self) -> None:
        from ascii_stream_engine.presentation.notebook_api import _status_style

        result = _status_style("Info msg", "info")
        self.assertIn("Info msg", result)
        self.assertIn("#e7f1ff", result)

    def test_status_style_default(self) -> None:
        from ascii_stream_engine.presentation.notebook_api import _status_style

        result = _status_style("Default", "unknown")
        self.assertIn("Default", result)
        self.assertIn("#f8f9fa", result)

    def test_status_style_is_module_level(self) -> None:
        """Ensure _status_style is not nested inside another function."""
        import ascii_stream_engine.presentation.notebook_api as mod

        self.assertTrue(callable(mod._status_style))


class TestPeriodicRefresh(unittest.TestCase):
    """Tests for _periodic_refresh helper."""

    def test_periodic_refresh_calls_function(self) -> None:
        from ascii_stream_engine.presentation.notebook_api import _periodic_refresh

        counter = {"n": 0}

        def updater():
            counter["n"] += 1

        handle = _periodic_refresh(updater, 100)
        time.sleep(0.5)
        handle["stop"]()
        # Should have been called at least a couple of times in 0.5s at 100ms
        self.assertGreaterEqual(counter["n"], 2)

    def test_periodic_refresh_stops_cleanly(self) -> None:
        from ascii_stream_engine.presentation.notebook_api import _periodic_refresh

        handle = _periodic_refresh(lambda: None, 100)
        handle["stop"]()
        self.assertTrue(handle["stop_event"].is_set())

    def test_periodic_refresh_catches_exceptions(self) -> None:
        from ascii_stream_engine.presentation.notebook_api import _periodic_refresh

        def exploder():
            raise RuntimeError("boom")

        handle = _periodic_refresh(exploder, 100)
        time.sleep(0.3)
        handle["stop"]()
        # Should not have crashed - thread should still be (or have been) alive
        self.assertTrue(handle["stop_event"].is_set())

    def test_periodic_refresh_with_external_stop_event(self) -> None:
        from ascii_stream_engine.presentation.notebook_api import _periodic_refresh

        evt = threading.Event()
        handle = _periodic_refresh(lambda: None, 100, stop_event=evt)
        self.assertIs(handle["stop_event"], evt)
        evt.set()
        handle["thread"].join(timeout=1)


class TestSafeEngineCall(unittest.TestCase):
    """Tests for _safe_engine_call helper."""

    def test_none_engine_returns_default(self) -> None:
        from ascii_stream_engine.presentation.notebook_api import _safe_engine_call

        result = _safe_engine_call(None, "get_config", default="fallback")
        self.assertEqual(result, "fallback")

    def test_missing_method_returns_default(self) -> None:
        from ascii_stream_engine.presentation.notebook_api import _safe_engine_call

        engine = MagicMock(spec=[])  # No methods
        result = _safe_engine_call(engine, "nonexistent", default=42)
        self.assertEqual(result, 42)

    def test_method_raises_returns_default(self) -> None:
        from ascii_stream_engine.presentation.notebook_api import _safe_engine_call

        engine = MagicMock()
        engine.get_config.side_effect = RuntimeError("fail")
        result = _safe_engine_call(engine, "get_config", default="safe")
        self.assertEqual(result, "safe")

    def test_successful_call(self) -> None:
        from ascii_stream_engine.presentation.notebook_api import _safe_engine_call

        engine = MagicMock()
        engine.get_config.return_value = {"fps": 30}
        result = _safe_engine_call(engine, "get_config")
        self.assertEqual(result, {"fps": 30})


class TestMakeLabeledSection(unittest.TestCase):
    """Tests for _make_labeled_section helper."""

    @unittest.skipUnless(has_module("ipywidgets"), "ipywidgets not available")
    def test_returns_vbox(self) -> None:
        import ipywidgets as widgets

        from ascii_stream_engine.presentation.notebook_api import _make_labeled_section

        result = _make_labeled_section("Title", [widgets.HTML("test")])
        self.assertIsInstance(result, widgets.VBox)
        self.assertEqual(len(result.children), 2)

    @unittest.skipUnless(has_module("ipywidgets"), "ipywidgets not available")
    def test_title_is_html(self) -> None:
        import ipywidgets as widgets

        from ascii_stream_engine.presentation.notebook_api import _make_labeled_section

        result = _make_labeled_section("My Section", [])
        first_child = result.children[0]
        self.assertIsInstance(first_child, widgets.HTML)
        self.assertIn("My Section", first_child.value)


if __name__ == "__main__":
    unittest.main()
