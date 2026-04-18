"""RendererNode — converts video frames to RenderFrame output."""

from abc import abstractmethod
from typing import Any, Dict, List

from ..core.base_node import BaseNode
from ..core.port_types import InputPort, OutputPort, PortType


class RendererNode(BaseNode):
    """Node that renders video frames into RenderFrame output.

    Ports: video_in + analysis_in (optional) -> render_out
    """

    def get_input_ports(self) -> List[InputPort]:
        return [
            InputPort("video_in", PortType.VIDEO_FRAME),
            InputPort("analysis_in", PortType.ANALYSIS_DATA, required=False),
        ]

    def get_output_ports(self) -> List[OutputPort]:
        return [OutputPort("render_out", PortType.RENDER_FRAME)]

    @abstractmethod
    def render(self, frame: Any, config: Any, analysis: Any) -> Any:
        """Render a frame. Returns RenderFrame."""

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        frame = inputs["video_in"]
        analysis = inputs.get("analysis_in", {})
        rendered = self.render(frame, self.config, analysis)
        return {"render_out": rendered}
