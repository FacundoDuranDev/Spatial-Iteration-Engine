"""Port type definitions for the graph execution model."""

from dataclasses import dataclass
from enum import Enum, auto


class PortType(Enum):
    """Data types that can flow between nodes."""

    VIDEO_FRAME = auto()
    ANALYSIS_DATA = auto()
    RENDER_FRAME = auto()
    TRACKING_DATA = auto()
    CONTROL_SIGNAL = auto()
    MASK = auto()
    CONFIG = auto()


@dataclass(frozen=True)
class OutputPort:
    """Declares a named output with a data type."""

    name: str
    data_type: PortType


@dataclass(frozen=True)
class InputPort:
    """Declares a named input with a data type and optionality."""

    name: str
    data_type: PortType
    required: bool = True
    default_value: object = None

    def accepts(self, output_port: OutputPort) -> bool:
        """Check if this input port can receive data from the given output port."""
        return self.data_type == output_port.data_type
