"""Central event bus for decoupled inter-module communication.

Thread-safe pub/sub with type-based subscriptions, priority delivery,
wildcard patterns, event filtering, replay buffer, and statistics.
"""

import fnmatch
import logging
import re
import threading
import time
from collections import defaultdict, deque
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..domain.events import BaseEvent

logger = logging.getLogger(__name__)


class EventBus:
    """Thread-safe event bus with subscriptions by event type.

    Supports:
    - Standard subscribe/publish (backward compatible)
    - Priority-based callback ordering
    - Wildcard pattern subscriptions (e.g., "analysis_*")
    - Event filtering via EventFilter protocol
    - Bounded event replay buffer
    - Statistics tracking
    """

    def __init__(self) -> None:
        """Initialize the event bus."""
        self._subscribers: Dict[str, List[Callable[[BaseEvent], None]]] = defaultdict(list)
        self._lock = threading.RLock()
        self._enabled = True

        # Priority subscribers: event_type -> sorted list of (priority, callback)
        # Higher priority = executed first
        self._priority_subscribers: Dict[str, List[Tuple[int, Callable]]] = defaultdict(list)

        # Wildcard pattern subscribers: list of (pattern, priority, callback)
        self._pattern_subscribers: List[Tuple[str, int, Callable]] = []

        # Event filters
        self._filters: List[Any] = []

        # Replay buffer (disabled by default)
        self._replay_enabled = False
        self._replay_buffer: deque = deque(maxlen=1000)

        # Statistics
        self._stats_events_published = 0
        self._stats_events_filtered = 0
        self._stats_events_delivered = 0

    def subscribe(self, event_type: str, callback: Callable[[BaseEvent], None]) -> None:
        """Subscribe a callback to an event type.

        Args:
            event_type: Event type (e.g., "frame_captured", "analysis_complete").
            callback: Function to call when the event is published.
        """
        with self._lock:
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)
                logger.debug(f"Callback subscribed to event '{event_type}'")

    def subscribe_with_priority(
        self, event_type: str, callback: Callable[[BaseEvent], None], priority: int = 0
    ) -> None:
        """Subscribe with a priority. Higher priority callbacks execute first.

        Args:
            event_type: Event type string.
            callback: Callback function.
            priority: Priority value (higher = executed first). Default 0.
        """
        with self._lock:
            for p, cb in self._priority_subscribers[event_type]:
                if cb is callback:
                    return
            self._priority_subscribers[event_type].append((priority, callback))
            self._priority_subscribers[event_type].sort(key=lambda x: -x[0])
            logger.debug(f"Priority callback subscribed to '{event_type}' with priority {priority}")

    def subscribe_pattern(
        self, pattern: str, callback: Callable[[BaseEvent], None], priority: int = 0
    ) -> None:
        """Subscribe to event types matching a wildcard pattern.

        Uses fnmatch-style patterns: "analysis_*" matches "analysis_complete".

        Args:
            pattern: Wildcard pattern (fnmatch syntax).
            callback: Callback function.
            priority: Priority value.
        """
        with self._lock:
            for pat, pri, cb in self._pattern_subscribers:
                if pat == pattern and cb is callback:
                    return
            self._pattern_subscribers.append((pattern, priority, callback))
            logger.debug(f"Pattern callback subscribed to '{pattern}' with priority {priority}")

    def unsubscribe(self, event_type: str, callback: Callable[[BaseEvent], None]) -> None:
        """Unsubscribe a callback from an event type.

        Args:
            event_type: Event type.
            callback: Function to unsubscribe.
        """
        with self._lock:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                logger.debug(f"Callback unsubscribed from event '{event_type}'")
            self._priority_subscribers[event_type] = [
                (p, cb) for p, cb in self._priority_subscribers[event_type] if cb is not callback
            ]

    def unsubscribe_pattern(self, pattern: str, callback: Callable[[BaseEvent], None]) -> None:
        """Unsubscribe a pattern callback.

        Args:
            pattern: The wildcard pattern.
            callback: The callback to remove.
        """
        with self._lock:
            self._pattern_subscribers = [
                (pat, pri, cb)
                for pat, pri, cb in self._pattern_subscribers
                if not (pat == pattern and cb is callback)
            ]

    def add_filter(self, event_filter: Any) -> None:
        """Add an event filter. Filters run before callback execution.

        Args:
            event_filter: Object with should_deliver(event, event_type) -> bool method.
        """
        with self._lock:
            if event_filter not in self._filters:
                self._filters.append(event_filter)
                logger.debug("Event filter added")

    def remove_filter(self, event_filter: Any) -> None:
        """Remove an event filter.

        Args:
            event_filter: The filter to remove.
        """
        with self._lock:
            if event_filter in self._filters:
                self._filters.remove(event_filter)
                logger.debug("Event filter removed")

    def publish(self, event: BaseEvent, event_type: Optional[str] = None) -> None:
        """Publish an event to all subscribers.

        Delivers to: standard subscribers, priority subscribers, and
        pattern subscribers whose pattern matches the event type.
        Filters are applied before delivery.

        Args:
            event: Event instance to publish.
            event_type: Event type (inferred from class name if None).
        """
        if not self._enabled:
            return

        if event_type is None:
            class_name = event.__class__.__name__
            event_type = self._camel_to_snake(class_name).replace("_event", "")

        with self._lock:
            self._stats_events_published += 1

            # Store in replay buffer if enabled
            if self._replay_enabled:
                self._replay_buffer.append((event_type, event, time.perf_counter()))

            # Collect all callbacks with priorities
            all_callbacks: List[Tuple[int, Callable]] = []

            # Standard subscribers (priority 0)
            for cb in self._subscribers[event_type]:
                all_callbacks.append((0, cb))

            # Priority subscribers
            for priority, cb in self._priority_subscribers[event_type]:
                all_callbacks.append((priority, cb))

            # Pattern subscribers
            for pattern, priority, cb in self._pattern_subscribers:
                if fnmatch.fnmatchcase(event_type, pattern):
                    all_callbacks.append((priority, cb))

            # Sort by priority descending (highest first)
            all_callbacks.sort(key=lambda x: -x[0])

            # Deduplicate (keep highest priority entry for each callback)
            seen_callbacks = set()
            unique_callbacks: List[Tuple[int, Callable]] = []
            for priority, cb in all_callbacks:
                cb_id = id(cb)
                if cb_id not in seen_callbacks:
                    seen_callbacks.add(cb_id)
                    unique_callbacks.append((priority, cb))

            # Copy filters list
            filters = list(self._filters)

        # Execute callbacks outside the lock to prevent deadlocks
        for priority, callback in unique_callbacks:
            # Apply filters
            filtered = False
            for f in filters:
                try:
                    if not f.should_deliver(event, event_type):
                        filtered = True
                        break
                except Exception as e:
                    logger.error(f"Error in event filter: {e}", exc_info=True)

            if filtered:
                with self._lock:
                    self._stats_events_filtered += 1
                continue

            try:
                callback(event)
                with self._lock:
                    self._stats_events_delivered += 1
            except Exception as e:
                logger.error(
                    f"Error executing callback for event '{event_type}': {e}",
                    exc_info=True,
                )

    def publish_async(self, event: BaseEvent, event_type: Optional[str] = None) -> None:
        """Publish an event asynchronously (non-blocking).

        Args:
            event: Event instance to publish.
            event_type: Event type (inferred from class name if None).
        """
        if not self._enabled:
            return

        if event_type is None:
            class_name = event.__class__.__name__
            event_type = self._camel_to_snake(class_name).replace("_event", "")

        def _async_publish() -> None:
            self.publish(event, event_type)

        thread = threading.Thread(target=_async_publish, daemon=True)
        thread.start()

    # --- Replay ---

    def enable_replay(self, max_events: int = 1000) -> None:
        """Enable the event replay buffer.

        Args:
            max_events: Maximum events to store in the replay buffer.
        """
        with self._lock:
            self._replay_enabled = True
            self._replay_buffer = deque(maxlen=max_events)
            logger.debug(f"Replay enabled with max_events={max_events}")

    def disable_replay(self) -> None:
        """Disable the event replay buffer and clear stored events."""
        with self._lock:
            self._replay_enabled = False
            self._replay_buffer.clear()

    def replay(
        self, event_type: Optional[str] = None, since: Optional[float] = None
    ) -> List[BaseEvent]:
        """Retrieve events from the replay buffer.

        Args:
            event_type: Filter by event type (None for all).
            since: Only return events after this perf_counter timestamp.

        Returns:
            List of matching events.
        """
        with self._lock:
            results = []
            for stored_type, event, ts in self._replay_buffer:
                if event_type is not None and stored_type != event_type:
                    continue
                if since is not None and ts < since:
                    continue
                results.append(event)
            return results

    def get_event_history(
        self, event_type: Optional[str] = None, limit: int = 100
    ) -> List[BaseEvent]:
        """Get recent events from the replay buffer.

        Args:
            event_type: Filter by event type (None for all).
            limit: Maximum number of events to return.

        Returns:
            List of events (most recent last).
        """
        with self._lock:
            results = []
            for stored_type, event, ts in reversed(self._replay_buffer):
                if event_type is not None and stored_type != event_type:
                    continue
                results.append(event)
                if len(results) >= limit:
                    break
            results.reverse()
            return results

    # --- Statistics ---

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics.

        Returns:
            Dict with events_published, events_filtered, events_delivered,
            subscribers_by_type, total_subscribers, pattern_subscribers.
        """
        with self._lock:
            subscribers_by_type = {et: len(cbs) for et, cbs in self._subscribers.items() if cbs}
            for et, entries in self._priority_subscribers.items():
                if entries:
                    subscribers_by_type[et] = subscribers_by_type.get(et, 0) + len(entries)

            return {
                "events_published": self._stats_events_published,
                "events_filtered": self._stats_events_filtered,
                "events_delivered": self._stats_events_delivered,
                "subscribers_by_type": subscribers_by_type,
                "total_subscribers": sum(subscribers_by_type.values()),
                "pattern_subscribers": len(self._pattern_subscribers),
                "filters_count": len(self._filters),
                "replay_enabled": self._replay_enabled,
                "replay_buffer_size": len(self._replay_buffer),
            }

    # --- Existing API (backward compatible) ---

    def clear(self) -> None:
        """Clear all subscriptions."""
        with self._lock:
            self._subscribers.clear()
            self._priority_subscribers.clear()
            self._pattern_subscribers.clear()
            self._filters.clear()
            self._replay_buffer.clear()
            logger.debug("All subscriptions have been cleared")

    def get_subscriber_count(self, event_type: Optional[str] = None) -> int:
        """Get the number of subscribers for an event type or total.

        Args:
            event_type: Event type (None for total).

        Returns:
            Number of subscribers.
        """
        with self._lock:
            if event_type:
                count = len(self._subscribers.get(event_type, []))
                count += len(self._priority_subscribers.get(event_type, []))
                return count
            total = sum(len(callbacks) for callbacks in self._subscribers.values())
            total += sum(len(entries) for entries in self._priority_subscribers.values())
            total += len(self._pattern_subscribers)
            return total

    def enable(self) -> None:
        """Enable the event bus."""
        self._enabled = True
        logger.debug("Event bus enabled")

    def disable(self) -> None:
        """Disable the event bus (events will not be published)."""
        self._enabled = False
        logger.debug("Event bus disabled")

    def is_enabled(self) -> bool:
        """Check if the event bus is enabled."""
        return self._enabled

    @staticmethod
    def _camel_to_snake(name: str) -> str:
        """Convert CamelCase to snake_case."""
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
