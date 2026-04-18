"""Bridge between StreamEngine's pipeline objects and the graph model."""

from .adapter_registry import get_node_for_adapter
from .graph_builder import GraphBuilder

__all__ = ["GraphBuilder", "get_node_for_adapter"]
