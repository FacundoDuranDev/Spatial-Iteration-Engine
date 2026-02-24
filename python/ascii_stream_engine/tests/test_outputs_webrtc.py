"""Tests for the WebRTC output sink."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame
from ascii_stream_engine.ports.output_capabilities import OutputCapability
from ascii_stream_engine.tests import has_module


@unittest.skipUnless(has_module("aiortc"), "requires aiortc")
@unittest.skipUnless(has_module("aiohttp"), "requires aiohttp")
class TestWebRTCOutput(unittest.TestCase):
    """Tests for WebRTCOutput."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        from PIL import Image

        self.config = EngineConfig(fps=20)
        self.output_size = (640, 480)
        self.test_image = Image.new("RGB", (640, 480), color=(255, 0, 0))

    def test_webrtc_output_initialization(self) -> None:
        """Test that WebRTCOutput initializes correctly."""
        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        output = WebRTCOutput(signaling_port=8081)
        self.assertEqual(output.signaling_port, 8081)
        self.assertTrue(output.enable_signaling)
        self.assertFalse(output.is_open())

    def test_webrtc_output_requires_aiortc(self) -> None:
        """Test that WebRTCOutput requires aiortc."""
        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        output = WebRTCOutput()
        self.assertIsNotNone(output)

    @patch("ascii_stream_engine.adapters.outputs.webrtc.webrtc_sink.RTCPeerConnection")
    @patch("ascii_stream_engine.adapters.outputs.webrtc.webrtc_sink.WebRTCSignalingServer")
    def test_webrtc_output_open(self, mock_signaling_class, mock_pc_class) -> None:
        """Test that open() configures the output correctly."""
        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        mock_signaling = MagicMock()
        mock_signaling_class.return_value = mock_signaling
        mock_pc = AsyncMock()
        mock_pc_class.return_value = mock_pc
        mock_pc.iceConnectionState = "new"

        output = WebRTCOutput(signaling_port=8082, enable_signaling=True)
        output.open(self.config, self.output_size)

        mock_signaling.start.assert_called_once()
        output.close()

    def test_webrtc_output_write_frame(self) -> None:
        """Test that write() processes frames correctly."""
        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        output = WebRTCOutput(signaling_port=8083, enable_signaling=False)
        mock_track = MagicMock()
        output._video_track = mock_track
        output._is_open = True

        frame = RenderFrame(image=self.test_image, text="test")
        output.write(frame)

        mock_track.put_frame.assert_called_once()
        output._is_open = False

    def test_webrtc_output_close(self) -> None:
        """Test that close() cleans up resources correctly."""
        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        output = WebRTCOutput(signaling_port=8084, enable_signaling=False)
        output._is_open = True

        mock_signaling = MagicMock()
        output._signaling_server = mock_signaling
        mock_pc = AsyncMock()
        mock_loop = MagicMock()
        output._peer_connection = mock_pc
        output._loop = mock_loop

        output.close()

        self.assertFalse(output._is_open)
        self.assertIsNone(output._peer_connection)
        self.assertIsNone(output._video_track)
        self.assertIsNone(output._loop)
        self.assertIsNone(output._thread)

    def test_webrtc_output_write_when_closed(self) -> None:
        """Test that write() on a closed sink is a no-op."""
        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        output = WebRTCOutput(signaling_port=8085, enable_signaling=False)
        output._is_open = False

        frame = RenderFrame(image=self.test_image, text="test")
        output.write(frame)  # Must not raise

    def test_webrtc_output_close_idempotent(self) -> None:
        """Test that close() can be called multiple times safely."""
        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        output = WebRTCOutput(signaling_port=8086, enable_signaling=False)
        output.close()
        output.close()  # Must not raise

    def test_webrtc_output_capabilities(self) -> None:
        """Verify capability flags, protocol name, and latency."""
        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        output = WebRTCOutput(signaling_port=8087, enable_signaling=False)
        caps = output.get_capabilities()

        self.assertTrue(caps.has_capability(OutputCapability.STREAMING))
        self.assertTrue(caps.has_capability(OutputCapability.WEBRTC))
        self.assertTrue(caps.has_capability(OutputCapability.LOW_LATENCY))
        self.assertTrue(caps.has_capability(OutputCapability.ADAPTIVE_QUALITY))
        self.assertTrue(caps.has_capability(OutputCapability.MULTI_CLIENT))
        self.assertEqual(caps.protocol_name, "WebRTC")
        self.assertEqual(caps.estimated_latency_ms, 50.0)

    def test_webrtc_output_estimated_latency(self) -> None:
        """Verify get_estimated_latency_ms() returns 50.0."""
        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        output = WebRTCOutput(signaling_port=8088, enable_signaling=False)
        self.assertEqual(output.get_estimated_latency_ms(), 50.0)

    def test_webrtc_output_supports_multiple_clients(self) -> None:
        """Verify supports_multiple_clients() returns True."""
        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        output = WebRTCOutput(signaling_port=8089, enable_signaling=False)
        self.assertTrue(output.supports_multiple_clients())

    def test_webrtc_output_write_image_conversion(self) -> None:
        """Verify RGBA images are handled without error."""
        from PIL import Image

        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        output = WebRTCOutput(signaling_port=8090, enable_signaling=False)
        mock_track = MagicMock()
        output._video_track = mock_track
        output._is_open = True

        rgba_image = Image.new("RGBA", (640, 480), (255, 0, 0, 128))
        frame = RenderFrame(image=rgba_image, text="test")
        output.write(frame)

        mock_track.put_frame.assert_called_once()
        output._is_open = False


