import unittest
from unittest.mock import MagicMock, patch

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame


class TestNdiOutputSink(unittest.TestCase):
    """Tests para el output sink NDI."""

    def setUp(self) -> None:
        """Configuración inicial para cada test."""
        self.config = EngineConfig(fps=30)
        self.output_size = (640, 480)

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", False)
    def test_ndi_unavailable_raises_error(self) -> None:
        """Test que verifica que se lanza error si NDI no está disponible."""
        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        with self.assertRaises(ImportError):
            NdiOutputSink()

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_initialization(self, mock_ndi: MagicMock) -> None:
        """Test que verifica la inicialización del output NDI."""
        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        # Configurar mocks
        mock_ndi.initialize.return_value = True
        mock_ndi.send_create.return_value = MagicMock()
        mock_ndi.LibNDISendCreate = MagicMock
        mock_ndi.VideoFrameV2 = MagicMock
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_send_video_v2 = MagicMock()
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        # Crear instancia
        output = NdiOutputSink(source_name="Test Source")
        self.assertEqual(output._source_name, "Test Source")

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_open(self, mock_ndi: MagicMock) -> None:
        """Test que verifica la apertura del output NDI."""
        from PIL import Image

        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        # Configurar mocks
        mock_ndi.initialize.return_value = True
        mock_sender = MagicMock()
        mock_ndi.send_create.return_value = mock_sender
        mock_ndi.LibNDISendCreate = MagicMock
        mock_ndi.VideoFrameV2 = MagicMock
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_send_video_v2 = MagicMock()
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        # Crear instancia y abrir
        output = NdiOutputSink()
        output.open(self.config, self.output_size)

        # Verificar que se inicializó NDI
        mock_ndi.initialize.assert_called_once()
        # Verificar que se creó el sender
        mock_ndi.send_create.assert_called_once()
        # Verificar que el output está abierto
        self.assertTrue(output._is_open)
        self.assertEqual(output._output_size, self.output_size)
        self.assertEqual(output._fps, self.config.fps)

        output.close()

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_write_frame(self, mock_ndi: MagicMock) -> None:
        """Test que verifica el envío de frames."""
        from PIL import Image

        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        # Configurar mocks
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

        # Crear instancia, abrir y escribir frame
        output = NdiOutputSink()
        output.open(self.config, self.output_size)

        # Crear frame de prueba
        image = Image.new("RGB", (640, 480), color=(255, 0, 0))
        frame = RenderFrame(image=image, text="test")

        # Escribir frame
        output.write(frame)

        # Verificar que se llamó send_send_video_v2
        mock_ndi.send_send_video_v2.assert_called_once()

        output.close()

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_close(self, mock_ndi: MagicMock) -> None:
        """Test que verifica el cierre del output NDI."""
        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        # Configurar mocks
        mock_ndi.initialize.return_value = True
        mock_sender = MagicMock()
        mock_ndi.send_create.return_value = mock_sender
        mock_ndi.LibNDISendCreate = MagicMock
        mock_ndi.VideoFrameV2 = MagicMock
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_send_video_v2 = MagicMock()
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        # Crear instancia, abrir y cerrar
        output = NdiOutputSink()
        output.open(self.config, self.output_size)
        output.close()

        # Verificar que se destruyó el sender
        mock_ndi.send_destroy.assert_called_once_with(mock_sender)
        # Verificar que el output está cerrado
        self.assertFalse(output._is_open)
        self.assertIsNone(output._ndi_send)

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_resize_frame(self, mock_ndi: MagicMock) -> None:
        """Test que verifica el redimensionado automático de frames."""
        from PIL import Image

        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        # Configurar mocks
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

        # Crear instancia con tamaño de salida diferente
        output = NdiOutputSink()
        output.open(self.config, (320, 240))

        # Crear frame con tamaño diferente
        image = Image.new("RGB", (640, 480), color=(0, 255, 0))
        frame = RenderFrame(image=image, text="test")

        # Escribir frame (debe redimensionarse automáticamente)
        output.write(frame)

        # Verificar que se llamó send_send_video_v2
        mock_ndi.send_send_video_v2.assert_called_once()

        output.close()

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_custom_source_name(self, mock_ndi: MagicMock) -> None:
        """Test que verifica el uso de un nombre de fuente personalizado."""
        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        # Configurar mocks
        mock_ndi.initialize.return_value = True
        mock_sender = MagicMock()
        mock_ndi.send_create.return_value = mock_sender
        mock_ndi.LibNDISendCreate = MagicMock
        mock_ndi.VideoFrameV2 = MagicMock
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_send_video_v2 = MagicMock()
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        # Crear instancia con nombre personalizado
        custom_name = "Mi Fuente Personalizada"
        output = NdiOutputSink(source_name=custom_name)
        self.assertEqual(output._source_name, custom_name)

        output.open(self.config, self.output_size)

        # Verificar que se usó el nombre personalizado
        call_args = mock_ndi.send_create.call_args[0][0]
        self.assertEqual(call_args.ndi_name, custom_name)

        output.close()

    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.NDI_AVAILABLE", True)
    @patch("ascii_stream_engine.adapters.outputs.ndi.ndi_sink.ndi", create=True)
    def test_ndi_output_write_when_closed(self, mock_ndi: MagicMock) -> None:
        """Test que verifica que escribir cuando está cerrado no causa error."""
        from PIL import Image

        from ascii_stream_engine.adapters.outputs.ndi.ndi_sink import NdiOutputSink

        # Configurar mocks
        mock_ndi.initialize.return_value = True
        mock_sender = MagicMock()
        mock_ndi.send_create.return_value = mock_sender
        mock_ndi.LibNDISendCreate = MagicMock
        mock_ndi.VideoFrameV2 = MagicMock
        mock_ndi.FOURCC_VIDEO_TYPE_BGRA = 0
        mock_ndi.send_send_video_v2 = MagicMock()
        mock_ndi.send_destroy = MagicMock()
        mock_ndi.destroy = MagicMock()

        # Crear instancia sin abrir
        output = NdiOutputSink()

        # Crear frame de prueba
        image = Image.new("RGB", (640, 480))
        frame = RenderFrame(image=image, text="test")

        # Escribir frame (no debe causar error)
        output.write(frame)

        # Verificar que no se llamó send_send_video_v2
        mock_ndi.send_send_video_v2.assert_not_called()


if __name__ == "__main__":
    unittest.main()
