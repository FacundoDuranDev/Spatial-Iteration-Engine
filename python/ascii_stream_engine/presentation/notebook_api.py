"""Jupyter notebook UI panels for the Spatial-Iteration-Engine.

All build_* functions live here. Each returns a Dict of widgets for
programmatic access. ipywidgets and IPython.display are guarded imports
inside every public function.
"""

import json
import os
import resource
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..adapters.outputs import NotebookPreviewSink
from ..adapters.renderers import AsciiRenderer, PassthroughRenderer
from ..adapters.sources import OpenCVCameraSource
from ..application.engine import StreamEngine
from ..application.pipeline import AnalyzerPipeline, FilterPipeline
from ..domain.config import EngineConfig

# ---------------------------------------------------------------------------
# Phase 1: Shared helpers (module-level)
# ---------------------------------------------------------------------------


def _status_style(msg: str, kind: str = "info") -> str:
    """Return an HTML snippet with a styled status message.

    Args:
        msg: The message text (may contain HTML).
        kind: One of 'ok', 'warn', 'info' (default 'info').

    Returns:
        HTML string with coloured background.
    """
    color = {"ok": "#d4edda", "warn": "#fff3cd", "info": "#e7f1ff"}.get(kind, "#f8f9fa")
    return (
        f'<div style="padding:8px 10px; background:{color}; '
        f"border-radius:6px; margin:6px 0; border:1px solid #dee2e6; "
        f'font-size:13px;">{msg}</div>'
    )


def _periodic_refresh(
    widget_update_fn: Callable[[], None],
    interval_ms: int,
    stop_event: Optional[threading.Event] = None,
) -> Dict[str, Any]:
    """Create a daemon thread that calls *widget_update_fn* periodically.

    Args:
        widget_update_fn: Callable invoked every *interval_ms* ms.
        interval_ms: Interval in milliseconds between calls.
        stop_event: Optional external stop event. If ``None`` a new one is
            created internally.

    Returns:
        ``{"thread": Thread, "stop": Callable, "stop_event": Event}``
    """
    if stop_event is None:
        stop_event = threading.Event()

    def _loop() -> None:
        interval_s = max(0.1, interval_ms / 1000.0)
        while not stop_event.is_set():
            try:
                widget_update_fn()
            except Exception:
                pass  # never crash the notebook kernel
            stop_event.wait(interval_s)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()

    def _stop() -> None:
        stop_event.set()

    return {"thread": t, "stop": _stop, "stop_event": stop_event}


def _safe_engine_call(
    engine: Any,
    method_name: str,
    *args: Any,
    default: Any = None,
) -> Any:
    """Safely call *engine.method_name(\\*args)* returning *default* on failure.

    Handles ``engine is None``, missing method, and any exception raised by the
    method itself.
    """
    if engine is None:
        return default
    method = getattr(engine, method_name, None)
    if method is None:
        return default
    try:
        return method(*args)
    except Exception:
        return default


def _make_labeled_section(title: str, children: list) -> Any:
    """Return a VBox with an HTML title and *children* widgets.

    Requires ipywidgets to be importable (caller is responsible for guarding).
    """
    import ipywidgets as widgets

    return widgets.VBox(
        [widgets.HTML(f"<b>{title}</b>"), *children],
        layout=widgets.Layout(padding="4px 0"),
    )


# ---------------------------------------------------------------------------
# Existing panels (preserved)
# ---------------------------------------------------------------------------


