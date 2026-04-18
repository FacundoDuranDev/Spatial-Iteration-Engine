"""GraphBuilder — converts StreamEngine's pipeline objects to a Graph."""

import logging
from typing import Any, Dict, List, Optional, Type

from ..core.base_node import BaseNode
from ..core.graph import Graph
from ..core.port_types import InputPort, OutputPort, PortType
from ..nodes import (
    AnalyzerNode,
    OutputNode,
    ProcessorNode,
    RendererNode,
    SourceNode,
    TrackerNode,
    TransformNode,
)
from .adapter_registry import get_node_for_adapter

logger = logging.getLogger(__name__)


class AnalysisMergeNode(BaseNode):
    """Merges multiple analysis outputs into a single analysis dict.

    Dynamic ports: analysis_in_0..N, video_in -> video_out, analysis_out.
    """

    name = "analysis_merge"

    def __init__(self, num_analyzers: int) -> None:
        super().__init__()
        self._num_analyzers = num_analyzers

    def get_input_ports(self) -> List[InputPort]:
        ports = [InputPort("video_in", PortType.VIDEO_FRAME)]
        for i in range(self._num_analyzers):
            ports.append(
                InputPort(f"analysis_in_{i}", PortType.ANALYSIS_DATA, required=False)
            )
        return ports

    def get_output_ports(self) -> List[OutputPort]:
        return [
            OutputPort("video_out", PortType.VIDEO_FRAME),
            OutputPort("analysis_out", PortType.ANALYSIS_DATA),
        ]

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        for i in range(self._num_analyzers):
            data = inputs.get(f"analysis_in_{i}", {})
            if isinstance(data, dict):
                merged.update(data)
            elif data is not None:
                logger.warning(
                    "AnalysisMergeNode: analysis_in_%d is not a dict (got %s), skipping",
                    i, type(data).__name__,
                )
        return {
            "video_out": inputs.get("video_in"),
            "analysis_out": merged,
        }


class _ExternalSourceNode(SourceNode):
    """Placeholder source node for externally-provided frames."""

    name = "external_source"

    def read_frame(self):
        return None  # Frame is injected by scheduler


class _AdapterRendererNode(RendererNode):
    """Wraps an existing renderer adapter instance as a node."""

    name = "renderer"

    def __init__(self, renderer_instance: Any) -> None:
        super().__init__()
        self._impl = renderer_instance

    def render(self, frame: Any, config: Any, analysis: Any) -> Any:
        return self._impl.render(frame, config, analysis)


class _AdapterOutputNode(OutputNode):
    """Wraps an existing output sink adapter instance as a node."""

    name = "output"

    def __init__(self, sink_instance: Any) -> None:
        super().__init__()
        self._impl = sink_instance

    def write(self, rendered: Any) -> None:
        self._impl.write(rendered)


class _InstanceProcessorNode(ProcessorNode):
    """Wraps an existing filter adapter instance as a ProcessorNode."""

    def __init__(self, filter_instance: Any) -> None:
        super().__init__()
        self._impl = filter_instance
        self.name = getattr(filter_instance, "name", type(filter_instance).__name__)
        self.required_input_history = getattr(filter_instance, "required_input_history", 0)
        self.needs_optical_flow = getattr(filter_instance, "needs_optical_flow", False)
        self.needs_delta_frame = getattr(filter_instance, "needs_delta_frame", False)
        self.needs_previous_output = getattr(filter_instance, "needs_previous_output", False)

    @property
    def enabled(self):
        return getattr(self._impl, "enabled", True)

    @enabled.setter
    def enabled(self, value):
        if hasattr(self._impl, "enabled"):
            self._impl.enabled = value

    def apply_filter(self, frame: Any, config: Any, analysis: Any) -> Any:
        return self._impl.apply(frame, config, analysis)


