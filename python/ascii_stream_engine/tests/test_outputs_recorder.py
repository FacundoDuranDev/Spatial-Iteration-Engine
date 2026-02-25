"""Tests for the video recorder output sink."""

import unittest
from unittest.mock import patch

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame
from ascii_stream_engine.ports.output_capabilities import OutputCapability
from ascii_stream_engine.tests import has_module
from ascii_stream_engine.tests.helpers import DummyProc


@unittest.skipUnless(has_module("PIL"), "requires pillow")
class TestVideoRecorderSink(unittest.TestCase):
    """Tests for the VideoRecorderSink."""

    def _get_sink_class(self):
        from ascii_stream_engine.adapters.outputs.recorder import VideoRecorderSink

        return VideoRecorderSink

    def _make_frame(self, size=(640, 480)):
        from PIL import Image

        image = Image.new("RGB", size)
        return RenderFrame(image=image, text="")

    def test_recorder_sink_lifecycle(self) -> None:
        """open/write/close with DummyProc."""
        VideoRecorderSink = self._get_sink_class()
        config = EngineConfig()
        sink = VideoRecorderSink(output_path="test_output.mp4")

        self.assertFalse(sink.is_open())

        with patch(
            "ascii_stream_engine.adapters.outputs.recorder.video_recorder_sink" ".subprocess.Popen",
            return_value=DummyProc(),
        ):
            sink.open(config, (640, 480))
            self.assertTrue(sink.is_open())

            frame = self._make_frame()
            sink.write(frame)

        sink.close()
        self.assertFalse(sink.is_open())

    def test_recorder_sink_close_idempotent(self) -> None:
        """Double close is safe."""
        VideoRecorderSink = self._get_sink_class()
        config = EngineConfig()
        sink = VideoRecorderSink()

        with patch(
            "ascii_stream_engine.adapters.outputs.recorder.video_recorder_sink" ".subprocess.Popen",
            return_value=DummyProc(),
        ):
            sink.open(config, (640, 480))

        sink.close()
        sink.close()  # Must not raise

    def test_recorder_sink_close_without_open(self) -> None:
        """close() on a never-opened sink is safe."""
        VideoRecorderSink = self._get_sink_class()
        sink = VideoRecorderSink()
        sink.close()  # Must not raise

    def test_recorder_sink_write_when_closed(self) -> None:
        """No-op, no exception."""
        VideoRecorderSink = self._get_sink_class()
        sink = VideoRecorderSink()
        frame = self._make_frame()
        sink.write(frame)  # Must not raise

    def test_recorder_sink_capabilities(self) -> None:
        """Verify RECORDING flag, protocol name."""
        VideoRecorderSink = self._get_sink_class()
        sink = VideoRecorderSink()
        caps = sink.get_capabilities()

        self.assertTrue(caps.has_capability(OutputCapability.RECORDING))
        self.assertTrue(caps.has_capability(OutputCapability.HIGH_QUALITY))
        self.assertTrue(caps.has_capability(OutputCapability.CUSTOM_BITRATE))
        self.assertFalse(caps.has_capability(OutputCapability.STREAMING))
        self.assertEqual(caps.protocol_name, "File (Video)")
        self.assertEqual(caps.max_clients, 1)

    def test_recorder_sink_spawns_ffmpeg_with_correct_args(self) -> None:
        """Verify ffmpeg command includes codec, bitrate, output path."""
        VideoRecorderSink = self._get_sink_class()
        config = EngineConfig(fps=30)
        sink = VideoRecorderSink(
            output_path="recording.mp4",
            codec="libx264",
            bitrate="3000k",
            preset="fast",
        )

        with patch(
            "ascii_stream_engine.adapters.outputs.recorder.video_recorder_sink" ".subprocess.Popen",
            return_value=DummyProc(),
        ) as popen:
            sink.open(config, (1920, 1080))
            sink.close()

        args = popen.call_args[0][0]
        self.assertEqual(args[0], "ffmpeg")
        self.assertIn("rawvideo", args)
        self.assertIn("rgb24", args)
        self.assertIn("1920x1080", args)
        self.assertIn("30", args)
        self.assertIn("libx264", args)
        self.assertIn("3000k", args)
        self.assertIn("fast", args)
        self.assertIn("recording.mp4", args)

    def test_recorder_sink_detects_mp4_format(self) -> None:
        """Verify .mp4 extension maps to mp4 format."""
        VideoRecorderSink = self._get_sink_class()
        config = EngineConfig()
        sink = VideoRecorderSink(output_path="video.mp4")

        with patch(
            "ascii_stream_engine.adapters.outputs.recorder.video_recorder_sink" ".subprocess.Popen",
            return_value=DummyProc(),
        ) as popen:
            sink.open(config, (640, 480))
            sink.close()

        args = popen.call_args[0][0]
        # Find the -f flag for output format
        f_indices = [i for i, a in enumerate(args) if a == "-f"]
        # The second -f is the output format (first is rawvideo input)
        output_format = args[f_indices[1] + 1]
        self.assertEqual(output_format, "mp4")

    def test_recorder_sink_detects_avi_format(self) -> None:
        """Verify .avi extension maps to avi format."""
        VideoRecorderSink = self._get_sink_class()
        config = EngineConfig()
        sink = VideoRecorderSink(output_path="video.avi")

        with patch(
            "ascii_stream_engine.adapters.outputs.recorder.video_recorder_sink" ".subprocess.Popen",
            return_value=DummyProc(),
        ) as popen:
            sink.open(config, (640, 480))
            sink.close()

        args = popen.call_args[0][0]
        f_indices = [i for i, a in enumerate(args) if a == "-f"]
        output_format = args[f_indices[1] + 1]
        self.assertEqual(output_format, "avi")

    def test_recorder_sink_detects_mkv_format(self) -> None:
        """Verify .mkv extension maps to matroska format."""
        VideoRecorderSink = self._get_sink_class()
        config = EngineConfig()
        sink = VideoRecorderSink(output_path="video.mkv")

        with patch(
            "ascii_stream_engine.adapters.outputs.recorder.video_recorder_sink" ".subprocess.Popen",
            return_value=DummyProc(),
        ) as popen:
            sink.open(config, (640, 480))
            sink.close()

        args = popen.call_args[0][0]
        f_indices = [i for i, a in enumerate(args) if a == "-f"]
        output_format = args[f_indices[1] + 1]
        self.assertEqual(output_format, "matroska")

    def test_recorder_sink_custom_codec(self) -> None:
        """Verify custom codec is passed to ffmpeg."""
        VideoRecorderSink = self._get_sink_class()
        config = EngineConfig()
        sink = VideoRecorderSink(codec="libx265")

        with patch(
            "ascii_stream_engine.adapters.outputs.recorder.video_recorder_sink" ".subprocess.Popen",
            return_value=DummyProc(),
        ) as popen:
            sink.open(config, (640, 480))
            sink.close()

        args = popen.call_args[0][0]
        codec_idx = args.index("-c:v")
        self.assertEqual(args[codec_idx + 1], "libx265")

    def test_recorder_sink_open_closes_previous(self) -> None:
        """Re-open is safe."""
        VideoRecorderSink = self._get_sink_class()
        config = EngineConfig()
        sink = VideoRecorderSink()

        with patch(
            "ascii_stream_engine.adapters.outputs.recorder.video_recorder_sink" ".subprocess.Popen",
            return_value=DummyProc(),
        ):
            sink.open(config, (640, 480))
            sink.open(config, (320, 240))  # Must not leak resources
            self.assertTrue(sink.is_open())

        sink.close()

    def test_recorder_sink_handles_image_conversion(self) -> None:
        """RGBA images are converted to RGB."""
        from PIL import Image

        VideoRecorderSink = self._get_sink_class()
        config = EngineConfig()
        sink = VideoRecorderSink()

        image = Image.new("RGBA", (640, 480), (255, 0, 0, 128))
        frame = RenderFrame(image=image, text="")

        with patch(
            "ascii_stream_engine.adapters.outputs.recorder.video_recorder_sink" ".subprocess.Popen",
            return_value=DummyProc(),
        ):
            sink.open(config, (640, 480))
            sink.write(frame)  # Must not raise
            sink.close()

    def test_recorder_sink_supports_multiple_clients(self) -> None:
        """Returns False for file-based recording."""
        VideoRecorderSink = self._get_sink_class()
        sink = VideoRecorderSink()
        self.assertFalse(sink.supports_multiple_clients())

    def test_recorder_sink_context_manager(self) -> None:
        """Verify the sink works as a context manager."""
        VideoRecorderSink = self._get_sink_class()
        config = EngineConfig()
        frame = self._make_frame()

        with patch(
            "ascii_stream_engine.adapters.outputs.recorder.video_recorder_sink" ".subprocess.Popen",
            return_value=DummyProc(),
        ):
            with VideoRecorderSink() as sink:
                sink.open(config, (640, 480))
                sink.write(frame)

    def test_recorder_sink_webm_uses_libvpx(self) -> None:
        """Verify .webm format uses libvpx codec by default."""
        VideoRecorderSink = self._get_sink_class()
        config = EngineConfig()
        sink = VideoRecorderSink(output_path="video.webm")

        with patch(
            "ascii_stream_engine.adapters.outputs.recorder.video_recorder_sink" ".subprocess.Popen",
            return_value=DummyProc(),
        ) as popen:
            sink.open(config, (640, 480))
            sink.close()

        args = popen.call_args[0][0]
        codec_idx = args.index("-c:v")
        self.assertEqual(args[codec_idx + 1], "libvpx")


if __name__ == "__main__":
    unittest.main()
