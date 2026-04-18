"""Helper utilities for the Gradio dashboard.

Provides convenience functions for filter management, frame preview, and
MP3 post-processing chain ordering.
"""

import json
import os

import cv2
import numpy as np

from ..adapters.processors.filters import ALL_FILTERS, deserialize_filter
from ..adapters.processors.filters._registry import _ensure_registry
from ..adapters.processors.filters.base import BaseFilter

# MP3 post-processing chain order (filter names in correct compositing order).
MP3_CHAIN_ORDER = [
    "motion_blur",
    "depth_of_field",
    "bloom_cinematic",
    "lens_flare",
    "bloom",
    "color_grading",
    "double_vision",
    "uv_displacement",
    "chromatic_aberration",
    "radial_blur",
    "radial_collapse",
    "glitch_block",
    "crt_glitch",
    "film_grain",
    "vignette",
    "kinetic_typography",
    "panel_compositor",
]


def get_or_create_filter(engine, name, cls, **defaults):
    """Find a filter by name in the engine's pipeline, or create and add it."""
    for f in engine._filters.filters:
        if f.name == name:
            return f
    instance = cls(**defaults)
    engine._filters.add(instance)
    return instance


def remove_filter_if_exists(engine, name):
    """Remove a filter by name from the engine's pipeline."""
    for f in list(engine._filters.filters):
        if f.name == name:
            engine._filters.remove(f)
            return True
    return False


def get_frame_for_preview(engine, max_width=640):
    """Get the latest frame from the engine buffer, converted BGR->RGB for Gradio."""
    if not hasattr(engine, "_frame_buffer") or engine._frame_buffer is None:
        return None

    result = engine._frame_buffer.peek_latest()
    if result is None:
        return None

    frame, _ = result
    if frame is None:
        return None

    # Handle RenderFrame objects (PIL Image).
    if hasattr(frame, "image"):
        frame_img = frame.image
        if hasattr(frame_img, "convert"):
            frame = np.array(frame_img.convert("RGB"))
            return _downscale(frame, max_width)

    # numpy array: BGR -> RGB.
    if isinstance(frame, np.ndarray) and frame.ndim == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return _downscale(frame, max_width)

    return None


def _downscale(frame, max_width):
    """Downscale frame if wider than max_width."""
    h, w = frame.shape[:2]
    if w > max_width:
        scale = max_width / w
        new_h = max(1, int(h * scale))
        frame = cv2.resize(frame, (max_width, new_h), interpolation=cv2.INTER_AREA)
    return frame


def order_mp3_filters(filter_list):
    """Sort a list of filter instances according to the MP3 compositing chain."""
    order_map = {name: i for i, name in enumerate(MP3_CHAIN_ORDER)}
    default_pos = len(MP3_CHAIN_ORDER)
    return sorted(filter_list, key=lambda f: order_map.get(f.name, default_pos))


def load_mp3_presets():
    """Load the built-in MP3 presets from data/presets/mp3_presets.json."""
    _ensure_registry()
    presets_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "data", "presets"
    )
    presets_file = os.path.join(presets_dir, "mp3_presets.json")
    if not os.path.isfile(presets_file):
        return []
    with open(presets_file) as f:
        return json.load(f)


def apply_preset_filters(engine, preset):
    """Apply a preset's filter configuration to the engine.

    Clears existing filters and adds the preset's filters in order.
    """
    _ensure_registry()
    engine._filters.clear()
    for fc in preset.get("filter_configs", []):
        try:
            instance = deserialize_filter(fc)
            engine._filters.add(instance)
        except (KeyError, TypeError) as e:
            print(f"Warning: could not load filter {fc.get('name')}: {e}")
