"""Performance budget tracker for per-phase latency monitoring.

Tracks per-phase latency against the 33.3ms frame budget from
rules/LATENCY_BUDGET.md, detects violations, and recommends
degradation steps.
"""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PhaseBudget:
    """Budget specification for a pipeline phase."""

    name: str
    budget_ms: float
    p95_max_ms: float


@dataclass
class BudgetViolation:
    """Represents a budget violation for a phase."""

    phase: str
    budget_ms: float
    actual_ms: float
    p95_ms: float
    p95_max_ms: float
    violation_count: int
    total_samples: int


class BudgetTracker:
    """Tracks per-phase latency against the frame budget.

    Budget constants from rules/LATENCY_BUDGET.md.
    Thread-safe with threading.Lock.
    All timing uses time.perf_counter().
    """

    FRAME_BUDGET_MS = 33.3

    PHASE_BUDGETS = {
        "capture": PhaseBudget("capture", 2.0, 5.0),
        "analysis": PhaseBudget("analysis", 15.0, 20.0),
        "tracking": PhaseBudget("tracking", 2.0, 3.0),
        "transformation": PhaseBudget("transformation", 2.0, 4.0),
        "filtering": PhaseBudget("filtering", 5.0, 8.0),
        "rendering": PhaseBudget("rendering", 3.0, 5.0),
        "writing": PhaseBudget("writing", 3.0, 5.0),
    }

    # Degradation steps from rules/LATENCY_BUDGET.md, in order
    DEGRADATION_STEPS = [
        "Skip perception on alternating frames",
        "Disable tracking",
        "Reduce inference resolution",
        "Disable non-essential filters",
        "Reduce target FPS",
    ]

    def __init__(self, max_history: int = 500) -> None:
        """Initialize the budget tracker.

        Args:
            max_history: Maximum number of samples to keep per phase.
        """
        self._lock = threading.Lock()
        self._max_history = max_history
        # phase -> deque of durations in seconds
        self._phase_history: Dict[str, deque] = {}
        for phase in self.PHASE_BUDGETS:
            self._phase_history[phase] = deque(maxlen=max_history)
        # Total frame durations
        self._frame_history: deque = deque(maxlen=max_history)

    def record_phase(self, phase: str, duration_s: float) -> None:
        """Record a phase duration.

        Args:
            phase: Phase name (must be in PHASE_BUDGETS).
            duration_s: Duration in seconds.
        """
        with self._lock:
            if phase not in self._phase_history:
                self._phase_history[phase] = deque(maxlen=self._max_history)
            self._phase_history[phase].append(duration_s)

    def record_frame(self, total_duration_s: float) -> None:
        """Record total frame duration.

        Args:
            total_duration_s: Total frame time in seconds.
        """
        with self._lock:
            self._frame_history.append(total_duration_s)

    def get_violations(self, window: int = 100) -> Dict[str, BudgetViolation]:
        """Get current budget violations for all phases.

        Args:
            window: Number of recent samples to consider.

        Returns:
            Dict of phase -> BudgetViolation for phases that are over budget.
        """
        violations = {}
        with self._lock:
            for phase, budget in self.PHASE_BUDGETS.items():
                history = self._phase_history.get(phase, deque())
                if not history:
                    continue
                samples = list(history)[-window:]
                if not samples:
                    continue

                avg_ms = (sum(samples) / len(samples)) * 1000.0
                p95_ms = self._calc_p95(samples) * 1000.0
                violation_count = sum(1 for s in samples if s * 1000.0 > budget.budget_ms)

                if avg_ms > budget.budget_ms or p95_ms > budget.p95_max_ms:
                    violations[phase] = BudgetViolation(
                        phase=phase,
                        budget_ms=budget.budget_ms,
                        actual_ms=avg_ms,
                        p95_ms=p95_ms,
                        p95_max_ms=budget.p95_max_ms,
                        violation_count=violation_count,
                        total_samples=len(samples),
                    )
        return violations

    def get_budget_utilization(self) -> Dict[str, float]:
        """Get percentage of budget used per phase.

        Returns:
            Dict of phase -> utilization percentage (0-100+).
        """
        utilization = {}
        with self._lock:
            for phase, budget in self.PHASE_BUDGETS.items():
                history = self._phase_history.get(phase, deque())
                if not history:
                    utilization[phase] = 0.0
                    continue
                avg_ms = (sum(history) / len(history)) * 1000.0
                utilization[phase] = (avg_ms / budget.budget_ms) * 100.0 if budget.budget_ms > 0 else 0.0
        return utilization

    def get_p95(self, phase: str) -> float:
        """Get 95th percentile latency for a phase in milliseconds.

        Args:
            phase: Phase name.

        Returns:
            p95 latency in ms (0.0 if no data).
        """
        with self._lock:
            history = self._phase_history.get(phase, deque())
            if not history:
                return 0.0
            return self._calc_p95(list(history)) * 1000.0

    def is_over_budget(self) -> bool:
        """Check if total frame time exceeds 33.3ms.

        Returns:
            True if average total frame time exceeds budget.
        """
        with self._lock:
            if not self._frame_history:
                return False
            avg_ms = (sum(self._frame_history) / len(self._frame_history)) * 1000.0
            return avg_ms > self.FRAME_BUDGET_MS

    def get_degradation_recommendation(self) -> Optional[str]:
        """Get the next degradation step recommendation.

        Follows the 5-step hierarchy from rules/LATENCY_BUDGET.md:
        1. Skip perception on alternating frames
        2. Disable tracking
        3. Reduce inference resolution
        4. Disable non-essential filters
        5. Reduce target FPS

        Returns:
            Recommendation string or None if not over budget.
        """
        if not self.is_over_budget():
            return None

        violations = self.get_violations()

        # Step 1: If analysis is over budget
        if "analysis" in violations:
            return self.DEGRADATION_STEPS[0]

        # Step 2: If tracking is over budget
        if "tracking" in violations:
            return self.DEGRADATION_STEPS[1]

        # Step 3: If still over budget, reduce resolution
        if "analysis" in self._phase_history and self._phase_history["analysis"]:
            return self.DEGRADATION_STEPS[2]

        # Step 4: If filtering is over budget
        if "filtering" in violations:
            return self.DEGRADATION_STEPS[3]

        # Step 5: General over-budget
        return self.DEGRADATION_STEPS[4]

    def get_summary(self) -> Dict[str, object]:
        """Get a summary of all budget tracking data.

        Returns:
            Dict with per-phase stats and overall status.
        """
        with self._lock:
            phases = {}
            for phase, budget in self.PHASE_BUDGETS.items():
                history = self._phase_history.get(phase, deque())
                if not history:
                    phases[phase] = {
                        "budget_ms": budget.budget_ms,
                        "avg_ms": 0.0,
                        "p95_ms": 0.0,
                        "samples": 0,
                    }
                    continue
                samples = list(history)
                avg_ms = (sum(samples) / len(samples)) * 1000.0
                p95_ms = self._calc_p95(samples) * 1000.0
                phases[phase] = {
                    "budget_ms": budget.budget_ms,
                    "avg_ms": round(avg_ms, 3),
                    "p95_ms": round(p95_ms, 3),
                    "samples": len(samples),
                }

            frame_avg_ms = 0.0
            if self._frame_history:
                frame_avg_ms = (sum(self._frame_history) / len(self._frame_history)) * 1000.0

            return {
                "frame_budget_ms": self.FRAME_BUDGET_MS,
                "frame_avg_ms": round(frame_avg_ms, 3),
                "over_budget": frame_avg_ms > self.FRAME_BUDGET_MS,
                "phases": phases,
            }

    def reset(self) -> None:
        """Reset all tracked data."""
        with self._lock:
            for history in self._phase_history.values():
                history.clear()
            self._frame_history.clear()

    @staticmethod
    def _calc_p95(samples: List[float]) -> float:
        """Calculate 95th percentile of a list of values.

        Args:
            samples: List of float values.

        Returns:
            95th percentile value.
        """
        if not samples:
            return 0.0
        sorted_samples = sorted(samples)
        idx = int(len(sorted_samples) * 0.95)
        idx = min(idx, len(sorted_samples) - 1)
        return sorted_samples[idx]