def build_control_panel(engine: StreamEngine) -> Dict[str, List[object]]:
    """Simple FPS/grid/contrast panel with filter checkboxes.

    Args:
        engine: A running or stopped StreamEngine instance.

    Returns:
        Dict with 'config' and 'filters' widget lists.
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as exc:
        raise ImportError("Install ipywidgets and ipython: pip install ipywidgets ipython") from exc

    cfg = engine.get_config()
    fps = widgets.IntSlider(value=cfg.fps, min=5, max=60, description="FPS")
    grid_w = widgets.IntSlider(value=cfg.grid_w, min=40, max=200, description="Grid W")
    grid_h = widgets.IntSlider(value=cfg.grid_h, min=20, max=120, description="Grid H")
    contrast = widgets.FloatSlider(
        value=cfg.contrast, min=0.5, max=3.0, step=0.1, description="Contrast"
    )
    brightness = widgets.IntSlider(
        value=cfg.brightness, min=-50, max=50, step=1, description="Brightness"
    )
    invert = widgets.Checkbox(value=cfg.invert, description="Invert")

    def on_change(_):
        engine.update_config(
            fps=fps.value,
            grid_w=grid_w.value,
            grid_h=grid_h.value,
            contrast=contrast.value,
            brightness=brightness.value,
            invert=invert.value,
        )

    for w in [fps, grid_w, grid_h, contrast, brightness, invert]:
        w.observe(on_change, names="value")

    filter_boxes: List[Any] = []
    for filter_obj in engine.filters:
        name = getattr(filter_obj, "name", filter_obj.__class__.__name__)
        enabled = getattr(filter_obj, "enabled", True)
        checkbox = widgets.Checkbox(value=enabled, description=name)

        def _toggle(change, target=filter_obj):
            if hasattr(target, "enabled"):
                setattr(target, "enabled", change["new"])

        checkbox.observe(_toggle, names="value")
        filter_boxes.append(checkbox)

    display(widgets.VBox([fps, grid_w, grid_h, contrast, brightness, invert]))
    if filter_boxes:
        display(widgets.VBox(filter_boxes))

    return {
        "config": [fps, grid_w, grid_h, contrast, brightness, invert],
        "filters": filter_boxes,
    }


def build_general_control_panel(
    engine: StreamEngine,
    filters: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Full 5-tab control panel (Network, Engine, Filters, View, AI).

    Args:
        engine: StreamEngine instance.
        filters: Optional dict of {name: Filter} objects. Auto-discovered if None.

    Returns:
        Dict with 'tabs', 'network', 'engine', 'filters', 'ascii', 'ia', 'status'.
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as exc:
        raise ImportError("Install ipywidgets and ipython: pip install ipywidgets ipython") from exc

    try:
        from ..adapters.processors import (
            BrightnessFilter,
            DetailBoostFilter,
            EdgeFilter,
            InvertFilter,
        )
    except Exception:
        BrightnessFilter = None
        DetailBoostFilter = None
        EdgeFilter = None
        InvertFilter = None
    try:
        from ..adapters.processors import CppInvertFilter
    except Exception:
        CppInvertFilter = None

    cfg = engine.get_config()
    Layout = getattr(widgets, "Layout", None)

    def _default_network_mode() -> str:
        if cfg.udp_broadcast:
            return "Broadcast"
        if cfg.host.startswith("239."):
            return "Multicast"
        if cfg.host in {"127.0.0.1", "localhost"}:
            return "Local"
        return "IP directa"

    status = widgets.HTML(
        value=_status_style("Ready. Use tabs and press Start in Engine tab.", "info")
    )

    # Network controls
    network_mode = widgets.Dropdown(
        options=["Local", "Broadcast", "Multicast", "IP directa"],
        value=_default_network_mode(),
        description="Net mode",
        style={"description_width": "80px"},
    )
    host_input = widgets.Text(
        value=cfg.host, description="Host", style={"description_width": "80px"}
    )
    port_input = widgets.IntText(
        value=cfg.port, description="Port", style={"description_width": "80px"}
    )
    apply_net_btn = widgets.Button(
        description="Apply network",
        layout=Layout(width="120px") if Layout else None,
    )

    # Camera controls
    camera_index = widgets.IntText(
        value=0, description="Camera", style={"description_width": "80px"}
    )
    apply_camera_btn = widgets.Button(
        description="Apply camera",
        layout=Layout(width="130px") if Layout else None,
    )

    # Filters
    if filters is None:
        filters = {}
        if EdgeFilter:
            filters["Edges"] = EdgeFilter(60, 120)
        if BrightnessFilter:
            filters["Brightness/Contrast"] = BrightnessFilter()
        if InvertFilter:
            filters["Invert"] = InvertFilter()
        if CppInvertFilter:
            filters["Invert (C++)"] = CppInvertFilter()
        if DetailBoostFilter:
            filters["Detail Boost"] = DetailBoostFilter()

    filter_checkboxes = {name: widgets.Checkbox(value=False, description=name) for name in filters}

    # ASCII/RAW controls
    dense_charset = " .'`^\\\",:;Il!i~+_-?][}{1)(|\\\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"

    fps_slider = widgets.IntSlider(value=cfg.fps, min=10, max=60, description="FPS")
    grid_w_slider = widgets.IntSlider(value=cfg.grid_w, min=60, max=200, description="Grid W")
    grid_h_slider = widgets.IntSlider(value=cfg.grid_h, min=20, max=120, description="Grid H")

    charset_options = {
        "Simple": " .:-=+*#",
        "Medium": " .:-=+*#%@",
        "Dense": dense_charset,
    }
    current_charset = cfg.charset
    if current_charset not in charset_options.values():
        charset_options["Current"] = current_charset
    charset_default = (
        current_charset
        if current_charset in charset_options.values()
        else charset_options["Simple"]
    )

    charset_dd = widgets.Dropdown(
        options=charset_options, value=charset_default, description="Charset"
    )

    render_mode = widgets.RadioButtons(
        options=[("ASCII", "ascii"), ("RAW (no ASCII)", "raw")],
        value=cfg.render_mode,
        description="Mode",
    )

    raw_width = widgets.IntText(value=cfg.raw_width or 640, description="Raw W")
    raw_height = widgets.IntText(value=cfg.raw_height or 360, description="Raw H")
    raw_use_size = widgets.Checkbox(
        value=cfg.raw_width is not None and cfg.raw_height is not None,
        description="Use RAW size",
    )

    contrast_slider = widgets.FloatSlider(
        value=cfg.contrast, min=0.5, max=3.0, step=0.1, description="Contrast"
    )
    brightness_slider = widgets.IntSlider(
        value=cfg.brightness, min=-50, max=50, step=1, description="Brightness"
    )
    frame_buffer_slider = widgets.IntSlider(
        value=cfg.frame_buffer_size, min=0, max=3, step=1, description="Buffer"
    )
    bitrate_text = widgets.Text(value=str(cfg.bitrate), description="Bitrate")

    apply_settings_btn = widgets.Button(
        description="Apply settings",
        layout=Layout(width="140px") if Layout else None,
    )
    clear_filters_btn = widgets.Button(
        description="Clear all",
        layout=Layout(width="120px") if Layout else None,
    )
    start_btn = widgets.Button(
        description="Start",
        layout=Layout(width="100px") if Layout else None,
    )
    stop_btn = widgets.Button(
        description="Stop",
        layout=Layout(width="100px") if Layout else None,
    )

    def _sync_host(change) -> None:
        mode = change["new"]
        if mode == "Local":
            host_input.value = "127.0.0.1"
        elif mode == "Broadcast":
            host_input.value = "255.255.255.255"
        elif mode == "Multicast":
            host_input.value = "239.0.0.1"

    def _apply_filters(_=None) -> None:
        selected = [filters[name] for name, cb in filter_checkboxes.items() if cb.value]
        if hasattr(engine, "filter_pipeline"):
            engine.filter_pipeline.replace(selected)
        elif hasattr(engine, "filters"):
            engine.filters[:] = selected
        if selected:
            names = ", ".join([getattr(f, "name", f.__class__.__name__) for f in selected])
            status.value = _status_style(f"Active filters: {names}", "ok")
        else:
            status.value = _status_style("No filters: normal image.", "info")

    def apply_network(_=None) -> None:
        mode = network_mode.value
        host = host_input.value.strip()
        udp_broadcast = False
        if mode == "Local":
            host = "127.0.0.1"
        elif mode == "Broadcast":
            udp_broadcast = True
            if not host:
                host = "255.255.255.255"
        elif mode == "Multicast":
            if not host:
                host = "239.0.0.1"
        elif mode == "IP directa":
            if not host:
                status.value = _status_style("Missing host for direct IP.", "warn")
                return

        was_running = engine.is_running
        if was_running:
            engine.stop()
        engine.update_config(host=host, port=port_input.value, udp_broadcast=udp_broadcast)
        if was_running:
            engine.start()
        status.value = _status_style(f"Network applied: {mode} -> {host}:{port_input.value}", "ok")

    def apply_camera(_=None) -> None:
        source = engine.get_source()
        if not hasattr(source, "set_camera_index"):
            status.value = _status_style(
                "Current source does not support camera switching.", "warn"
            )
            return
        was_running = engine.is_running
        if was_running:
            engine.stop()
        source.set_camera_index(int(camera_index.value))
        if was_running:
            engine.start()
        status.value = _status_style(f"Camera changed to index {camera_index.value}.", "ok")

    # AI overlay renderer
    try:
        from ..adapters.renderers import LandmarksOverlayRenderer
    except Exception:
        LandmarksOverlayRenderer = None

    def _sync_renderer() -> None:
        """Set renderer based on current view mode + AI overlay state."""
        base = AsciiRenderer() if render_mode.value == "ascii" else PassthroughRenderer()
        if LandmarksOverlayRenderer and ai_viz_dd.value == "Overlay landmarks":
            engine.set_renderer(LandmarksOverlayRenderer(inner=base))
        else:
            engine.set_renderer(base)

    def apply_settings(_=None) -> None:
        was_running = engine.is_running
        if was_running:
            engine.stop()
        raw_w = raw_width.value if raw_use_size.value else None
        raw_h = raw_height.value if raw_use_size.value else None
        engine.update_config(
            fps=fps_slider.value,
            grid_w=grid_w_slider.value,
            grid_h=grid_h_slider.value,
            charset=charset_dd.value,
            contrast=contrast_slider.value,
            brightness=brightness_slider.value,
            render_mode=render_mode.value,
            raw_width=raw_w,
            raw_height=raw_h,
            frame_buffer_size=frame_buffer_slider.value,
            bitrate=bitrate_text.value,
        )
        if was_running:
            engine.start()
        status.value = _status_style("View settings applied.", "ok")

    def clear_filters(_=None) -> None:
        for cb in filter_checkboxes.values():
            cb.value = False
        _apply_filters()

    def start_engine(_=None) -> None:
        engine.start()
        status.value = _status_style("Engine running.", "ok")

    def stop_engine(_=None) -> None:
        engine.stop()
        status.value = _status_style("Engine stopped.", "info")

    apply_net_btn.on_click(apply_network)
    network_mode.observe(_sync_host, names="value")
    apply_camera_btn.on_click(apply_camera)
    apply_settings_btn.on_click(apply_settings)
    clear_filters_btn.on_click(clear_filters)
    start_btn.on_click(start_engine)
    stop_btn.on_click(stop_engine)

    for cb in filter_checkboxes.values():
        cb.observe(_apply_filters, names="value")

    network_box = widgets.VBox(
        [
            widgets.HTML("<b>Network</b>"),
            widgets.HTML("<small>Local = 127.0.0.1. Broadcast/Multicast for UDP.</small>"),
            network_mode,
            widgets.HBox([host_input, port_input]),
            apply_net_btn,
        ],
        layout=Layout(padding="0 0 10px 0") if Layout else None,
    )

    engine_box = widgets.VBox(
        [
            widgets.HTML("<b>Engine</b>"),
            widgets.HTML("<small>Start to see preview in the cell above.</small>"),
            widgets.HBox([start_btn, stop_btn]),
            widgets.HTML("<b>Camera</b>"),
            widgets.HBox([camera_index, apply_camera_btn]),
        ],
        layout=Layout(padding="0 0 10px 0") if Layout else None,
    )

    filter_list = list(filter_checkboxes.values())
    n = len(filter_list)
    mid = max(1, (n + 1) // 2)
    row1 = widgets.HBox(filter_list[:mid])
    row2 = widgets.HBox(filter_list[mid:]) if mid < n else widgets.HTML("")
    filters_box = widgets.VBox(
        [
            widgets.HTML("<b>Image Filters</b>"),
            widgets.HTML("<small>Applied before render (ASCII/RAW). " "Combine multiple.</small>"),
            row1,
            row2,
            clear_filters_btn,
        ],
        layout=Layout(padding="0 0 10px 0") if Layout else None,
    )

    settings_box = widgets.VBox(
        [
            widgets.HTML("<b>View (ASCII / RAW)</b>"),
            widgets.HTML("<small>Video</small>"),
            fps_slider,
            widgets.HBox([grid_w_slider, grid_h_slider]),
            widgets.HTML("<small>Appearance</small>"),
            charset_dd,
            widgets.HBox([contrast_slider, brightness_slider]),
            render_mode,
            widgets.HTML("<small>RAW (size)</small>"),
            widgets.HBox([raw_use_size, raw_width, raw_height]),
            widgets.HBox([frame_buffer_slider, bitrate_text]),
            apply_settings_btn,
        ],
        layout=Layout(padding="0 0 10px 0") if Layout else None,
    )

    # AI tab
    def _analyzer_enabled(name: str) -> bool:
        if not hasattr(engine, "analyzer_pipeline"):
            return False
        for a in engine.analyzer_pipeline.analyzers:
            if getattr(a, "name", "") == name:
                return getattr(a, "enabled", False)
        return False

    face_cb = widgets.Checkbox(value=_analyzer_enabled("face"), description="Face detection")
    hands_cb = widgets.Checkbox(value=_analyzer_enabled("hands"), description="Hands detection")
    pose_cb = widgets.Checkbox(value=_analyzer_enabled("pose"), description="Pose detection")
    ai_viz_dd = widgets.Dropdown(
        options=["Normal (ASCII/RAW)", "Overlay landmarks"],
        value="Normal (ASCII/RAW)",
        description="Visualization",
    )
    apply_ai_btn = widgets.Button(description="Apply AI")

    detector_status_html = widgets.HTML(
        value="<i>Press Refresh detector status with engine running.</i>"
    )
    refresh_detector_btn = widgets.Button(description="Refresh detector status")

    def _count_points(v: object) -> int:
        if not isinstance(v, dict):
            return 0
        n = 0
        if "points" in v:
            arr = v["points"]
            if hasattr(arr, "size") and arr.size > 0:
                n += int(arr.size) // 2
            elif isinstance(arr, (list, tuple)):
                n += len(arr) // 2
        for key in ("left", "right", "joints"):
            if key not in v:
                continue
            arr = v[key]
            if hasattr(arr, "size") and arr.size > 0:
                n += int(arr.size) // 2
            elif isinstance(arr, (list, tuple)) and len(arr) > 0:
                n += len(arr) // 2 if hasattr(arr[0], "__len__") else len(arr)
        return n

    def _format_detector_status() -> str:
        if not hasattr(engine, "get_last_analysis"):
            return "<i>Engine has no analysis.</i>"
        _has_a = (
            hasattr(engine, "analyzer_pipeline")
            and getattr(engine.analyzer_pipeline, "has_any", lambda: False)()
        )
        a = engine.get_last_analysis()
        lines = []
        for name, label in (
            ("face", "Face"),
            ("hands", "Hands"),
            ("pose", "Pose"),
        ):
            pts = _count_points(a.get(name))
            lines.append(f"{label}: {pts} pts" if pts else f"{label}: --")
        out = "<b>Detector</b><br>" + " | ".join(lines)
        if not _has_a:
            out += "<br><small style='color:#856404'>No perception module." "</small>"
        return out

    def refresh_detector(_=None) -> None:
        detector_status_html.value = _format_detector_status()

    refresh_detector_btn.on_click(refresh_detector)

    def apply_ai(_=None) -> None:
        was_running = engine.is_running
        if was_running:
            engine.stop()
        if hasattr(engine, "analyzer_pipeline"):
            ap = engine.analyzer_pipeline
            ap.set_enabled("face", face_cb.value)
            ap.set_enabled("hands", hands_cb.value)
            ap.set_enabled("pose", pose_cb.value)
        _sync_renderer()
        if ai_viz_dd.value == "Overlay landmarks":
            status.value = _status_style("AI: landmarks overlay active.", "ok")
        else:
            status.value = _status_style("AI: normal visualization.", "info")
        if was_running:
            engine.start()

    apply_ai_btn.on_click(apply_ai)
    apply_ai_btn.layout = Layout(width="120px") if Layout else None
    refresh_detector_btn.layout = Layout(width="200px") if Layout else None

    def _on_analyzer_toggle(change):
        if hasattr(engine, "analyzer_pipeline"):
            ap = engine.analyzer_pipeline
            ap.set_enabled("face", face_cb.value)
            ap.set_enabled("hands", hands_cb.value)
            ap.set_enabled("pose", pose_cb.value)

    for cb in (face_cb, hands_cb, pose_cb):
        cb.observe(_on_analyzer_toggle, names="value")

    _has_analyzers = (
        hasattr(engine, "analyzer_pipeline")
        and getattr(engine.analyzer_pipeline, "has_any", lambda: False)()
    )
    if _has_analyzers:
        ai_aviso = widgets.HTML(
            value=(
                '<div style="padding:6px; background:#f8f9fa; '
                'border-radius:4px; font-size:12px;">'
                "1) Enable face/hands/pose - 2) Choose Overlay landmarks - "
                "3) Apply AI - 4) Start engine.</div>"
            )
        )
    else:
        ai_aviso = widgets.HTML(
            value=(
                '<div style="padding:8px; background:#fff3cd; '
                'border-radius:4px; font-size:12px; margin:4px 0;">'
                "<b>No perception module.</b> Start Jupyter with "
                "<code>PYTHONPATH=python:cpp/build</code> after running "
                "<code>bash cpp/build.sh</code>.</div>"
            )
        )

    ai_box = widgets.VBox(
        [
            widgets.HTML("<b>Perception (AI)</b>"),
            ai_aviso,
            widgets.HBox([face_cb, hands_cb, pose_cb]),
            ai_viz_dd,
            apply_ai_btn,
            widgets.HTML("<b>Detector status</b>"),
            detector_status_html,
            refresh_detector_btn,
        ],
        layout=Layout(padding="0 0 10px 0") if Layout else None,
    )

    tabs = widgets.Tab(children=[network_box, engine_box, filters_box, settings_box])
    tabs.set_title(0, "Red")
    tabs.set_title(1, "Motor")
    tabs.set_title(2, "Filtros")
    tabs.set_title(3, "Vista")

    display(widgets.HTML("<b>Status</b>"))
    display(status)
    display(widgets.HTML("<b>Controls</b>"))
    display(tabs)

    return {
        "tabs": tabs,
        "network": {
            "mode": network_mode,
            "host": host_input,
            "port": port_input,
            "apply": apply_net_btn,
        },
        "engine": {
            "start": start_btn,
            "stop": stop_btn,
            "camera_index": camera_index,
            "apply_camera": apply_camera_btn,
        },
        "filters": filter_checkboxes,
        "ascii": {
            "fps": fps_slider,
            "grid_w": grid_w_slider,
            "grid_h": grid_h_slider,
            "charset": charset_dd,
            "contrast": contrast_slider,
            "brightness": brightness_slider,
            "render_mode": render_mode,
            "raw_width": raw_width,
            "raw_height": raw_height,
            "raw_use_size": raw_use_size,
            "frame_buffer_size": frame_buffer_slider,
            "bitrate": bitrate_text,
            "apply": apply_settings_btn,
        },
        "status": status,
    }


# ---------------------------------------------------------------------------
# Device info helpers (used by diagnostics)
# ---------------------------------------------------------------------------


def _get_device_info() -> Dict[str, Any]:
    """Collect video device and OpenCV information for the diagnostics panel."""
    info: Dict[str, Any] = {
        "devices": [],
        "open_indices": [],
        "groups": "",
        "in_video_group": False,
        "cv2_version": None,
        "backend": None,
    }
    if sys.platform == "linux" and os.path.exists("/dev"):
        videos = [f for f in os.listdir("/dev") if f.startswith("video")]
        videos.sort(key=lambda x: (len(x), x))
        for v in videos:
            path = f"/dev/{v}"
            try:
                st = os.stat(path)
                info["devices"].append({"path": path, "mode": oct(st.st_mode)[-3:]})
            except Exception as e:
                info["devices"].append({"path": path, "error": str(e)})
    try:
        out = subprocess.run(["groups"], capture_output=True, text=True, timeout=2)
        info["groups"] = (out.stdout or out.stderr or "").strip()
        info["in_video_group"] = "video" in (out.stdout or "")
    except Exception:
        pass
    try:
        import cv2

        info["cv2_version"] = cv2.__version__
        cap_backend = cv2.CAP_V4L2 if sys.platform == "linux" else getattr(cv2, "CAP_ANY", 0)
        stderr_fd = sys.stderr.fileno()
        save_fd = os.dup(stderr_fd)
        devnull = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(devnull, stderr_fd)
            for i in range(6):
                cap = cv2.VideoCapture(i, cap_backend)
                if cap.isOpened():
                    ret, frame = cap.read()
                    shape = frame.shape if (ret and frame is not None) else None
                    cap.release()
                    info["open_indices"].append({"index": i, "shape": shape})
            cap = cv2.VideoCapture(0, cap_backend if sys.platform == "linux" else 0)
            if cap.isOpened():
                info["backend"] = getattr(cap, "getBackendName", lambda: "?")()
                cap.release()
        finally:
            os.dup2(save_fd, stderr_fd)
            os.close(devnull)
            os.close(save_fd)
    except Exception as e:
        info["cv2_error"] = str(e)
    return info


def _device_info_to_html(data: Dict[str, Any]) -> str:
    """Convert _get_device_info() output to readable HTML."""
    lines = ["<b>Video devices</b>"]
    if data["devices"]:
        for d in data["devices"]:
            if "error" in d:
                lines.append(f"  {d['path']}: error {d['error']}")
            else:
                lines.append(f"  {d['path']} (mode {d['mode']})")
    else:
        lines.append("  No /dev/video*")
    lines.append("<br><b>Video group</b>: " + ("yes" if data["in_video_group"] else "no"))
    lines.append("  groups: " + (data["groups"] or "--"))
    lines.append("<br><b>OpenCV</b> " + (data["cv2_version"] or "not available"))
    if data.get("cv2_error"):
        lines.append("  Error: " + data["cv2_error"])
    elif data["open_indices"]:
        for o in data["open_indices"]:
            s = f"  index {o['index']}: OPENS"
            if o.get("shape") is not None:
                s += f" shape={o['shape']}"
            lines.append(s)
        if data.get("backend"):
            lines.append("  backend: " + data["backend"])
    else:
        lines.append("  No index 0..5 opens")
    return "<pre>" + "\n".join(lines) + "</pre>"


# ---------------------------------------------------------------------------
# Existing diagnostics panel (preserved)
# ---------------------------------------------------------------------------


def build_diagnostics_panel(
    engine: Optional[StreamEngine] = None,
) -> Dict[str, Any]:
    """Diagnostics panel: devices, latency, benchmarking.

    Args:
        engine: Optional StreamEngine. If provided, shows latency and enables
            benchmarking.

    Returns:
        Dict with widgets (devices_html, latency_html, refresh_btn, etc.).
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as exc:
        raise ImportError("Install ipywidgets and ipython: pip install ipywidgets ipython") from exc

    devices_html = widgets.HTML(value=_device_info_to_html(_get_device_info()))
    latency_html = widgets.HTML(value="<i>Start the engine to see real-time latency.</i>")
    benchmark_output = widgets.Output()
    benchmark_seconds = widgets.IntText(value=5, description="Seconds")
    benchmark_btn = widgets.Button(description="Run benchmark")

    def refresh(_=None) -> None:
        data = _get_device_info()
        devices_html.value = _device_info_to_html(data)
        if engine is not None and engine.is_running:
            m = engine.metrics.get_summary()
            latency_html.value = (
                "<b>Latency / metrics</b><br>"
                f"FPS: {m['fps']:.1f} | "
                f"Frames: {m['frames_processed']} | "
                f"Latency avg: {m['latency_avg']*1000:.1f} ms | "
                f"min: {m['latency_min']*1000:.1f} ms | "
                f"max: {m['latency_max']*1000:.1f} ms<br>"
                f"Uptime: {m['uptime']:.1f} s | "
                f"Errors: {m['total_errors']}"
            )
        else:
            latency_html.value = (
                "<i>Engine not running.</i> Start the engine and press " "Refresh to see latency."
            )

    def run_benchmark(_=None) -> None:
        if engine is None:
            with benchmark_output:
                print("No engine associated.")
            return
        secs = max(1, min(60, int(benchmark_seconds.value)))
        benchmark_btn.disabled = True
        benchmark_output.clear_output()

        def _run() -> None:
            try:
                was_running = engine.is_running
                if not was_running:
                    engine.start(blocking=False)
                time.sleep(secs)
                if not was_running:
                    engine.stop()
                report = _safe_engine_call(engine, "get_profiling_report", default="")
                summary = engine.metrics.get_summary()
                with benchmark_output:
                    print(f"=== Benchmark {secs} s ===\n")
                    print(
                        f"Metrics: FPS={summary['fps']:.1f}  "
                        f"frames={summary['frames_processed']}  "
                        f"latency_avg="
                        f"{summary['latency_avg'] * 1000:.2f} ms"
                    )
                    if report:
                        print("\n" + report)
            except Exception as e:
                with benchmark_output:
                    print("Benchmark error:", e)
            finally:
                benchmark_btn.disabled = False

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    refresh_btn = widgets.Button(description="Refresh")
    refresh_btn.on_click(refresh)
    benchmark_btn.on_click(run_benchmark)

    section_devices = widgets.VBox(
        [
            widgets.HTML("<b>Connected devices</b>"),
            devices_html,
            refresh_btn,
        ]
    )
    section_latency = widgets.VBox(
        [
            widgets.HTML("<b>Process latency</b>"),
            latency_html,
            widgets.HTML("<small>Press Refresh with engine running.</small>"),
        ]
    )
    section_benchmark = widgets.VBox(
        [
            widgets.HTML("<b>Benchmarking</b>"),
            widgets.HBox([benchmark_seconds, widgets.HTML("s")]),
            benchmark_btn,
            benchmark_output,
        ]
    )

    panel = widgets.VBox(
        [
            widgets.HTML("<h3>Diagnostics & Benchmarking</h3>"),
            section_devices,
            widgets.HTML("<br>"),
            section_latency,
            widgets.HTML("<br>"),
            section_benchmark,
        ]
    )
    display(panel)

    return {
        "panel": panel,
        "devices_html": devices_html,
        "latency_html": latency_html,
        "refresh_btn": refresh_btn,
        "benchmark_btn": benchmark_btn,
        "benchmark_output": benchmark_output,
        "refresh": refresh,
    }


