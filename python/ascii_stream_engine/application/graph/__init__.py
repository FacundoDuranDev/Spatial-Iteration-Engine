"""Graph-based execution model for the frame pipeline.

Every filter, analyzer, renderer, and output is wrapped as a node with
typed ports. Nodes are connected into a DAG and executed in topological
order by the GraphScheduler — StreamEngine's sole execution backend.

Usage:
    engine = StreamEngine(source, renderer, sink)  # builds the graph automatically
    # or build/customize manually:
    graph = engine.build_graph()
    graph.add_branch(...)
"""

from .core import BaseNode, Connection, Graph, InputPort, OutputPort, PortType

__all__ = [
    "BaseNode",
    "Connection",
    "Graph",
    "InputPort",
    "OutputPort",
    "PortType",
]
