"""Tracker adapter nodes — wrap tracker implementations as TrackerNode."""

from typing import Any, Dict, Type

from ..nodes.tracker_node import TrackerNode


def _make_tracker_node(tracker_class: type) -> Type[TrackerNode]:
    """Generate a TrackerNode subclass that delegates to a tracker adapter."""

    class AdapterTrackerNode(TrackerNode):
        name = getattr(tracker_class, "name", tracker_class.__name__)

        def __init__(self, **kwargs):
            super().__init__()
            self._impl = tracker_class(**kwargs)
            self.enabled = getattr(self._impl, "enabled", True)

        def track(self, frame: Any, detections: dict, config: Any) -> Any:
            return self._impl.track(frame, detections, config)

        def reset(self) -> None:
            if hasattr(self._impl, "reset"):
                self._impl.reset()

        @property
        def adapter(self):
            return self._impl

    AdapterTrackerNode.__name__ = f"{tracker_class.__name__}Node"
    AdapterTrackerNode.__qualname__ = f"{tracker_class.__name__}Node"
    return AdapterTrackerNode


def _build_tracker_nodes() -> Dict[str, Type[TrackerNode]]:
    nodes: Dict[str, Type[TrackerNode]] = {}
    try:
        from ....adapters.trackers import (
            KalmanTracker,
            MultiObjectTracker,
            OpenCVTracker,
        )

        for cls in [OpenCVTracker, KalmanTracker, MultiObjectTracker]:
            nodes[cls.__name__] = _make_tracker_node(cls)
    except ImportError:
        pass
    return nodes


TRACKER_NODE_CLASSES = _build_tracker_nodes()