@unittest.skipUnless(has_module("aiohttp"), "requires aiohttp")
class TestWebRTCSignalingServer(unittest.TestCase):
    """Tests for WebRTCSignalingServer."""

    def test_signaling_server_initialization(self) -> None:
        """Test that the signaling server initializes correctly."""
        from ascii_stream_engine.adapters.outputs.webrtc.signaling import (
            WebRTCSignalingServer,
        )

        server = WebRTCSignalingServer(host="127.0.0.1", port=8091)
        self.assertEqual(server.host, "127.0.0.1")
        self.assertEqual(server.port, 8091)

    def test_signaling_server_offer_handling(self) -> None:
        """Test that the server handles offers correctly."""
        from ascii_stream_engine.adapters.outputs.webrtc.signaling import (
            WebRTCSignalingServer,
        )

        server = WebRTCSignalingServer(port=8092)
        offer_data = {
            "sdp": "v=0\r\no=- 123456 2 IN IP4 127.0.0.1\r\n",
            "type": "offer",
            "peer_id": "test_peer",
        }
        server._pending_offers["test_peer"] = offer_data

        retrieved = server.get_pending_offer("test_peer")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["sdp"], offer_data["sdp"])
        self.assertIsNone(server.get_pending_offer("test_peer"))

    def test_signaling_server_answer_handling(self) -> None:
        """Test that the server handles answers correctly."""
        from ascii_stream_engine.adapters.outputs.webrtc.signaling import (
            WebRTCSignalingServer,
        )

        server = WebRTCSignalingServer(port=8093)
        answer_data = {
            "sdp": "v=0\r\no=- 123456 2 IN IP4 127.0.0.1\r\n",
            "type": "answer",
            "peer_id": "test_peer",
        }
        server.set_answer("test_peer", answer_data)

        retrieved = server.get_answer("test_peer")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["sdp"], answer_data["sdp"])
        self.assertIsNone(server.get_answer("test_peer"))

    def test_signaling_server_peer_tracking(self) -> None:
        """Test that the server tracks connected peers."""
        from ascii_stream_engine.adapters.outputs.webrtc.signaling import (
            WebRTCSignalingServer,
        )

        server = WebRTCSignalingServer(port=8094)
        server.mark_peer_connected("peer1")
        self.assertIn("peer1", server._connected_peers)

        server.mark_peer_disconnected("peer1")
        self.assertNotIn("peer1", server._connected_peers)


if __name__ == "__main__":
    unittest.main()
