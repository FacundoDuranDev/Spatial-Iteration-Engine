"""WebSocket protocol guardrails. See .claude/scratch/ws_protocol.md (v=1).

Phase A: minimal whitelists. Phase B extends with filter/param whitelists
backed by the registry.
"""
from __future__ import annotations
from typing import Any

PROTOCOL_VERSION = "1"

ALLOWED_OPS = frozenset({"start", "stop", "toggle_filter", "set_param", "pong"})


def is_allowed_op(op: Any) -> bool:
    return isinstance(op, str) and op in ALLOWED_OPS


def clamp_float(value: Any, lo: float, hi: float, default: float = 0.0) -> float:
    """Coerce to float, clamp to [lo, hi]. Bad input → default."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def clamp_int(value: Any, lo: int, hi: int, step: int = 1, default: int = 0) -> int:
    """Coerce to int (snapped to `step`), clamp to [lo, hi]."""
    try:
        v = int(round(float(value) / step) * step)
    except (TypeError, ValueError):
        return default
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def coerce_bool(value: Any) -> bool:
    """Truthy → True, falsy → False. Strings 'false'/'0' → False."""
    if isinstance(value, str):
        return value.strip().lower() not in {"", "false", "0", "no", "off"}
    return bool(value)
