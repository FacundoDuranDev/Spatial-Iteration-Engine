"""AnalyzerNode — analyzes video frames without modifying them."""

from abc import abstractmethod
from typing import Any, Dict, List

from ..core.base_node import BaseNode
from ..core.port_types import InputPort, OutputPort, PortType


class AnalyzerNode(BaseNode):
    """Node that analyzes video frames and produces analysis data.

    Analyzers MUST NOT modify the input frame (passthrough enforced).

    Ports: video_in -> video_out (passthrough) + analysis_out
    """

    def get_input_ports(self) -> List[InputPort]:
        return [InputPort("video_in", PortType.VIDEO_FRAME)]

    def get_output_ports(self) -> List[OutputPort]:
        return [
            OutputPort("video_out", PortType.VIDEO_FRAME),
            OutputPort("analysis_out", PortType.ANALYSIS_DATA),
        ]

    @abstractmethod
    def analyze(self, frame: Any) -> dict:
        """Analyze a frame. Returns analysis results dict. Must NOT modify frame."""

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        frame = inputs["video_in"]
        result = self.analyze(frame)
        return {
            "video_out": frame,
            "analysis_out": {self.name: result},
        }
