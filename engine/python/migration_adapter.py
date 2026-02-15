"""Compatibility adapter from legacy pipelines to runtime graph IR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from .runtime_graph import (
    ClockMode,
    FrameClockConfig,
    NodeBackend,
    ResourceKind,
    ResourceSpec,
    RuntimeEdgeSpec,
    RuntimeExecutionConfig,
    RuntimeGraphSpec,
    RuntimeNodeSpec,
)


@dataclass(frozen=True)
class AdapterOptions:
    """Configuration for legacy-to-runtime graph adaptation."""

    width: int = 1280
    height: int = 720
    target_fps: float = 60.0
    clock_mode: ClockMode = ClockMode.FIXED
    ensure_mvp_blur: bool = True
    ensure_mvp_feedback: bool = True
    feedback_mix: float = 0.85
    feedback_decay: float = 0.98
    blur_sigma: float = 2.0


class LegacyPipelineToGraphAdapter:
    """Builds RuntimeGraphSpec from current pipeline objects."""

    _TRANSFORM_OPS: Dict[str, str] = {
        "warp_transformer": "warp",
        "projection_mapper": "warp_perspective",
        "blend_transformer": "mix",
    }

    _FILTER_OPS: Dict[str, str] = {
        "brightness": "color_gain_offset",
        "invert": "invert",
        "edges": "edge_detect",
        "detail_boost": "unsharp_mask",
        "blur": "blur",
        "gaussian_blur": "blur",
    }

    def __init__(self, options: Optional[AdapterOptions] = None) -> None:
        self._options = options or AdapterOptions()

    def build_from_pipelines(
        self,
        transformations: Optional[Any] = None,
        filters: Optional[Any] = None,
    ) -> RuntimeGraphSpec:
        """Converts legacy transformation/filter pipelines to runtime graph."""
        nodes: List[RuntimeNodeSpec] = []
        edges: List[RuntimeEdgeSpec] = []

        source_node = RuntimeNodeSpec(
            node_id="input_camera",
            op_type="source.camera",
            backend=NodeBackend.IO,
            input_slots=[],
            output_slots=["frame"],
        )
        nodes.append(source_node)
        previous_node_id = source_node.node_id
        previous_slot = "frame"

        transform_nodes = self._build_transform_nodes(transformations)
        for node in transform_nodes:
            nodes.append(node)
            edges.append(
                RuntimeEdgeSpec(
                    src_node=previous_node_id,
                    src_slot=previous_slot,
                    dst_node=node.node_id,
                    dst_slot="in",
                )
            )
            previous_node_id = node.node_id
            previous_slot = "out"

        filter_nodes = self._build_filter_nodes(filters)
        for node in filter_nodes:
            nodes.append(node)
            edges.append(
                RuntimeEdgeSpec(
                    src_node=previous_node_id,
                    src_slot=previous_slot,
                    dst_node=node.node_id,
                    dst_slot="in",
                )
            )
            previous_node_id = node.node_id
            previous_slot = "out"

        has_blur = any(node.op_type == "blur" for node in nodes)
        if self._options.ensure_mvp_blur and not has_blur:
            blur_node = RuntimeNodeSpec(
                node_id="mvp_blur",
                op_type="blur",
                backend=NodeBackend.GPU,
                input_slots=["in"],
                output_slots=["out"],
                params={"sigma": self._options.blur_sigma},
            )
            nodes.append(blur_node)
            edges.append(
                RuntimeEdgeSpec(
                    src_node=previous_node_id,
                    src_slot=previous_slot,
                    dst_node=blur_node.node_id,
                    dst_slot="in",
                )
            )
            previous_node_id = blur_node.node_id
            previous_slot = "out"

        feedback_node_id: Optional[str] = None
        if self._options.ensure_mvp_feedback:
            feedback_node = RuntimeNodeSpec(
                node_id="mvp_feedback",
                op_type="feedback",
                backend=NodeBackend.GPU,
                input_slots=["in", "history"],
                output_slots=["out"],
                stateful=True,
                params={
                    "mix": self._options.feedback_mix,
                    "decay": self._options.feedback_decay,
                },
            )
            nodes.append(feedback_node)
            edges.append(
                RuntimeEdgeSpec(
                    src_node=previous_node_id,
                    src_slot=previous_slot,
                    dst_node=feedback_node.node_id,
                    dst_slot="in",
                )
            )
            edges.append(
                RuntimeEdgeSpec(
                    src_node=feedback_node.node_id,
                    src_slot="out",
                    dst_node=feedback_node.node_id,
                    dst_slot="history",
                    feedback=True,
                    delay_frames=1,
                )
            )
            feedback_node_id = feedback_node.node_id
            previous_node_id = feedback_node.node_id
            previous_slot = "out"

        sink_node = RuntimeNodeSpec(
            node_id="output_present",
            op_type="sink.present",
            backend=NodeBackend.IO,
            input_slots=["in"],
            output_slots=["out"],
        )
        nodes.append(sink_node)
        edges.append(
            RuntimeEdgeSpec(
                src_node=previous_node_id,
                src_slot=previous_slot,
                dst_node=sink_node.node_id,
                dst_slot="in",
            )
        )

        resources = [
            ResourceSpec(
                resource_id="input_main",
                kind=ResourceKind.TEXTURE_2D,
                width=self._options.width,
                height=self._options.height,
                format="rgba8",
                persistent=True,
            ),
            ResourceSpec(
                resource_id="processing_main",
                kind=ResourceKind.TEXTURE_2D,
                width=self._options.width,
                height=self._options.height,
                format="rgba8",
                persistent=True,
            ),
            ResourceSpec(
                resource_id="output_main",
                kind=ResourceKind.TEXTURE_2D,
                width=self._options.width,
                height=self._options.height,
                format="rgba8",
                persistent=True,
            ),
        ]
        if feedback_node_id:
            resources.append(
                ResourceSpec(
                    resource_id="feedback_prev",
                    kind=ResourceKind.TEXTURE_2D,
                    width=self._options.width,
                    height=self._options.height,
                    format="rgba8",
                    persistent=True,
                )
            )

        graph = RuntimeGraphSpec(
            nodes=nodes,
            edges=edges,
            resources=resources,
            clock=FrameClockConfig(
                mode=self._options.clock_mode,
                target_fps=self._options.target_fps,
            ),
            execution=RuntimeExecutionConfig(
                deterministic=True,
                input_ring_size=3,
                processing_pool_size=6,
                output_ring_size=3,
                allow_dynamic_resolution=True,
            ),
            metadata={"generated_by": "LegacyPipelineToGraphAdapter"},
        )
        graph.validate()
        return graph

    def build_mvp_graph(self) -> RuntimeGraphSpec:
        """Builds a canonical warp->blur->feedback graph for MVP runtime."""
        nodes = [
            RuntimeNodeSpec(
                node_id="input_camera",
                op_type="source.camera",
                backend=NodeBackend.IO,
                input_slots=[],
                output_slots=["frame"],
            ),
            RuntimeNodeSpec(
                node_id="warp",
                op_type="warp",
                backend=NodeBackend.GPU,
                input_slots=["in"],
                output_slots=["out"],
                params={"mode": "perspective"},
            ),
            RuntimeNodeSpec(
                node_id="blur",
                op_type="blur",
                backend=NodeBackend.GPU,
                input_slots=["in"],
                output_slots=["out"],
                params={"sigma": self._options.blur_sigma},
            ),
            RuntimeNodeSpec(
                node_id="feedback",
                op_type="feedback",
                backend=NodeBackend.GPU,
                input_slots=["in", "history"],
                output_slots=["out"],
                params={
                    "mix": self._options.feedback_mix,
                    "decay": self._options.feedback_decay,
                },
                stateful=True,
            ),
            RuntimeNodeSpec(
                node_id="output_present",
                op_type="sink.present",
                backend=NodeBackend.IO,
                input_slots=["in"],
                output_slots=["out"],
            ),
        ]
        edges = [
            RuntimeEdgeSpec("input_camera", "frame", "warp", "in"),
            RuntimeEdgeSpec("warp", "out", "blur", "in"),
            RuntimeEdgeSpec("blur", "out", "feedback", "in"),
            RuntimeEdgeSpec("feedback", "out", "feedback", "history", feedback=True, delay_frames=1),
            RuntimeEdgeSpec("feedback", "out", "output_present", "in"),
        ]
        graph = RuntimeGraphSpec(
            nodes=nodes,
            edges=edges,
            resources=[
                ResourceSpec(
                    resource_id="input_main",
                    kind=ResourceKind.TEXTURE_2D,
                    width=self._options.width,
                    height=self._options.height,
                    format="rgba8",
                ),
                ResourceSpec(
                    resource_id="processing_main",
                    kind=ResourceKind.TEXTURE_2D,
                    width=self._options.width,
                    height=self._options.height,
                    format="rgba8",
                ),
                ResourceSpec(
                    resource_id="feedback_prev",
                    kind=ResourceKind.TEXTURE_2D,
                    width=self._options.width,
                    height=self._options.height,
                    format="rgba8",
                ),
                ResourceSpec(
                    resource_id="output_main",
                    kind=ResourceKind.TEXTURE_2D,
                    width=self._options.width,
                    height=self._options.height,
                    format="rgba8",
                ),
            ],
            clock=FrameClockConfig(
                mode=self._options.clock_mode,
                target_fps=self._options.target_fps,
            ),
            execution=RuntimeExecutionConfig(
                deterministic=True,
                input_ring_size=3,
                processing_pool_size=6,
                output_ring_size=3,
                allow_dynamic_resolution=True,
            ),
            metadata={"profile": "mvp_warp_blur_feedback"},
        )
        graph.validate()
        return graph

    def _build_transform_nodes(self, transformations: Optional[Any]) -> List[RuntimeNodeSpec]:
        items = self._extract_items(transformations, "transforms")
        nodes: List[RuntimeNodeSpec] = []
        for index, item in enumerate(items, start=1):
            name = self._item_name(item)
            op_type = self._TRANSFORM_OPS.get(name, f"legacy_transform.{name}")
            backend = NodeBackend.GPU if op_type in {"warp", "warp_perspective", "mix"} else NodeBackend.CPU
            nodes.append(
                RuntimeNodeSpec(
                    node_id=f"transform_{index:02d}_{name}",
                    op_type=op_type,
                    backend=backend,
                    input_slots=["in"],
                    output_slots=["out"],
                    params=self._extract_params(item),
                    stateful=False,
                )
            )
        return nodes

    def _build_filter_nodes(self, filters: Optional[Any]) -> List[RuntimeNodeSpec]:
        items = self._extract_items(filters, "filters")
        nodes: List[RuntimeNodeSpec] = []
        for index, item in enumerate(items, start=1):
            name = self._item_name(item)
            op_type = self._FILTER_OPS.get(name, f"legacy_filter.{name}")
            backend = NodeBackend.GPU if not op_type.startswith("legacy_filter.") else NodeBackend.CPU
            nodes.append(
                RuntimeNodeSpec(
                    node_id=f"filter_{index:02d}_{name}",
                    op_type=op_type,
                    backend=backend,
                    input_slots=["in"],
                    output_slots=["out"],
                    params=self._extract_params(item),
                    stateful=False,
                )
            )
        return nodes

    @staticmethod
    def _extract_items(pipeline: Optional[Any], attr_name: str) -> List[Any]:
        if pipeline is None:
            return []
        snapshot = getattr(pipeline, "snapshot", None)
        if callable(snapshot):
            items = snapshot()
        else:
            items = getattr(pipeline, attr_name, [])
        return [item for item in list(items) if LegacyPipelineToGraphAdapter._is_enabled(item)]

    @staticmethod
    def _is_enabled(item: Any) -> bool:
        enabled = getattr(item, "enabled", True)
        return bool(enabled)

    @staticmethod
    def _item_name(item: Any) -> str:
        raw_name = getattr(item, "name", item.__class__.__name__)
        return str(raw_name).strip().lower()

    @staticmethod
    def _extract_params(item: Any) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in vars(item).items():
            if key.startswith("_"):
                # Keep internal scalar tuning parameters as they are often runtime-relevant.
                if key.startswith("__"):
                    continue
                normalized = key.lstrip("_")
            else:
                normalized = key

            if isinstance(value, (bool, int, float, str)):
                result[normalized] = value
            elif isinstance(value, tuple) and all(isinstance(v, (int, float)) for v in value):
                result[normalized] = list(value)
        return result
