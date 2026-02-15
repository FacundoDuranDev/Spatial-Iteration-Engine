"""Python-to-C++ runtime binding contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol, Sequence

from .runtime_graph import ParamValue, RuntimeGraphSpec


@dataclass(frozen=True)
class FrameInputBinding:
    """Binds an external producer stream to a runtime resource."""

    stream_id: str
    resource_id: str
    timestamp_seconds: float
    frame_token: Optional[str] = None

    def validate(self) -> None:
        if not self.stream_id:
            raise ValueError("stream_id is required")
        if not self.resource_id:
            raise ValueError("resource_id is required")
        if self.timestamp_seconds < 0:
            raise ValueError("timestamp_seconds must be >= 0")


@dataclass(frozen=True)
class ParameterUpdate:
    """Runtime parameter update emitted by Python control-plane."""

    node_id: str
    param_name: str
    value: ParamValue

    def validate(self) -> None:
        if not self.node_id:
            raise ValueError("node_id is required")
        if not self.param_name:
            raise ValueError("param_name is required")


@dataclass
class FrameExecutionStats:
    """Per-frame execution statistics returned by the runtime."""

    frame_index: int
    frame_time_ms: float
    schedule_time_ms: float
    gpu_time_ms: float
    dropped: bool = False
    node_times_ms: Dict[str, float] = field(default_factory=dict)
    diagnostics: Dict[str, ParamValue] = field(default_factory=dict)

    def validate(self) -> None:
        if self.frame_index < 0:
            raise ValueError("frame_index must be >= 0")
        if self.frame_time_ms < 0:
            raise ValueError("frame_time_ms must be >= 0")
        if self.schedule_time_ms < 0:
            raise ValueError("schedule_time_ms must be >= 0")
        if self.gpu_time_ms < 0:
            raise ValueError("gpu_time_ms must be >= 0")


class RuntimeBinding(Protocol):
    """Bridge contract used by Python to drive C++ runtime."""

    def initialize(self, graph: RuntimeGraphSpec) -> None:
        """Allocates runtime resources and validates graph contract."""
        ...

    def replace_graph(self, graph: RuntimeGraphSpec) -> None:
        """Hot-swaps runtime graph while preserving stable resources when possible."""
        ...

    def update_parameters(self, updates: Sequence[ParameterUpdate]) -> None:
        """Applies parameter deltas without recreating graph resources."""
        ...

    def push_inputs(self, inputs: Sequence[FrameInputBinding]) -> None:
        """Registers external input frames that are already GPU-accessible."""
        ...

    def tick(self, frame_index: int, frame_time_seconds: float) -> FrameExecutionStats:
        """Executes one deterministic frame step."""
        ...

    def read_output_handle(self, resource_id: str) -> Optional[str]:
        """Returns an opaque handle for output resource consumption."""
        ...

    def shutdown(self) -> None:
        """Releases runtime resources."""
        ...
