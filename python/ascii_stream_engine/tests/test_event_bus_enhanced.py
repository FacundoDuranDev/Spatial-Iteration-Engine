"""Tests for enhanced EventBus features: priority, wildcards, filters, replay, stats."""

import time

import pytest

from ascii_stream_engine.domain.events import BaseEvent, ErrorEvent
from ascii_stream_engine.infrastructure.event_bus import EventBus
from ascii_stream_engine.infrastructure.event_filter import (
    DeduplicationFilter,
    RateLimitFilter,
)


class TestEventBusBackwardCompatibility:
    """Verify existing API still works."""

    def test_basic_pubsub(self):
        """Standard subscribe/publish works."""
        bus = EventBus()
        received = []
        bus.subscribe("test", lambda e: received.append(e))
        event = BaseEvent()
        bus.publish(event, "test")
        assert len(received) == 1

    def test_disabled_bus(self):
        """Disabled bus does not deliver events."""
        bus = EventBus()
        received = []
        bus.subscribe("test", lambda e: received.append(e))
        bus.disable()
        bus.publish(BaseEvent(), "test")
        assert len(received) == 0

    def test_unsubscribe(self):
        """Unsubscribed callback no longer receives events."""
        bus = EventBus()
        received = []
        callback = lambda e: received.append(e)
        bus.subscribe("test", callback)
        bus.unsubscribe("test", callback)
        bus.publish(BaseEvent(), "test")
        assert len(received) == 0

    def test_clear(self):
        """Clear removes all subscriptions."""
        bus = EventBus()
        received = []
        bus.subscribe("test", lambda e: received.append(e))
        bus.clear()
        bus.publish(BaseEvent(), "test")
        assert len(received) == 0

    def test_event_type_inference(self):
        """Event type is inferred from class name."""
        bus = EventBus()
        received = []
        bus.subscribe("error", lambda e: received.append(e))
        event = ErrorEvent(error_type="test", error_message="msg", module_name="mod")
        bus.publish(event)
        assert len(received) == 1

    def test_subscriber_count(self):
        """get_subscriber_count returns correct count."""
        bus = EventBus()
        bus.subscribe("test", lambda e: None)
        bus.subscribe("test", lambda e: None)
        assert bus.get_subscriber_count("test") == 2

    def test_enable_disable(self):
        """enable/disable toggles event delivery."""
        bus = EventBus()
        assert bus.is_enabled()
        bus.disable()
        assert not bus.is_enabled()
        bus.enable()
        assert bus.is_enabled()


class TestPrioritySubscriptions:
    """Tests for priority-based callback ordering."""

    def test_higher_priority_executes_first(self):
        """Callbacks with higher priority are invoked before lower ones."""
        bus = EventBus()
        order = []
        bus.subscribe_with_priority("test", lambda e: order.append("low"), priority=1)
        bus.subscribe_with_priority("test", lambda e: order.append("high"), priority=10)
        bus.subscribe_with_priority("test", lambda e: order.append("mid"), priority=5)
        bus.publish(BaseEvent(), "test")
        assert order == ["high", "mid", "low"]

    def test_priority_and_standard_mixed(self):
        """Standard subscribers (priority 0) run after higher priority."""
        bus = EventBus()
        order = []
        bus.subscribe("test", lambda e: order.append("standard"))
        bus.subscribe_with_priority("test", lambda e: order.append("priority"), priority=5)
        bus.publish(BaseEvent(), "test")
        assert order == ["priority", "standard"]

    def test_same_priority_both_execute(self):
        """Multiple callbacks at the same priority all execute."""
        bus = EventBus()
        received = []
        bus.subscribe_with_priority("test", lambda e: received.append("a"), priority=5)
        bus.subscribe_with_priority("test", lambda e: received.append("b"), priority=5)
        bus.publish(BaseEvent(), "test")
        assert len(received) == 2

    def test_no_duplicate_priority_subscription(self):
        """Same callback cannot be subscribed twice to same event with priority."""
        bus = EventBus()
        received = []
        callback = lambda e: received.append(1)
        bus.subscribe_with_priority("test", callback, priority=5)
        bus.subscribe_with_priority("test", callback, priority=10)  # Duplicate, ignored
        bus.publish(BaseEvent(), "test")
        assert len(received) == 1


class TestWildcardSubscriptions:
    """Tests for wildcard pattern subscriptions."""

    def test_pattern_matching(self):
        """Wildcard pattern matches event types."""
        bus = EventBus()
        received = []
        bus.subscribe_pattern("analysis_*", lambda e: received.append(e))
        bus.publish(BaseEvent(), "analysis_complete")
        bus.publish(BaseEvent(), "analysis_started")
        bus.publish(BaseEvent(), "filter_applied")
        assert len(received) == 2

    def test_star_pattern_matches_all(self):
        """* pattern matches everything."""
        bus = EventBus()
        received = []
        bus.subscribe_pattern("*", lambda e: received.append(e))
        bus.publish(BaseEvent(), "anything")
        bus.publish(BaseEvent(), "something_else")
        assert len(received) == 2

    def test_unsubscribe_pattern(self):
        """Pattern subscription can be removed."""
        bus = EventBus()
        received = []
        callback = lambda e: received.append(e)
        bus.subscribe_pattern("test_*", callback)
        bus.unsubscribe_pattern("test_*", callback)
        bus.publish(BaseEvent(), "test_event")
        assert len(received) == 0

    def test_pattern_no_match(self):
        """Non-matching patterns are not triggered."""
        bus = EventBus()
        received = []
        bus.subscribe_pattern("analysis_*", lambda e: received.append(e))
        bus.publish(BaseEvent(), "filter_applied")
        assert len(received) == 0


