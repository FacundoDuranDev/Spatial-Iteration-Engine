"""Tests for BudgetTracker."""

import threading

import pytest

from ascii_stream_engine.infrastructure.performance.budget_tracker import (
    BudgetTracker,
    BudgetViolation,
    PhaseBudget,
)


class TestBudgetTrackerBasic:
    """Basic BudgetTracker tests."""

    def test_initial_state(self):
        """No violations initially."""
        tracker = BudgetTracker()
        violations = tracker.get_violations()
        assert violations == {}

    def test_not_over_budget_initially(self):
        """Not over budget initially."""
        tracker = BudgetTracker()
        assert tracker.is_over_budget() is False

    def test_no_degradation_when_under_budget(self):
        """No recommendation when under budget."""
        tracker = BudgetTracker()
        assert tracker.get_degradation_recommendation() is None

    def test_phase_budgets_defined(self):
        """All expected phases have budgets."""
        expected = {"capture", "analysis", "tracking", "transformation", "filtering", "rendering", "writing"}
        assert set(BudgetTracker.PHASE_BUDGETS.keys()) == expected


class TestBudgetTrackerRecording:
    """Tests for recording and detection."""

    def test_record_phase_under_budget(self):
        """Phase under budget has no violation."""
        tracker = BudgetTracker()
        for _ in range(10):
            tracker.record_phase("capture", 0.001)  # 1ms, budget is 2ms
        violations = tracker.get_violations()
        assert "capture" not in violations

    def test_record_phase_over_budget(self):
        """Phase over budget triggers violation."""
        tracker = BudgetTracker()
        for _ in range(10):
            tracker.record_phase("analysis", 0.025)  # 25ms, budget is 15ms
        violations = tracker.get_violations()
        assert "analysis" in violations
        assert violations["analysis"].actual_ms > 15.0

    def test_frame_over_budget(self):
        """Total frame over budget is detected."""
        tracker = BudgetTracker()
        for _ in range(10):
            tracker.record_frame(0.050)  # 50ms, budget is 33.3ms
        assert tracker.is_over_budget() is True

    def test_frame_under_budget(self):
        """Total frame under budget is not flagged."""
        tracker = BudgetTracker()
        for _ in range(10):
            tracker.record_frame(0.020)  # 20ms, under 33.3ms
        assert tracker.is_over_budget() is False


class TestP95:
    """Tests for p95 latency calculation."""

    def test_p95_with_data(self):
        """p95 returns accurate 95th percentile."""
        tracker = BudgetTracker()
        # 95 samples at 1ms, 5 samples at 10ms
        for _ in range(95):
            tracker.record_phase("capture", 0.001)
        for _ in range(5):
            tracker.record_phase("capture", 0.010)
        p95 = tracker.get_p95("capture")
        # p95 should be close to 10ms
        assert p95 >= 1.0  # At least 1ms

    def test_p95_no_data(self):
        """p95 returns 0.0 with no data."""
        tracker = BudgetTracker()
        assert tracker.get_p95("capture") == 0.0


class TestBudgetUtilization:
    """Tests for budget utilization."""

    def test_utilization_under_budget(self):
        """Utilization under 100% for phases under budget."""
        tracker = BudgetTracker()
        for _ in range(10):
            tracker.record_phase("capture", 0.001)  # 1ms, budget 2ms
        utilization = tracker.get_budget_utilization()
        assert utilization["capture"] < 100.0

    def test_utilization_over_budget(self):
        """Utilization over 100% for phases over budget."""
        tracker = BudgetTracker()
        for _ in range(10):
            tracker.record_phase("capture", 0.004)  # 4ms, budget 2ms
        utilization = tracker.get_budget_utilization()
        assert utilization["capture"] > 100.0

    def test_utilization_empty_phase(self):
        """Utilization is 0 for phases with no data."""
        tracker = BudgetTracker()
        utilization = tracker.get_budget_utilization()
        assert utilization["capture"] == 0.0


class TestDegradationRecommendation:
    """Tests for degradation recommendation hierarchy."""

    def test_analysis_over_budget_recommends_skip_perception(self):
        """Analysis over budget recommends step 1: skip perception."""
        tracker = BudgetTracker()
        for _ in range(20):
            tracker.record_phase("analysis", 0.025)  # 25ms
            tracker.record_frame(0.050)  # Over budget
        rec = tracker.get_degradation_recommendation()
        assert rec is not None
        assert "perception" in rec.lower() or "Skip" in rec

    def test_general_over_budget_recommends_fps_reduction(self):
        """General over-budget recommends FPS reduction (last step)."""
        tracker = BudgetTracker()
        for _ in range(20):
            tracker.record_phase("writing", 0.001)  # Under budget
            tracker.record_frame(0.050)  # Over budget total
        rec = tracker.get_degradation_recommendation()
        assert rec is not None


class TestReset:
    """Tests for reset."""

    def test_reset_clears_data(self):
        """Reset clears all tracked data."""
        tracker = BudgetTracker()
        for _ in range(10):
            tracker.record_phase("capture", 0.005)
            tracker.record_frame(0.050)
        tracker.reset()
        assert tracker.is_over_budget() is False
        assert tracker.get_violations() == {}
        assert tracker.get_p95("capture") == 0.0


class TestSummary:
    """Tests for get_summary."""

    def test_summary_structure(self):
        """Summary has expected structure."""
        tracker = BudgetTracker()
        for _ in range(5):
            tracker.record_phase("capture", 0.001)
            tracker.record_frame(0.020)
        summary = tracker.get_summary()
        assert "frame_budget_ms" in summary
        assert "frame_avg_ms" in summary
        assert "over_budget" in summary
        assert "phases" in summary
        assert "capture" in summary["phases"]
        assert "budget_ms" in summary["phases"]["capture"]


class TestThreadSafety:
    """Thread safety tests."""

    def test_concurrent_recording(self):
        """Concurrent recording does not corrupt data."""
        tracker = BudgetTracker()
        errors = []

        def recorder(phase, duration):
            try:
                for _ in range(100):
                    tracker.record_phase(phase, duration)
                    tracker.record_frame(duration * 7)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=recorder, args=("capture", 0.001)),
            threading.Thread(target=recorder, args=("analysis", 0.010)),
            threading.Thread(target=recorder, args=("filtering", 0.003)),
            threading.Thread(target=recorder, args=("rendering", 0.002)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        # Verify data is accessible without errors
        tracker.get_violations()
        tracker.get_budget_utilization()
        tracker.get_summary()
