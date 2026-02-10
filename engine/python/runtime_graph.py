"""Graph IR and execution config for realtime runtime control-plane."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Set, Tuple, Union

Scalar = Union[bool, int, float, str]
ParamValue = Union[Scalar, Sequence[Scalar]]


class ClockMode(str, Enum):
    """Frame clock modes."""

    FIXED = "fixed"
    ADAPTIVE = "adaptive"


class NodeBackend(str, Enum):
    """Execution backend declared by a node."""

    GPU = "gpu"
    CPU = "cpu"
    IO = "io"


class ResourceKind(str, Enum):
    """Runtime resource kinds."""

    TEXTURE_2D = "texture_2d"
    BUFFER = "buffer"


@dataclass(frozen=True)
class FrameClockConfig:
    """Clock configuration for per-frame execution."""

    mode: ClockMode = ClockMode.FIXED
    target_fps: float = 60.0
    min_fps: float = 24.0
    max_frame_skip: int = 0

    def validate(self) -> None:
        if self.target_fps <= 0:
            raise ValueError("target_fps must be > 0")
        if self.min_fps <= 0:
            raise ValueError("min_fps must be > 0")
        if self.min_fps > self.target_fps:
            raise ValueError("min_fps cannot be greater than target_fps")
        if self.max_frame_skip < 0:
            raise ValueError("max_frame_skip must be >= 0")


@dataclass(frozen=True)
class RuntimeExecutionConfig:
    """Runtime behavior constraints."""

    deterministic: bool = True
    input_ring_size: int = 3
    processing_pool_size: int = 6
    output_ring_size: int = 3
    allow_dynamic_resolution: bool = False

    def validate(self) -> None:
        if self.input_ring_size <= 0:
            raise ValueError("input_ring_size must be > 0")
        if self.processing_pool_size <= 0:
            raise ValueError("processing_pool_size must be > 0")
        if self.output_ring_size <= 0:
            raise ValueError("output_ring_size must be > 0")


@dataclass(frozen=True)
class ResourceSpec:
    """Declared resource managed by the runtime."""

    resource_id: str
    kind: ResourceKind
    width: int
    height: int
    format: str = "rgba8"
    persistent: bool = True

    def validate(self) -> None:
        if not self.resource_id:
            raise ValueError("resource_id is required")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("resource dimensions must be > 0")


@dataclass
class RuntimeNodeSpec:
    """Node declaration for scheduler and GPU dispatch."""

    node_id: str
    op_type: str
    backend: NodeBackend = NodeBackend.GPU
    input_slots: List[str] = field(default_factory=list)
    output_slots: List[str] = field(default_factory=list)
    params: Dict[str, ParamValue] = field(default_factory=dict)
    stateful: bool = False
    enabled: bool = True

    def validate(self) -> None:
        if not self.node_id:
            raise ValueError("node_id is required")
        if not self.op_type:
            raise ValueError("op_type is required")
        if not self.output_slots:
            raise ValueError(f"node '{self.node_id}' must define output_slots")
        if len(set(self.input_slots)) != len(self.input_slots):
            raise ValueError(f"node '{self.node_id}' has duplicate input_slots")
        if len(set(self.output_slots)) != len(self.output_slots):
            raise ValueError(f"node '{self.node_id}' has duplicate output_slots")


@dataclass(frozen=True)
class RuntimeEdgeSpec:
    """Connection between node slots."""

    src_node: str
    src_slot: str
    dst_node: str
    dst_slot: str
    feedback: bool = False
    delay_frames: int = 0

    def validate(self) -> None:
        if not self.src_node or not self.dst_node:
            raise ValueError("src_node and dst_node are required")
        if not self.src_slot or not self.dst_slot:
            raise ValueError("src_slot and dst_slot are required")
        if self.feedback and self.delay_frames < 1:
            raise ValueError("feedback edges must use delay_frames >= 1")
        if not self.feedback and self.delay_frames != 0:
            raise ValueError("non-feedback edges must use delay_frames == 0")


@dataclass
class RuntimeGraphSpec:
    """Complete graph description sent from Python to C++ runtime."""

    nodes: List[RuntimeNodeSpec] = field(default_factory=list)
    edges: List[RuntimeEdgeSpec] = field(default_factory=list)
    resources: List[ResourceSpec] = field(default_factory=list)
    clock: FrameClockConfig = field(default_factory=FrameClockConfig)
    execution: RuntimeExecutionConfig = field(default_factory=RuntimeExecutionConfig)
    metadata: Dict[str, ParamValue] = field(default_factory=dict)

    def validate(self) -> None:
        self.clock.validate()
        self.execution.validate()

        for resource in self.resources:
            resource.validate()
        resource_ids = [resource.resource_id for resource in self.resources]
        if len(resource_ids) != len(set(resource_ids)):
            raise ValueError("resource_id values must be unique")

        node_by_id: Dict[str, RuntimeNodeSpec] = {}
        for node in self.nodes:
            node.validate()
            if node.node_id in node_by_id:
                raise ValueError(f"duplicate node_id: {node.node_id}")
            node_by_id[node.node_id] = node

        for edge in self.edges:
            edge.validate()
            if edge.src_node not in node_by_id:
                raise ValueError(f"edge references unknown src_node '{edge.src_node}'")
            if edge.dst_node not in node_by_id:
                raise ValueError(f"edge references unknown dst_node '{edge.dst_node}'")

            src_node = node_by_id[edge.src_node]
            dst_node = node_by_id[edge.dst_node]
            if edge.src_slot not in src_node.output_slots:
                raise ValueError(
                    f"edge references missing src_slot '{edge.src_slot}' in node '{src_node.node_id}'"
                )
            if edge.dst_slot not in dst_node.input_slots:
                raise ValueError(
                    f"edge references missing dst_slot '{edge.dst_slot}' in node '{dst_node.node_id}'"
                )

        # The immediate graph (without delayed feedback edges) must remain acyclic.
        self.topological_order()

    def topological_order(self) -> List[str]:
        """Returns deterministic topological order excluding delayed feedback edges."""
        node_ids = [node.node_id for node in self.nodes if node.enabled]
        enabled: Set[str] = set(node_ids)

        adjacency: Dict[str, Set[str]] = {node_id: set() for node_id in node_ids}
        in_degree: Dict[str, int] = {node_id: 0 for node_id in node_ids}

        for edge in self.edges:
            if edge.src_node not in enabled or edge.dst_node not in enabled:
                continue
            if edge.feedback:
                continue
            adjacency[edge.src_node].add(edge.dst_node)

        for src_node, out_nodes in adjacency.items():
            del src_node
            for dst_node in out_nodes:
                in_degree[dst_node] += 1

        ready = sorted([node_id for node_id, degree in in_degree.items() if degree == 0])
        ordered: List[str] = []

        while ready:
            current = ready.pop(0)
            ordered.append(current)
            for dst in sorted(adjacency[current]):
                in_degree[dst] -= 1
                if in_degree[dst] == 0:
                    ready.append(dst)
            ready.sort()

        if len(ordered) != len(node_ids):
            raise ValueError("graph contains a non-feedback cycle")
        return ordered

    def enabled_node_count(self) -> int:
        return len([node for node in self.nodes if node.enabled])

    def edges_for_node(self, node_id: str) -> Tuple[List[RuntimeEdgeSpec], List[RuntimeEdgeSpec]]:
        """Returns incoming and outgoing edges for a node."""
        incoming = [edge for edge in self.edges if edge.dst_node == node_id]
        outgoing = [edge for edge in self.edges if edge.src_node == node_id]
        return incoming, outgoing
