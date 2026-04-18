"""Factory-generated ProcessorNode subclasses for each filter adapter."""

from typing import Any, Dict, List, Type

from ..nodes.processor_node import ProcessorNode


def _make_filter_node(filter_class: type) -> Type[ProcessorNode]:
    """Generate a ProcessorNode subclass that delegates to a filter adapter.

    Copies temporal declarations so TemporalManager.configure() sees them.
    """

    class AdapterFilterNode(ProcessorNode):
        name = getattr(filter_class, "name", filter_class.__name__)
        required_input_history = getattr(filter_class, "required_input_history", 0)
        needs_optical_flow = getattr(filter_class, "needs_optical_flow", False)
        needs_delta_frame = getattr(filter_class, "needs_delta_frame", False)
        needs_previous_output = getattr(filter_class, "needs_previous_output", False)

        def __init__(self, **kwargs):
            super().__init__()
            self._impl = filter_class(**kwargs)
            self.enabled = self._impl.enabled

        def apply_filter(self, frame: Any, config: Any, analysis: Any) -> Any:
            return self._impl.apply(frame, config, analysis)

        @property
        def adapter(self):
            """Access the underlying adapter instance."""
            return self._impl

    AdapterFilterNode.__name__ = f"{filter_class.__name__}Node"
    AdapterFilterNode.__qualname__ = f"{filter_class.__name__}Node"
    return AdapterFilterNode


def _build_filter_nodes() -> Dict[str, Type[ProcessorNode]]:
    """Build node classes for all filter adapters. Graceful on ImportError."""
    nodes: Dict[str, Type[ProcessorNode]] = {}

    from ....adapters.processors.filters import (
        BaseFilter,
        BoidsFilter,
        BrightnessFilter,
        CRTGlitchFilter,
        DetailBoostFilter,
        EdgeFilter,
        EdgeSmoothFilter,
        GeometricPatternFilter,
        InvertFilter,
        OpticalFlowParticlesFilter,
        PhysarumFilter,
        RadialCollapseFilter,
        StipplingFilter,
        UVDisplacementFilter,
    )

    filter_classes: List[type] = [
        BoidsFilter,
        BrightnessFilter,
        CRTGlitchFilter,
        DetailBoostFilter,
        EdgeFilter,
        EdgeSmoothFilter,
        GeometricPatternFilter,
        InvertFilter,
        OpticalFlowParticlesFilter,
        PhysarumFilter,
        RadialCollapseFilter,
        StipplingFilter,
        UVDisplacementFilter,
    ]

    # C++ filters (optional, may not be compiled)
    for cls_name in [
        "CppBrightnessContrastFilter",
        "CppChannelSwapFilter",
        "CppGrayscaleFilter",
        "CppInvertFilter",
        "CppImageModifierFilter",
        "CppPhysarumFilter",
    ]:
        try:
            from ....adapters.processors.filters import __dict__ as _fmod
        except Exception:
            break
        import importlib

        mod = importlib.import_module("ascii_stream_engine.adapters.processors.filters")
        cls = getattr(mod, cls_name, None)
        if cls is not None and cls is not BaseFilter:
            filter_classes.append(cls)

    for cls in filter_classes:
        node_cls = _make_filter_node(cls)
        nodes[cls.__name__] = node_cls

    return nodes


FILTER_NODE_CLASSES = _build_filter_nodes()
