"""Filter registry for the v3 web dashboard.

Declarative spec: id, name (Spanish), category, wip flag, factory, and a list
of params. Each param carries metadata used by the WS protocol layer to
clamp/coerce values, plus an `apply(filter_instance, value)` callback that
mutates the live filter.

WIP filters have ``factory=None`` and ``params=[]`` — the bridge refuses to
instantiate them and the WS layer rejects ops with ``error code wip_filter``.

Param ``kind`` values:
- ``slider``  — numeric range (float or int via step inference).
- ``stepper`` — integer range with discrete step.
- ``angle``   — float in [0, 360].
- ``select``  — discrete set of string ``options``.
- ``switch``  — boolean toggle.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from ascii_stream_engine.adapters.processors.filters import (
    BloomFilter,
    ChromaticAberrationFilter,
    CppBrightnessContrastFilter,
    CppInvertFilter,
    CppTemporalScanFilter,
)


# --- mutator helpers --------------------------------------------------------
# The v2 mobile dashboard used `setattr(f, "intensity", v)` etc. — but the
# underlying filter classes store those as private attributes (`_intensity`,
# `_brightness_delta`, ...) so the public setattr was a silent no-op. We use
# explicit helpers here so param mutations actually take effect.

def _bloom_set_intensity(f: BloomFilter, v: Any) -> None:
    f._intensity = float(v)


def _bloom_set_threshold(f: BloomFilter, v: Any) -> None:
    f._threshold = int(v)


def _bloom_set_audio_react(f: BloomFilter, v: Any) -> None:
    f._audio_reactive = float(v)


def _bc_set_brightness(f: CppBrightnessContrastFilter, v: Any) -> None:
    f._brightness_delta = int(v)


def _bc_set_contrast(f: CppBrightnessContrastFilter, v: Any) -> None:
    f._contrast_factor = float(v)


# --- registry ---------------------------------------------------------------

FILTERS: List[Dict[str, Any]] = [
    # ── DISTORT ────────────────────────────────────────────────────────────
    {
        "id": "temporal_scan",
        "name": "TemporalScan",
        "cat": "DISTORT",
        "wip": False,
        "factory": lambda: CppTemporalScanFilter(angle_deg=0.0, max_frames=30),
        "params": [
            {
                "id": "angle",
                "kind": "angle",
                "min": 0.0,
                "max": 360.0,
                "step": 1.0,
                "default": 0.0,
                "label": "Ángulo de scan",
                "apply": lambda f, v: setattr(f, "angle_deg", float(v)),
            },
            {
                "id": "buffer",
                "kind": "stepper",
                "min": 2,
                "max": 60,
                "step": 2,
                "default": 30,
                "label": "Buffer (frames)",
                "apply": lambda f, v: setattr(f, "max_frames", int(v)),
            },
            {
                "id": "curve",
                "kind": "select",
                "options": ["linear", "ease"],
                "default": "linear",
                "label": "Curva",
                "apply": lambda f, v: setattr(f, "curve", v),
            },
        ],
    },
    # ── COLOR ──────────────────────────────────────────────────────────────
    {
        "id": "bc_cpp",
        "name": "Brillo / Contraste",
        "cat": "COLOR",
        "wip": False,
        "factory": lambda: CppBrightnessContrastFilter(
            brightness_delta=0, contrast_factor=1.0
        ),
        "params": [
            {
                "id": "brightness",
                "kind": "slider",
                "min": -100,
                "max": 100,
                "step": 5,
                "default": 0,
                "label": "Brillo",
                "apply": _bc_set_brightness,
            },
            {
                "id": "contrast",
                "kind": "slider",
                "min": 0.5,
                "max": 3.0,
                "step": 0.1,
                "default": 1.0,
                "label": "Contraste",
                "apply": _bc_set_contrast,
            },
        ],
    },
    {
        "id": "bloom",
        "name": "Bloom · audio-reactivo",
        "cat": "COLOR",
        "wip": False,
        "factory": lambda: BloomFilter(
            threshold=200, intensity=0.6, audio_reactive=1.0
        ),
        "params": [
            {
                "id": "intensity",
                "kind": "slider",
                "min": 0.0,
                "max": 1.0,
                "step": 0.05,
                "default": 0.6,
                "label": "Intensidad",
                "apply": _bloom_set_intensity,
            },
            {
                "id": "threshold",
                "kind": "slider",
                "min": 100,
                "max": 255,
                "step": 5,
                "default": 200,
                "label": "Umbral",
                "apply": _bloom_set_threshold,
            },
            {
                "id": "audio_react",
                "kind": "slider",
                "min": 0.0,
                "max": 3.0,
                "step": 0.1,
                "default": 1.0,
                "label": "Reactividad audio (Bass)",
                "apply": _bloom_set_audio_react,
            },
        ],
    },
    # ── GLITCH ─────────────────────────────────────────────────────────────
    {
        "id": "chroma",
        "name": "Aberración cromática",
        "cat": "GLITCH",
        "wip": False,
        "factory": lambda: ChromaticAberrationFilter(
            strength=3.0, center_x=0.5, center_y=0.5, radial=True
        ),
        "params": [
            {
                "id": "strength",
                "kind": "slider",
                "min": 0.0,
                "max": 15.0,
                "step": 0.5,
                "default": 3.0,
                "label": "Fuerza",
                "apply": lambda f, v: setattr(f, "strength", float(v)),
            },
            {
                "id": "center_x",
                "kind": "slider",
                "min": 0.0,
                "max": 1.0,
                "step": 0.05,
                "default": 0.5,
                "label": "Centro X",
                "apply": lambda f, v: setattr(f, "center_x", float(v)),
            },
            {
                "id": "center_y",
                "kind": "slider",
                "min": 0.0,
                "max": 1.0,
                "step": 0.05,
                "default": 0.5,
                "label": "Centro Y",
                "apply": lambda f, v: setattr(f, "center_y", float(v)),
            },
            {
                "id": "radial",
                "kind": "switch",
                "default": True,
                "label": "Radial",
                "apply": lambda f, v: setattr(f, "radial", bool(v)),
            },
        ],
    },
    # ── STYLIZE ────────────────────────────────────────────────────────────
    {
        "id": "invert",
        "name": "Invertir",
        "cat": "STYLIZE",
        "wip": False,
        "factory": lambda: CppInvertFilter(),
        "params": [],  # only the enabled toggle (managed in cat list / detail)
    },
]


CATEGORIES: List[Dict[str, str]] = [
    {"id": "DISTORT", "name": "Distorsión"},
    {"id": "COLOR", "name": "Color"},
    {"id": "GLITCH", "name": "Glitch"},
    {"id": "STYLIZE", "name": "Estilo"},
]


FILTERS_BY_ID: Dict[str, Dict[str, Any]] = {f["id"]: f for f in FILTERS}


def find_filter(fid: str) -> Optional[Dict[str, Any]]:
    """Return the registry entry for ``fid`` or None."""
    return FILTERS_BY_ID.get(fid)


def find_param(fid: str, pid: str) -> Optional[Dict[str, Any]]:
    """Return the param spec for ``(fid, pid)`` or None."""
    spec = FILTERS_BY_ID.get(fid)
    if spec is None:
        return None
    for p in spec["params"]:
        if p["id"] == pid:
            return p
    return None


def default_params(fid: str) -> Dict[str, Any]:
    """Return ``{pid: default}`` for the snapshot of un-instantiated filters."""
    spec = FILTERS_BY_ID.get(fid)
    if spec is None:
        return {}
    return {p["id"]: p["default"] for p in spec["params"]}
