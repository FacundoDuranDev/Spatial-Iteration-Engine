"""Tests for the RTSP output sink."""

import unittest
from unittest.mock import patch

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame
from ascii_stream_engine.ports.output_capabilities import OutputCapability
from ascii_stream_engine.tests import has_module
from ascii_stream_engine.tests.helpers import DummyProc


@unittest.skipUnless(has_module("PIL"), "requires pillow")
class TestFfmpegRtspSink(unittest.TestCase):
    """Tests for the RTSP streaming output sink."""

    def _get_sink_class(self):
        from ascii_stream_engine.adapters.outputs.rtsp import FfmpegRtspSink

        return FfmpegRtspSink

    def _make_frame(self, size=(640, 480)):
        from PIL import Image

        image = Image.new("RGB", size)
        return RenderFrame(image=image, text="")

    def test_rtsp_sink_spawns_ffmpeg_with_correct_args(self) -> None:
        """Verify that the RTSP sink starts ffmpeg with correct arguments."""
        FfmpegRtspSink = self._get_sink_class()
        config = EngineConfig(fps=30, bitrate="2000k")
        output = FfmpegRtspSink(rtsp_url="rtsp://0.0.0.0:8554/test")
        frame = self._make_frame()

        with patch(
            "ascii_stream_engine.adapters.outputs.rtsp.rtsp_sink.subprocess.Popen",
            return_value=DummyProc(),
        ) as popen:
            output.open(config, (640, 480))
            output.write(frame)
            output.close()

        self.assertTrue(popen.called)
        args = popen.call_args[0][0]
        self.assertEqual(args[0], "ffmpeg")
        self.assertIn("rawvideo", args)
        self.assertIn("rgb24", args)
        self.assertIn("640x480", args)
        self.assertIn("30", args)
        self.assertIn("libx264", args)
        self.assertIn("rtsp", args)
        self.assertIn("rtsp://0.0.0.0:8554/test", args)

    def test_rtsp_sink_uses_default_url_if_not_provided(self) -> None:
        """Verify that the default URL is used if none is provided."""
        FfmpegRtspSink = self._get_sink_class()
        config = EngineConfig()
        output = FfmpegRtspSink()

        with patch(
            "ascii_stream_engine.adapters.outputs.rtsp.rtsp_sink.subprocess.Popen",
            return_value=DummyProc(),
        ) as popen:
            output.open(config, (320, 240))
            output.close()

        args = popen.call_args[0][0]
        self.assertIn("rtsp://0.0.0.0:8554/stream", args)

    def test_rtsp_sink_handles_image_conversion(self) -> None:
        """Verify that RGBA images are converted to RGB."""
        from PIL import Image

        FfmpegRtspSink = self._get_sink_class()
        config = EngineConfig()
        output = FfmpegRtspSink()

        image = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
        frame = RenderFrame(image=image, text="")

        with patch(
            "ascii_stream_engine.adapters.outputs.rtsp.rtsp_sink.subprocess.Popen",
            return_value=DummyProc(),
        ):
            output.open(config, (100, 100))
            output.write(frame)
            output.close()

    def test_rtsp_sink_is_open_lifecycle(self) -> None:
        """Verify is_open() returns correct values through lifecycle."""
        FfmpegRtspSink = self._get_sink_class()
        config = EngineConfig()
        output = FfmpegRtspSink()

        self.assertFalse(output.is_open())

        with patch(
            "ascii_stream_engine.adapters.outputs.rtsp.rtsp_sink.subprocess.Popen",
            return_value=DummyProc(),
        ):
            output.open(config, (640, 480))
            self.assertTrue(output.is_open())

        output.close()
        self.assertFalse(output.is_open())

    def test_rtsp_sink_capabilities(self) -> None:
        """Verify correct capability flags, protocol name, latency."""
        FfmpegRtspSink = self._get_sink_class()
        output = FfmpegRtspSink()
        caps = output.get_capabilities()

        self.assertTrue(caps.has_capability(OutputCapability.STREAMING))
        self.assertTrue(caps.has_capability(OutputCapability.RTSP))
        self.assertTrue(caps.has_capability(OutputCapability.TCP))
        self.assertTrue(caps.has_capability(OutputCapability.LOW_LATENCY))
        self.assertTrue(caps.has_capability(OutputCapability.CUSTOM_BITRATE))
        self.assertTrue(caps.has_capability(OutputCapability.MULTI_CLIENT))
        self.assertEqual(caps.protocol_name, "RTSP/H.264")

    def test_rtsp_sink_close_idempotent(self) -> None:
        """close() can be called multiple times safely."""
        FfmpegRtspSink = self._get_sink_class()
        config = EngineConfig()
        output = FfmpegRtspSink()

        with patch(
            "ascii_stream_engine.adapters.outputs.rtsp.rtsp_sink.subprocess.Popen",
            return_value=DummyProc(),
        ):
            output.open(config, (640, 480))

        output.close()
        output.close()  # Must not raise

    def test_rtsp_sink_close_without_open(self) -> None:
        """close() on a never-opened sink is safe."""
        FfmpegRtspSink = self._get_sink_class()
        output = FfmpegRtspSink()
        output.close()  # Must not raise

    def test_rtsp_sink_write_when_closed(self) -> None:
        """write() on a closed sink is a no-op."""
        FfmpegRtspSink = self._get_sink_class()
        output = FfmpegRtspSink()
        frame = self._make_frame()
        output.write(frame)  # Must not raise

    def test_rtsp_sink_open_closes_previous(self) -> None:
        """Opening again closes previous connection first."""
        FfmpegRtspSink = self._get_sink_class()
        config = EngineConfig()
        output = FfmpegRtspSink()

        with patch(
            "ascii_stream_engine.adapters.outputs.rtsp.rtsp_sink.subprocess.Popen",
            return_value=DummyProc(),
        ):
            output.open(config, (640, 480))
            output.open(config, (320, 240))  # Must not leak resources
            self.assertTrue(output.is_open())

        output.close()

    def test_rtsp_sink_supports_multiple_clients(self) -> None:
        """Verify supports_multiple_clients() returns True."""
        FfmpegRtspSink = self._get_sink_class()
        output = FfmpegRtspSink()
        self.assertTrue(output.supports_multiple_clients())

    def test_rtsp_sink_context_manager(self) -> None:
        """Verify the sink works as a context manager."""
        FfmpegRtspSink = self._get_sink_class()
        config = EngineConfig()
        frame = self._make_frame((100, 100))

        with patch(
            "ascii_stream_engine.adapters.outputs.rtsp.rtsp_sink.subprocess.Popen",
            return_value=DummyProc(),
        ):
            with FfmpegRtspSink() as output:
                output.open(config, (100, 100))
                output.write(frame)

    def test_rtsp_sink_custom_codec_and_preset(self) -> None:
        """Verify custom codec and preset are passed to ffmpeg."""
        FfmpegRtspSink = self._get_sink_class()
        config = EngineConfig()
        output = FfmpegRtspSink(codec="libx265", preset="medium", tune="fastdecode")

        with patch(
            "ascii_stream_engine.adapters.outputs.rtsp.rtsp_sink.subprocess.Popen",
            return_value=DummyProc(),
        ) as popen:
            output.open(config, (640, 480))
            output.close()

        args = popen.call_args[0][0]
        codec_idx = args.index("-c:v")
        self.assertEqual(args[codec_idx + 1], "libx265")
        preset_idx = args.index("-preset")
        self.assertEqual(args[preset_idx + 1], "medium")
        tune_idx = args.index("-tune")
        self.assertEqual(args[tune_idx + 1], "fastdecode")

    def test_rtsp_sink_uses_config_bitrate(self) -> None:
        """Verify config bitrate is used when no custom bitrate is set."""
        FfmpegRtspSink = self._get_sink_class()
        config = EngineConfig(bitrate="3000k")
        output = FfmpegRtspSink()

        with patch(
            "ascii_stream_engine.adapters.outputs.rtsp.rtsp_sink.subprocess.Popen",
            return_value=DummyProc(),
        ) as popen:
            output.open(config, (640, 480))
            output.close()

        args = popen.call_args[0][0]
        bitrate_idx = args.index("-b:v")
        self.assertEqual(args[bitrate_idx + 1], "3000k")


if __name__ == "__main__":
    unittest.main()
