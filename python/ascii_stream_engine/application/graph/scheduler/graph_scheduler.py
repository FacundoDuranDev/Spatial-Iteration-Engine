"""GraphScheduler — executes a graph of nodes in topological order.

Single execution path of StreamEngine: one frame per tick, scheduled across
the DAG produced by GraphBuilder.
"""

import logging
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from ..core.base_node import BaseNode
from ..core.graph import Graph
from ..nodes.analyzer_node import AnalyzerNode
from ..nodes.composite_node import CompositeNode
from ..nodes.mosaic_node import MosaicFilterNode
from ..nodes.output_node import OutputNode
from ..nodes.processor_node import ProcessorNode
from ..nodes.render_composite_node import RenderFrameCompositeNode
from ..nodes.renderer_node import RendererNode
from ..nodes.source_node import SourceNode
from ..nodes.spatial_map_node import SpatialMapNode
from ..nodes.spatial_smoothing_node import SpatialSmoothingNode
from ..nodes.tracker_node import TrackerNode
from ..nodes.transform_node import TransformNode
from ...pipeline.filter_context import FilterContext

logger = logging.getLogger(__name__)

# Map node types to profiler phase names
_NODE_PHASE_MAP = {
    SourceNode: "capture",
    AnalyzerNode: "analysis",
    TrackerNode: "analysis",
    SpatialMapNode: "analysis",
    SpatialSmoothingNode: "analysis",
    TransformNode: "transformation",
    ProcessorNode: "filtering",
    CompositeNode: "filtering",
    MosaicFilterNode: "filtering",
    RendererNode: "rendering",
    RenderFrameCompositeNode: "rendering",
    OutputNode: "writing",
}


def _phase_for_node(node: BaseNode) -> Optional[str]:
    """Return the profiler phase name for a node, or None if unknown."""
    for cls, phase in _NODE_PHASE_MAP.items():
        if isinstance(node, cls):
            return phase
    return None


