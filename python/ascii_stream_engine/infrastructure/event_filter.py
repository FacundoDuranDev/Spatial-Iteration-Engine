"""Event filters for the EventBus.

Provides protocol and built-in implementations for filtering events
before delivery to subscribers.
"""

import logging
import time
from collections import defaultdict, deque
from typing import Protocol

from ..domain.events import BaseEvent

logger = logging.getLogger(__name__)


class EventFilter(Protocol):
    """Protocol for filtering events before delivery."""

    def should_deliver(self, event: BaseEvent, event_type: str) -> bool:
        """Determine whether an event should be delivered.

        Args:
            event: The event instance.
            event_type: The event type string.

        Returns:
            True if the event should be delivered, False to suppress it.
        """
        ...  # pragma: no cover


class RateLimitFilter:
    """Limits event delivery to N per second per event_type.

    Uses time.perf_counter() for accurate timing. Bounded history
    per event type using deque(maxlen).
    """

    def __init__(self, max_per_second: float = 10.0, max_tracked_types: int = 100) -> None:
        """Initialize the rate limit filter.

        Args:
            max_per_second: Maximum events per second per event type.
            max_tracked_types: Maximum number of event types to track.
        """
        self._max_per_second = max_per_second
        self._max_tracked_types = max_tracked_types
        self._window = 1.0 / max_per_second if max_per_second > 0 else 0.0
        # event_type -> deque of delivery timestamps (perf_counter)
        self._delivery_times: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=int(max_per_second) + 1)
        )

    def should_deliver(self, event: BaseEvent, event_type: str) -> bool:
        """Check if the event is within the rate limit.

        Args:
            event: The event instance.
            event_type: The event type string.

        Returns:
            True if the event can be delivered.
        """
        now = time.perf_counter()
        times = self._delivery_times[event_type]

        # Prune old entries outside the 1-second window
        while times and (now - times[0]) > 1.0:
            times.popleft()

        if len(times) >= self._max_per_second:
            return False

        times.append(now)

        # Bound the number of tracked event types
        if len(self._delivery_times) > self._max_tracked_types:
            # Remove the oldest-accessed type
            oldest_type = next(iter(self._delivery_times))
            del self._delivery_times[oldest_type]

        return True


class DeduplicationFilter:
    """Suppresses duplicate events within a time window.

    Deduplication is based on the (event_type, source_id) pair.
    Uses time.perf_counter() for timing. History is bounded.
    """

    def __init__(self, window_seconds: float = 1.0, max_history: int = 100) -> None:
        """Initialize the deduplication filter.

        Args:
            window_seconds: Time window for deduplication.
            max_history: Maximum number of tracked event keys.
        """
        self._window_seconds = window_seconds
        self._max_history = max_history
        # (event_type, source_id) -> last delivery timestamp (perf_counter)
        self._seen: dict[tuple, float] = {}

    def should_deliver(self, event: BaseEvent, event_type: str) -> bool:
        """Check if the event is a duplicate within the window.

        Args:
            event: The event instance.
            event_type: The event type string.

        Returns:
            True if the event is not a duplicate.
        """
        now = time.perf_counter()
        key = (event_type, getattr(event, "source_id", None))

        last_seen = self._seen.get(key)
        if last_seen is not None and (now - last_seen) < self._window_seconds:
            return False

        self._seen[key] = now

        # Bound the history
        if len(self._seen) > self._max_history:
            # Remove oldest entries
            sorted_keys = sorted(self._seen, key=self._seen.get)
            for old_key in sorted_keys[: len(self._seen) - self._max_history]:
                del self._seen[old_key]

        return True