class _InstanceAnalyzerNode(AnalyzerNode):
    """Wraps an existing analyzer adapter instance as an AnalyzerNode."""

    def __init__(self, analyzer_instance: Any) -> None:
        super().__init__()
        self._impl = analyzer_instance
        self.name = getattr(analyzer_instance, "name", type(analyzer_instance).__name__)

    @property
    def enabled(self):
        return getattr(self._impl, "enabled", True)

    @enabled.setter
    def enabled(self, value):
        if hasattr(self._impl, "enabled"):
            self._impl.enabled = value

    def analyze(self, frame: Any) -> dict:
        return self._impl.analyze(frame, self.config)


class _InstanceTrackerNode(TrackerNode):
    """Wraps an existing tracker adapter instance as a TrackerNode."""

    def __init__(self, tracker_instance: Any) -> None:
        super().__init__()
        self._impl = tracker_instance
        self.name = getattr(tracker_instance, "name", type(tracker_instance).__name__)

    @property
    def enabled(self):
        return getattr(self._impl, "enabled", True)

    @enabled.setter
    def enabled(self, value):
        if hasattr(self._impl, "enabled"):
            self._impl.enabled = value

    def track(self, frame: Any, detections: dict, config: Any) -> Any:
        return self._impl.track(frame, detections, config)


class _InstanceTransformNode(TransformNode):
    """Wraps an existing transform adapter instance as a TransformNode."""

    def __init__(self, transform_instance: Any) -> None:
        super().__init__()
        self._impl = transform_instance
        self.name = getattr(transform_instance, "name", type(transform_instance).__name__)

    def transform(self, frame: Any) -> Any:
        return self._impl.transform(frame)