# ---------------------------------------------------------------------------
# Existing engine factory (preserved)
# ---------------------------------------------------------------------------


def build_engine_for_notebook(
    camera_index: int = 0,
    config: Optional[EngineConfig] = None,
) -> StreamEngine:
    """Create a StreamEngine wired for notebook display.

    Creates an ipywidgets.Image preview widget, wires it to a
    NotebookPreviewSink, and optionally adds perception analyzers.

    Args:
        camera_index: OpenCV camera index (default 0).
        config: Optional EngineConfig override.

    Returns:
        A configured StreamEngine ready to start.
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as exc:
        raise ImportError("Install ipywidgets and ipython: pip install ipywidgets ipython") from exc

    image_widget = widgets.Image(format="jpeg")
    display(widgets.HTML("<b>Preview (image appears after Start)</b>"))
    display(image_widget)

    sink = NotebookPreviewSink(image_widget=image_widget)
    cfg = config or EngineConfig(host="127.0.0.1", port=1234)

    analyzers: Optional[AnalyzerPipeline] = None
    try:
        from ..adapters.perception import (
            FaceLandmarkAnalyzer,
            HandLandmarkAnalyzer,
            PoseLandmarkAnalyzer,
        )

        analyzers = AnalyzerPipeline(
            [
                FaceLandmarkAnalyzer(),
                HandLandmarkAnalyzer(),
                PoseLandmarkAnalyzer(),
            ]
        )
    except Exception:
        pass

    engine = StreamEngine(
        source=OpenCVCameraSource(camera_index),
        renderer=PassthroughRenderer(),
        sink=sink,
        config=cfg,
        analyzers=analyzers,
        filters=FilterPipeline([]),
    )
    return engine


# ---------------------------------------------------------------------------
# Phase 2: Advanced Diagnostics Panel
# ---------------------------------------------------------------------------


def build_advanced_diagnostics_panel(
    engine: Optional[StreamEngine] = None,
) -> Dict[str, Any]:
    """Advanced diagnostics panel with profiler stats, memory, CPU, errors.

    Provides per-stage profiling table, memory consumption, CPU utilization,
    error breakdown, and auto-refresh capability.

    Args:
        engine: Optional StreamEngine. If None, shows placeholder text.

    Returns:
        Dict with widget references for programmatic access.
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as exc:
        raise ImportError("Install ipywidgets and ipython: pip install ipywidgets ipython") from exc

    profiler_html = widgets.HTML(value="<i>No profiling data yet.</i>")
    memory_html = widgets.HTML(value="<i>Memory info loading...</i>")
    cpu_html = widgets.HTML(value="<i>CPU info loading...</i>")
    errors_html = widgets.HTML(value="<i>No error data.</i>")
    status = widgets.HTML(value=_status_style("Advanced diagnostics ready.", "info"))

    auto_refresh_cb = widgets.Checkbox(value=True, description="Auto-refresh (2s)")
    profiler_enable_cb = widgets.Checkbox(value=False, description="Enable profiler")
    refresh_btn = widgets.Button(description="Refresh")

    # Track CPU times across refreshes
    _cpu_state: Dict[str, float] = {"user": 0.0, "sys": 0.0, "wall": 0.0}

    # Initialize profiler checkbox from engine state
    if engine is not None and hasattr(engine, "profiler"):
        profiler_enable_cb.value = engine.profiler.enabled

    # Phase names and order
    phase_names = [
        "capture",
        "analysis",
        "transformation",
        "filtering",
        "rendering",
        "writing",
        "total_frame",
    ]

    def _build_profiler_table() -> str:
        stats = _safe_engine_call(engine, "get_profiling_stats", default={})
        if not stats:
            return "<i>No profiling data. Enable profiler and run engine.</i>"
        rows = []
        for phase in phase_names:
            if phase in stats:
                s = stats[phase]
                rows.append(
                    f"<tr><td>{phase}</td>"
                    f"<td>{s['avg_time']*1000:.2f}</td>"
                    f"<td>{s['min_time']*1000:.2f}</td>"
                    f"<td>{s['max_time']*1000:.2f}</td>"
                    f"<td>{s['std_dev']*1000:.2f}</td>"
                    f"<td>{s['count']}</td></tr>"
                )
        if not rows:
            return "<i>Profiler enabled but no data collected yet.</i>"
        header = (
            "<table style='border-collapse:collapse; font-size:12px;'>"
            "<tr style='background:#f0f0f0;'>"
            "<th style='padding:4px 8px; border:1px solid #ddd;'>Phase</th>"
            "<th style='padding:4px 8px; border:1px solid #ddd;'>Avg (ms)</th>"
            "<th style='padding:4px 8px; border:1px solid #ddd;'>Min (ms)</th>"
            "<th style='padding:4px 8px; border:1px solid #ddd;'>Max (ms)</th>"
            "<th style='padding:4px 8px; border:1px solid #ddd;'>Std (ms)</th>"
            "<th style='padding:4px 8px; border:1px solid #ddd;'>Count</th>"
            "</tr>"
        )
        return header + "".join(rows) + "</table>"

    def _build_memory_html() -> str:
        try:
            peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            peak_mb = peak_kb / 1024.0
            lines = [f"Peak RSS: {peak_mb:.1f} MB"]
        except Exception:
            lines = ["Peak RSS: N/A"]
        try:
            with open("/proc/self/status", "r") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        vm_rss = line.split(":")[1].strip()
                        lines.append(f"Current VmRSS: {vm_rss}")
                        break
        except Exception:
            pass
        return "<br>".join(lines)

    def _build_cpu_html() -> str:
        try:
            t = os.times()
            user = t.user
            sys_t = t.system
            wall = time.monotonic()
            prev_user = _cpu_state.get("user", user)
            prev_sys = _cpu_state.get("sys", sys_t)
            prev_wall = _cpu_state.get("wall", wall)
            delta_wall = wall - prev_wall
            if delta_wall > 0.01:
                raw_pct = ((user - prev_user) + (sys_t - prev_sys)) / delta_wall * 100
                num_cpus = os.cpu_count() or 1
                cpu_pct = raw_pct / num_cpus
            else:
                cpu_pct = 0.0
            _cpu_state["user"] = user
            _cpu_state["sys"] = sys_t
            _cpu_state["wall"] = wall
            color = "#28a745" if cpu_pct < 50 else "#ffc107" if cpu_pct < 80 else "#dc3545"
            bar_width = min(100, max(1, int(cpu_pct)))
            return (
                f"CPU: {cpu_pct:.1f}%<br>"
                f'<div style="background:#eee; border-radius:4px; '
                f'height:16px; width:200px; display:inline-block;">'
                f'<div style="background:{color}; height:16px; '
                f'width:{bar_width}%; border-radius:4px;"></div></div>'
            )
        except Exception:
            return "CPU info: N/A"

    def _build_errors_html() -> str:
        if engine is None:
            return "<i>No engine.</i>"
        errors = _safe_engine_call(engine, "get_errors", default=None)
        if errors is None:
            errors = {}
            if hasattr(engine, "metrics"):
                errors = engine.metrics.get_errors()
        if not errors:
            return "<i>No errors recorded.</i>"
        rows = "".join(
            f"<tr><td>{comp}</td><td>{count}</td></tr>" for comp, count in sorted(errors.items())
        )
        return (
            "<table style='border-collapse:collapse; font-size:12px;'>"
            "<tr style='background:#f0f0f0;'>"
            "<th style='padding:4px 8px; border:1px solid #ddd;'>"
            "Component</th>"
            "<th style='padding:4px 8px; border:1px solid #ddd;'>"
            "Errors</th></tr>" + rows + "</table>"
        )

    def _refresh(_=None) -> None:
        profiler_html.value = _build_profiler_table()
        memory_html.value = _build_memory_html()
        cpu_html.value = _build_cpu_html()
        errors_html.value = _build_errors_html()

    # Initialize CPU state
    try:
        t = os.times()
        _cpu_state["user"] = t.user
        _cpu_state["sys"] = t.system
        _cpu_state["wall"] = time.monotonic()
    except Exception:
        pass

    _refresh()

    refresh_btn.on_click(_refresh)

    # Auto-refresh management
    _auto_refresh_state: Dict[str, Any] = {"handle": None}

    def _on_auto_refresh_toggle(change) -> None:
        if change["new"]:
            handle = _periodic_refresh(_refresh, 2000)
            _auto_refresh_state["handle"] = handle
        else:
            handle = _auto_refresh_state.get("handle")
            if handle:
                handle["stop"]()
            _auto_refresh_state["handle"] = None

    auto_refresh_cb.observe(_on_auto_refresh_toggle, names="value")

    # Start auto-refresh immediately since default is True
    _auto_refresh_state["handle"] = _periodic_refresh(_refresh, 2000)

    # Profiler enable toggle
    def _on_profiler_toggle(change) -> None:
        if engine is not None and hasattr(engine, "profiler"):
            engine.profiler.enabled = change["new"]
        if not change["new"]:
            status.value = _status_style("Profiler disabled. Stats will be stale.", "warn")
        else:
            status.value = _status_style("Profiler enabled.", "ok")

    profiler_enable_cb.observe(_on_profiler_toggle, names="value")

    def _stop_refresh() -> None:
        auto_refresh_cb.value = False
        handle = _auto_refresh_state.get("handle")
        if handle:
            handle["stop"]()

    panel = widgets.VBox(
        [
            widgets.HTML("<h3>Advanced Diagnostics</h3>"),
            _make_labeled_section("Profiler Stats", [profiler_html]),
            _make_labeled_section("Memory", [memory_html]),
            _make_labeled_section("CPU Usage", [cpu_html]),
            _make_labeled_section("Error Breakdown", [errors_html]),
            widgets.HBox([auto_refresh_cb, profiler_enable_cb, refresh_btn]),
            status,
        ]
    )
    display(panel)

    return {
        "panel": panel,
        "profiler_html": profiler_html,
        "memory_html": memory_html,
        "cpu_html": cpu_html,
        "errors_html": errors_html,
        "auto_refresh_cb": auto_refresh_cb,
        "profiler_enable_cb": profiler_enable_cb,
        "refresh_btn": refresh_btn,
        "refresh": _refresh,
        "stop_refresh": _stop_refresh,
    }


