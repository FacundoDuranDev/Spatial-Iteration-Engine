"""Maps adapter class instances to their corresponding graph node classes."""

import logging
import threading
from typing import Dict, Optional, Type

from ..core.base_node import BaseNode

logger = logging.getLogger(__name__)

# Registry: adapter class -> node class
_ADAPTER_TO_NODE: Dict[type, Type[BaseNode]] = {}
_registry_lock = threading.Lock()
_registry_built = False


def _build_registry() -> None:
    """Populate the registry from all adapter_nodes modules. Thread-safe."""
    global _registry_built
    if _registry_built:
        return
    with _registry_lock:
        if _registry_built:
            return

        from ..adapter_nodes.filter_nodes import FILTER_NODE_CLASSES
        from ..adapter_nodes.analyzer_nodes import ANALYZER_NODE_CLASSES
        from ..adapter_nodes.renderer_nodes import RENDERER_NODE_CLASSES
        from ..adapter_nodes.source_nodes import SOURCE_NODE_CLASSES
        from ..adapter_nodes.output_nodes import OUTPUT_NODE_CLASSES
        from ..adapter_nodes.tracker_nodes import TRACKER_NODE_CLASSES
        from ..adapter_nodes.transform_nodes import TRANSFORM_NODE_CLASSES

        all_mappings = {}
        all_mappings.update(FILTER_NODE_CLASSES)
        all_mappings.update(ANALYZER_NODE_CLASSES)
        all_mappings.update(RENDERER_NODE_CLASSES)
        all_mappings.update(SOURCE_NODE_CLASSES)
        all_mappings.update(OUTPUT_NODE_CLASSES)
        all_mappings.update(TRACKER_NODE_CLASSES)
        all_mappings.update(TRANSFORM_NODE_CLASSES)

        for adapter_name, node_cls in all_mappings.items():
            _ADAPTER_TO_NODE[adapter_name] = node_cls

        _registry_built = True
        logger.debug("Adapter registry built: %d mappings", len(_ADAPTER_TO_NODE))


def get_node_class(adapter_class_name: str) -> Optional[Type[BaseNode]]:
    """Look up the node class for an adapter class name."""
    _build_registry()
    return _ADAPTER_TO_NODE.get(adapter_class_name)


def get_node_for_adapter(adapter_instance: object) -> Optional[Type[BaseNode]]:
    """Look up the node class for an adapter instance, walking MRO."""
    _build_registry()
    for cls in type(adapter_instance).__mro__:
        node_cls = _ADAPTER_TO_NODE.get(cls.__name__)
        if node_cls is not None:
            return node_cls
    return None


def get_all_mappings() -> Dict[str, Type[BaseNode]]:
    """Get all adapter->node mappings (for debugging)."""
    _build_registry()
    return dict(_ADAPTER_TO_NODE)