class GraphBuilder:
    """Builds a Graph from StreamEngine's pipeline objects.

    Converts existing adapters (filters, analyzers, trackers, transforms,
    renderer, sink) into graph nodes connected in the correct pipeline order:
    Source -> Analyzers -> Merge -> Trackers -> Transforms -> Filters -> Renderer -> Output
    """

    @staticmethod
    def build(
        source: Any = None,
        renderer: Any = None,
        sink: Any = None,
        filters: Any = None,
        analyzers: Any = None,
        trackers: Any = None,
        transforms: Any = None,
    ) -> Graph:
        """Build a complete pipeline graph from adapter instances.

        Args:
            source: FrameSource instance (or None for external frame injection)
            renderer: FrameRenderer instance
            sink: OutputSink instance
            filters: FilterPipeline or list of Filter instances
            analyzers: AnalyzerPipeline or list of Analyzer instances
            trackers: TrackingPipeline or list of tracker instances
            transforms: TransformationPipeline or list of transform instances

        Returns:
            Configured Graph ready for GraphScheduler.
        """
        g = Graph()
        name_counter: Dict[str, int] = {}

        def unique_name(base: str) -> str:
            count = name_counter.get(base, 0)
            name_counter[base] = count + 1
            return f"{base}_{count}" if count > 0 else base

        # 1. Source node
        src_node = _ExternalSourceNode()
        g.add_node(src_node)
        last_video_node = src_node

        # 2. Analyzer nodes
        analyzer_list = _extract_list(analyzers, "analyzers")
        analyzer_nodes: List[AnalyzerNode] = []
        for analyzer in analyzer_list:
            node = _InstanceAnalyzerNode(analyzer)
            node.name = unique_name(node.name)
            analyzer_nodes.append(node)
            g.add_node(node)
            g.connect(last_video_node, "video_out", node, "video_in")

        # Merge analyzer outputs if any
        merge_node = None
        if len(analyzer_nodes) > 0:
            merge_node = AnalysisMergeNode(len(analyzer_nodes))
            g.add_node(merge_node)
            g.connect(analyzer_nodes[0], "video_out", merge_node, "video_in")
            for i, a_node in enumerate(analyzer_nodes):
                g.connect(a_node, "analysis_out", merge_node, f"analysis_in_{i}")
            last_video_node = merge_node

        # 3. Tracker nodes
        tracker_list = _extract_list(trackers, "trackers")
        if tracker_list and merge_node is None:
            raise ValueError(
                "Trackers require analysis data but no analyzers are configured. "
                "Add at least one analyzer to the pipeline."
            )
        for tracker in tracker_list:
            node = _InstanceTrackerNode(tracker)
            node.name = unique_name(node.name)
            g.add_node(node)
            g.connect(last_video_node, "video_out", node, "video_in")
            g.connect(merge_node, "analysis_out", node, "analysis_in")
            last_video_node = node

        # 4. Transform nodes
        transform_list = _extract_list(transforms, "transforms")
        for xform in transform_list:
            node = _InstanceTransformNode(xform)
            node.name = unique_name(node.name)
            g.add_node(node)
            g.connect(last_video_node, "video_out", node, "video_in")
            last_video_node = node

        # 5. Filter nodes
        filter_list = _extract_list(filters, "filters")
        for filt in filter_list:
            node = _InstanceProcessorNode(filt)
            node.name = unique_name(node.name)
            g.add_node(node)
            g.connect(last_video_node, "video_out", node, "video_in")
            if merge_node is not None:
                g.connect(merge_node, "analysis_out", node, "analysis_in")
            last_video_node = node

        # 6. Renderer node
        if renderer is not None:
            renderer_node = _AdapterRendererNode(renderer)
            g.add_node(renderer_node)
            g.connect(last_video_node, "video_out", renderer_node, "video_in")
            if merge_node is not None:
                g.connect(merge_node, "analysis_out", renderer_node, "analysis_in")

            # 7. Output node
            if sink is not None:
                output_node = _AdapterOutputNode(sink)
                g.add_node(output_node)
                g.connect(renderer_node, "render_out", output_node, "render_in")

        return g

    @staticmethod
    def add_branch(
        graph: Graph, from_node: BaseNode, from_port: str, *branch_nodes: BaseNode
    ) -> None:
        """Connect one output port to the video_in of multiple branch nodes (fan-out).

        Each branch_node must already be added to the graph and have a 'video_in' port.
        """
        for node in branch_nodes:
            graph.connect(from_node, from_port, node, "video_in")

    @staticmethod
    def add_composite(
        graph: Graph,
        node_a: BaseNode,
        port_a: str,
        node_b: BaseNode,
        port_b: str,
        composite: BaseNode,
    ) -> None:
        """Connect two nodes into a composite node's first two required inputs.

        The composite node must already be added to the graph. The first two
        required input ports (in declaration order) receive node_a:port_a and
        node_b:port_b respectively.
        """
        required_inputs = [p for p in composite.get_input_ports() if p.required]
        if len(required_inputs) < 2:
            raise ValueError(
                f"Composite node {composite.name!r} must have at least 2 required inputs"
            )
        graph.connect(node_a, port_a, composite, required_inputs[0].name)
        graph.connect(node_b, port_b, composite, required_inputs[1].name)

    @staticmethod
    def fan_out(
        graph: Graph,
        source_node: BaseNode,
        source_port: str,
        targets: List,
    ) -> None:
        """Connect one output port to multiple target (node, port) pairs.

        Args:
            graph: The graph to add connections to.
            source_node: Node providing the output.
            source_port: Output port name on source_node.
            targets: List of (target_node, target_port) tuples.
        """
        for target_node, target_port in targets:
            graph.connect(source_node, source_port, target_node, target_port)


def _extract_list(pipeline: Any, attr: str) -> list:
    """Extract a list of adapters from a pipeline or list."""
    if pipeline is None:
        return []
    if isinstance(pipeline, list):
        return pipeline
    # Pipeline objects have a snapshot() or list attribute
    if hasattr(pipeline, "snapshot"):
        return pipeline.snapshot()
    if hasattr(pipeline, attr):
        return getattr(pipeline, attr)
    return []
