"""Tests for the OSC output sink."""

import unittest
from unittest.mock import MagicMock, patch

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame
from ascii_stream_engine.ports.output_capabilities import OutputCapability
from ascii_stream_engine.tests import has_module


@unittest.skipUnless(has_module("pythonosc"), "requires python-osc")
class TestOscOutputSink(unittest.TestCase):
    """Tests for OscOutputSink."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        from PIL import Image

        self.config = EngineConfig(fps=30)
        self.output_size = (640, 480)
        self.test_image = Image.new("RGB", (640, 480), color=(255, 0, 0))

    def _get_sink_class(self):
        from ascii_stream_engine.adapters.outputs.osc import OscOutputSink

        return OscOutputSink

    def test_osc_sink_lifecycle(self) -> None:
        """Open/write/close cycle works."""
        OscOutputSink = self._get_sink_class()
        sink = OscOutputSink()

        self.assertFalse(sink.is_open())

        sink.open(self.config, self.output_size)
        self.assertTrue(sink.is_open())

        frame = RenderFrame(image=self.test_image)
        sink.write(frame)

        sink.close()
        self.assertFalse(sink.is_open())

    def test_osc_sink_close_idempotent(self) -> None:
        """Double close is safe."""
        OscOutputSink = self._get_sink_class()
        sink = OscOutputSink()

        sink.open(self.config, self.output_size)
        sink.close()
        sink.close()  # Must not raise

    def test_osc_sink_close_without_open(self) -> None:
        """close() on a never-opened sink is safe."""
        OscOutputSink = self._get_sink_class()
        sink = OscOutputSink()
        sink.close()  # Must not raise

    def test_osc_sink_write_when_closed(self) -> None:
        """No-op, no exception when writing to closed sink."""
        OscOutputSink = self._get_sink_class()
        sink = OscOutputSink()

        frame = RenderFrame(image=self.test_image)
        sink.write(frame)  # Must not raise

    def test_osc_sink_capabilities(self) -> None:
        """Verify flags, protocol name."""
        OscOutputSink = self._get_sink_class()
        sink = OscOutputSink()
        caps = sink.get_capabilities()

        self.assertTrue(caps.has_capability(OutputCapability.STREAMING))
        self.assertTrue(caps.has_capability(OutputCapability.UDP))
        self.assertTrue(caps.has_capability(OutputCapability.LOW_LATENCY))
        self.assertTrue(caps.has_capability(OutputCapability.ULTRA_LOW_LATENCY))
        self.assertEqual(caps.protocol_name, "OSC/UDP")
        self.assertEqual(caps.estimated_latency_ms, 1.0)

    def test_osc_sink_sends_frame_info(self) -> None:
        """Verify frame size and index are sent."""
        OscOutputSink = self._get_sink_class()
        sink = OscOutputSink()
        sink.open(self.config, self.output_size)

        # Mock the client
        mock_client = MagicMock()
        sink._client = mock_client

        frame = RenderFrame(image=self.test_image)
        sink.write(frame)

        # Verify send_message was called with frame size and index
        calls = mock_client.send_message.call_args_list
        addresses = [c[0][0] for c in calls]
        self.assertIn("/spatial/frame/size", addresses)
        self.assertIn("/spatial/frame/index", addresses)

        # Verify frame size values
        for call in calls:
            if call[0][0] == "/spatial/frame/size":
                self.assertEqual(call[0][1], [640, 480])
            if call[0][0] == "/spatial/frame/index":
                self.assertEqual(call[0][1], 0)

        sink.close()

    def test_osc_sink_sends_analysis_data(self) -> None:
        """Verify face/hands/pose data is sent when available in metadata."""
        import numpy as np

        OscOutputSink = self._get_sink_class()
        sink = OscOutputSink()
        sink.open(self.config, self.output_size)

        mock_client = MagicMock()
        sink._client = mock_client

        analysis = {
            "face": {"points": np.array([[0.1, 0.2], [0.3, 0.4]])},
            "hands": {
                "left": np.array([[0.5, 0.6]]),
                "right": np.array([[0.7, 0.8]]),
            },
            "pose": {"joints": np.array([[0.1, 0.2, 0.3]])},
        }
        frame = RenderFrame(
            image=self.test_image, metadata={"analysis": analysis}
        )
        sink.write(frame)

        calls = mock_client.send_message.call_args_list
        addresses = [c[0][0] for c in calls]

        self.assertIn("/spatial/analysis/face/points", addresses)
        self.assertIn("/spatial/analysis/hands/left", addresses)
        self.assertIn("/spatial/analysis/hands/right", addresses)
        self.assertIn("/spatial/analysis/pose/joints", addresses)

        # Verify face points are flat floats
        for call in calls:
            if call[0][0] == "/spatial/analysis/face/points":
                self.assertEqual(call[0][1], [0.1, 0.2, 0.3, 0.4])

        sink.close()

    def test_osc_sink_handles_missing_analysis(self) -> None:
        """No error when metadata has no analysis."""
        OscOutputSink = self._get_sink_class()
        sink = OscOutputSink()
        sink.open(self.config, self.output_size)

        mock_client = MagicMock()
        sink._client = mock_client

        # No metadata at all
        frame1 = RenderFrame(image=self.test_image)
        sink.write(frame1)  # Must not raise

        # Metadata without analysis
        frame2 = RenderFrame(image=self.test_image, metadata={"fps": 30})
        sink.write(frame2)  # Must not raise

        # Metadata with empty analysis
        frame3 = RenderFrame(
            image=self.test_image, metadata={"analysis": {}}
        )
        sink.write(frame3)  # Must not raise

        sink.close()

    def test_osc_sink_open_closes_previous(self) -> None:
        """Re-open is safe."""
        OscOutputSink = self._get_sink_class()
        sink = OscOutputSink()

        sink.open(self.config, self.output_size)
        self.assertTrue(sink.is_open())

        sink.open(self.config, (320, 240))
        self.assertTrue(sink.is_open())

        sink.close()

    def test_osc_sink_estimated_latency(self) -> None:
        """Returns 1.0."""
        OscOutputSink = self._get_sink_class()
        sink = OscOutputSink()
        self.assertEqual(sink.get_estimated_latency_ms(), 1.0)

    def test_osc_sink_supports_multiple_clients(self) -> None:
        """Returns True."""
        OscOutputSink = self._get_sink_class()
        sink = OscOutputSink()
        self.assertTrue(sink.supports_multiple_clients())

    def test_osc_sink_custom_prefix(self) -> None:
        """Verify custom address prefix is used."""
        OscOutputSink = self._get_sink_class()
        sink = OscOutputSink(address_prefix="/custom")
        sink.open(self.config, self.output_size)

        mock_client = MagicMock()
        sink._client = mock_client

        frame = RenderFrame(image=self.test_image)
        sink.write(frame)

        calls = mock_client.send_message.call_args_list
        for call in calls:
            self.assertTrue(
                call[0][0].startswith("/custom/"),
                f"Address {call[0][0]} does not start with /custom/",
            )

        sink.close()

    def test_osc_sink_sends_metadata_values(self) -> None:
        """Verify metadata key/value pairs are sent."""
        OscOutputSink = self._get_sink_class()
        sink = OscOutputSink()
        sink.open(self.config, self.output_size)

        mock_client = MagicMock()
        sink._client = mock_client

        frame = RenderFrame(
            image=self.test_image,
            metadata={"fps": 30, "active_filters": "brightness"},
        )
        sink.write(frame)

        calls = mock_client.send_message.call_args_list
        addresses = [c[0][0] for c in calls]

        self.assertIn("/spatial/metadata/fps", addresses)
        self.assertIn("/spatial/metadata/active_filters", addresses)

        sink.close()

    def test_osc_sink_frame_counter_increments(self) -> None:
        """Verify frame counter increments with each write."""
        OscOutputSink = self._get_sink_class()
        sink = OscOutputSink()
        sink.open(self.config, self.output_size)

        mock_client = MagicMock()
        sink._client = mock_client

        frame = RenderFrame(image=self.test_image)
        sink.write(frame)
        sink.write(frame)

        # Find the frame index messages
        index_values = []
        for call in mock_client.send_message.call_args_list:
            if call[0][0] == "/spatial/frame/index":
                index_values.append(call[0][1])

        self.assertEqual(index_values, [0, 1])

        sink.close()


if __name__ == "__main__":
    unittest.main()
