"""MJPEG streamer for live frame preview.

Generates MJPEG stream from a FrameBuffer for the /stream endpoint.
Requires cv2 (optional dependency).
"""

import logging
import time
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class MJPEGStreamer:
    """Generates MJPEG stream from FrameBuffer for live preview.

    Uses cv2.imencode() for JPEG compression (optional dep).
    Reads from FrameBuffer.peek_latest() (non-destructive).
    """

    def __init__(
        self,
        frame_buffer: Any,
        target_fps: float = 10.0,
        jpeg_quality: int = 50,
        max_width: int = 320,
    ) -> None:
        """Initialize the MJPEG streamer.

        Args:
            frame_buffer: FrameBuffer instance with peek_latest() method.
            target_fps: Maximum frames per second for the stream.
            jpeg_quality: JPEG compression quality (0-100).
            max_width: Maximum width; frames are downscaled if wider.
        """
        self._frame_buffer = frame_buffer
        self._target_fps = target_fps
        self._jpeg_quality = jpeg_quality
        self._max_width = max_width
        self._frame_interval = 1.0 / target_fps if target_fps > 0 else 0.1

    def generate_frames(self) -> Iterator[bytes]:
        """Yield JPEG-encoded frames for MJPEG streaming.

        Yields:
            JPEG encoded bytes for each frame.
        """
        if not CV2_AVAILABLE:
            logger.warning("cv2 not available, MJPEG stream cannot generate frames")
            return

        while True:
            start = time.perf_counter()

            result = self._frame_buffer.peek_latest()
            if result is not None:
                frame, timestamp = result
                frame = self._resize_frame(frame)
                encoded = self._encode_jpeg(frame)
                if encoded is not None:
                    yield encoded

            # Rate limit
            elapsed = time.perf_counter() - start
            sleep_time = self._frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _resize_frame(self, frame: Any) -> Any:
        """Downscale frame if it exceeds max_width.

        Args:
            frame: numpy array (H, W, 3).

        Returns:
            Resized frame.
        """
        if not CV2_AVAILABLE:
            return frame

        h, w = frame.shape[:2]
        if w > self._max_width:
            scale = self._max_width / w
            new_w = self._max_width
            new_h = int(h * scale)
            return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        return frame

    def _encode_jpeg(self, frame: Any) -> Optional[bytes]:
        """Encode a frame as JPEG.

        Args:
            frame: numpy array (H, W, 3).

        Returns:
            JPEG bytes or None on failure.
        """
        if not CV2_AVAILABLE:
            return None

        try:
            params = [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
            success, encoded = cv2.imencode(".jpg", frame, params)
            if success:
                return encoded.tobytes()
        except Exception as e:
            logger.error(f"JPEG encoding error: {e}")
        return None
