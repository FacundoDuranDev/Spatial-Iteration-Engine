"""Graph container with topological sort and cycle detection."""

from collections import defaultdict, deque
from typing import Dict, List, Optional, Set

from .base_node import BaseNode
from .connection import Connection


class Graph:
    """DAG of nodes connected by typed ports.

    Supports topological ordering (Kahn's algorithm), cycle detection,
    and validation of unconnected required ports.
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, BaseNode] = {}
        self._connections: List[Connection] = []
        self._cached_order: Optional[List[BaseNode]] = None

    def add_node(self, node: BaseNode) -> None:
        """Add a node. Raises ValueError on duplicate name."""
        if node.name in self._nodes:
            raise ValueError(f"Duplicate node name: {node.name!r}")
        self._nodes[node.name] = node
        self._cached_order = None

    def connect(
        self, src: BaseNode, src_port: str, tgt: BaseNode, tgt_port: str
    ) -> Connection:
        """Connect src.src_port -> tgt.tgt_port with type validation."""
        if src.name not in self._nodes:
            raise ValueError(f"Source node {src.name!r} not in graph")
        if tgt.name not in self._nodes:
            raise ValueError(f"Target node {tgt.name!r} not in graph")
        conn = Connection(src, src_port, tgt, tgt_port)
        self._connections.append(conn)
        self._cached_order = None
        return conn

    def get_nodes(self) -> List[BaseNode]:
        """Get all nodes in insertion order."""
        return list(self._nodes.values())

    def get_node(self, name: str) -> Optional[BaseNode]:
        """Get a node by name."""
        return self._nodes.get(name)

    def get_connections(self) -> List[Connection]:
        """Get all connections."""
        return list(self._connections)

    def get_connections_to(self, node: BaseNode) -> List[Connection]:
        """Get all connections feeding into the given node."""
        return [c for c in self._connections if c.target_node is node]

    def get_connections_from(self, node: BaseNode) -> List[Connection]:
        """Get all connections originating from the given node."""
        return [c for c in self._connections if c.source_node is node]

    def validate(self) -> List[str]:
        """Validate the graph. Returns a list of error messages (empty = valid)."""
        errors: List[str] = []

        # Check unconnected required input ports
        for node in self._nodes.values():
            connected_inputs: Set[str] = set()
            for conn in self.get_connections_to(node):
                connected_inputs.add(conn.target_port)
            for port in node.get_input_ports():
                if port.required and port.name not in connected_inputs:
                    errors.append(
                        f"Required input port {node.name}.{port.name} is not connected"
                    )

        # Check for cycles
        if self._has_cycle():
            errors.append("Graph contains a cycle")

        return errors

    def get_execution_order(self) -> List[BaseNode]:
        """Topological sort via Kahn's algorithm. Raises ValueError on cycle."""
        if self._cached_order is not None:
            return list(self._cached_order)

        # Build adjacency and in-degree
        in_degree: Dict[str, int] = {name: 0 for name in self._nodes}
        adjacency: Dict[str, List[str]] = defaultdict(list)

        for conn in self._connections:
            src_name = conn.source_node.name
            tgt_name = conn.target_node.name
            adjacency[src_name].append(tgt_name)
            in_degree[tgt_name] += 1

        # Start with nodes that have no incoming edges
        queue: deque = deque()
        for name, degree in in_degree.items():
            if degree == 0:
                queue.append(name)

        order: List[BaseNode] = []
        while queue:
            name = queue.popleft()
            order.append(self._nodes[name])
            for neighbor in adjacency[name]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self._nodes):
            raise ValueError("Graph contains a cycle — topological sort impossible")

        self._cached_order = order
        return list(order)

    def _has_cycle(self) -> bool:
        """DFS-based cycle detection."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {name: WHITE for name in self._nodes}
        adjacency: Dict[str, List[str]] = defaultdict(list)
        for conn in self._connections:
            adjacency[conn.source_node.name].append(conn.target_node.name)

        def dfs(name: str) -> bool:
            color[name] = GRAY
            for neighbor in adjacency[name]:
                if color[neighbor] == GRAY:
                    return True
                if color[neighbor] == WHITE and dfs(neighbor):
                    return True
            color[name] = BLACK
            return False

        for name in self._nodes:
            if color[name] == WHITE:
                if dfs(name):
                    return True
        return False

    def __len__(self) -> int:
        return len(self._nodes)

    def __repr__(self) -> str:
        return f"<Graph nodes={len(self._nodes)} connections={len(self._connections)}>"
