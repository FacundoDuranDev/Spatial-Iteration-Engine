"""OutputNode — writes RenderFrame to a sink."""

from abc import abstractmethod
from typing import Any, Dict, List

from ..core.base_node import BaseNode
from ..core.port_types import InputPort, OutputPort, PortType


class OutputNode(BaseNode):
    """Node that writes rendered frames to an output sink.

    Ports: render_in -> (none)
    """

    def get_input_ports(self) -> List[InputPort]:
        return [InputPort("render_in", PortType.RENDER_FRAME)]

    def get_output_ports(self) -> List[OutputPort]:
        return []

    @abstractmethod
    def write(self, rendered: Any) -> None:
        """Write a rendered frame to the sink."""

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.write(inputs["render_in"])
        return {}
