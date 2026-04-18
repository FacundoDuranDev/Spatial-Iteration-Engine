"""TrackerNode — tracks objects across frames using analysis data."""

from abc import abstractmethod
from typing import Any, Dict, List

from ..core.base_node import BaseNode
from ..core.port_types import InputPort, OutputPort, PortType


class TrackerNode(BaseNode):
    """Node that tracks objects using video and analysis data.

    Ports: video_in + analysis_in -> video_out (passthrough) + tracking_out
    """

    def get_input_ports(self) -> List[InputPort]:
        return [
            InputPort("video_in", PortType.VIDEO_FRAME),
            InputPort("analysis_in", PortType.ANALYSIS_DATA),
        ]

    def get_output_ports(self) -> List[OutputPort]:
        return [
            OutputPort("video_out", PortType.VIDEO_FRAME),
            OutputPort("tracking_out", PortType.TRACKING_DATA),
        ]

    @abstractmethod
    def track(self, frame: Any, detections: dict, config: Any) -> Any:
        """Track objects in the frame. Returns tracking data."""

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        frame = inputs["video_in"]
        analysis = inputs["analysis_in"]
        tracking = self.track(frame, analysis, self.config)
        return {
            "video_out": frame,
            "tracking_out": tracking,
        }
