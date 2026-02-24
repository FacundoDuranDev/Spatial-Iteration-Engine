"""
Backend de salida WebRTC para streaming en tiempo real.

Este módulo implementa un OutputSink que transmite frames vía WebRTC,
permitiendo visualización en navegadores web en tiempo real.
"""

import asyncio
import logging
import threading
from typing import Optional, Tuple

try:
    from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
    from av import VideoFrame
except ImportError:
    RTCPeerConnection = None  # type: ignore
    RTCSessionDescription = None  # type: ignore
    VideoStreamTrack = None  # type: ignore
    VideoFrame = None  # type: ignore

from PIL import Image

from ...domain.config import EngineConfig
from ...domain.types import RenderFrame
from .signaling import WebRTCSignalingServer

logger = logging.getLogger(__name__)


class FrameVideoTrack(VideoStreamTrack):
    """
    Track de video WebRTC que transmite frames desde el engine.

    Esta clase convierte frames PIL Image a VideoFrame de av (que WebRTC puede usar)
    y los transmite a los clientes conectados.
    """

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        """
        Inicializa el track de video.

        Args:
            loop: Loop de eventos asyncio (opcional, se obtiene del contexto si no se proporciona)
        """
        if VideoStreamTrack is None:
            raise ImportError("aiortc no está instalado. Instala con: pip install aiortc")
        super().__init__()
        self._loop = loop
        if loop is not None:
            self._frame_queue: Optional[asyncio.Queue] = asyncio.Queue(maxsize=2, loop=loop)
        else:
            self._frame_queue: Optional[asyncio.Queue] = None
        self._current_frame: Optional[VideoFrame] = None
        self._frame_lock = threading.Lock()
        self._frame_counter = 0

    def _ensure_queue(self) -> asyncio.Queue:
        """Asegura que la cola existe, creándola si es necesario."""
        if self._frame_queue is None:
            if self._loop:
                self._frame_queue = asyncio.Queue(maxsize=2, loop=self._loop)
            else:
                # Si no hay loop, intentar obtenerlo del contexto
                try:
                    loop = asyncio.get_event_loop()
                    self._loop = loop
                    self._frame_queue = asyncio.Queue(maxsize=2, loop=loop)
                except RuntimeError:
                    # Si no hay loop en el contexto, crear uno nuevo
                    self._loop = asyncio.new_event_loop()
                    self._frame_queue = asyncio.Queue(maxsize=2, loop=self._loop)
        return self._frame_queue

    def put_frame(self, image: Image.Image) -> None:
        """
        Coloca un frame en la cola para transmisión.

        Args:
            image: Imagen PIL a transmitir
        """
        if self._frame_queue is None:
            # Si la cola no está inicializada, no hacer nada
            return

        try:
            # Convertir PIL Image a VideoFrame
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Convertir a numpy array
            import numpy as np

            frame_array = np.array(image)

            # Crear VideoFrame de av
            frame = VideoFrame.from_ndarray(frame_array, format="rgb24")
            frame.pts = self._frame_counter
            frame.time_base = None
            self._frame_counter += 1

            # Obtener el loop de eventos
            loop = self._loop
            if loop is None:
                return

            # Poner el frame en la cola de forma thread-safe
            queue = self._frame_queue

            def put_frame_async():
                try:
                    queue.put_nowait(frame)
                except asyncio.QueueFull:
                    # Si la cola está llena, descartar el frame más antiguo
                    try:
                        queue.get_nowait()
                        queue.put_nowait(frame)
                    except asyncio.QueueEmpty:
                        pass

            if loop.is_running():
                loop.call_soon_threadsafe(put_frame_async)
            else:
                # Si el loop no está corriendo, ejecutar directamente
                put_frame_async()

        except Exception as e:
            logger.error(f"Error putting frame: {e}", exc_info=True)

    async def recv(self):
        """
        Recibe el siguiente frame para transmisión (async).

        Returns:
            VideoFrame para WebRTC
        """
        queue = self._ensure_queue()

        if self._current_frame is None:
            # Esperar el primer frame
            self._current_frame = await queue.get()

        # Intentar obtener un frame nuevo (no bloquea)
        try:
            self._current_frame = queue.get_nowait()
        except asyncio.QueueEmpty:
            # Si no hay frame nuevo, usar el último frame
            pass

        # Ajustar timestamp si es necesario
        if self._current_frame.pts is None:
            import time

            self._current_frame.pts = int(time.time() * 90000)  # 90kHz clock

        # Asegurar que el frame tiene time_base
        if self._current_frame.time_base is None:
            from fractions import Fraction

            self._current_frame.time_base = Fraction(1, 90000)  # 90kHz

        return self._current_frame


