"""Tests for Phase 6: Preset Manager Panel."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.tests import has_module


class MockAnalyzer:
    def __init__(self, name, enabled=False):
        self.name = name
        self.enabled = enabled


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


class MockEngine:
    def __init__(self):
        self._config = EngineConfig()
        self.analyzer_pipeline = MockAnalyzerPipeline()
        self.filter_pipeline = MockFilterPipeline()
        self.is_running = False
        self._renderer = MagicMock()

    def get_config(self):
        return self._config

    def update_config(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self._config, k, v)

    def get_renderer(self):
        return self._renderer

    def set_renderer(self, r):
        self._renderer = r

    def stop(self):
        self.is_running = False

    def start(self):
        self.is_running = True


@unittest.skipUnless(has_module("ipywidgets"), "ipywidgets not available")
@unittest.skipUnless(has_module("IPython"), "IPython not available")
class TestPresetManagerPanel(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.presets_path = Path(self.tmpdir) / "test_presets.json"

    @patch("IPython.display.display")
    def test_returns_expected_keys(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_preset_manager_panel,
        )

        engine = MockEngine()
        result = build_preset_manager_panel(engine, presets_path=self.presets_path)

        expected_keys = {
            "panel",
            "preset_name_input",
            "save_btn",
            "preset_dropdown",
            "load_btn",
            "delete_btn",
            "preset_list_html",
            "import_export_textarea",
            "import_btn",
            "export_btn",
            "status",
        }
        self.assertTrue(expected_keys.issubset(set(result.keys())))

    @patch("IPython.display.display")
    def test_save_creates_json(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_preset_manager_panel,
        )

        engine = MockEngine()
        result = build_preset_manager_panel(engine, presets_path=self.presets_path)
        result["preset_name_input"].value = "test_preset"
        result["save_btn"].click()

        self.assertTrue(self.presets_path.exists())
        data = json.loads(self.presets_path.read_text())
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "test_preset")
        self.assertIn("config", data[0])
        self.assertIn("filters", data[0])
        self.assertIn("analyzers", data[0])
        self.assertIn("renderer", data[0])
        self.assertIn("created", data[0])

    @patch("IPython.display.display")
    def test_load_applies_config(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_preset_manager_panel,
        )

        engine = MockEngine()
        # Pre-seed a preset
        preset_data = [
            {
                "name": "fast",
                "created": "2024-01-01T00:00:00",
                "config": {"fps": 60, "grid_w": 80, "grid_h": 40},
                "filters": [],
                "analyzers": {"face": True, "hands": False, "pose": False},
                "renderer": "ascii",
            }
        ]
        self.presets_path.parent.mkdir(parents=True, exist_ok=True)
        self.presets_path.write_text(json.dumps(preset_data))

        result = build_preset_manager_panel(engine, presets_path=self.presets_path)
        result["preset_dropdown"].value = "fast"
        result["load_btn"].click()

        self.assertEqual(engine._config.fps, 60)
        self.assertTrue(engine.analyzer_pipeline.analyzers[0].enabled)  # face

    @patch("IPython.display.display")
    def test_delete_removes_preset(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_preset_manager_panel,
        )

        engine = MockEngine()
        preset_data = [
            {
                "name": "to_delete",
                "created": "2024-01-01T00:00:00",
                "config": {},
                "filters": [],
                "analyzers": {},
                "renderer": "ascii",
            }
        ]
        self.presets_path.parent.mkdir(parents=True, exist_ok=True)
        self.presets_path.write_text(json.dumps(preset_data))

        result = build_preset_manager_panel(engine, presets_path=self.presets_path)
        result["preset_dropdown"].value = "to_delete"
        result["delete_btn"].click()

        data = json.loads(self.presets_path.read_text())
        self.assertEqual(len(data), 0)

    @patch("IPython.display.display")
    def test_export_import_roundtrip(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_preset_manager_panel,
        )

        engine = MockEngine()
        result = build_preset_manager_panel(engine, presets_path=self.presets_path)

        # Save a preset
        result["preset_name_input"].value = "roundtrip"
        result["save_btn"].click()

        # Export
        result["export_btn"].click()
        exported = result["import_export_textarea"].value
        self.assertTrue(len(exported) > 0)

        # Delete all
        result["preset_dropdown"].value = "roundtrip"
        result["delete_btn"].click()

        # Import
        result["import_export_textarea"].value = exported
        result["import_btn"].click()

        data = json.loads(self.presets_path.read_text())
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "roundtrip")

    @patch("IPython.display.display")
    def test_none_engine_no_crash(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_preset_manager_panel,
        )

        result = build_preset_manager_panel(engine=None, presets_path=self.presets_path)
        self.assertIn("panel", result)

    @patch("IPython.display.display")
    def test_save_disabled_without_engine(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_preset_manager_panel,
        )

        result = build_preset_manager_panel(engine=None, presets_path=self.presets_path)
        result["preset_name_input"].value = "test"
        result["save_btn"].click()
        # Should show warning, not crash. The warning status uses #fff3cd background.
        self.assertIn("#fff3cd", result["status"].value)

    @patch("IPython.display.display")
    def test_corrupt_json_does_not_crash(self, mock_display) -> None:
        from ascii_stream_engine.presentation.notebook_api import (
            build_preset_manager_panel,
        )

        self.presets_path.parent.mkdir(parents=True, exist_ok=True)
        self.presets_path.write_text("NOT JSON{{")
        result = build_preset_manager_panel(MockEngine(), presets_path=self.presets_path)
        self.assertIn("panel", result)


if __name__ == "__main__":
    unittest.main()