# ---------------------------------------------------------------------------
# Phase 3: Perception Control Panel
# ---------------------------------------------------------------------------


def build_perception_control_panel(
    engine: Optional[StreamEngine] = None,
) -> Dict[str, Any]:
    """Perception control panel with per-analyzer toggles, confidence, status.

    Args:
        engine: Optional StreamEngine with analyzer_pipeline.

    Returns:
        Dict with widget references for programmatic access.
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as exc:
        raise ImportError("Install ipywidgets and ipython: pip install ipywidgets ipython") from exc

    try:
        from ..adapters.renderers import LandmarksOverlayRenderer
    except Exception:
        LandmarksOverlayRenderer = None

    try:
        import perception_cpp  # noqa: F401

        cpp_available = True
    except ImportError:
        cpp_available = False

    status = widgets.HTML(value=_status_style("Perception control ready.", "info"))
    model_info_html = widgets.HTML(value="")
    analysis_html = widgets.HTML(value="<i>No analysis data yet.</i>")
    refresh_btn = widgets.Button(description="Refresh")

    # Discover analyzers
    analyzer_names = ["face", "hands", "pose"]
    has_pipeline = (
        engine is not None
        and hasattr(engine, "analyzer_pipeline")
        and getattr(engine.analyzer_pipeline, "has_any", lambda: False)()
    )

    # Per-analyzer widgets
    analyzer_widgets: Dict[str, Dict[str, Any]] = {}

    def _get_analyzer(name: str) -> Any:
        """Get analyzer object by name from pipeline."""
        if engine is None or not hasattr(engine, "analyzer_pipeline"):
            return None
        for a in engine.analyzer_pipeline.analyzers:
            if getattr(a, "name", "") == name:
                return a
        return None

    def _is_enabled(name: str) -> bool:
        a = _get_analyzer(name)
        if a is None:
            return False
        return getattr(a, "enabled", False)

    for aname in analyzer_names:
        enabled_cb = widgets.Checkbox(
            value=_is_enabled(aname) if has_pipeline else False,
            description=aname.capitalize(),
            disabled=not has_pipeline,
        )
        analyzer_obj = _get_analyzer(aname)
        has_conf = analyzer_obj is not None and (
            hasattr(analyzer_obj, "confidence_threshold") or hasattr(analyzer_obj, "min_confidence")
        )
        conf_attr = None
        conf_val = 0.5
        if analyzer_obj is not None:
            if hasattr(analyzer_obj, "confidence_threshold"):
                conf_attr = "confidence_threshold"
                conf_val = getattr(analyzer_obj, "confidence_threshold", 0.5)
            elif hasattr(analyzer_obj, "min_confidence"):
                conf_attr = "min_confidence"
                conf_val = getattr(analyzer_obj, "min_confidence", 0.5)

        confidence = widgets.FloatSlider(
            value=conf_val,
            min=0.0,
            max=1.0,
            step=0.05,
            description="Confidence",
            disabled=not has_conf,
        )
        status_html = widgets.HTML(value="<i>--</i>")

        # Bind toggle
        def _make_toggle_cb(name_):
            def _toggle(change):
                if engine is not None and hasattr(engine, "analyzer_pipeline"):
                    engine.analyzer_pipeline.set_enabled(name_, change["new"])

            return _toggle

        enabled_cb.observe(_make_toggle_cb(aname), names="value")

        # Bind confidence
        def _make_conf_cb(name_, attr_):
            def _conf_change(change):
                a = _get_analyzer(name_)
                if a is not None and attr_ is not None:
                    setattr(a, attr_, change["new"])

            return _conf_change

        if conf_attr:
            confidence.observe(_make_conf_cb(aname, conf_attr), names="value")

        analyzer_widgets[aname] = {
            "enabled_cb": enabled_cb,
            "confidence": confidence,
            "status_html": status_html,
        }

    # Model info
    model_lines = []
    if cpp_available:
        model_lines.append('<span style="color:#28a745;">perception_cpp: available</span>')
    else:
        model_lines.append('<span style="color:#ffc107;">perception_cpp: not available</span>')
    for aname in analyzer_names:
        a = _get_analyzer(aname)
        if a is not None:
            mpath = getattr(a, "model_path", None)
            if mpath:
                model_lines.append(f"{aname}: {mpath}")
    model_info_html.value = "<br>".join(model_lines) if model_lines else "--"

    # Visualization mode
    viz_options = ["Normal (ASCII/RAW)", "Overlay landmarks"]
    viz_mode = widgets.Dropdown(
        options=viz_options,
        value="Normal (ASCII/RAW)",
        description="Viz mode",
    )
    apply_viz_btn = widgets.Button(description="Apply viz")

    def _apply_viz(_=None) -> None:
        if engine is None:
            status.value = _status_style("No engine.", "warn")
            return
        was_running = engine.is_running
        if was_running:
            engine.stop()
        current_renderer = _safe_engine_call(engine, "get_renderer")
        is_ascii = type(current_renderer).__name__ == "AsciiRenderer"
        base = AsciiRenderer() if is_ascii else PassthroughRenderer()
        if LandmarksOverlayRenderer and viz_mode.value == "Overlay landmarks":
            engine.set_renderer(LandmarksOverlayRenderer(inner=base))
        else:
            engine.set_renderer(base)
        if was_running:
            engine.start()
        status.value = _status_style(f"Visualization: {viz_mode.value}", "ok")

    apply_viz_btn.on_click(_apply_viz)

    def _count_points_analysis(v: object) -> int:
        """Count landmark points from analysis result."""
        if not isinstance(v, dict):
            return 0
        n = 0
        for key in ("points", "left", "right", "joints"):
            if key not in v:
                continue
            arr = v[key]
            if hasattr(arr, "size") and arr.size > 0:
                n += int(arr.size) // 2
            elif isinstance(arr, (list, tuple)) and len(arr) > 0:
                if hasattr(arr[0], "__len__"):
                    n += len(arr) // 2
                else:
                    n += len(arr)
        return n

    def _refresh_analysis(_=None) -> None:
        a = _safe_engine_call(engine, "get_last_analysis", default={})
        parts = []
        for aname in analyzer_names:
            pts = _count_points_analysis(a.get(aname))
            analyzer_widgets[aname]["status_html"].value = f"{pts} pts" if pts else "--"
            parts.append(f"{aname}: {pts} pts" if pts else f"{aname}: --")
        analysis_html.value = " | ".join(parts)
        # Parallel info
        if has_pipeline:
            active = sum(1 for an in analyzer_names if analyzer_widgets[an]["enabled_cb"].value)
            par_info = "parallel execution" if active > 1 else "sequential execution"
            analysis_html.value += f"<br><small>({par_info})</small>"

    refresh_btn.on_click(_refresh_analysis)
    _refresh_analysis()

    # Build cards
    cards = []
    for aname in analyzer_names:
        aw = analyzer_widgets[aname]
        cards.append(
            widgets.VBox(
                [
                    aw["enabled_cb"],
                    aw["confidence"],
                    aw["status_html"],
                ],
                layout=widgets.Layout(
                    border="1px solid #ddd",
                    padding="6px",
                    margin="4px",
                ),
            )
        )

    if not has_pipeline:
        warning = widgets.HTML(
            value=_status_style(
                "No perception module available. Install perception_cpp.",
                "warn",
            )
        )
    else:
        warning = widgets.HTML(value="")

    panel = widgets.VBox(
        [
            widgets.HTML("<h3>Perception Control</h3>"),
            warning,
            widgets.HBox(cards),
            _make_labeled_section("Model Info", [model_info_html]),
            _make_labeled_section(
                "Visualization",
                [widgets.HBox([viz_mode, apply_viz_btn])],
            ),
            _make_labeled_section("Analysis Results", [analysis_html, refresh_btn]),
            status,
        ]
    )
    display(panel)

    return {
        "panel": panel,
        "analyzers": analyzer_widgets,
        "model_info_html": model_info_html,
        "viz_mode": viz_mode,
        "analysis_html": analysis_html,
        "refresh_btn": refresh_btn,
        "apply_viz_btn": apply_viz_btn,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Phase 4A: Filter Designer Panel
# ---------------------------------------------------------------------------


def build_filter_designer_panel(
    engine: Optional[StreamEngine] = None,
    filters: Optional[Dict[str, object]] = None,
) -> Dict[str, Any]:
    """Filter designer panel with per-filter parameter sliders and ordering.

    Args:
        engine: Optional StreamEngine.
        filters: Optional dict of {name: Filter}. Auto-discovered if None.

    Returns:
        Dict with widget references for programmatic access.
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as exc:
        raise ImportError("Install ipywidgets and ipython: pip install ipywidgets ipython") from exc

    # Discover filters
    if filters is None:
        filters = {}
        try:
            from ..adapters.processors import (
                BrightnessFilter,
                DetailBoostFilter,
                EdgeFilter,
                InvertFilter,
            )
        except Exception:
            BrightnessFilter = None
            DetailBoostFilter = None
            EdgeFilter = None
            InvertFilter = None
        try:
            from ..adapters.processors import (
                CppBrightnessContrastFilter,
                CppChannelSwapFilter,
                CppGrayscaleFilter,
                CppInvertFilter,
            )
        except Exception:
            CppBrightnessContrastFilter = None
            CppChannelSwapFilter = None
            CppGrayscaleFilter = None
            CppInvertFilter = None

        if EdgeFilter:
            filters["Edges"] = EdgeFilter(60, 120)
        if BrightnessFilter:
            filters["Brightness/Contrast"] = BrightnessFilter()
        if InvertFilter:
            filters["Invert"] = InvertFilter()
        if DetailBoostFilter:
            filters["Detail Boost"] = DetailBoostFilter()
        if CppInvertFilter:
            filters["Invert (C++)"] = CppInvertFilter()
        if CppBrightnessContrastFilter:
            filters["Brightness (C++)"] = CppBrightnessContrastFilter()
        if CppGrayscaleFilter:
            filters["Grayscale (C++)"] = CppGrayscaleFilter()
        if CppChannelSwapFilter:
            filters["Channel Swap (C++)"] = CppChannelSwapFilter()

    status = widgets.HTML(value=_status_style("Filter designer ready.", "info"))
    active_summary_html = widgets.HTML(value="<i>No active filters.</i>")
    clear_all_btn = widgets.Button(description="Clear all")

    # Track filter order
    filter_order: List[str] = list(filters.keys())
    filter_cards: Dict[str, Dict[str, Any]] = {}

    def _apply_filters() -> None:
        """Apply enabled filters in current order to the engine."""
        selected = [
            filters[name]
            for name in filter_order
            if name in filter_cards and filter_cards[name]["enabled_cb"].value
        ]
        if engine is not None and hasattr(engine, "filter_pipeline"):
            engine.filter_pipeline.replace(selected)
        elif engine is not None and hasattr(engine, "filters"):
            engine.filters[:] = selected
        # Update summary
        if selected:
            parts = []
            for f in selected:
                fname = getattr(f, "name", f.__class__.__name__)
                parts.append(fname)
            active_summary_html.value = "Active: " + ", ".join(parts)
        else:
            active_summary_html.value = "<i>No active filters.</i>"

    # Known parameter mappings
    _param_specs: Dict[str, List[Dict[str, Any]]] = {
        "Edges": [
            {
                "attr": "low_threshold",
                "widget": "IntSlider",
                "kwargs": {
                    "min": 0,
                    "max": 255,
                    "description": "Low threshold",
                },
            },
            {
                "attr": "high_threshold",
                "widget": "IntSlider",
                "kwargs": {
                    "min": 0,
                    "max": 255,
                    "description": "High threshold",
                },
            },
        ],
        "Brightness/Contrast": [
            {
                "attr": "alpha",
                "widget": "FloatSlider",
                "kwargs": {
                    "min": 0.5,
                    "max": 3.0,
                    "step": 0.1,
                    "description": "Contrast",
                },
            },
            {
                "attr": "beta",
                "widget": "IntSlider",
                "kwargs": {
                    "min": -100,
                    "max": 100,
                    "description": "Brightness",
                },
            },
        ],
        "Detail Boost": [
            {
                "attr": "strength",
                "widget": "FloatSlider",
                "kwargs": {
                    "min": 0.0,
                    "max": 5.0,
                    "step": 0.1,
                    "description": "Strength",
                },
            },
        ],
        "hand_spatial_warp": [
            {
                "attr": "strength",
                "widget": "FloatSlider",
                "kwargs": {
                    "min": 0.0,
                    "max": 800.0,
                    "step": 10.0,
                    "description": "Strength",
                },
            },
            {
                "attr": "falloff",
                "widget": "FloatSlider",
                "kwargs": {
                    "min": 0.05,
                    "max": 0.8,
                    "step": 0.01,
                    "description": "Falloff",
                },
            },
            {
                "attr": "mode",
                "widget": "Dropdown",
                "kwargs": {
                    "options": ["stretch", "compress", "twist"],
                    "description": "Mode",
                },
            },
        ],
        "hand_frame": [
            {
                "attr": "effect",
                "widget": "Dropdown",
                "kwargs": {
                    "options": ["ascii", "invert", "blur", "pixelate", "edge", "tint"],
                    "description": "Effect",
                },
            },
            {
                "attr": "effect_strength",
                "widget": "FloatSlider",
                "kwargs": {
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.1,
                    "description": "Strength",
                },
            },
            {
                "attr": "border_thickness",
                "widget": "IntSlider",
                "kwargs": {
                    "min": 0,
                    "max": 10,
                    "description": "Border",
                },
            },
        ],
    }

    for fname, fobj in filters.items():
        enabled_cb = widgets.Checkbox(value=False, description=fname)
        params: Dict[str, Any] = {}
        param_widgets_list: List[Any] = []

        specs = _param_specs.get(fname, [])
        for spec in specs:
            attr = spec["attr"]
            if not hasattr(fobj, attr):
                continue
            current_val = getattr(fobj, attr)
            wtype = getattr(widgets, spec["widget"])
            kw = dict(spec["kwargs"])
            kw["value"] = current_val
            w = wtype(**kw)

            def _make_param_cb(filter_obj, attr_name):
                def _on_change(change):
                    setattr(filter_obj, attr_name, change["new"])

                return _on_change

            w.observe(_make_param_cb(fobj, attr), names="value")
            params[attr] = w
            param_widgets_list.append(w)

        def _make_enable_cb(name_):
            def _on_enable(change):
                _apply_filters()

            return _on_enable

        enabled_cb.observe(_make_enable_cb(fname), names="value")

        filter_cards[fname] = {
            "enabled_cb": enabled_cb,
            "params": params,
        }

    def _clear_all(_=None) -> None:
        for card in filter_cards.values():
            card["enabled_cb"].value = False
        _apply_filters()
        status.value = _status_style("All filters cleared.", "info")

    clear_all_btn.on_click(_clear_all)

    # Build visual cards
    card_boxes = []
    for fname in filter_order:
        if fname not in filter_cards:
            continue
        card = filter_cards[fname]
        children = [card["enabled_cb"]]
        for pw in card["params"].values():
            children.append(pw)
        card_boxes.append(
            widgets.VBox(
                children,
                layout=widgets.Layout(
                    border="1px solid #ddd",
                    padding="6px",
                    margin="4px",
                ),
            )
        )

    panel = widgets.VBox(
        [
            widgets.HTML("<h3>Filter Designer</h3>"),
            *card_boxes,
            active_summary_html,
            clear_all_btn,
            status,
        ]
    )
    display(panel)

    return {
        "panel": panel,
        "filter_cards": filter_cards,
        "active_summary_html": active_summary_html,
        "clear_all_btn": clear_all_btn,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Phase 4B: Output Manager Panel
# ---------------------------------------------------------------------------


def build_output_manager_panel(
    engine: Optional[StreamEngine] = None,
) -> Dict[str, Any]:
    """Output manager panel for multi-sink configuration.

    Args:
        engine: Optional StreamEngine.

    Returns:
        Dict with widget references for programmatic access.
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as exc:
        raise ImportError("Install ipywidgets and ipython: pip install ipywidgets ipython") from exc

    # Guarded imports for sink types
    try:
        from ..adapters.outputs import CompositeOutputSink
    except Exception:
        CompositeOutputSink = None
    try:
        from ..adapters.outputs import FfmpegUdpOutput
    except Exception:
        FfmpegUdpOutput = None
    try:
        from ..adapters.outputs import AsciiFrameRecorder
    except Exception:
        AsciiFrameRecorder = None
    try:
        from ..adapters.outputs import PreviewSink
    except Exception:
        PreviewSink = None
    try:
        from ..adapters.outputs import FfmpegRtspSink
    except Exception:
        FfmpegRtspSink = None
    try:
        from ..adapters.outputs import WebRTCOutput
    except Exception:
        WebRTCOutput = None

    status = widgets.HTML(value=_status_style("Output manager ready.", "info"))
    current_sinks_html = widgets.HTML(value="<i>Loading...</i>")
    refresh_btn = widgets.Button(description="Refresh")

    # Available sink types
    available_types = ["NotebookPreviewSink"]
    if FfmpegUdpOutput:
        available_types.append("FfmpegUdpOutput")
    if AsciiFrameRecorder:
        available_types.append("AsciiFrameRecorder")
    if PreviewSink:
        available_types.append("PreviewSink")
    if FfmpegRtspSink:
        available_types.append("FfmpegRtspSink")
    if WebRTCOutput:
        available_types.append("WebRTCOutput")

    sink_type_dd = widgets.Dropdown(options=available_types, description="Sink type")

    # Config widgets (dynamic)
    udp_host = widgets.Text(value="127.0.0.1", description="Host")
    udp_port = widgets.IntText(value=1234, description="Port")
    udp_bitrate = widgets.Text(value="1500k", description="Bitrate")
    recorder_path = widgets.Text(value="recording.txt", description="File path")
    sink_config = widgets.VBox([])
    add_sink_btn = widgets.Button(description="Add Sink")

    def _update_config_widgets(change=None) -> None:
        stype = sink_type_dd.value
        if stype == "FfmpegUdpOutput":
            sink_config.children = [udp_host, udp_port, udp_bitrate]
        elif stype == "AsciiFrameRecorder":
            sink_config.children = [recorder_path]
        else:
            sink_config.children = []

    sink_type_dd.observe(_update_config_widgets, names="value")
    _update_config_widgets()

    def _get_sink_list() -> List[Any]:
        """Get list of current sinks."""
        if engine is None:
            return []
        sink = _safe_engine_call(engine, "get_sink")
        if sink is None:
            return []
        if CompositeOutputSink and isinstance(sink, CompositeOutputSink):
            return list(getattr(sink, "sinks", [sink]))
        return [sink]

    def _refresh_sinks(_=None) -> None:
        sinks = _get_sink_list()
        if not sinks:
            current_sinks_html.value = "<i>No sinks configured.</i>"
            return
        lines = []
        for i, s in enumerate(sinks):
            tname = type(s).__name__
            is_open = getattr(s, "is_open", None)
            if callable(is_open):
                open_str = "open" if is_open() else "closed"
            elif isinstance(is_open, bool):
                open_str = "open" if is_open else "closed"
            else:
                open_str = "unknown"
            color = "#28a745" if open_str == "open" else "#dc3545"
            lines.append(f"{i+1}. {tname} " f'<span style="color:{color};">[{open_str}]</span>')
        current_sinks_html.value = "<br>".join(lines)

    refresh_btn.on_click(_refresh_sinks)
    _refresh_sinks()

    sink_controls: List[Dict[str, Any]] = []

    def _add_sink(_=None) -> None:
        if engine is None:
            status.value = _status_style("No engine.", "warn")
            return
        stype = sink_type_dd.value
        try:
            new_sink: Any = None
            if stype == "NotebookPreviewSink":
                iw = widgets.Image(format="jpeg")
                display(iw)
                new_sink = NotebookPreviewSink(image_widget=iw)
            elif stype == "FfmpegUdpOutput" and FfmpegUdpOutput:
                new_sink = FfmpegUdpOutput(
                    host=udp_host.value,
                    port=udp_port.value,
                    bitrate=udp_bitrate.value,
                )
            elif stype == "AsciiFrameRecorder" and AsciiFrameRecorder:
                new_sink = AsciiFrameRecorder(output_path=recorder_path.value)
            elif stype == "PreviewSink" and PreviewSink:
                new_sink = PreviewSink()
            else:
                status.value = _status_style(f"Cannot create {stype}.", "warn")
                return

            if new_sink is None:
                status.value = _status_style("Failed to create sink.", "warn")
                return

            was_running = engine.is_running
            if was_running:
                engine.stop()

            current_sink = _safe_engine_call(engine, "get_sink")
            if (
                CompositeOutputSink
                and current_sink is not None
                and isinstance(current_sink, CompositeOutputSink)
            ):
                current_sink.add_sink(new_sink)
            elif CompositeOutputSink and current_sink is not None:
                composite = CompositeOutputSink([current_sink, new_sink])
                engine.set_sink(composite)
            else:
                engine.set_sink(new_sink)

            if was_running:
                engine.start()

            _refresh_sinks()
            status.value = _status_style(f"Added {stype}.", "ok")
        except Exception as e:
            status.value = _status_style(f"Error adding sink: {e}", "warn")

    add_sink_btn.on_click(_add_sink)

    panel = widgets.VBox(
        [
            widgets.HTML("<h3>Output Manager</h3>"),
            _make_labeled_section("Current Sinks", [current_sinks_html]),
            _make_labeled_section(
                "Add Sink",
                [sink_type_dd, sink_config, add_sink_btn],
            ),
            refresh_btn,
            status,
        ]
    )
    display(panel)

    return {
        "panel": panel,
        "current_sinks_html": current_sinks_html,
        "sink_type_dd": sink_type_dd,
        "sink_config": sink_config,
        "add_sink_btn": add_sink_btn,
        "sink_controls": sink_controls,
        "refresh_btn": refresh_btn,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Phase 5: Performance Monitor Panel
# ---------------------------------------------------------------------------

# Latency budgets from rules/LATENCY_BUDGET.md
_LATENCY_BUDGETS: Dict[str, float] = {
    "capture": 2.0,
    "analysis": 15.0,
    "transformation": 2.0,
    "filtering": 5.0,
    "rendering": 3.0,
    "writing": 3.0,
    "overhead": 1.3,
    "total_frame": 33.3,
}


def build_performance_monitor_panel(
    engine: Optional[StreamEngine] = None,
) -> Dict[str, Any]:
    """Performance monitor panel with latency budget visualization.

    Shows per-stage timing against the 33.3ms budget, FPS gauge, degradation
    suggestions, frame time histogram, and bottleneck identification.

    Args:
        engine: Optional StreamEngine.

    Returns:
        Dict with widget references for programmatic access.
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as exc:
        raise ImportError("Install ipywidgets and ipython: pip install ipywidgets ipython") from exc

    budget_chart_html = widgets.HTML(value="<i>No timing data yet.</i>")
    fps_gauge_html = widgets.HTML(value="<i>--</i>")
    degradation_html = widgets.HTML(value="")
    histogram_output = widgets.Output()
    bottleneck_html = widgets.HTML(value="")
    node_timings_html = widgets.HTML(value="<i>Graph mode per-node timings.</i>")
    status = widgets.HTML(value=_status_style("Performance monitor ready.", "info"))

    auto_refresh_cb = widgets.Checkbox(value=True, description="Auto-refresh (1.5s)")
    refresh_btn = widgets.Button(description="Refresh")

    def _build_budget_chart() -> str:
        stats = _safe_engine_call(engine, "get_profiling_stats", default={})
        if not stats:
            profiler_enabled = False
            if engine is not None and hasattr(engine, "profiler"):
                profiler_enabled = engine.profiler.enabled
            if not profiler_enabled:
                return "<i>Enable profiler for timing data.</i>"
            return "<i>No timing data collected yet.</i>"

        stages = [
            "capture",
            "analysis",
            "transformation",
            "filtering",
            "rendering",
            "writing",
            "total_frame",
        ]
        rows = []
        for stage in stages:
            budget_ms = _LATENCY_BUDGETS.get(stage, 0)
            if budget_ms == 0:
                continue
            actual_ms = 0.0
            if stage in stats:
                actual_ms = stats[stage]["avg_time"] * 1000
            ratio = actual_ms / budget_ms if budget_ms > 0 else 0
            if ratio < 0.8:
                color = "#28a745"
            elif ratio <= 1.0:
                color = "#ffc107"
            else:
                color = "#dc3545"
            bar_width = min(100, max(1, int(ratio * 100)))
            rows.append(
                f'<tr><td style="padding:2px 6px; font-size:12px;">'
                f"{stage}</td>"
                f'<td style="padding:2px 6px; font-size:12px;">'
                f"{actual_ms:.1f}/{budget_ms:.1f} ms</td>"
                f'<td style="padding:2px 6px;">'
                f'<div style="background:#eee; width:120px; height:14px; '
                f'border-radius:3px; display:inline-block;">'
                f'<div style="background:{color}; width:{bar_width}%; '
                f'height:14px; border-radius:3px;"></div></div></td></tr>'
            )
        if not rows:
            return "<i>No stage data.</i>"
        return "<table style='border-collapse:collapse;'>" + "".join(rows) + "</table>"

    def _build_fps_gauge() -> str:
        if engine is None:
            return "<i>No engine.</i>"
        cfg = _safe_engine_call(engine, "get_config")
        target_fps = getattr(cfg, "fps", 30) if cfg else 30
        actual_fps = 0.0
        if hasattr(engine, "metrics"):
            actual_fps = engine.metrics.get_fps()
        if target_fps > 0:
            pct = actual_fps / target_fps * 100
        else:
            pct = 0
        if pct > 90:
            color = "#28a745"
        elif pct > 70:
            color = "#ffc107"
        else:
            color = "#dc3545"
        return (
            f'<span style="color:{color}; font-weight:bold;">'
            f"FPS: {actual_fps:.1f} / {target_fps} "
            f"({pct:.0f}%)</span>"
        )

    def _build_degradation() -> str:
        stats = _safe_engine_call(engine, "get_profiling_stats", default={})
        if not stats:
            return ""
        suggestions = []
        total_avg = 0.0
        if "total_frame" in stats:
            total_avg = stats["total_frame"]["avg_time"] * 1000
        analysis_avg = 0.0
        if "analysis" in stats:
            analysis_avg = stats["analysis"]["avg_time"] * 1000
        filtering_avg = 0.0
        if "filtering" in stats:
            filtering_avg = stats["filtering"]["avg_time"] * 1000

        if total_avg > 33.3:
            suggestions.append(
                '<span style="color:#dc3545;">CRITICAL:</span> '
                "Total frame > 33.3ms. Skip perception on alternating "
                "frames."
            )
        if analysis_avg > 15.0:
            suggestions.append(
                '<span style="color:#ffc107;">WARNING:</span> '
                "Analysis > 15ms. Disable tracking or reduce inference "
                "resolution."
            )
        if filtering_avg > 5.0:
            suggestions.append(
                '<span style="color:#ffc107;">WARNING:</span> '
                "Filtering > 5ms. Disable non-essential filters."
            )
        if total_avg > 50.0:
            suggestions.append(
                '<span style="color:#dc3545;">CRITICAL:</span> '
                "Severely over budget. Reduce target FPS."
            )
        if not suggestions:
            return '<span style="color:#28a745;">All stages within budget.' "</span>"
        return "<br>".join(suggestions)

    def _build_histogram() -> str:
        stats = _safe_engine_call(engine, "get_profiling_stats", default={})
        if not stats or "total_frame" not in stats:
            return "No frame time data.\n"
        # We cannot access raw times via public API, so use summary stats
        # to create an approximate distribution display
        s = stats["total_frame"]
        avg_ms = s["avg_time"] * 1000
        min_ms = s["min_time"] * 1000
        max_ms = s["max_time"] * 1000
        count = s["count"]
        lines = [
            f"Frame time stats ({count} samples):",
            f"  Min:  {min_ms:.1f} ms",
            f"  Avg:  {avg_ms:.1f} ms",
            f"  Max:  {max_ms:.1f} ms",
            f"  Std:  {s['std_dev']*1000:.1f} ms",
            "",
            "Distribution estimate:",
        ]
        # Simple bucket estimate
        buckets = {
            "0-10ms": 0,
            "10-20ms": 0,
            "20-33ms": 0,
            "33-50ms": 0,
            ">50ms": 0,
        }
        # Approximate: place avg in its bucket
        if avg_ms <= 10:
            buckets["0-10ms"] = count
        elif avg_ms <= 20:
            buckets["10-20ms"] = count
        elif avg_ms <= 33:
            buckets["20-33ms"] = count
        elif avg_ms <= 50:
            buckets["33-50ms"] = count
        else:
            buckets[">50ms"] = count
        max_bar = max(buckets.values()) if any(buckets.values()) else 1
        for label, cnt in buckets.items():
            bar_len = int(cnt / max_bar * 30) if max_bar > 0 else 0
            bar = "#" * bar_len
            lines.append(f"  {label:>8s} | {bar} ({cnt})")
        return "\n".join(lines)

    def _build_bottleneck() -> str:
        stats = _safe_engine_call(engine, "get_profiling_stats", default={})
        if not stats or "total_frame" not in stats:
            return ""
        total_avg = stats["total_frame"]["avg_time"]
        if total_avg <= 0:
            return ""
        stages = [
            "capture",
            "analysis",
            "transformation",
            "filtering",
            "rendering",
            "writing",
        ]
        worst_stage = ""
        worst_pct = 0.0
        for stage in stages:
            if stage in stats:
                pct = stats[stage]["avg_time"] / total_avg * 100
                if pct > worst_pct:
                    worst_pct = pct
                    worst_stage = stage
        if worst_stage:
            return (
                f'<span style="color:#dc3545; font-weight:bold;">'
                f"Bottleneck: {worst_stage} "
                f"({worst_pct:.1f}% of frame time)</span>"
            )
        return ""

    def _build_node_timings() -> str:
        timings = _safe_engine_call(engine, "get_node_timings", default={})
        if not timings:
            return "<i>No node timings (start engine in graph mode).</i>"
        rows = []
        sorted_nodes = sorted(timings.items(), key=lambda x: x[1], reverse=True)
        total = sum(t for _, t in sorted_nodes) or 1e-9
        for name, secs in sorted_nodes:
            ms = secs * 1000
            pct = secs / total * 100
            if ms < 1.0:
                color = "#28a745"
            elif ms < 5.0:
                color = "#ffc107"
            else:
                color = "#dc3545"
            bar_w = min(100, max(1, int(pct)))
            rows.append(
                f'<tr><td style="padding:2px 6px; font-size:12px;">{name}</td>'
                f'<td style="padding:2px 6px; font-size:12px;">{ms:.2f} ms</td>'
                f'<td style="padding:2px 6px; font-size:12px;">{pct:.0f}%</td>'
                f'<td style="padding:2px 6px;">'
                f'<div style="background:#eee; width:120px; height:14px; '
                f'border-radius:3px; display:inline-block;">'
                f'<div style="background:{color}; width:{bar_w}%; '
                f'height:14px; border-radius:3px;"></div></div></td></tr>'
            )
        header = (
            '<tr style="border-bottom:1px solid #ccc;">'
            '<th style="padding:2px 6px; font-size:11px; text-align:left;">Node</th>'
            '<th style="padding:2px 6px; font-size:11px; text-align:left;">Time</th>'
            '<th style="padding:2px 6px; font-size:11px; text-align:left;">%</th>'
            '<th style="padding:2px 6px; font-size:11px; text-align:left;">Bar</th></tr>'
        )
        return (
            "<table style='border-collapse:collapse;'>"
            + header
            + "".join(rows)
            + "</table>"
        )

    def _refresh(_=None) -> None:
        budget_chart_html.value = _build_budget_chart()
        fps_gauge_html.value = _build_fps_gauge()
        degradation_html.value = _build_degradation()
        with histogram_output:
            histogram_output.clear_output()
            print(_build_histogram())
        bottleneck_html.value = _build_bottleneck()
        node_timings_html.value = _build_node_timings()

    _refresh()
    refresh_btn.on_click(_refresh)

    # Auto-refresh management
    _auto_state: Dict[str, Any] = {"handle": None}

    def _on_auto_toggle(change) -> None:
        if change["new"]:
            handle = _periodic_refresh(_refresh, 1500)
            _auto_state["handle"] = handle
        else:
            handle = _auto_state.get("handle")
            if handle:
                handle["stop"]()
            _auto_state["handle"] = None

    auto_refresh_cb.observe(_on_auto_toggle, names="value")

    # Start auto-refresh immediately since default is True
    _auto_state["handle"] = _periodic_refresh(_refresh, 1500)

    def _stop_refresh() -> None:
        auto_refresh_cb.value = False
        handle = _auto_state.get("handle")
        if handle:
            handle["stop"]()

    panel = widgets.VBox(
        [
            widgets.HTML("<h3>Performance Monitor</h3>"),
            _make_labeled_section("Latency Budget", [budget_chart_html]),
            _make_labeled_section("FPS", [fps_gauge_html]),
            _make_labeled_section("Node Timings (Graph)", [node_timings_html]),
            _make_labeled_section("Degradation Suggestions", [degradation_html]),
            _make_labeled_section("Frame Time Stats", [histogram_output]),
            _make_labeled_section("Bottleneck", [bottleneck_html]),
            widgets.HBox([auto_refresh_cb, refresh_btn]),
            status,
        ]
    )
    display(panel)

    return {
        "panel": panel,
        "budget_chart_html": budget_chart_html,
        "fps_gauge_html": fps_gauge_html,
        "node_timings_html": node_timings_html,
        "degradation_html": degradation_html,
        "histogram_output": histogram_output,
        "bottleneck_html": bottleneck_html,
        "auto_refresh_cb": auto_refresh_cb,
        "refresh_btn": refresh_btn,
        "refresh": _refresh,
        "stop_refresh": _stop_refresh,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Phase 6: Preset Manager Panel
# ---------------------------------------------------------------------------

_DEFAULT_PRESETS_PATH = Path.home() / ".ascii_stream_engine" / "presets.json"


def build_preset_manager_panel(
    engine: Optional[StreamEngine] = None,
    presets_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Preset manager panel to save/load/delete named pipeline configurations.

    Presets are stored as JSON at *presets_path* (defaults to
    ``~/.ascii_stream_engine/presets.json``).

    Args:
        engine: Optional StreamEngine.
        presets_path: Optional path for the presets JSON file.

    Returns:
        Dict with widget references for programmatic access.
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as exc:
        raise ImportError("Install ipywidgets and ipython: pip install ipywidgets ipython") from exc

    path = presets_path or _DEFAULT_PRESETS_PATH
    status = widgets.HTML(value=_status_style("Preset manager ready.", "info"))

    preset_name_input = widgets.Text(value="", description="Preset name", placeholder="my_preset")
    save_btn = widgets.Button(description="Save")
    preset_dropdown = widgets.Dropdown(options=[], description="Presets", value=None)
    load_btn = widgets.Button(description="Load")
    delete_btn = widgets.Button(description="Delete")
    preset_list_html = widgets.HTML(value="<i>No presets.</i>")
    import_export_textarea = widgets.Textarea(
        value="",
        description="JSON",
        layout=widgets.Layout(width="80%", height="100px"),
    )
    import_btn = widgets.Button(description="Import JSON")
    export_btn = widgets.Button(description="Export JSON")

    # Preset I/O helpers
    def _load_presets() -> List[Dict[str, Any]]:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    def _save_presets(presets: List[Dict[str, Any]]) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(presets, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            status.value = _status_style(f"Error saving presets: {e}", "warn")

    def _refresh_preset_list() -> None:
        presets = _load_presets()
        names = [p.get("name", "unnamed") for p in presets]
        preset_dropdown.options = names
        if names:
            preset_dropdown.value = names[0]
        else:
            preset_dropdown.value = None

        if not presets:
            preset_list_html.value = "<i>No presets saved.</i>"
        else:
            lines = []
            for p in presets:
                name = p.get("name", "unnamed")
                created = p.get("created", "")
                cfg = p.get("config", {})
                fps_val = cfg.get("fps", "?")
                rm = cfg.get("render_mode", "?")
                f_list = p.get("filters", [])
                a_info = p.get("analyzers", {})
                active_a = [k for k, v in a_info.items() if v]
                summary_parts = [
                    f"{fps_val} FPS",
                    rm,
                ]
                if f_list:
                    summary_parts.append("+".join(f_list))
                if active_a:
                    summary_parts.append("+".join(active_a))
                summary = ", ".join(summary_parts)
                lines.append(f"<b>{name}</b> ({created[:19]}): {summary}")
            preset_list_html.value = "<br>".join(lines)

    _refresh_preset_list()

    def _capture_state() -> Dict[str, Any]:
        """Capture current engine state as a preset dict."""
        cfg = _safe_engine_call(engine, "get_config")
        config_dict = {}
        if cfg:
            config_dict = {
                "fps": cfg.fps,
                "grid_w": cfg.grid_w,
                "grid_h": cfg.grid_h,
                "charset": cfg.charset,
                "render_mode": cfg.render_mode,
                "contrast": cfg.contrast,
                "brightness": cfg.brightness,
                "raw_width": cfg.raw_width,
                "raw_height": cfg.raw_height,
            }

        # Active filters
        filter_names: List[str] = []
        if engine is not None and hasattr(engine, "filter_pipeline"):
            for f in engine.filter_pipeline.filters:
                fname = getattr(f, "name", f.__class__.__name__)
                filter_names.append(fname)

        # Analyzer states
        analyzers_state = {"face": False, "hands": False, "pose": False}
        if engine is not None and hasattr(engine, "analyzer_pipeline"):
            for a in engine.analyzer_pipeline.analyzers:
                name = getattr(a, "name", "")
                if name in analyzers_state:
                    analyzers_state[name] = getattr(a, "enabled", False)

        # Renderer type
        renderer = "ascii"
        if engine is not None and hasattr(engine, "get_renderer"):
            r = engine.get_renderer()
            rtype = type(r).__name__
            if "Passthrough" in rtype:
                renderer = "raw"
            elif "Overlay" in rtype or "Landmarks" in rtype:
                renderer = "overlay_landmarks"

        return {
            "name": preset_name_input.value or "unnamed",
            "created": datetime.now(timezone.utc).isoformat(),
            "config": config_dict,
            "filters": filter_names,
            "analyzers": analyzers_state,
            "renderer": renderer,
        }

    def _on_save(_=None) -> None:
        if engine is None:
            status.value = _status_style("No engine. Cannot save preset.", "warn")
            return
        name = preset_name_input.value.strip()
        if not name:
            status.value = _status_style("Enter a preset name first.", "warn")
            return
        preset = _capture_state()
        preset["name"] = name
        presets = _load_presets()
        presets.append(preset)
        _save_presets(presets)
        _refresh_preset_list()
        status.value = _status_style(f"Preset '{name}' saved.", "ok")

    save_btn.on_click(_on_save)

    def _on_load(_=None) -> None:
        if engine is None:
            status.value = _status_style("No engine.", "warn")
            return
        name = preset_dropdown.value
        if not name:
            status.value = _status_style("Select a preset.", "warn")
            return
        presets = _load_presets()
        preset = None
        for p in presets:
            if p.get("name") == name:
                preset = p
                break
        if preset is None:
            status.value = _status_style(f"Preset '{name}' not found.", "warn")
            return

        was_running = engine.is_running
        if was_running:
            engine.stop()

        # Apply config
        cfg = preset.get("config", {})
        if cfg:
            try:
                engine.update_config(**cfg)
            except Exception as e:
                status.value = _status_style(f"Error applying config: {e}", "warn")

        # Apply analyzer states
        analyzer_states = preset.get("analyzers", {})
        if hasattr(engine, "analyzer_pipeline"):
            for aname, enabled in analyzer_states.items():
                try:
                    engine.analyzer_pipeline.set_enabled(aname, enabled)
                except Exception:
                    pass

        # Apply renderer
        renderer_type = preset.get("renderer", "ascii")
        try:
            if renderer_type == "ascii":
                engine.set_renderer(AsciiRenderer())
            elif renderer_type == "raw":
                engine.set_renderer(PassthroughRenderer())
            elif renderer_type == "overlay_landmarks":
                try:
                    from ..adapters.renderers import (
                        LandmarksOverlayRenderer,
                    )

                    engine.set_renderer(LandmarksOverlayRenderer(inner=PassthroughRenderer()))
                except Exception:
                    engine.set_renderer(PassthroughRenderer())
        except Exception:
            pass

        if was_running:
            engine.start()
        status.value = _status_style(f"Preset '{name}' loaded.", "ok")

    load_btn.on_click(_on_load)

    def _on_delete(_=None) -> None:
        name = preset_dropdown.value
        if not name:
            status.value = _status_style("Select a preset.", "warn")
            return
        presets = _load_presets()
        presets = [p for p in presets if p.get("name") != name]
        _save_presets(presets)
        _refresh_preset_list()
        status.value = _status_style(f"Preset '{name}' deleted.", "ok")

    delete_btn.on_click(_on_delete)

    def _on_export(_=None) -> None:
        presets = _load_presets()
        import_export_textarea.value = json.dumps(presets, indent=2, default=str)
        status.value = _status_style("Presets exported to textarea.", "ok")

    export_btn.on_click(_on_export)

    def _on_import(_=None) -> None:
        raw = import_export_textarea.value.strip()
        if not raw:
            status.value = _status_style("Textarea is empty.", "warn")
            return
        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                data = [data]
            _save_presets(data)
            _refresh_preset_list()
            status.value = _status_style(f"Imported {len(data)} preset(s).", "ok")
        except json.JSONDecodeError as e:
            status.value = _status_style(f"Invalid JSON: {e}", "warn")

    import_btn.on_click(_on_import)

    panel = widgets.VBox(
        [
            widgets.HTML("<h3>Preset Manager</h3>"),
            _make_labeled_section(
                "Save Preset",
                [widgets.HBox([preset_name_input, save_btn])],
            ),
            _make_labeled_section(
                "Load / Delete",
                [widgets.HBox([preset_dropdown, load_btn, delete_btn])],
            ),
            _make_labeled_section("Saved Presets", [preset_list_html]),
            _make_labeled_section(
                "Import / Export",
                [
                    import_export_textarea,
                    widgets.HBox([import_btn, export_btn]),
                ],
            ),
            status,
        ]
    )
    display(panel)

    return {
        "panel": panel,
        "preset_name_input": preset_name_input,
        "save_btn": save_btn,
        "preset_dropdown": preset_dropdown,
        "load_btn": load_btn,
        "delete_btn": delete_btn,
        "preset_list_html": preset_list_html,
        "import_export_textarea": import_export_textarea,
        "import_btn": import_btn,
        "export_btn": export_btn,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Phase 7: Full Dashboard (Integration)
# ---------------------------------------------------------------------------


def build_full_dashboard(
    engine: Optional[StreamEngine] = None,
    filters: Optional[Dict[str, object]] = None,
) -> Dict[str, Any]:
    """Master dashboard combining all panels in a tabbed interface.

    Creates a Tab widget with 7 tabs: Control, Diagnostics, Perception,
    Filters, Outputs, Performance, and Presets.

    Args:
        engine: Optional StreamEngine.
        filters: Optional dict of {name: Filter} for filter panels.

    Returns:
        Dict with 'tabs' and sub-dicts for each panel.
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as exc:
        raise ImportError("Install ipywidgets and ipython: pip install ipywidgets ipython") from exc

    # Build sub-panels (suppress individual display calls by patching)
    import unittest.mock

    # We need to suppress display() calls inside each build_ function
    with unittest.mock.patch("IPython.display.display"):
        control = (
            build_general_control_panel(engine, filters)
            if engine is not None
            else {"tabs": widgets.HTML("<i>No engine provided.</i>")}
        )
        diagnostics = build_advanced_diagnostics_panel(engine)
        perception = build_perception_control_panel(engine)
        filter_designer = build_filter_designer_panel(engine, filters)
        outputs = build_output_manager_panel(engine)
        performance = build_performance_monitor_panel(engine)
        presets = build_preset_manager_panel(engine)

    # Sync filter checkboxes between Control and Filter Designer panels
    # to prevent one panel from wiping the other's filter state.
    _syncing_filters = [False]
    ctrl_filters = control.get("filters", {})
    designer_cards = filter_designer.get("filter_cards", {})
    for fname in ctrl_filters:
        if fname not in designer_cards:
            continue
        ctrl_cb = ctrl_filters[fname]
        des_cb = designer_cards[fname]["enabled_cb"]

        def _make_sync(src, dst):
            def _sync(change):
                if not _syncing_filters[0]:
                    _syncing_filters[0] = True
                    dst.value = change["new"]
                    _syncing_filters[0] = False

            return _sync

        ctrl_cb.observe(_make_sync(ctrl_cb, des_cb), names="value")
        des_cb.observe(_make_sync(des_cb, ctrl_cb), names="value")

    # Extract the main panel widget from each sub-panel
    control_widget = control.get("tabs", widgets.HTML(""))
    diag_widget = diagnostics.get("panel", widgets.HTML(""))
    perception_widget = perception.get("panel", widgets.HTML(""))
    filters_widget = filter_designer.get("panel", widgets.HTML(""))
    outputs_widget = outputs.get("panel", widgets.HTML(""))
    perf_widget = performance.get("panel", widgets.HTML(""))
    presets_widget = presets.get("panel", widgets.HTML(""))

    tabs = widgets.Tab(
        children=[
            control_widget,
            diag_widget,
            perception_widget,
            filters_widget,
            outputs_widget,
            perf_widget,
            presets_widget,
        ]
    )
    tabs.set_title(0, "Control")
    tabs.set_title(1, "Diagnostics")
    tabs.set_title(2, "Perception")
    tabs.set_title(3, "Filters")
    tabs.set_title(4, "Outputs")
    tabs.set_title(5, "Performance")
    tabs.set_title(6, "Presets")

    display(tabs)

    return {
        "tabs": tabs,
        "control": control,
        "diagnostics": diagnostics,
        "perception": perception,
        "filters": filter_designer,
        "outputs": outputs,
        "performance": performance,
        "presets": presets,
    }
