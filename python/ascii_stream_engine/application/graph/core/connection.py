"""Connection between two node ports with type validation."""

from dataclasses import dataclass

from .base_node import BaseNode


@dataclass(frozen=True)
class Connection:
    """A validated connection from one node's output port to another's input port."""

    source_node: BaseNode
    source_port: str
    target_node: BaseNode
    target_port: str

    def __post_init__(self) -> None:
        out = self.source_node.get_output_port(self.source_port)
        if out is None:
            raise ValueError(
                f"Node {self.source_node.name!r} has no output port {self.source_port!r}"
            )
        inp = self.target_node.get_input_port(self.target_port)
        if inp is None:
            raise ValueError(
                f"Node {self.target_node.name!r} has no input port {self.target_port!r}"
            )
        if not inp.accepts(out):
            raise TypeError(
                f"Type mismatch: {self.source_node.name}.{self.source_port} "
                f"({out.data_type.name}) -> {self.target_node.name}.{self.target_port} "
                f"({inp.data_type.name})"
            )
