"""Analyzer adapter nodes — wrap perception analyzers as AnalyzerNode."""

from typing import Any, Dict, Type

from ..nodes.analyzer_node import AnalyzerNode


def _make_analyzer_node(analyzer_class: type) -> Type[AnalyzerNode]:
    """Generate an AnalyzerNode subclass that delegates to an analyzer adapter."""

    class AdapterAnalyzerNode(AnalyzerNode):
        name = getattr(analyzer_class, "name", analyzer_class.__name__)

        def __init__(self, **kwargs):
            super().__init__()
            self._impl = analyzer_class(**kwargs)
            self.enabled = getattr(self._impl, "enabled", True)

        def analyze(self, frame: Any) -> dict:
            return self._impl.analyze(frame, self.config)

        @property
        def adapter(self):
            return self._impl

    AdapterAnalyzerNode.__name__ = f"{analyzer_class.__name__}Node"
    AdapterAnalyzerNode.__qualname__ = f"{analyzer_class.__name__}Node"
    return AdapterAnalyzerNode


def _build_analyzer_nodes() -> Dict[str, Type[AnalyzerNode]]:
    nodes: Dict[str, Type[AnalyzerNode]] = {}
    try:
        from ....adapters.perception import (
            FaceLandmarkAnalyzer,
            HandGestureAnalyzer,
            HandLandmarkAnalyzer,
            PoseLandmarkAnalyzer,
            PoseSkeletonAnalyzer,
        )

        for cls in [
            FaceLandmarkAnalyzer,
            HandGestureAnalyzer,
            HandLandmarkAnalyzer,
            PoseLandmarkAnalyzer,
            PoseSkeletonAnalyzer,
        ]:
            nodes[cls.__name__] = _make_analyzer_node(cls)
    except ImportError:
        pass
    return nodes


ANALYZER_NODE_CLASSES = _build_analyzer_nodes()
