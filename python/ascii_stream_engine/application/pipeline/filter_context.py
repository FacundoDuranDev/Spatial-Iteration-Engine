"""FilterContext — dict-compatible wrapper providing lazy access to temporal + analysis data.

Backwards compatible: existing filters using analysis.get("face") work unchanged.
Adds lazy temporal properties that delegate to TemporalManager.
"""

from typing import Any, Iterator, Optional


class FilterContext:
    """Dict-compatible wrapper providing lazy access to temporal + analysis data.

    Wraps an analysis dict + optional TemporalManager reference.
    Supports dict protocol (__contains__, __getitem__, get, keys) for backwards compatibility.
    """

    def __init__(self, analysis: Optional[dict] = None, temporal=None) -> None:
        self._analysis = analysis or {}
        self._temporal = temporal

    # --- Dict protocol (backwards compatible) ---

    def __contains__(self, key: str) -> bool:
        return key in self._analysis

    def __getitem__(self, key: str) -> Any:
        return self._analysis[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._analysis.get(key, default)

    def keys(self):
        return self._analysis.keys()

    def values(self):
        return self._analysis.values()

    def items(self):
        return self._analysis.items()

    def __iter__(self) -> Iterator[str]:
        return iter(self._analysis)

    def __len__(self) -> int:
        return len(self._analysis)

    def __bool__(self) -> bool:
        return True  # FilterContext is always truthy (even with empty analysis)

    # --- Temporal properties (lazy, delegate to TemporalManager) ---

    @property
    def previous_input(self):
        """Get previous input frame (read-only view or None)."""
        if self._temporal is None:
            return None
        return self._temporal.get_previous_input(1)

    def get_previous_input(self, n: int = 1):
        """Get nth previous input frame (read-only view or None)."""
        if self._temporal is None:
            return None
        return self._temporal.get_previous_input(n)

    @property
    def previous_output(self):
        """Get previous processed output frame (read-only view or None)."""
        if self._temporal is None:
            return None
        return self._temporal.get_previous_output()

    @property
    def optical_flow(self):
        """Get shared optical flow (computed lazily on first access per frame)."""
        if self._temporal is None:
            return None
        return self._temporal.get_optical_flow()

    @property
    def delta_frame(self):
        """Get input frame diff (computed lazily on first access per frame)."""
        if self._temporal is None:
            return None
        return self._temporal.get_delta()

    # --- Perception shortcuts ---

    @property
    def face(self):
        """Shortcut for analysis face data."""
        return self._analysis.get("face")

    @property
    def hands(self):
        """Shortcut for analysis hands data."""
        return self._analysis.get("hands")

    @property
    def pose(self):
        """Shortcut for analysis pose data."""
        return self._analysis.get("pose")

    @property
    def tracking(self):
        """Shortcut for tracking data."""
        return self._analysis.get("tracking")
