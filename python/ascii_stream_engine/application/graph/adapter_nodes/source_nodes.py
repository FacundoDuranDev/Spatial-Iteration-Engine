"""Source adapter nodes — wrap FrameSource implementations as SourceNode."""

from typing import Any, Dict, Type

from ..nodes.source_node import SourceNode


def _make_source_node(source_class: type) -> Type[SourceNode]:
    """Generate a SourceNode subclass that delegates to a source adapter."""

    class AdapterSourceNode(SourceNode):
        name = getattr(source_class, "name", source_class.__name__)

        def __init__(self, **kwargs):
            super().__init__()
            self._impl = source_class(**kwargs)

        def read_frame(self) -> Any:
            return self._impl.read()

        def setup(self) -> None:
            self._impl.open()

        def teardown(self) -> None:
            self._impl.close()

        @property
        def adapter(self):
            return self._impl

    AdapterSourceNode.__name__ = f"{source_class.__name__}Node"
    AdapterSourceNode.__qualname__ = f"{source_class.__name__}Node"
    return AdapterSourceNode


def _build_source_nodes() -> Dict[str, Type[SourceNode]]:
    nodes: Dict[str, Type[SourceNode]] = {}
    try:
        from ....adapters.sources import OpenCVCameraSource, VideoFileSource

        for cls in [OpenCVCameraSource, VideoFileSource]:
            nodes[cls.__name__] = _make_source_node(cls)
    except ImportError:
        pass
    return nodes


SOURCE_NODE_CLASSES = _build_source_nodes()
