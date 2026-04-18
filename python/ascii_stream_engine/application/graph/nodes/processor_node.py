"""ProcessorNode — modifies video frames (filters)."""

from abc import abstractmethod
from typing import Any, Dict, List

from ..core.base_node import BaseNode
from ..core.port_types import InputPort, OutputPort, PortType


class ProcessorNode(BaseNode):
    """Node that modifies video frames using optional analysis context.

    Ports: video_in + analysis_in (optional) -> video_out
    """

    def get_input_ports(self) -> List[InputPort]:
        return [
            InputPort("video_in", PortType.VIDEO_FRAME),
            InputPort("analysis_in", PortType.ANALYSIS_DATA, required=False),
        ]

    def get_output_ports(self) -> List[OutputPort]:
        return [OutputPort("video_out", PortType.VIDEO_FRAME)]

    @abstractmethod
    def apply_filter(self, frame: Any, config: Any, analysis: Any) -> Any:
        """Apply the filter to a frame. Returns modified frame."""

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        frame = inputs["video_in"]
        analysis = inputs.get("analysis_in", {})
        result = self.apply_filter(frame, self.config, analysis)
        return {"video_out": result}
