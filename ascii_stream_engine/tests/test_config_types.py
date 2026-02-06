import unittest

from ascii_stream_engine.domain.config import ConfigValidationError, EngineConfig
from ascii_stream_engine.domain.types import RenderFrame


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

    def test_config_validation_fps(self) -> None:
        """Verifica validación de fps."""
        # FPS válido
        config = EngineConfig(fps=30)
        self.assertEqual(config.fps, 30)

        # FPS fuera de rango (muy bajo)
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(fps=0)
        self.assertIn("fps", str(cm.exception).lower())

        # FPS fuera de rango (muy alto)
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(fps=200)
        self.assertIn("fps", str(cm.exception).lower())

    def test_config_validation_grid(self) -> None:
        """Verifica validación de grid_w y grid_h."""
        # Grid válido
        config = EngineConfig(grid_w=100, grid_h=50)
        self.assertEqual(config.grid_w, 100)
        self.assertEqual(config.grid_h, 50)

        # grid_w muy pequeño
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(grid_w=5)
        self.assertIn("grid_w", str(cm.exception).lower())

        # grid_h muy grande
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(grid_h=2000)
        self.assertIn("grid_h", str(cm.exception).lower())

    def test_config_validation_charset(self) -> None:
        """Verifica validación de charset."""
        # Charset válido
        config = EngineConfig(charset=" .:-=+*#%@")
        self.assertEqual(config.charset, " .:-=+*#%@")

        # Charset vacío
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(charset="")
        self.assertIn("charset", str(cm.exception).lower())

        # Charset muy corto
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(charset="a")
        self.assertIn("charset", str(cm.exception).lower())

    def test_config_validation_render_mode(self) -> None:
        """Verifica validación de render_mode."""
        # Modos válidos
        config_ascii = EngineConfig(render_mode="ascii")
        self.assertEqual(config_ascii.render_mode, "ascii")

        config_raw = EngineConfig(render_mode="raw")
        self.assertEqual(config_raw.render_mode, "raw")

        # Modo inválido
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(render_mode="invalid")
        self.assertIn("render_mode", str(cm.exception).lower())

    def test_config_validation_raw_dimensions(self) -> None:
        """Verifica validación de raw_width y raw_height."""
        # Dimensiones válidas
        config = EngineConfig(render_mode="raw", raw_width=1920, raw_height=1080)
        self.assertEqual(config.raw_width, 1920)
        self.assertEqual(config.raw_height, 1080)

        # raw_width muy pequeño
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(render_mode="raw", raw_width=5)
        self.assertIn("raw_width", str(cm.exception).lower())

        # raw_height muy grande
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(render_mode="raw", raw_height=20000)
        self.assertIn("raw_height", str(cm.exception).lower())

    def test_config_validation_contrast(self) -> None:
        """Verifica validación de contrast."""
        # Contrast válido
        config = EngineConfig(contrast=1.5)
        self.assertEqual(config.contrast, 1.5)

        # Contrast muy bajo
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(contrast=0.05)
        self.assertIn("contrast", str(cm.exception).lower())

        # Contrast muy alto
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(contrast=10.0)
        self.assertIn("contrast", str(cm.exception).lower())

    def test_config_validation_brightness(self) -> None:
        """Verifica validación de brightness."""
        # Brightness válido
        config = EngineConfig(brightness=50)
        self.assertEqual(config.brightness, 50)

        # Brightness fuera de rango (muy bajo)
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(brightness=-300)
        self.assertIn("brightness", str(cm.exception).lower())

        # Brightness fuera de rango (muy alto)
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(brightness=300)
        self.assertIn("brightness", str(cm.exception).lower())

    def test_config_validation_host(self) -> None:
        """Verifica validación de host."""
        # Hosts válidos
        valid_hosts = ["127.0.0.1", "192.168.1.1", "localhost", "example.com"]
        for host in valid_hosts:
            config = EngineConfig(host=host)
            self.assertEqual(config.host, host)

        # Host inválido
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(host="invalid..host")
        self.assertIn("host", str(cm.exception).lower())

    def test_config_validation_port(self) -> None:
        """Verifica validación de port."""
        # Puerto válido
        config = EngineConfig(port=8080)
        self.assertEqual(config.port, 8080)

        # Puerto fuera de rango (muy bajo)
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(port=0)
        self.assertIn("port", str(cm.exception).lower())

        # Puerto fuera de rango (muy alto)
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(port=70000)
        self.assertIn("port", str(cm.exception).lower())

    def test_config_validation_pkt_size(self) -> None:
        """Verifica validación de pkt_size."""
        # pkt_size válido
        config = EngineConfig(pkt_size=1500)
        self.assertEqual(config.pkt_size, 1500)

        # pkt_size muy pequeño
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(pkt_size=100)
        self.assertIn("pkt_size", str(cm.exception).lower())

        # pkt_size muy grande
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(pkt_size=70000)
        self.assertIn("pkt_size", str(cm.exception).lower())

    def test_config_validation_bitrate(self) -> None:
        """Verifica validación de bitrate."""
        # Bitrates válidos
        valid_bitrates = ["1500k", "2m", "1000", "500K", "1M"]
        for bitrate in valid_bitrates:
            config = EngineConfig(bitrate=bitrate)
            self.assertEqual(config.bitrate, bitrate)

        # Bitrate inválido (formato incorrecto)
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(bitrate="invalid")
        self.assertIn("bitrate", str(cm.exception).lower())

    def test_config_validation_frame_buffer_size(self) -> None:
        """Verifica validación de frame_buffer_size."""
        # frame_buffer_size válido (0 para deshabilitado)
        config = EngineConfig(frame_buffer_size=0)
        self.assertEqual(config.frame_buffer_size, 0)

        # frame_buffer_size válido (positivo)
        config = EngineConfig(frame_buffer_size=10)
        self.assertEqual(config.frame_buffer_size, 10)

        # frame_buffer_size inválido (negativo)
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(frame_buffer_size=-1)
        self.assertIn("frame_buffer_size", str(cm.exception).lower())

    def test_config_validation_sleep_on_empty(self) -> None:
        """Verifica validación de sleep_on_empty."""
        # sleep_on_empty válido
        config = EngineConfig(sleep_on_empty=0.1)
        self.assertEqual(config.sleep_on_empty, 0.1)

        # sleep_on_empty inválido (cero o negativo)
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(sleep_on_empty=0)
        self.assertIn("sleep_on_empty", str(cm.exception).lower())

        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(sleep_on_empty=-0.1)
        self.assertIn("sleep_on_empty", str(cm.exception).lower())

    def test_config_validation_multiple_errors(self) -> None:
        """Verifica que se reportan múltiples errores."""
        with self.assertRaises(ConfigValidationError) as cm:
            EngineConfig(fps=200, grid_w=5, port=70000)
        error_msg = str(cm.exception).lower()
        self.assertIn("fps", error_msg)
        self.assertIn("grid_w", error_msg)
        self.assertIn("port", error_msg)


if __name__ == "__main__":
    unittest.main()
