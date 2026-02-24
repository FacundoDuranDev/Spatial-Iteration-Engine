"""Tests for the NDI output sink."""

import unittest
from unittest.mock import MagicMock, patch

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame
from ascii_stream_engine.ports.output_capabilities import OutputCapability


class TestNdiOutputSink(unittest.TestCase):
    """Tests for the NDI output sink."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.config = EngineConfig(fps=30)
        self.output_size = (640, 480)

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", False)
    def test_ndi_unavailable_raises_error(self) -> None:
        """Verify ImportError is raised when NDI is not available."""
        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        with self.assertRaises(ImportError):
            NdiOutputSink()

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_initialization(self, mock_ndi: MagicMock) -> None:
        """Verify NDI output initializes correctly."""
        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        mock_ndi.initialize.return_value = True
        mock_ndi.send_create.return_value = MagicMock()
        mock_ndi.LibNDISendCreate = MagicMock
        mock_ndi.VideoFrameV2 = MagicMock
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        output = NdiOutputSink(source_name="Test Source")
        self.assertEqual(output._source_name, "Test Source")
        self.assertFalse(output.is_open())

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_open(self, mock_ndi: MagicMock) -> None:
        """Verify NDI output opens correctly."""
        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        mock_ndi.initialize.return_value = True
        mock_sender = MagicMock()
        mock_ndi.send_create.return_value = mock_sender
        mock_ndi.LibNDISendCreate = MagicMock
        mock_ndi.VideoFrameV2 = MagicMock
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        output = NdiOutputSink()
        output.open(self.config, self.output_size)

        mock_ndi.initialize.assert_called_once()
        mock_ndi.send_create.assert_called_once()
        self.assertTrue(output.is_open())
        self.assertEqual(output._output_size, self.output_size)

        output.close()

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_write_frame(self, mock_ndi: MagicMock) -> None:
        """Verify frame sending works."""
        from PIL import Image

        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        mock_ndi.initialize.return_value = True
        mock_sender = MagicMock()
        mock_ndi.send_create.return_value = mock_sender
        mock_ndi.LibNDISendCreate = MagicMock
        mock_video_frame = MagicMock()
        mock_video_frame.p_data = bytearray(640 * 480 * 4)
        mock_ndi.VideoFrameV2 = lambda: mock_video_frame
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_send_video_v2 = MagicMock()
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        output = NdiOutputSink()
        output.open(self.config, self.output_size)

        image = Image.new("RGB", (640, 480), color=(255, 0, 0))
        frame = RenderFrame(image=image, text="test")
        output.write(frame)

        mock_ndi.send_send_video_v2.assert_called_once()
        output.close()

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_close(self, mock_ndi: MagicMock) -> None:
        """Verify NDI output closes and cleans up."""
        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        mock_ndi.initialize.return_value = True
        mock_sender = MagicMock()
        mock_ndi.send_create.return_value = mock_sender
        mock_ndi.LibNDISendCreate = MagicMock
        mock_ndi.VideoFrameV2 = MagicMock
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        output = NdiOutputSink()
        output.open(self.config, self.output_size)
        output.close()

        mock_ndi.send_destroy.assert_called_once_with(mock_sender)
        self.assertFalse(output.is_open())
        self.assertIsNone(output._ndi_send)

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_close_idempotent(self, mock_ndi: MagicMock) -> None:
        """close() can be called multiple times safely."""
        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        mock_ndi.initialize.return_value = True
        mock_sender = MagicMock()
        mock_ndi.send_create.return_value = mock_sender
        mock_ndi.LibNDISendCreate = MagicMock
        mock_ndi.VideoFrameV2 = MagicMock
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        output = NdiOutputSink()
        output.open(self.config, self.output_size)
        output.close()
        output.close()  # Must not raise

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_close_without_open(self, mock_ndi: MagicMock) -> None:
        """close() on a never-opened sink is safe."""
        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        mock_ndi.initialize.return_value = True
        mock_ndi.send_create.return_value = MagicMock()
        mock_ndi.LibNDISendCreate = MagicMock
        mock_ndi.VideoFrameV2 = MagicMock
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        output = NdiOutputSink()
        output.close()  # Must not raise

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_write_when_closed(self, mock_ndi: MagicMock) -> None:
        """write() on a closed sink is a no-op."""
        from PIL import Image

        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        mock_ndi.initialize.return_value = True
        mock_ndi.send_create.return_value = MagicMock()
        mock_ndi.LibNDISendCreate = MagicMock
        mock_ndi.VideoFrameV2 = MagicMock
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_send_video_v2 = MagicMock()
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        output = NdiOutputSink()
        image = Image.new("RGB", (640, 480))
        frame = RenderFrame(image=image, text="test")
        output.write(frame)  # Must not raise

        mock_ndi.send_send_video_v2.assert_not_called()

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_capabilities(self, mock_ndi: MagicMock) -> None:
        """Verify flags include NDI, STREAMING, MULTI_CLIENT."""
        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        mock_ndi.initialize.return_value = True
        mock_ndi.send_create.return_value = MagicMock()
        mock_ndi.LibNDISendCreate = MagicMock
        mock_ndi.VideoFrameV2 = MagicMock
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        output = NdiOutputSink()
        caps = output.get_capabilities()

        self.assertTrue(caps.has_capability(OutputCapability.STREAMING))
        self.assertTrue(caps.has_capability(OutputCapability.NDI))
        self.assertTrue(caps.has_capability(OutputCapability.MULTI_CLIENT))
        self.assertTrue(caps.has_capability(OutputCapability.LOW_LATENCY))
        self.assertTrue(caps.has_capability(OutputCapability.HIGH_QUALITY))
        self.assertEqual(caps.protocol_name, "NDI")
        self.assertEqual(caps.estimated_latency_ms, 10.0)

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_estimated_latency(self, mock_ndi: MagicMock) -> None:
        """Returns 10.0."""
        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        mock_ndi.initialize.return_value = True
        mock_ndi.send_create.return_value = MagicMock()
        mock_ndi.LibNDISendCreate = MagicMock
        mock_ndi.VideoFrameV2 = MagicMock
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        output = NdiOutputSink()
        self.assertEqual(output.get_estimated_latency_ms(), 10.0)

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_supports_multiple_clients(self, mock_ndi: MagicMock) -> None:
        """Returns True."""
        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        mock_ndi.initialize.return_value = True
        mock_ndi.send_create.return_value = MagicMock()
        mock_ndi.LibNDISendCreate = MagicMock
        mock_ndi.VideoFrameV2 = MagicMock
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        output = NdiOutputSink()
        self.assertTrue(output.supports_multiple_clients())

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_context_manager(self, mock_ndi: MagicMock) -> None:
        """Verify 'with NdiOutputSink() as sink:' works."""
        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        mock_ndi.initialize.return_value = True
        mock_ndi.send_create.return_value = MagicMock()
        mock_ndi.LibNDISendCreate = MagicMock
        mock_ndi.VideoFrameV2 = MagicMock
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        with NdiOutputSink() as output:
            output.open(self.config, self.output_size)
            self.assertTrue(output.is_open())

        # After exiting context, close() was called
        self.assertFalse(output.is_open())

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_open_closes_previous(self, mock_ndi: MagicMock) -> None:
        """Re-open calls close first."""
        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        mock_ndi.initialize.return_value = True
        mock_sender = MagicMock()
        mock_ndi.send_create.return_value = mock_sender
        mock_ndi.LibNDISendCreate = MagicMock
        mock_ndi.VideoFrameV2 = MagicMock
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        output = NdiOutputSink()
        output.open(self.config, self.output_size)
        output.open(self.config, (320, 240))  # Must not leak resources
        self.assertTrue(output.is_open())
        output.close()

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_handles_rgba_image(self, mock_ndi: MagicMock) -> None:
        """RGBA images are handled without error."""
        from PIL import Image

        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        mock_ndi.initialize.return_value = True
        mock_sender = MagicMock()
        mock_ndi.send_create.return_value = mock_sender
        mock_ndi.LibNDISendCreate = MagicMock
        mock_video_frame = MagicMock()
        mock_video_frame.p_data = bytearray(640 * 480 * 4)
        mock_ndi.VideoFrameV2 = lambda: mock_video_frame
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_send_video_v2 = MagicMock()
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        output = NdiOutputSink()
        output.open(self.config, self.output_size)

        rgba_image = Image.new("RGBA", (640, 480), (255, 0, 0, 128))
        frame = RenderFrame(image=rgba_image, text="test")
        output.write(frame)  # Must not raise

        mock_ndi.send_send_video_v2.assert_called_once()
        output.close()

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_custom_source_name(self, mock_ndi: MagicMock) -> None:
        """Verify custom source name is used."""
        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        mock_ndi.initialize.return_value = True
        mock_sender = MagicMock()
        mock_ndi.send_create.return_value = mock_sender
        mock_ndi.LibNDISendCreate = MagicMock
        mock_ndi.VideoFrameV2 = MagicMock
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        custom_name = "Custom NDI Source"
        output = NdiOutputSink(source_name=custom_name)
        self.assertEqual(output._source_name, custom_name)

        output.open(self.config, self.output_size)
        call_args = mock_ndi.send_create.call_args[0][0]
        self.assertEqual(call_args.ndi_name, custom_name)
        output.close()

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_resize_frame(self, mock_ndi: MagicMock) -> None:
        """Verify automatic frame resizing."""
        from PIL import Image

        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        mock_ndi.initialize.return_value = True
        mock_sender = MagicMock()
        mock_ndi.send_create.return_value = mock_sender
        mock_ndi.LibNDISendCreate = MagicMock
        mock_video_frame = MagicMock()
        mock_video_frame.p_data = bytearray(320 * 240 * 4)
        mock_ndi.VideoFrameV2 = lambda: mock_video_frame
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_send_video_v2 = MagicMock()
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        output = NdiOutputSink()
        output.open(self.config, (320, 240))

        # Create frame with different size
        image = Image.new("RGB", (640, 480), color=(0, 255, 0))
        frame = RenderFrame(image=image, text="test")
        output.write(frame)

        mock_ndi.send_send_video_v2.assert_called_once()
        output.close()


if __name__ == "__main__":
    unittest.main()
