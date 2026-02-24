"""OSC (Open Sound Control) output sink for VJ tool integration.

Sends perception data (face landmarks, hand positions, pose joints) and
engine state as OSC messages over UDP. This is the standard protocol for
VJ/live performance ecosystems: TouchDesigner, Max/MSP, Resolume, Ableton.

Unlike image-based sinks, the OSC sink does not transmit pixel data.
It sends structured analysis data as OSC messages.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

try:
    from pythonosc.udp_client import SimpleUDPClient
except ImportError:
    SimpleUDPClient = None  # type: ignore

from ....domain.config import EngineConfig
from ....domain.types import RenderFrame
from ....ports.output_capabilities import (
    OutputCapabilities,
    OutputCapability,
    OutputQuality,
)

logger = logging.getLogger(__name__)


class OscOutputSink:
    """Output sink that sends analysis data as OSC messages over UDP.

    Extracts metadata, analysis results, and frame dimensions from
    RenderFrame and sends them as OSC messages to VJ tools.

    Args:
        host: Target host for OSC messages (default: "127.0.0.1").
        port: Target port for OSC messages (default: 9000).
        address_prefix: Prefix for all OSC address patterns (default: "/spatial").
        send_image_info: Whether to send frame size/index info.
        send_analysis: Whether to send analysis data (face/hands/pose).
        send_metadata: Whether to send metadata key/value pairs.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9000,
        address_prefix: str = "/spatial",
        send_image_info: bool = True,
        send_analysis: bool = True,
        send_metadata: bool = True,
    ) -> None:
        if SimpleUDPClient is None:
            raise ImportError("python-osc is not installed. Install with: pip install python-osc")

        self._host = host
        self._port = port
        self._address_prefix = address_prefix.rstrip("/")
        self._send_image_info = send_image_info
        self._send_analysis = send_analysis
        self._send_metadata = send_metadata

        self._client: Optional[SimpleUDPClient] = None
        self._is_open = False
        self._output_size: Optional[Tuple[int, int]] = None
        self._frame_counter = 0

    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        """Open the OSC output and create the UDP client.

        Args:
            config: Engine configuration.
            output_size: Output dimensions as (width, height).
        """
        self.close()
        self._output_size = output_size
        self._frame_counter = 0

        try:
            self._client = SimpleUDPClient(self._host, self._port)
            self._is_open = True
            logger.info(f"OSC output opened: {self._host}:{self._port}")
        except Exception as e:
            raise RuntimeError(f"Error opening OSC output: {e}")

    def write(self, frame: RenderFrame) -> None:
        """Write frame data as OSC messages.

        Extracts analysis data from the frame metadata and sends it
        as OSC messages. Does not transmit pixel data.

        Args:
            frame: Rendered frame containing analysis metadata.
        """
        if not self._is_open or not self._client:
            return

        try:
            prefix = self._address_prefix

            # Send frame info
            if self._send_image_info:
                if self._output_size:
                    self._client.send_message(
                        f"{prefix}/frame/size",
                        [self._output_size[0], self._output_size[1]],
                    )
                self._client.send_message(f"{prefix}/frame/index", self._frame_counter)

            # Send analysis data
            if self._send_analysis and frame.metadata:
                analysis = frame.metadata.get("analysis")
                if isinstance(analysis, dict):
                    self._send_analysis_data(analysis, prefix)

            # Send metadata
            if self._send_metadata and frame.metadata:
                self._send_metadata_values(frame.metadata, prefix)

            self._frame_counter += 1

        except Exception as e:
            logger.error(f"Error writing OSC message: {e}")

    def _send_analysis_data(self, analysis: Dict[str, Any], prefix: str) -> None:
        """Send analysis data (face, hands, pose) as OSC messages.

        Args:
            analysis: Analysis dictionary from perception pipeline.
            prefix: OSC address prefix.
        """
        # Face landmarks
        face_data = analysis.get("face")
        if isinstance(face_data, dict):
            points = face_data.get("points")
            if points is not None:
                flat_list = self._to_flat_float_list(points)
                if flat_list:
                    self._client.send_message(f"{prefix}/analysis/face/points", flat_list)

        # Hand landmarks
        hands_data = analysis.get("hands")
        if isinstance(hands_data, dict):
            left = hands_data.get("left")
            if left is not None:
                flat_list = self._to_flat_float_list(left)
                if flat_list:
                    self._client.send_message(f"{prefix}/analysis/hands/left", flat_list)

            right = hands_data.get("right")
            if right is not None:
                flat_list = self._to_flat_float_list(right)
                if flat_list:
                    self._client.send_message(f"{prefix}/analysis/hands/right", flat_list)

        # Pose joints
        pose_data = analysis.get("pose")
        if isinstance(pose_data, dict):
            joints = pose_data.get("joints")
            if joints is not None:
                flat_list = self._to_flat_float_list(joints)
                if flat_list:
                    self._client.send_message(f"{prefix}/analysis/pose/joints", flat_list)

    def _send_metadata_values(self, metadata: Dict[str, Any], prefix: str) -> None:
        """Send individual metadata key/value pairs as OSC messages.

        Args:
            metadata: Frame metadata dictionary.
            prefix: OSC address prefix.
        """
        for key, value in metadata.items():
            if key == "analysis":
                continue  # Already handled separately

            try:
                osc_value = self._to_osc_value(value)
                if osc_value is not None:
                    self._client.send_message(f"{prefix}/metadata/{key}", osc_value)
            except Exception as e:
                logger.debug(f"Could not send metadata key '{key}': {e}")

    @staticmethod
    def _to_flat_float_list(data: Any) -> List[float]:
        """Convert numpy array or nested list to a flat list of floats.

        Args:
            data: numpy ndarray or nested list.

        Returns:
            Flat list of Python floats suitable for OSC.
        """
        try:
            import numpy as np

            if isinstance(data, np.ndarray):
                return [float(x) for x in data.flatten()]
        except ImportError:
            pass

        if isinstance(data, (list, tuple)):
            result = []
            for item in data:
                if isinstance(item, (list, tuple)):
                    result.extend(float(x) for x in item)
                else:
                    result.append(float(item))
            return result

        return []

    @staticmethod
    def _to_osc_value(value: Any) -> Any:
        """Convert a Python value to an OSC-compatible value.

        Args:
            value: The value to convert.

        Returns:
            OSC-compatible value, or None if not convertible.
        """
        if isinstance(value, (int, float, str, bool)):
            return value
        if isinstance(value, (list, tuple)):
            # Only send if all elements are simple types
            if all(isinstance(v, (int, float, str, bool)) for v in value):
                return list(value)
        return None

    def close(self) -> None:
        """Close the OSC output. Idempotent."""
        self._client = None
        self._is_open = False
        self._output_size = None

    def is_open(self) -> bool:
        """Check if the sink is open and ready to write."""
        return self._is_open

    def get_capabilities(self) -> OutputCapabilities:
        """Get the capabilities of this OSC sink."""
        return OutputCapabilities(
            capabilities=(
                OutputCapability.STREAMING
                | OutputCapability.UDP
                | OutputCapability.LOW_LATENCY
                | OutputCapability.ULTRA_LOW_LATENCY
            ),
            estimated_latency_ms=1.0,
            supported_qualities=[OutputQuality.LOW, OutputQuality.MEDIUM],
            max_clients=None,  # UDP can broadcast
            protocol_name="OSC/UDP",
            metadata={
                "host": self._host,
                "port": self._port,
                "address_prefix": self._address_prefix,
            },
        )

    def get_estimated_latency_ms(self) -> Optional[float]:
        """Get the estimated latency in milliseconds."""
        return 1.0

    def supports_multiple_clients(self) -> bool:
        """UDP can broadcast to multiple receivers."""
        return True
