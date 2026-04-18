"""BaseNode ABC — the primary abstraction for the graph execution model."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .port_types import InputPort, OutputPort


class BaseNode(ABC):
    """Abstract base for all graph nodes.

    Subclasses declare their ports via get_input_ports/get_output_ports and
    implement process(). The scheduler calls process() with resolved inputs
    and collects the returned outputs dict.

    Temporal declarations mirror BaseFilter attributes so TemporalManager.configure()
    works unchanged when scanning graph nodes.
    """

    name: str = "unnamed"
    enabled: bool = True

    # Temporal declarations (mirrored from BaseFilter for TemporalManager compatibility)
    required_input_history: int = 0
    needs_optical_flow: bool = False
    needs_delta_frame: bool = False
    needs_previous_output: bool = False

    def __init__(self) -> None:
        self._config: Optional[Any] = None

    @property
    def config(self) -> Any:
        """Engine config, injected by the scheduler before each process() call."""
        return self._config

    @config.setter
    def config(self, value: Any) -> None:
        self._config = value

    @abstractmethod
    def get_input_ports(self) -> List[InputPort]:
        """Declare input ports this node expects."""

    @abstractmethod
    def get_output_ports(self) -> List[OutputPort]:
        """Declare output ports this node produces."""

    @abstractmethod
    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Process inputs and return outputs.

        Args:
            inputs: Dict mapping input port name -> data value.
                    Missing optional ports are absent from the dict.

        Returns:
            Dict mapping output port name -> data value.
        """

    def setup(self) -> None:
        """Called once before the first frame. Override for initialization."""

    def teardown(self) -> None:
        """Called once after the last frame. Override for cleanup."""

    def reset(self) -> None:
        """Reset internal state (e.g. on resolution change)."""

    def get_input_port(self, name: str) -> Optional[InputPort]:
        """Look up an input port by name."""
        for port in self.get_input_ports():
            if port.name == name:
                return port
        return None

    def get_output_port(self, name: str) -> Optional[OutputPort]:
        """Look up an output port by name."""
        for port in self.get_output_ports():
            if port.name == name:
                return port
        return None

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