class GraphScheduler:
    """Executes a graph of nodes in topological order.

    StreamEngine's sole execution backend: ``process_frame(frame, timestamp)``
    returns ``(success, error_message)`` and feeds the frame through the
    source → analyzers → trackers → transforms → filters → renderer → output
    chain as wired by GraphBuilder.
    """

    def __init__(
        self,
        graph: Graph,
        config: Any,
        temporal_manager: Any = None,
        event_bus: Any = None,
        profiler: Any = None,
        metrics: Any = None,
        parallel_analyzers: bool = False,
    ) -> None:
        self._graph = graph
        self._config = config
        self._temporal = temporal_manager
        self._event_bus = event_bus
        self._profiler = profiler
        self._metrics = metrics
        self._temporal_configured = False

        # Pre-compute execution order and input maps
        self._execution_order: List[BaseNode] = graph.get_execution_order()
        self._input_map: Dict[str, List[Tuple[str, str, str]]] = {}
        for node in self._execution_order:
            conns = graph.get_connections_to(node)
            self._input_map[node.name] = [
                (c.source_node.name, c.source_port, c.target_port) for c in conns
            ]

        # Pre-compute fan-out ports (src_name, src_port) that feed 2+ consumers
        self._fan_out_ports: Set[Tuple[str, str]] = self._detect_fan_out_ports()

        # Per-frame output store
        self._outputs: Dict[str, Dict[str, Any]] = {}
        self._last_analysis: Dict[str, Any] = {}
        self._frame_id_counter = 0

        # Per-node timing (Step 1)
        self._node_timings: Dict[str, float] = {}

        # Identify processor nodes for temporal configuration
        self._processor_nodes = [
            n for n in self._execution_order if isinstance(n, ProcessorNode)
        ]

        # Parallel analyzer execution (Step 5)
        self._parallel_analyzers = parallel_analyzers
        self._parallel_groups: List[List[int]] = []
        self._parallel_node_indices: Set[int] = set()
        if parallel_analyzers:
            self._parallel_groups = self._detect_parallel_groups()
            for group in self._parallel_groups:
                for idx in group:
                    self._parallel_node_indices.add(idx)

    def _detect_parallel_groups(self) -> List[List[int]]:
        """Find groups of consecutive AnalyzerNodes that share the same predecessors."""
        groups: List[List[int]] = []
        current_group: List[int] = []
        current_preds: Optional[frozenset] = None

        for i, node in enumerate(self._execution_order):
            if isinstance(node, AnalyzerNode):
                preds = frozenset(
                    src_name for src_name, _, _ in self._input_map.get(node.name, [])
                )
                if current_group and preds == current_preds:
                    current_group.append(i)
                else:
                    if len(current_group) >= 2:
                        groups.append(current_group)
                    current_group = [i]
                    current_preds = preds
            else:
                if len(current_group) >= 2:
                    groups.append(current_group)
                current_group = []
                current_preds = None

        if len(current_group) >= 2:
            groups.append(current_group)

        return groups

    def _detect_fan_out_ports(self) -> Set[Tuple[str, str]]:
        """Find (node_name, port_name) pairs connected to 2+ consumers."""
        consumer_count: Dict[Tuple[str, str], int] = defaultdict(int)
        for conns in self._input_map.values():
            for src_name, src_port, _ in conns:
                consumer_count[(src_name, src_port)] += 1
        return {key for key, count in consumer_count.items() if count >= 2}

    def _apply_fan_out_safety(self, node_name: str, outputs: Dict[str, Any]) -> None:
        """Mark ndarray outputs as read-only when they feed multiple consumers."""
        import numpy as np

        for port_name, value in outputs.items():
            if (node_name, port_name) in self._fan_out_ports:
                if isinstance(value, np.ndarray) and value.flags.writeable:
                    value.flags.writeable = False

    def setup(self) -> None:
        """Initialize all nodes."""
        for node in self._execution_order:
            try:
                node.setup()
            except Exception as e:
                logger.warning("Node %s setup failed: %s", node.name, e)

    def teardown(self) -> None:
        """Tear down all nodes."""
        for node in reversed(self._execution_order):
            try:
                node.teardown()
            except Exception as e:
                logger.warning("Node %s teardown failed: %s", node.name, e)

    def process_frame(
        self,
        frame: Any = None,
        timestamp: Optional[float] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Process one frame through the graph.

        Args:
            frame: Input video frame (injected into the first SourceNode's output).
            timestamp: Frame timestamp.

        Returns:
            ``(success, error_message)``: ``success`` is False when a fatal
            node (source/renderer/output) raised; analyzer/filter failures
            are logged and swallowed, not propagated.
        """
        if timestamp is None:
            timestamp = time.time()

        self._frame_id_counter += 1
        frame_id = f"frame_{int(timestamp * 1000)}_{self._frame_id_counter}"

        # Start frame profiling
        if self._profiler:
            self._profiler.start_frame()

        # Temporal: begin new frame
        if self._temporal:
            self._temporal.begin_frame()

        # Configure temporal on first frame
        if self._temporal and not self._temporal_configured:
            self._temporal.configure(self._processor_nodes)
            self._temporal_configured = True

        # Clear per-frame state
        self._outputs.clear()
        self._node_timings.clear()
        analysis: Dict[str, Any] = {}

        current_phase: Optional[str] = None
        phase_start_time: float = 0.0

        def _end_current_phase() -> None:
            """End the current profiler phase and publish its event."""
            nonlocal current_phase, phase_start_time
            if current_phase is not None:
                phase_duration = time.perf_counter() - phase_start_time
                if self._profiler:
                    self._profiler.end_phase(current_phase)
                self._publish_phase_event(
                    current_phase, frame_id, timestamp, phase_duration, analysis
                )
                current_phase = None

        def _ensure_phase(phase: str) -> None:
            """Transition to a new phase if different from current."""
            nonlocal current_phase, phase_start_time
            if phase == current_phase:
                return
            _end_current_phase()
            current_phase = phase
            phase_start_time = time.perf_counter()
            if self._profiler:
                self._profiler.start_phase(phase)

        for i, node in enumerate(self._execution_order):
            # Skip nodes that are part of a parallel group (handled when group leader hit)
            if i in self._parallel_node_indices:
                group = self._find_group_for_index(i)
                if group is not None and i == group[0]:
                    # This is the group leader — execute the whole group
                    _ensure_phase("analysis")
                    self._execute_parallel_group(group, frame, analysis)
                    continue
                elif group is not None:
                    # Already executed as part of group leader
                    continue

            if not node.enabled:
                self._passthrough_disabled(node)
                continue

            # Transition profiler phase
            node_phase = _phase_for_node(node)
            if node_phase is not None:
                _ensure_phase(node_phase)

            # Inject config
            node.config = self._config

            # Resolve inputs from upstream outputs
            inputs = self._resolve_inputs(node, frame, analysis)

            # SourceNode with external frame: already handled by _resolve_inputs
            if isinstance(node, SourceNode) and frame is not None:
                self._apply_fan_out_safety(node.name, self._outputs.get(node.name, {}))
                continue

            # For ProcessorNodes: push temporal input before first one
            if isinstance(node, ProcessorNode) and self._temporal:
                video_in = inputs.get("video_in")
                if video_in is not None:
                    # Only push once per frame (before first processor)
                    if node is self._processor_nodes[0]:
                        self._temporal.push_input(video_in)
                    # Wrap analysis as FilterContext for temporal access
                    inputs["analysis_in"] = FilterContext(
                        analysis, self._temporal
                    )

            # Execute node with timing
            node_start = time.perf_counter()
            try:
                outputs = node.process(inputs)
            except Exception as e:
                node_duration = time.perf_counter() - node_start
                self._node_timings[node.name] = node_duration
                error_category = _phase_for_node(node) or node.name
                # Fatal for renderer and output nodes
                if isinstance(node, (RendererNode, OutputNode)):
                    if self._metrics:
                        self._metrics.record_error(error_category)
                    _end_current_phase()
                    if self._profiler:
                        self._profiler.end_frame()
                    return False, f"Fatal error in {node.name}: {e}"
                # Non-fatal: log and passthrough
                logger.warning("Node %s failed: %s", node.name, e)
                if self._metrics:
                    self._metrics.record_error(error_category)
                self._passthrough_disabled(node)
                continue

            node_duration = time.perf_counter() - node_start
            self._node_timings[node.name] = node_duration

            # Store outputs and apply fan-out safety
            self._outputs[node.name] = outputs
            self._apply_fan_out_safety(node.name, outputs)

            # Collect analysis from analyzer nodes
            if isinstance(node, AnalyzerNode):
                analysis_out = outputs.get("analysis_out", {})
                analysis.update(analysis_out)

            # Collect tracking data
            if isinstance(node, TrackerNode):
                tracking = outputs.get("tracking_out")
                if tracking is not None:
                    if hasattr(tracking, "to_dict"):
                        analysis["tracking"] = tracking.to_dict()
                    else:
                        analysis["tracking"] = tracking

            # Push temporal output after last processor
            if isinstance(node, ProcessorNode) and self._temporal:
                if node is self._processor_nodes[-1]:
                    video_out = outputs.get("video_out")
                    if video_out is not None:
                        self._temporal.push_output(video_out)

        # End final phase
        _end_current_phase()

        # Store analysis for external access
        analysis["timestamp"] = timestamp
        self._last_analysis = analysis

        # Record successful frame
        if self._metrics:
            self._metrics.record_frame()

        # End frame profiling
        if self._profiler:
            self._profiler.end_frame()

        return True, None

    def _publish_phase_event(
        self,
        phase: str,
        frame_id: str,
        timestamp: float,
        duration: float,
        analysis: Dict[str, Any],
    ) -> None:
        """Publish an event when a profiler phase ends."""
        if not self._event_bus:
            return

        from ....domain.events import (
            AnalysisCompleteEvent,
            FilterAppliedEvent,
            FrameWrittenEvent,
            RenderCompleteEvent,
        )

        if phase == "analysis":
            event = AnalysisCompleteEvent(
                frame_id=frame_id,
                results=dict(analysis),
                analysis_time=duration,
                timestamp=timestamp,
            )
            self._event_bus.publish_async(event, "analysis_complete")
        elif phase == "filtering":
            event = FilterAppliedEvent(
                frame_id=frame_id,
                filter_name="graph_filters",
                filter_time=duration,
                timestamp=timestamp,
            )
            self._event_bus.publish_async(event, "filter_applied")
        elif phase == "rendering":
            event = RenderCompleteEvent(
                frame_id=frame_id,
                render_time=duration,
                timestamp=timestamp,
            )
            self._event_bus.publish_async(event, "render_complete")
        elif phase == "writing":
            event = FrameWrittenEvent(
                frame_id=frame_id,
                write_time=duration,
                timestamp=timestamp,
            )
            self._event_bus.publish_async(event, "frame_written")

    def _find_group_for_index(self, idx: int) -> Optional[List[int]]:
        """Find the parallel group containing the given index."""
        for group in self._parallel_groups:
            if idx in group:
                return group
        return None

    def _execute_parallel_group(
        self,
        group: List[int],
        frame: Any,
        analysis: Dict[str, Any],
    ) -> None:
        """Execute a group of analyzer nodes in parallel."""
        nodes = [self._execution_order[i] for i in group]

        # Filter to enabled nodes only
        enabled_nodes = [n for n in nodes if n.enabled]
        disabled_nodes = [n for n in nodes if not n.enabled]

        # Passthrough disabled nodes
        for node in disabled_nodes:
            self._passthrough_disabled(node)

        if not enabled_nodes:
            return

        # Single analyzer — skip thread pool
        if len(enabled_nodes) == 1:
            node = enabled_nodes[0]
            node.config = self._config
            inputs = self._resolve_inputs(node, frame, analysis)
            node_start = time.perf_counter()
            try:
                outputs = node.process(inputs)
            except Exception as e:
                self._node_timings[node.name] = time.perf_counter() - node_start
                logger.warning("Node %s failed: %s", node.name, e)
                if self._metrics:
                    self._metrics.record_error(_phase_for_node(node) or node.name)
                self._passthrough_disabled(node)
                return
            self._node_timings[node.name] = time.perf_counter() - node_start
            self._outputs[node.name] = outputs
            self._apply_fan_out_safety(node.name, outputs)
            analysis_out = outputs.get("analysis_out", {})
            analysis.update(analysis_out)
            return

        # Pre-set config and resolve inputs on main thread
        all_inputs = {}
        for node in enabled_nodes:
            node.config = self._config
            all_inputs[node.name] = self._resolve_inputs(node, frame, analysis)

        # Execute in parallel
        def _run_analyzer(node: AnalyzerNode, inputs: Dict[str, Any]) -> Tuple[str, Dict, float]:
            start = time.perf_counter()
            outputs = node.process(inputs)
            duration = time.perf_counter() - start
            return node.name, outputs, duration

        with ThreadPoolExecutor(max_workers=len(enabled_nodes)) as pool:
            futures = {
                pool.submit(_run_analyzer, node, all_inputs[node.name]): node
                for node in enabled_nodes
            }
            for future in as_completed(futures):
                node = futures[future]
                try:
                    name, outputs, duration = future.result()
                    self._node_timings[name] = duration
                    self._outputs[name] = outputs
                    self._apply_fan_out_safety(name, outputs)
                    analysis_out = outputs.get("analysis_out", {})
                    analysis.update(analysis_out)
                except Exception as e:
                    self._node_timings[node.name] = 0.0
                    logger.warning("Node %s failed: %s", node.name, e)
                    if self._metrics:
                        self._metrics.record_error(_phase_for_node(node) or node.name)
                    self._passthrough_disabled(node)

    def _resolve_inputs(
        self,
        node: BaseNode,
        external_frame: Any,
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Resolve inputs for a node from upstream outputs or external frame."""
        inputs: Dict[str, Any] = {}

        # SourceNode gets the external frame injected
        if isinstance(node, SourceNode):
            # Source nodes produce frames; for bridge mode, we inject the external frame
            # Store it as the source's output directly
            self._outputs[node.name] = {"video_out": external_frame}
            return {}

        connections = self._input_map.get(node.name, [])
        for src_name, src_port, tgt_port in connections:
            src_outputs = self._outputs.get(src_name, {})
            if src_port in src_outputs:
                inputs[tgt_port] = src_outputs[src_port]

        # For nodes that need analysis_in but aren't connected to an analyzer,
        # provide the accumulated analysis
        if node.get_input_port("analysis_in") is not None and "analysis_in" not in inputs:
            inputs["analysis_in"] = analysis

        return inputs

    def _passthrough_disabled(self, node: BaseNode) -> None:
        """For disabled nodes, pass through matching port types."""
        connections = self._input_map.get(node.name, [])
        outputs: Dict[str, Any] = {}

        for src_name, src_port, tgt_port in connections:
            src_outputs = self._outputs.get(src_name, {})
            if src_port in src_outputs:
                # Find matching output port by type
                in_port = node.get_input_port(tgt_port)
                if in_port is not None:
                    for out_port in node.get_output_ports():
                        if out_port.data_type == in_port.data_type:
                            outputs[out_port.name] = src_outputs[src_port]
                            break

        self._outputs[node.name] = outputs

    def get_node_timings(self) -> Dict[str, float]:
        """Get per-node timing data from the last frame."""
        return dict(self._node_timings)

    def get_last_analysis(self) -> Dict[str, Any]:
        """Return the most recent frame's merged analyzer output."""
        return dict(self._last_analysis)

    def get_node_output(self, node_name: str, port_name: str) -> Any:
        """Get a specific output value from the last processed frame.

        Args:
            node_name: Name of the node (node.name attribute).
            port_name: Name of the output port.

        Returns:
            The output value, or None if the node/port is not found.
        """
        return self._outputs.get(node_name, {}).get(port_name)

    def get_all_node_outputs(self, node_name: str) -> Dict[str, Any]:
        """Get all outputs from a node for the last processed frame.

        Args:
            node_name: Name of the node (node.name attribute).

        Returns:
            Dict mapping port name to value, or empty dict if node not found.
        """
        return dict(self._outputs.get(node_name, {}))

    def update_config(self, config: Any) -> None:
        """Update config for next frame."""
        self._config = config
