"""Custom Gradio widgets for the Spatial-Iteration-Engine dashboard.

Each widget is a small factory function that returns a hidden value
component plus the visible HTML/SVG. The JS that drives the widget lives
in ``static/`` and is bundled once per Gradio app via ``bundle_js()`` /
``bundle_css()``.

Visual style is ported from ``design/ui_kits/mcp_v2`` (phosphor-cyan
mobile control surface). See ``README.md`` for how to author new widgets.
"""

from pathlib import Path
from typing import List

_STATIC_DIR = Path(__file__).parent / "static"

_JS_FILES: List[str] = []
_CSS_FILES: List[str] = []


def register_assets(js: str = "", css: str = "") -> None:
    """Register a widget's JS and/or CSS file names (relative to static/)."""
    if js and js not in _JS_FILES:
        _JS_FILES.append(js)
    if css and css not in _CSS_FILES:
        _CSS_FILES.append(css)


def bundle_js() -> str:
    """Concatenate all registered JS files. Pass to ``gr.Blocks(js=...)``."""
    parts = []
    for name in _JS_FILES:
        parts.append((_STATIC_DIR / name).read_text(encoding="utf-8"))
    return "\n".join(parts) or ""


def bundle_css() -> str:
    """Concatenate all registered CSS files. Pass to ``gr.Blocks(css=...)``."""
    parts = []
    for name in _CSS_FILES:
        parts.append((_STATIC_DIR / name).read_text(encoding="utf-8"))
    return "\n".join(parts) or ""


# Base stylesheet ships with every widget — register before the factories
# so it lands first in the bundle.
register_assets(css="widgets.css")

from .angle_dial import angle_dial  # noqa: E402,F401
from .slider_row import slider_row  # noqa: E402,F401
from .stepper import stepper  # noqa: E402,F401
from .toggle import toggle  # noqa: E402,F401

__all__ = [
    "angle_dial",
    "slider_row",
    "stepper",
    "toggle",
    "bundle_js",
    "bundle_css",
    "register_assets",
]
