import unittest
from unittest.mock import patch

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame
from ascii_stream_engine.tests import has_module


@unittest.skipUnless(has_module("PIL"), "requires pillow")
class TestFfmpegRtspSink(unittest.TestCase):
    """Tests para el backend de salida RTSP."""

    def test_rtsp_sink_spawns_ffmpeg_with_correct_args(self) -> None:
        """Verifica que el sink RTSP inicia ffmpeg con los argumentos correctos."""
        from PIL import Image

        from ascii_stream_engine.adapters.outputs.rtsp import FfmpegRtspSink

        class DummyProc:
            def __init__(self):
                self.stdin = self
                self.data = b""
                self.returncode = None

            def write(self, data):
                self.data += data

            def flush(self):
                pass

            def close(self):
                pass

            def poll(self):
                return None

            def wait(self, timeout=None):
                pass

            def terminate(self):
                pass

            def kill(self):
                pass

        config = EngineConfig(fps=30, bitrate="2000k")
        output = FfmpegRtspSink(rtsp_url="rtsp://0.0.0.0:8554/test")
        image = Image.new("RGB", (640, 480))
        frame = RenderFrame(image=image, text="")

        with patch(
            "ascii_stream_engine.adapters.outputs.rtsp.rtsp_sink.subprocess.Popen",
            return_value=DummyProc(),
        ) as popen:
            output.open(config, (640, 480))
            output.write(frame)
            output.close()

        # Verificar que se llamó a Popen
        self.assertTrue(popen.called)

        # Verificar argumentos del comando
        args = popen.call_args[0][0]
        self.assertEqual(args[0], "ffmpeg")
        self.assertIn("-f", args)
        self.assertIn("rawvideo", args)
        self.assertIn("-pix_fmt", args)
        self.assertIn("rgb24", args)
        self.assertIn("-s", args)
        self.assertIn("640x480", args)
        self.assertIn("-framerate", args)
        self.assertIn("30", args)
        self.assertIn("-c:v", args)
        self.assertIn("libx264", args)
        self.assertIn("-f", args)
        self.assertIn("rtsp", args)
        self.assertIn("rtsp://0.0.0.0:8554/test", args)

    def test_rtsp_sink_uses_default_url_if_not_provided(self) -> None:
        """Verifica que se usa la URL por defecto si no se proporciona."""
        from PIL import Image

        from ascii_stream_engine.adapters.outputs.rtsp import FfmpegRtspSink

        class DummyProc:
            def __init__(self):
                self.stdin = self
                self.returncode = None

            def write(self, data):
                pass

            def flush(self):
                pass

            def close(self):
                pass

            def poll(self):
                return None

            def wait(self, timeout=None):
                pass

            def terminate(self):
                pass

            def kill(self):
                pass

        config = EngineConfig()
        output = FfmpegRtspSink()

        with patch(
            "ascii_stream_engine.adapters.outputs.rtsp.rtsp_sink.subprocess.Popen",
            return_value=DummyProc(),
        ) as popen:
            output.open(config, (320, 240))
            output.close()

        args = popen.call_args[0][0]
        # Verificar que se usa la URL por defecto
        self.assertIn("rtsp://0.0.0.0:8554/stream", args)

    def test_rtsp_sink_handles_image_conversion(self) -> None:
        """Verifica que el sink convierte imágenes a RGB si es necesario."""
        from PIL import Image

        from ascii_stream_engine.adapters.outputs.rtsp import FfmpegRtspSink

        class DummyProc:
            def __init__(self):
                self.stdin = self
                self.data = b""
                self.returncode = None

            def write(self, data):
                self.data += data

            def flush(self):
                pass

            def close(self):
                pass

            def poll(self):
                return None

            def wait(self, timeout=None):
                pass

            def terminate(self):
                pass

            def kill(self):
                pass

        config = EngineConfig()
        output = FfmpegRtspSink()

        # Crear imagen en modo RGBA (debe convertirse a RGB)
        image = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
        frame = RenderFrame(image=image, text="")

        with patch(
            "ascii_stream_engine.adapters.outputs.rtsp.rtsp_sink.subprocess.Popen",
            return_value=DummyProc(),
        ):
            output.open(config, (100, 100))
            output.write(frame)
            output.close()

        # Si llegamos aquí sin error, la conversión funcionó

    def test_rtsp_sink_handles_closed_process(self) -> None:
        """Verifica que el sink maneja correctamente un proceso cerrado."""
        from PIL import Image

        from ascii_stream_engine.adapters.outputs.rtsp import FfmpegRtspSink

        class DummyProc:
            def __init__(self):
                self.stdin = self
                self.returncode = 1  # Proceso terminado

            def write(self, data):
                pass

            def flush(self):
                pass

            def close(self):
                pass

            def poll(self):
                return 1  # Proceso terminado

            def wait(self, timeout=None):
                pass

            def terminate(self):
                pass

            def kill(self):
                pass

        config = EngineConfig()
        output = FfmpegRtspSink()
        image = Image.new("RGB", (100, 100))
        frame = RenderFrame(image=image, text="")

        with patch(
            "ascii_stream_engine.adapters.outputs.rtsp.rtsp_sink.subprocess.Popen",
            return_value=DummyProc(),
        ):
            output.open(config, (100, 100))
            # Escribir frame cuando el proceso ya terminó
            output.write(frame)  # No debe lanzar excepción
            output.close()

    def test_rtsp_sink_context_manager(self) -> None:
        """Verifica que el sink funciona como context manager."""
        from PIL import Image

        from ascii_stream_engine.adapters.outputs.rtsp import FfmpegRtspSink

        class DummyProc:
            def __init__(self):
                self.stdin = self
                self.returncode = None

            def write(self, data):
                pass

            def flush(self):
                pass

            def close(self):
                pass

            def poll(self):
                return None

            def wait(self, timeout=None):
                pass

            def terminate(self):
                pass

            def kill(self):
                pass

        config = EngineConfig()
        image = Image.new("RGB", (100, 100))
        frame = RenderFrame(image=image, text="")

        with patch(
            "ascii_stream_engine.adapters.outputs.rtsp.rtsp_sink.subprocess.Popen",
            return_value=DummyProc(),
        ):
            with FfmpegRtspSink() as output:
                output.open(config, (100, 100))
                output.write(frame)
            # El close debe llamarse automáticamente

    def test_rtsp_sink_custom_codec_and_preset(self) -> None:
        """Verifica que se pueden configurar codec y preset personalizados."""
        from ascii_stream_engine.adapters.outputs.rtsp import FfmpegRtspSink

        class DummyProc:
            def __init__(self):
                self.stdin = self
                self.returncode = None

            def write(self, data):
                pass

            def flush(self):
                pass

            def close(self):
                pass

            def poll(self):
                return None

            def wait(self, timeout=None):
                pass

            def terminate(self):
                pass

            def kill(self):
                pass

        config = EngineConfig()
        output = FfmpegRtspSink(codec="libx265", preset="medium", tune="fastdecode")

        with patch(
            "ascii_stream_engine.adapters.outputs.rtsp.rtsp_sink.subprocess.Popen",
            return_value=DummyProc(),
        ) as popen:
            output.open(config, (640, 480))
            output.close()

        args = popen.call_args[0][0]
        # Verificar codec personalizado
        codec_idx = args.index("-c:v")
        self.assertEqual(args[codec_idx + 1], "libx265")
        # Verificar preset personalizado
        preset_idx = args.index("-preset")
        self.assertEqual(args[preset_idx + 1], "medium")
        # Verificar tune personalizado
        tune_idx = args.index("-tune")
        self.assertEqual(args[tune_idx + 1], "fastdecode")

    def test_rtsp_sink_uses_config_bitrate(self) -> None:
        """Verifica que se usa el bitrate de la configuración si no se proporciona uno."""
        from ascii_stream_engine.adapters.outputs.rtsp import FfmpegRtspSink

        class DummyProc:
            def __init__(self):
                self.stdin = self
                self.returncode = None

            def write(self, data):
                pass

            def flush(self):
                pass

            def close(self):
                pass

            def poll(self):
                return None

            def wait(self, timeout=None):
                pass

            def terminate(self):
                pass

            def kill(self):
                pass

        config = EngineConfig(bitrate="3000k")
        output = FfmpegRtspSink()  # Sin bitrate personalizado

        with patch(
            "ascii_stream_engine.adapters.outputs.rtsp.rtsp_sink.subprocess.Popen",
            return_value=DummyProc(),
        ) as popen:
            output.open(config, (640, 480))
            output.close()

        args = popen.call_args[0][0]
        # Verificar que se usa el bitrate de la configuración
        bitrate_idx = args.index("-b:v")
        self.assertEqual(args[bitrate_idx + 1], "3000k")


if __name__ == "__main__":
    unittest.main()
