import unittest

from ascii_stream_engine.tests import has_module


@unittest.skipUnless(
    has_module("cv2") and has_module("numpy") and has_module("PIL"),
    "requires cv2, numpy, pillow",
)
class TestAsciiRenderer(unittest.TestCase):
    def test_render_ascii(self) -> None:
        import numpy as np

        from ascii_stream_engine.domain.config import EngineConfig
        from ascii_stream_engine.adapters.renderers.ascii import AsciiRenderer

        config = EngineConfig(grid_w=12, grid_h=10, charset="@.")
        renderer = AsciiRenderer()
        frame = np.zeros((24, 48), dtype=np.uint8)
        result = renderer.render(frame, config)

        self.assertEqual(len(result.lines), config.grid_h)
        self.assertEqual(len(result.lines[0]), config.grid_w)
        self.assertIn("\n", result.text)

    def test_render_raw(self) -> None:
        import numpy as np

        from ascii_stream_engine.domain.config import EngineConfig
        from ascii_stream_engine.adapters.renderers.ascii import AsciiRenderer

        config = EngineConfig(render_mode="raw", raw_width=20, raw_height=10)
        renderer = AsciiRenderer()
        frame = np.zeros((10, 20, 3), dtype=np.uint8)
        result = renderer.render(frame, config)

        self.assertIsNone(result.text)
        self.assertIsNone(result.lines)
        self.assertEqual(result.image.size, (20, 10))


if __name__ == "__main__":
    unittest.main()