class TestEventFilters:
    """Tests for event filtering."""

    def test_rate_limit_filter(self):
        """RateLimitFilter suppresses events beyond the rate."""
        bus = EventBus()
        rate_filter = RateLimitFilter(max_per_second=2.0)
        bus.add_filter(rate_filter)

        received = []
        bus.subscribe("test", lambda e: received.append(e))

        # Publish 5 events rapidly
        for _ in range(5):
            bus.publish(BaseEvent(), "test")

        # Should only deliver 2 (rate limit)
        assert len(received) == 2

    def test_deduplication_filter(self):
        """DeduplicationFilter suppresses duplicate events."""
        bus = EventBus()
        dedup_filter = DeduplicationFilter(window_seconds=1.0)
        bus.add_filter(dedup_filter)

        received = []
        bus.subscribe("test", lambda e: received.append(e))

        # Publish same event type 3 times rapidly
        for _ in range(3):
            bus.publish(BaseEvent(source_id="src1"), "test")

        # Only first should be delivered
        assert len(received) == 1

    def test_remove_filter(self):
        """Removed filter no longer affects delivery."""
        bus = EventBus()
        rate_filter = RateLimitFilter(max_per_second=1.0)
        bus.add_filter(rate_filter)
        bus.remove_filter(rate_filter)

        received = []
        bus.subscribe("test", lambda e: received.append(e))

        for _ in range(5):
            bus.publish(BaseEvent(), "test")

        assert len(received) == 5

    def test_filter_stats_tracked(self):
        """Filtered events are counted in stats."""
        bus = EventBus()
        rate_filter = RateLimitFilter(max_per_second=1.0)
        bus.add_filter(rate_filter)
        bus.subscribe("test", lambda e: None)

        for _ in range(5):
            bus.publish(BaseEvent(), "test")

        stats = bus.get_stats()
        assert stats["events_published"] == 5
        assert stats["events_filtered"] >= 4  # At least 4 filtered
        assert stats["events_delivered"] <= 1


class TestReplayBuffer:
    """Tests for event replay functionality."""

    def test_replay_disabled_by_default(self):
        """Replay buffer is disabled by default."""
        bus = EventBus()
        assert bus.get_stats()["replay_enabled"] is False

    def test_enable_replay(self):
        """Replay can be enabled."""
        bus = EventBus()
        bus.enable_replay(max_events=100)
        assert bus.get_stats()["replay_enabled"] is True

    def test_replay_captures_events(self):
        """Replay buffer stores published events."""
        bus = EventBus()
        bus.enable_replay(max_events=100)
        event1 = BaseEvent()
        event2 = BaseEvent()
        bus.publish(event1, "test")
        bus.publish(event2, "other")
        replayed = bus.replay()
        assert len(replayed) == 2

    def test_replay_filter_by_type(self):
        """Replay can filter by event type."""
        bus = EventBus()
        bus.enable_replay(max_events=100)
        bus.publish(BaseEvent(), "test")
        bus.publish(BaseEvent(), "other")
        replayed = bus.replay(event_type="test")
        assert len(replayed) == 1

    def test_replay_bounded(self):
        """Replay buffer is bounded by max_events."""
        bus = EventBus()
        bus.enable_replay(max_events=5)
        for _ in range(10):
            bus.publish(BaseEvent(), "test")
        replayed = bus.replay()
        assert len(replayed) == 5

    def test_get_event_history(self):
        """get_event_history returns recent events."""
        bus = EventBus()
        bus.enable_replay(max_events=100)
        for i in range(10):
            bus.publish(BaseEvent(source_id=f"src_{i}"), "test")
        history = bus.get_event_history(limit=3)
        assert len(history) == 3

    def test_disable_replay_clears_buffer(self):
        """Disabling replay clears the buffer."""
        bus = EventBus()
        bus.enable_replay(max_events=100)
        bus.publish(BaseEvent(), "test")
        bus.disable_replay()
        replayed = bus.replay()
        assert len(replayed) == 0


class TestEventBusStats:
    """Tests for statistics tracking."""

    def test_initial_stats(self):
        """Initial stats are zero."""
        bus = EventBus()
        stats = bus.get_stats()
        assert stats["events_published"] == 0
        assert stats["events_filtered"] == 0
        assert stats["events_delivered"] == 0

    def test_stats_after_publish(self):
        """Stats update after publishing."""
        bus = EventBus()
        bus.subscribe("test", lambda e: None)
        bus.publish(BaseEvent(), "test")
        stats = bus.get_stats()
        assert stats["events_published"] == 1
        assert stats["events_delivered"] == 1

    def test_stats_subscribers_by_type(self):
        """subscribers_by_type counts correctly."""
        bus = EventBus()
        bus.subscribe("test", lambda e: None)
        bus.subscribe("test", lambda e: None)
        bus.subscribe("other", lambda e: None)
        stats = bus.get_stats()
        assert stats["subscribers_by_type"]["test"] == 2
        assert stats["subscribers_by_type"]["other"] == 1

    def test_stats_includes_pattern_count(self):
        """Stats include pattern subscriber count."""
        bus = EventBus()
        bus.subscribe_pattern("test_*", lambda e: None)
        bus.subscribe_pattern("other_*", lambda e: None)
        stats = bus.get_stats()
        assert stats["pattern_subscribers"] == 2

    def test_stats_includes_filter_count(self):
        """Stats include filter count."""
        bus = EventBus()
        bus.add_filter(RateLimitFilter())
        stats = bus.get_stats()
        assert stats["filters_count"] == 1
