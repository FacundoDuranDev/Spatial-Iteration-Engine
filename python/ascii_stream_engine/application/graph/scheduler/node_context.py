"""NodeContext — per-frame context passed to each node during execution."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class NodeContext:
    """Context available to nodes during graph execution.

    Holds per-frame state like timestamp, frame_id, and accumulated analysis.
    """

    timestamp: float = 0.0
    frame_id: str = ""
    analysis: Dict[str, Any] = field(default_factory=dict)
    tracking: Optional[Any] = None
