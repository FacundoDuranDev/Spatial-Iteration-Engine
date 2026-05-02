"""WebSocket protocol guardrails. See .claude/scratch/ws_protocol.md (v=1).

Phase A: minimal whitelists. Phase B extends with filter/param whitelists
backed by the registry.
"""
from __future__ import annotations
from typing import Any

PROTOCOL_VERSION = "1"

ALLOWED_OPS = frozenset({
    "start", "stop", "toggle_filter", "set_param", "clear_filters",
    "toggle_analyzer", "toggle_overlay",
    "add_modulation", "remove_modulation", "clear_modulations",
    "toggle_projection", "set_projection_corners",
    "set_projection_corner", "reset_projection",
    "set_projection_mesh_size", "set_projection_mesh_points",
    "set_projection_mesh_point",
    "add_projection_region", "remove_projection_region",
    "set_projection_active_region", "set_projection_region_enabled",
    "rename_projection_region",
    "pong",
})


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


def validate_modulation_payload(
    payload: Any,
    valid_signals: frozenset,
    registry,  # web_dashboard.registry module-like
    valid_curves: frozenset,
):
    """Validates and normalizes an add_modulation payload.

    Returns (normalized_dict, None) on success, or (None, error_message) on
    rejection. Out-of-range floats are clamped silently (igual que set_param).

    Required keys: signal, filter, param.
    Optional: in_min, in_max, out_min, out_max, curve, smoothing, enabled.
    """
    if not isinstance(payload, dict):
        return None, "payload must be object"
    sig = payload.get("signal")
    if not isinstance(sig, str) or sig not in valid_signals:
        return None, f"unknown signal: {sig!r}"
    fid = payload.get("filter")
    if not isinstance(fid, str) or registry.find_filter(fid) is None:
        return None, f"unknown filter: {fid!r}"
    pid = payload.get("param")
    if not isinstance(pid, str) or registry.find_param(fid, pid) is None:
        return None, f"unknown param: {fid}.{pid}"
    # Numeric ranges — silent clamp [-1e6, 1e6] para evitar inf/nan en el bus.
    in_min = clamp_float(payload.get("in_min", 0.0), -1e6, 1e6, default=0.0)
    in_max = clamp_float(payload.get("in_max", 1.0), -1e6, 1e6, default=1.0)
    out_min = clamp_float(payload.get("out_min", 0.0), -1e6, 1e6, default=0.0)
    out_max = clamp_float(payload.get("out_max", 1.0), -1e6, 1e6, default=1.0)
    curve = payload.get("curve", "linear")
    if not isinstance(curve, str) or curve not in valid_curves:
        return None, f"unknown curve: {curve!r}"
    smoothing = clamp_float(payload.get("smoothing", 0.3), 0.0, 1.0, default=0.3)
    enabled = coerce_bool(payload.get("enabled", True))
    return {
        "signal": sig,
        "filter_id": fid,
        "param_id": pid,
        "in_min": in_min,
        "in_max": in_max,
        "out_min": out_min,
        "out_max": out_max,
        "curve": curve,
        "smoothing": smoothing,
        "enabled": enabled,
    }, None
