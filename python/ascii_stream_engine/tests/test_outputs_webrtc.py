"""
Tests para el backend de salida WebRTC.
"""

import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame
from ascii_stream_engine.tests import has_module


@unittest.skipUnless(has_module("aiortc"), "requires aiortc")
@unittest.skipUnless(has_module("aiohttp"), "requires aiohttp")
class TestWebRTCOutput(unittest.TestCase):
    """Tests para WebRTCOutput."""

    def setUp(self) -> None:
        """Configuración antes de cada test."""
        from PIL import Image

        self.config = EngineConfig(fps=20)
        self.output_size = (640, 480)
        self.test_image = Image.new("RGB", (640, 480), color=(255, 0, 0))

    def test_webrtc_output_initialization(self) -> None:
        """Test que WebRTCOutput se inicializa correctamente."""
        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        output = WebRTCOutput(signaling_port=8081)
        self.assertEqual(output.signaling_port, 8081)
        self.assertTrue(output.enable_signaling)

    def test_webrtc_output_requires_aiortc(self) -> None:
        """Test que WebRTCOutput requiere aiortc."""
        # Este test solo se ejecuta si aiortc está disponible
        # Si no está disponible, el test se omite por el decorador
        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        output = WebRTCOutput()
        self.assertIsNotNone(output)

    @patch("ascii_stream_engine.adapters.outputs.webrtc.webrtc_sink.RTCPeerConnection")
    @patch("ascii_stream_engine.adapters.outputs.webrtc.webrtc_sink.WebRTCSignalingServer")
    def test_webrtc_output_open(self, mock_signaling_class, mock_pc_class) -> None:
        """Test que open() configura correctamente el output."""
        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        # Mock del servidor de signaling
        mock_signaling = MagicMock()
        mock_signaling_class.return_value = mock_signaling

        # Mock del peer connection
        mock_pc = AsyncMock()
        mock_pc_class.return_value = mock_pc
        mock_pc.iceConnectionState = "new"

        output = WebRTCOutput(signaling_port=8082, enable_signaling=True)
        output.open(self.config, self.output_size)

        # Verificar que el servidor de signaling se inició
        mock_signaling.start.assert_called_once()

        # Limpiar
        output.close()

    def test_webrtc_output_write_frame(self) -> None:
        """Test que write() procesa frames correctamente."""
        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        output = WebRTCOutput(signaling_port=8083, enable_signaling=False)

        # Mock del video track
        mock_track = MagicMock()
        output._video_track = mock_track
        output._is_open = True

        frame = RenderFrame(image=self.test_image, text="test")
        output.write(frame)

        # Verificar que put_frame fue llamado
        mock_track.put_frame.assert_called_once()

        output.close()

    def test_webrtc_output_close(self) -> None:
        """Test que close() limpia recursos correctamente."""
        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        output = WebRTCOutput(signaling_port=8084, enable_signaling=False)
        output._is_open = True

        # Mock del servidor de signaling
        mock_signaling = MagicMock()
        output._signaling_server = mock_signaling

        # Mock del peer connection y loop
        mock_pc = AsyncMock()
        mock_loop = MagicMock()
        output._peer_connection = mock_pc
        output._loop = mock_loop

        output.close()

        # Verificar que se cerró
        self.assertFalse(output._is_open)
        self.assertIsNone(output._peer_connection)
        self.assertIsNone(output._video_track)

    def test_webrtc_output_write_when_closed(self) -> None:
        """Test que write() no hace nada cuando está cerrado."""
        from ascii_stream_engine.adapters.outputs.webrtc import WebRTCOutput

        output = WebRTCOutput(signaling_port=8085, enable_signaling=False)
        output._is_open = False

        frame = RenderFrame(image=self.test_image, text="test")
        output.write(frame)  # No debería lanzar excepción

        output.close()


@unittest.skipUnless(has_module("aiohttp"), "requires aiohttp")
class TestWebRTCSignalingServer(unittest.TestCase):
    """Tests para WebRTCSignalingServer."""

    def test_signaling_server_initialization(self) -> None:
        """Test que el servidor de signaling se inicializa correctamente."""
        from ascii_stream_engine.adapters.outputs.webrtc.signaling import (
            WebRTCSignalingServer,
        )

        server = WebRTCSignalingServer(host="127.0.0.1", port=8086)
        self.assertEqual(server.host, "127.0.0.1")
        self.assertEqual(server.port, 8086)

    def test_signaling_server_offer_handling(self) -> None:
        """Test que el servidor maneja ofertas correctamente."""
        from ascii_stream_engine.adapters.outputs.webrtc.signaling import (
            WebRTCSignalingServer,
        )

        server = WebRTCSignalingServer(port=8087)

        # Simular una oferta
        offer_data = {
            "sdp": "v=0\r\no=- 123456 2 IN IP4 127.0.0.1\r\n",
            "type": "offer",
            "peer_id": "test_peer",
        }

        # Guardar oferta manualmente (simulando lo que haría handle_offer)
        server._pending_offers["test_peer"] = offer_data

        # Recuperar la oferta
        retrieved = server.get_pending_offer("test_peer")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["sdp"], offer_data["sdp"])

        # Verificar que se eliminó de pendientes
        self.assertIsNone(server.get_pending_offer("test_peer"))

    def test_signaling_server_answer_handling(self) -> None:
        """Test que el servidor maneja respuestas correctamente."""
        from ascii_stream_engine.adapters.outputs.webrtc.signaling import (
            WebRTCSignalingServer,
        )

        server = WebRTCSignalingServer(port=8088)

        answer_data = {
            "sdp": "v=0\r\no=- 123456 2 IN IP4 127.0.0.1\r\n",
            "type": "answer",
            "peer_id": "test_peer",
        }

        # Establecer respuesta
        server.set_answer("test_peer", answer_data)

        # Recuperar la respuesta
        retrieved = server.get_answer("test_peer")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["sdp"], answer_data["sdp"])

        # Verificar que se eliminó
        self.assertIsNone(server.get_answer("test_peer"))

    def test_signaling_server_peer_tracking(self) -> None:
        """Test que el servidor rastrea peers conectados."""
        from ascii_stream_engine.adapters.outputs.webrtc.signaling import (
            WebRTCSignalingServer,
        )

        server = WebRTCSignalingServer(port=8089)

        # Marcar peer como conectado
        server.mark_peer_connected("peer1")
        self.assertIn("peer1", server._connected_peers)

        # Marcar como desconectado
        server.mark_peer_disconnected("peer1")
        self.assertNotIn("peer1", server._connected_peers)


if __name__ == "__main__":
    unittest.main()
