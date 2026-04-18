"""TransformNode — applies spatial transformations to video frames."""

from abc import abstractmethod
from typing import Any, Dict, List

from ..core.base_node import BaseNode
from ..core.port_types import InputPort, OutputPort, PortType


class TransformNode(BaseNode):
    """Node that applies spatial transformations (warp, projection, blend).

    Ports: video_in -> video_out
    """

    def get_input_ports(self) -> List[InputPort]:
        return [InputPort("video_in", PortType.VIDEO_FRAME)]

    def get_output_ports(self) -> List[OutputPort]:
        return [OutputPort("video_out", PortType.VIDEO_FRAME)]

    @abstractmethod
    def transform(self, frame: Any) -> Any:
        """Apply spatial transformation. Returns modified frame."""

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        frame = inputs["video_in"]
        result = self.transform(frame)
        return {"video_out": result}
