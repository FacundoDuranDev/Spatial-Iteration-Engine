"""Transform adapter nodes — wrap spatial transforms as TransformNode."""

from typing import Any, Dict, Type

from ..nodes.transform_node import TransformNode


def _make_transform_node(transform_class: type) -> Type[TransformNode]:
    """Generate a TransformNode subclass that delegates to a transform adapter."""

    class AdapterTransformNode(TransformNode):
        name = getattr(transform_class, "name", transform_class.__name__)

        def __init__(self, **kwargs):
            super().__init__()
            self._impl = transform_class(**kwargs)

        def transform(self, frame: Any) -> Any:
            return self._impl.transform(frame)

        @property
        def adapter(self):
            return self._impl

    AdapterTransformNode.__name__ = f"{transform_class.__name__}Node"
    AdapterTransformNode.__qualname__ = f"{transform_class.__name__}Node"
    return AdapterTransformNode


def _build_transform_nodes() -> Dict[str, Type[TransformNode]]:
    nodes: Dict[str, Type[TransformNode]] = {}
    try:
        from ....adapters.transformations import (
            BlendTransformer,
            ProjectionMapper,
            WarpTransformer,
        )

        for cls in [ProjectionMapper, WarpTransformer, BlendTransformer]:
            nodes[cls.__name__] = _make_transform_node(cls)
    except ImportError:
        pass
    return nodes


TRANSFORM_NODE_CLASSES = _build_transform_nodes()
