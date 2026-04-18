"""SourceNode — produces video frames with no inputs."""

from abc import abstractmethod
from typing import Any, Dict, List

from ..core.base_node import BaseNode
from ..core.port_types import InputPort, OutputPort, PortType


class SourceNode(BaseNode):
    """Node that produces video frames (camera, file, network).

    Ports: (none) -> video_out
    """

    def get_input_ports(self) -> List[InputPort]:
        return []

    def get_output_ports(self) -> List[OutputPort]:
        return [OutputPort("video_out", PortType.VIDEO_FRAME)]

    @abstractmethod
    def read_frame(self) -> Any:
        """Read a frame from the source. Returns numpy array or None."""

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        frame = self.read_frame()
        return {"video_out": frame}
