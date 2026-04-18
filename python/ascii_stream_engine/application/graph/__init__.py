"""Graph-based execution model for the frame pipeline.

Opt-in alternative to PipelineOrchestrator. Each filter, analyzer, renderer
is an independent node with typed ports. Nodes are connected into a DAG and
executed in topological order by the GraphScheduler.

Usage:
    engine = StreamEngine(source, renderer, sink, use_graph=True)
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
