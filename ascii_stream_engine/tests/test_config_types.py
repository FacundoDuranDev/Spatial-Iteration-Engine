import unittest

from ascii_stream_engine.core.config import EngineConfig
from ascii_stream_engine.core.types import RenderFrame


class TestConfigAndTypes(unittest.TestCase):
    def test_engine_config_defaults(self) -> None:
        config = EngineConfig()
        self.assertEqual(config.fps, 20)
        self.assertEqual(config.grid_w, 120)
        self.assertEqual(config.grid_h, 60)
        self.assertEqual(config.charset, " .:-=+*#%@")
        self.assertEqual(config.render_mode, "ascii")
        self.assertIsNone(config.raw_width)
        self.assertIsNone(config.raw_height)
        self.assertEqual(config.invert, False)
        self.assertEqual(config.contrast, 1.2)
        self.assertEqual(config.brightness, 0)
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 1234)
        self.assertEqual(config.pkt_size, 1316)
        self.assertEqual(config.bitrate, "1500k")
        self.assertEqual(config.udp_broadcast, False)
        self.assertEqual(config.frame_buffer_size, 2)
        self.assertEqual(config.sleep_on_empty, 0.01)

    def test_render_frame_defaults(self) -> None:
        image = object()
        frame = RenderFrame(image=image)
        self.assertIs(frame.image, image)
        self.assertIsNone(frame.text)
        self.assertIsNone(frame.lines)
        self.assertIsNone(frame.metadata)


if __name__ == "__main__":
    unittest.main()
