import unittest
from unittest.mock import patch

from ascii_stream_engine.core.config import EngineConfig
from ascii_stream_engine.tests import has_module


class DummyFilterPipeline:
    def __init__(self):
        self.filters = []

    def replace(self, filters):
        self.filters = list(filters)


class DummySource:
    def __init__(self):
        self.camera_index = 0

    def set_camera_index(self, index: int) -> None:
        self.camera_index = index


class DummyEngine:
    def __init__(self):
        self._config = EngineConfig()
        self.filters = []
        self.filter_pipeline = DummyFilterPipeline()
        self._source = DummySource()
        self.is_running = False

    def get_config(self):
        return self._config

    def update_config(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self._config, key, value)

    def get_source(self):
        return self._source

    def start(self):
        self.is_running = True

    def stop(self):
        self.is_running = False


class TestNotebookControl(unittest.TestCase):
    def test_build_control_panel_imports(self) -> None:
        from ascii_stream_engine.control.notebook_api import build_control_panel

        engine = DummyEngine()

        if not has_module("ipywidgets"):
            with self.assertRaises(ImportError):
                build_control_panel(engine)
            return

        if not has_module("IPython"):
            with self.assertRaises(ImportError):
                build_control_panel(engine)
            return

        with patch("IPython.display.display") as _:
            panel = build_control_panel(engine)
        self.assertIn("config", panel)
        self.assertIn("filters", panel)

    def test_build_general_control_panel_imports(self) -> None:
        from ascii_stream_engine.control.notebook_api import build_general_control_panel

        engine = DummyEngine()

        if not has_module("ipywidgets"):
            with self.assertRaises(ImportError):
                build_general_control_panel(engine)
            return

        if not has_module("IPython"):
            with self.assertRaises(ImportError):
                build_general_control_panel(engine)
            return

        with patch("IPython.display.display") as _:
            panel = build_general_control_panel(engine)
        self.assertIn("tabs", panel)
        self.assertIn("network", panel)
        self.assertIn("engine", panel)
        self.assertIn("filters", panel)
        self.assertIn("ascii", panel)


if __name__ == "__main__":
    unittest.main()
