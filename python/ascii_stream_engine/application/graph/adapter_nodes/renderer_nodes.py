"""Renderer adapter nodes — wrap renderers as RendererNode."""

from typing import Any, Dict, Type

from ..nodes.renderer_node import RendererNode


def _make_renderer_node(renderer_class: type) -> Type[RendererNode]:
    """Generate a RendererNode subclass that delegates to a renderer adapter."""

    class AdapterRendererNode(RendererNode):
        name = getattr(renderer_class, "name", renderer_class.__name__)

        def __init__(self, **kwargs):
            super().__init__()
            self._impl = renderer_class(**kwargs)

        def render(self, frame: Any, config: Any, analysis: Any) -> Any:
            return self._impl.render(frame, config, analysis)

        def output_size(self, config: Any):
            return self._impl.output_size(config)

        @property
        def adapter(self):
            return self._impl

    AdapterRendererNode.__name__ = f"{renderer_class.__name__}Node"
    AdapterRendererNode.__qualname__ = f"{renderer_class.__name__}Node"
    return AdapterRendererNode


def _build_renderer_nodes() -> Dict[str, Type[RendererNode]]:
    nodes: Dict[str, Type[RendererNode]] = {}
    try:
        from ....adapters.renderers import (
            AsciiRenderer,
            LandmarksOverlayRenderer,
            PassthroughRenderer,
        )

        for cls in [AsciiRenderer, LandmarksOverlayRenderer, PassthroughRenderer]:
            nodes[cls.__name__] = _make_renderer_node(cls)
    except ImportError:
        pass

    # C++ renderer (optional)
    try:
        from ....adapters.renderers import CppDeformedRenderer

        nodes["CppDeformedRenderer"] = _make_renderer_node(CppDeformedRenderer)
    except ImportError:
        pass

    return nodes


RENDERER_NODE_CLASSES = _build_renderer_nodes()