class WebRTCOutput:
    """
    Output sink que transmite frames vía WebRTC.

    Este sink implementa el protocolo OutputSink y transmite frames
    a clientes WebRTC conectados a través de un navegador web.
    """

    def __init__(
        self,
        signaling_host: str = "0.0.0.0",
        signaling_port: int = 8080,
        enable_signaling: bool = True,
    ):
        """
        Inicializa el output WebRTC.

        Args:
            signaling_host: Host donde escuchar el servidor de signaling
            signaling_port: Puerto donde escuchar el servidor de signaling
            enable_signaling: Si True, inicia el servidor de signaling automáticamente
        """
        if RTCPeerConnection is None:
            raise ImportError("aiortc no está instalado. Instala con: pip install aiortc")

        self.signaling_host = signaling_host
        self.signaling_port = signaling_port
        self.enable_signaling = enable_signaling

        self._signaling_server: Optional[WebRTCSignalingServer] = None
        self._peer_connection: Optional[RTCPeerConnection] = None
        self._video_track: Optional[FrameVideoTrack] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._output_size: Optional[Tuple[int, int]] = None
        self._config: Optional[EngineConfig] = None
        self._is_open = False
        self._stop_offers = False

    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        """
        Abre el output WebRTC y prepara la conexión.

        Args:
            config: Configuración del engine
            output_size: Tamaño de salida (width, height)
        """
        if self._is_open:
            self.close()

        self._config = config
        self._output_size = output_size

        # Iniciar servidor de signaling si está habilitado
        if self.enable_signaling:
            self._signaling_server = WebRTCSignalingServer(
                host=self.signaling_host, port=self.signaling_port
            )
            self._signaling_server.start()

        # Iniciar loop de eventos asyncio en un hilo separado
        def run_webrtc():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._setup_webrtc())

        self._thread = threading.Thread(target=run_webrtc, daemon=True)
        self._thread.start()

        # Esperar un poco para que se configure
        import time

        time.sleep(0.5)
        self._is_open = True

        logger.info(
            f"WebRTC output opened. Signaling server at "
            f"http://{self.signaling_host}:{self.signaling_port}"
        )

    async def _setup_webrtc(self) -> None:
        """Configura la conexión WebRTC (async)."""
        try:
            # Crear peer connection
            self._peer_connection = RTCPeerConnection()

            # Crear video track con referencia al loop
            self._video_track = FrameVideoTrack(loop=self._loop)
            self._peer_connection.addTrack(self._video_track)

            # Configurar ICE candidates
            @self._peer_connection.on("iceconnectionstatechange")
            async def on_iceconnectionstatechange():
                logger.info(f"ICE connection state: {self._peer_connection.iceConnectionState}")
                if self._peer_connection.iceConnectionState == "failed":
                    await self._peer_connection.close()

            # Manejar ofertas del cliente
            if self._signaling_server:
                # Esperar ofertas del cliente
                await self._handle_offers()

        except Exception as e:
            logger.error(f"Error setting up WebRTC: {e}", exc_info=True)

    async def _handle_offers(self) -> None:
        """Maneja ofertas SDP del cliente (async)."""
        if not self._signaling_server or not self._peer_connection:
            return

        self._stop_offers = False
        while not self._stop_offers:
            try:
                # Revisar si hay ofertas pendientes
                offer_data = self._signaling_server.get_pending_offer()
                if offer_data:
                    offer = RTCSessionDescription(sdp=offer_data["sdp"], type=offer_data["type"])

                    # Establecer la oferta remota
                    await self._peer_connection.setRemoteDescription(offer)

                    # Crear respuesta
                    answer = await self._peer_connection.createAnswer()
                    await self._peer_connection.setLocalDescription(answer)

                    # Enviar respuesta al cliente
                    self._signaling_server.set_answer(
                        offer_data["peer_id"],
                        {
                            "sdp": self._peer_connection.localDescription.sdp,
                            "type": self._peer_connection.localDescription.type,
                        },
                    )

                    logger.info("WebRTC connection established")

                await asyncio.sleep(0.1)  # Revisar cada 100ms

            except asyncio.CancelledError:
                logger.info("Offer handling cancelled")
                break
            except Exception as e:
                logger.error(f"Error handling offers: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    def write(self, frame: RenderFrame) -> None:
        """
        Escribe un frame al output WebRTC.

        Args:
            frame: Frame renderizado a transmitir
        """
        if not self._is_open or not self._video_track:
            return

        try:
            image = frame.image if isinstance(frame, RenderFrame) else frame
            if isinstance(image, Image.Image):
                # Colocar el frame en el track de video
                self._video_track.put_frame(image)
        except Exception as e:
            logger.error(f"Error writing frame to WebRTC: {e}", exc_info=True)

    def close(self) -> None:
        """Cierra el output WebRTC y limpia recursos."""
        if not self._is_open:
            return

        self._is_open = False
        self._stop_offers = True

        # Cerrar peer connection
        if self._peer_connection and self._loop:
            try:
                # Cerrar la conexión de forma asíncrona
                future = asyncio.run_coroutine_threadsafe(self._peer_connection.close(), self._loop)
                # Esperar un poco para que se cierre
                future.result(timeout=2.0)
            except Exception as e:
                logger.error(f"Error closing peer connection: {e}")

        # Detener servidor de signaling
        if self._signaling_server:
            self._signaling_server.stop()

        # Limpiar referencias
        self._peer_connection = None
        self._video_track = None
        self._signaling_server = None

        logger.info("WebRTC output closed")
