"""WebRTC output sink for real-time browser streaming.

This module implements an OutputSink that streams frames via WebRTC,
enabling real-time visualization in web browsers.
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
from ...ports.output_capabilities import (
    OutputCapabilities,
    OutputCapability,
    OutputQuality,
)
from .signaling import WebRTCSignalingServer

logger = logging.getLogger(__name__)


class FrameVideoTrack(VideoStreamTrack):
    """WebRTC video track that streams frames from the engine.

    Converts PIL Image frames to av VideoFrame objects that WebRTC can
    transmit to connected clients.
    """

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        """Initialize the video track.

        Args:
            loop: Asyncio event loop (optional).
        """
        if VideoStreamTrack is None:
            raise ImportError("aiortc is not installed. Install with: pip install aiortc")
        super().__init__()
        self._loop = loop
        # Do not pass loop parameter to Queue (removed in Python 3.10)
        self._frame_queue: Optional[asyncio.Queue] = asyncio.Queue(maxsize=2)
        self._current_frame: Optional[VideoFrame] = None
        self._frame_lock = threading.Lock()
        self._frame_counter = 0

    def put_frame(self, image: Image.Image) -> None:
        """Place a frame in the queue for transmission.

        Args:
            image: PIL Image to transmit.
        """
        if self._frame_queue is None:
            return

        try:
            # Convert PIL Image to VideoFrame
            if image.mode != "RGB":
                image = image.convert("RGB")

            import numpy as np

            frame_array = np.array(image)
            frame = VideoFrame.from_ndarray(frame_array, format="rgb24")
            frame.pts = self._frame_counter
            frame.time_base = None
            self._frame_counter += 1

            loop = self._loop
            if loop is None:
                return

            queue = self._frame_queue

            def put_frame_async():
                try:
                    queue.put_nowait(frame)
                except asyncio.QueueFull:
                    try:
                        queue.get_nowait()
                        queue.put_nowait(frame)
                    except asyncio.QueueEmpty:
                        pass

            if loop.is_running():
                loop.call_soon_threadsafe(put_frame_async)
            else:
                put_frame_async()

        except Exception as e:
            logger.error(f"Error putting frame: {e}", exc_info=True)

    async def recv(self):
        """Receive the next frame for transmission (async).

        Returns:
            VideoFrame for WebRTC.
        """
        if self._frame_queue is None:
            self._frame_queue = asyncio.Queue(maxsize=2)

        if self._current_frame is None:
            self._current_frame = await self._frame_queue.get()

        try:
            self._current_frame = self._frame_queue.get_nowait()
        except asyncio.QueueEmpty:
            pass

        if self._current_frame.pts is None:
            import time

            self._current_frame.pts = int(time.time() * 90000)

        if self._current_frame.time_base is None:
            from fractions import Fraction

            self._current_frame.time_base = Fraction(1, 90000)

        return self._current_frame


class WebRTCOutput:
    """Output sink that streams frames via WebRTC.

    Implements the OutputSink protocol to transmit frames to WebRTC
    clients connected through a web browser.
    """

    def __init__(
        self,
        signaling_host: str = "0.0.0.0",
        signaling_port: int = 8080,
        enable_signaling: bool = True,
    ):
        """Initialize the WebRTC output.

        Args:
            signaling_host: Host for the signaling server.
            signaling_port: Port for the signaling server.
            enable_signaling: If True, start the signaling server automatically.
        """
        if RTCPeerConnection is None:
            raise ImportError("aiortc is not installed. Install with: pip install aiortc")

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
        """Open the WebRTC output and prepare the connection.

        Args:
            config: Engine configuration.
            output_size: Output dimensions as (width, height).
        """
        self.close()

        self._config = config
        self._output_size = output_size

        # Start signaling server if enabled
        if self.enable_signaling:
            self._signaling_server = WebRTCSignalingServer(
                host=self.signaling_host, port=self.signaling_port
            )
            self._signaling_server.start()

        # Start asyncio event loop in a separate thread
        def run_webrtc():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._setup_webrtc())

        self._thread = threading.Thread(target=run_webrtc, daemon=True)
        self._thread.start()

        import time

        time.sleep(0.5)
        self._is_open = True

        logger.info(
            f"WebRTC output opened. Signaling server at "
            f"http://{self.signaling_host}:{self.signaling_port}"
        )

    async def _setup_webrtc(self) -> None:
        """Set up the WebRTC connection (async)."""
        try:
            self._peer_connection = RTCPeerConnection()
            self._video_track = FrameVideoTrack(loop=self._loop)
            self._peer_connection.addTrack(self._video_track)

            @self._peer_connection.on("iceconnectionstatechange")
            async def on_iceconnectionstatechange():
                logger.info(f"ICE connection state: {self._peer_connection.iceConnectionState}")
                if self._peer_connection.iceConnectionState == "failed":
                    await self._peer_connection.close()

            if self._signaling_server:
                await self._handle_offers()

        except Exception as e:
            logger.error(f"Error setting up WebRTC: {e}", exc_info=True)

    async def _handle_offers(self) -> None:
        """Handle SDP offers from clients (async)."""
        if not self._signaling_server or not self._peer_connection:
            return

        self._stop_offers = False
        while not self._stop_offers:
            try:
                offer_data = self._signaling_server.get_pending_offer()
                if offer_data:
                    offer = RTCSessionDescription(sdp=offer_data["sdp"], type=offer_data["type"])
                    await self._peer_connection.setRemoteDescription(offer)
                    answer = await self._peer_connection.createAnswer()
                    await self._peer_connection.setLocalDescription(answer)
                    self._signaling_server.set_answer(
                        offer_data["peer_id"],
                        {
                            "sdp": self._peer_connection.localDescription.sdp,
                            "type": self._peer_connection.localDescription.type,
                        },
                    )
                    logger.info("WebRTC connection established")

                await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                logger.info("Offer handling cancelled")
                break
            except Exception as e:
                logger.error(f"Error handling offers: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    def write(self, frame: RenderFrame) -> None:
        """Write a frame to the WebRTC output.

        Args:
            frame: Rendered frame to transmit.
        """
        if not self._is_open or not self._video_track:
            return

        try:
            image = frame.image if isinstance(frame, RenderFrame) else frame
            if isinstance(image, Image.Image):
                self._video_track.put_frame(image)
        except Exception as e:
            logger.error(f"Error writing frame to WebRTC: {e}", exc_info=True)

    def close(self) -> None:
        """Close the WebRTC output and clean up resources."""
        self._is_open = False
        self._stop_offers = True

        # Close peer connection
        if self._peer_connection and self._loop:
            try:
                future = asyncio.run_coroutine_threadsafe(self._peer_connection.close(), self._loop)
                future.result(timeout=2.0)
            except Exception as e:
                logger.debug(f"Error closing peer connection: {e}")

        # Stop signaling server
        if self._signaling_server:
            try:
                self._signaling_server.stop()
            except Exception as e:
                logger.debug(f"Error stopping signaling server: {e}")

        # Stop event loop
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        # Join thread
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        # Clean up references
        self._peer_connection = None
        self._video_track = None
        self._signaling_server = None
        self._loop = None
        self._thread = None
        self._output_size = None

        logger.info("WebRTC output closed")

    def is_open(self) -> bool:
        """Check if the sink is open and ready to write."""
        return self._is_open

    def get_capabilities(self) -> OutputCapabilities:
        """Get the capabilities of this WebRTC sink."""
        return OutputCapabilities(
            capabilities=(
                OutputCapability.STREAMING
                | OutputCapability.WEBRTC
                | OutputCapability.LOW_LATENCY
                | OutputCapability.ADAPTIVE_QUALITY
                | OutputCapability.MULTI_CLIENT
            ),

            supported_qualities=[
                OutputQuality.LOW,
                OutputQuality.MEDIUM,
                OutputQuality.HIGH,
            ],
            max_clients=10,
            protocol_name="WebRTC",
            metadata={
                "signaling_host": self.signaling_host,
                "signaling_port": self.signaling_port,
            },
        )

    def supports_multiple_clients(self) -> bool:
        """WebRTC supports multiple peer connections."""
        return True
