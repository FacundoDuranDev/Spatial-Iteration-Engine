"""Wire protocol for distributed metrics: JSON-over-UDP message format.

Messages are serialized as JSON with compact keys to fit within
UDP packet size limits (max 65000 bytes).
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Maximum UDP payload size (leaving margin from 65535)
MAX_MESSAGE_SIZE = 65000


@dataclass
class MetricsMessage:
    """Wire format for distributed metrics."""

    version: int = 1
    instance_id: str = ""
    timestamp: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)

    def serialize(self) -> bytes:
        """Serialize to JSON-encoded UTF-8 bytes.

        Uses compact keys to minimize size.

        Returns:
            UTF-8 encoded bytes (max MAX_MESSAGE_SIZE).

        Raises:
            ValueError: If serialized message exceeds MAX_MESSAGE_SIZE.
        """
        compact = {
            "v": self.version,
            "id": self.instance_id,
            "ts": self.timestamp,
            "m": self.metrics,
        }
        data = json.dumps(compact, separators=(",", ":")).encode("utf-8")
        if len(data) > MAX_MESSAGE_SIZE:
            raise ValueError(
                f"Serialized message exceeds max size: {len(data)} > {MAX_MESSAGE_SIZE}"
            )
        return data

    @classmethod
    def deserialize(cls, data: bytes) -> "MetricsMessage":
        """Deserialize from JSON-encoded UTF-8 bytes.

        Args:
            data: UTF-8 encoded bytes.

        Returns:
            MetricsMessage instance.

        Raises:
            ValueError: If data is invalid.
        """
        try:
            compact = json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"Invalid message data: {e}") from e

        return cls(
            version=compact.get("v", 1),
            instance_id=compact.get("id", ""),
            timestamp=compact.get("ts", 0.0),
            metrics=compact.get("m", {}),
        )

    @classmethod
    def create_now(cls, instance_id: str, metrics: Dict[str, Any]) -> "MetricsMessage":
        """Create a message with the current timestamp.

        Args:
            instance_id: Unique identifier for this engine instance.
            metrics: Metrics data dict.

        Returns:
            MetricsMessage with current perf_counter timestamp.
        """
        return cls(
            version=1,
            instance_id=instance_id,
            timestamp=time.perf_counter(),
            metrics=metrics,
        )
