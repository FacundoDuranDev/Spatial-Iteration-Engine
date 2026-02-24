import os
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional

from ..adapters.outputs import NotebookPreviewSink
from ..adapters.renderers import AsciiRenderer, PassthroughRenderer
from ..adapters.sources import OpenCVCameraSource
from ..application.engine import StreamEngine
from ..application.pipeline import AnalyzerPipeline, FilterPipeline
from ..domain.config import EngineConfig


def build_control_panel(engine: StreamEngine) -> Dict[str, List[object]]:
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as exc:
        raise ImportError(
            "Instala ipywidgets e ipython para usar el panel: "
            "python -m pip install ipywidgets ipython"
        ) from exc

    cfg = engine.get_config()
    fps = widgets.IntSlider(value=cfg.fps, min=5, max=60, description="FPS")
    grid_w = widgets.IntSlider(
        value=cfg.grid_w, min=40, max=200, description="Grid W"
    )
    grid_h = widgets.IntSlider(
        value=cfg.grid_h, min=20, max=120, description="Grid H"
    )
    contrast = widgets.FloatSlider(
        value=cfg.contrast, min=0.5, max=3.0, step=0.1, description="Contraste"
    )
    brightness = widgets.IntSlider(
        value=cfg.brightness, min=-50, max=50, step=1, description="Brillo"
    )
    invert = widgets.Checkbox(value=cfg.invert, description="Invertir")

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

    filter_boxes = []
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

    return {"config": [fps, grid_w, grid_h, contrast, brightness, invert], "filters": filter_boxes}


def build_general_control_panel(
    engine: StreamEngine,
    filters: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as exc:
        raise ImportError(
            "Instala ipywidgets e ipython para usar el panel: "
            "python -m pip install ipywidgets ipython"
        ) from exc

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

    def _status_style(msg: str, kind: str = "info") -> str:
        color = {"ok": "#d4edda", "warn": "#fff3cd", "info": "#e7f1ff"}.get(kind, "#f8f9fa")
        return f'<div style="padding:8px 10px; background:{color}; border-radius:6px; margin:6px 0; border:1px solid #dee2e6; font-size:13px;">{msg}</div>'

    status = widgets.HTML(value=_status_style("Listo. Usa las pestañas y pulsa Start en Motor.", "info"))

    # Network controls
    network_mode = widgets.Dropdown(
        options=["Local", "Broadcast", "Multicast", "IP directa"],
        value=_default_network_mode(),
        description="Modo red",
        style={"description_width": "80px"},
    )
    host_input = widgets.Text(value=cfg.host, description="Host", style={"description_width": "80px"})
    port_input = widgets.IntText(value=cfg.port, description="Puerto", style={"description_width": "80px"})
    apply_net_btn = widgets.Button(description="Aplicar red", layout=Layout(width="120px") if Layout else None)

    # Camera controls
    camera_index = widgets.IntText(value=0, description="Cámara", style={"description_width": "80px"})
    apply_camera_btn = widgets.Button(description="Aplicar cámara", layout=Layout(width="130px") if Layout else None)

    # Filters (incl. C++ para MVP_02)
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

    filter_checkboxes = {
        name: widgets.Checkbox(value=False, description=name)
        for name in filters
    }

    # ASCII/RAW controls
    dense_charset = (
        " .'`^\\\",:;Il!i~+_-?][}{1)(|\\\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
    )

    fps_slider = widgets.IntSlider(value=cfg.fps, min=10, max=60, description="FPS")
    grid_w_slider = widgets.IntSlider(
        value=cfg.grid_w, min=60, max=200, description="Grid W"
    )
    grid_h_slider = widgets.IntSlider(
        value=cfg.grid_h, min=20, max=120, description="Grid H"
    )

    charset_options = {
        "Simple": " .:-=+*#",
        "Medio": " .:-=+*#%@",
        "Denso": dense_charset,
    }
    current_charset = cfg.charset
    if current_charset not in charset_options.values():
        charset_options["Actual"] = current_charset
    charset_default = (
        current_charset
        if current_charset in charset_options.values()
        else charset_options["Simple"]
    )

    charset_dd = widgets.Dropdown(
        options=charset_options,
        value=charset_default,
        description="Charset",
    )

    render_mode = widgets.RadioButtons(
        options=[("ASCII", "ascii"), ("RAW (sin ASCII)", "raw")],
        value=cfg.render_mode,
        description="Modo",
    )

    raw_width = widgets.IntText(value=cfg.raw_width or 640, description="Raw W")
    raw_height = widgets.IntText(value=cfg.raw_height or 360, description="Raw H")
    raw_use_size = widgets.Checkbox(
        value=cfg.raw_width is not None and cfg.raw_height is not None,
        description="Usar tamano RAW",
    )

    contrast_slider = widgets.FloatSlider(
        value=cfg.contrast, min=0.5, max=3.0, step=0.1, description="Contraste"
    )
    brightness_slider = widgets.IntSlider(
        value=cfg.brightness, min=-50, max=50, step=1, description="Brillo"
    )
    frame_buffer_slider = widgets.IntSlider(
        value=cfg.frame_buffer_size, min=0, max=3, step=1, description="Buffer"
    )
    bitrate_text = widgets.Text(value=str(cfg.bitrate), description="Bitrate")

    apply_settings_btn = widgets.Button(description="Aplicar ajustes", layout=Layout(width="140px") if Layout else None)
    clear_filters_btn = widgets.Button(description="Quitar todos", layout=Layout(width="120px") if Layout else None)
    start_btn = widgets.Button(description="▶ Iniciar", layout=Layout(width="100px") if Layout else None)
    stop_btn = widgets.Button(description="■ Detener", layout=Layout(width="100px") if Layout else None)

    def _sync_host(change) -> None:
        mode = change["new"]
        if mode == "Local":
            host_input.value = "127.0.0.1"
        elif mode == "Broadcast":
            host_input.value = "255.255.255.255"
        elif mode == "Multicast":
            host_input.value = "239.0.0.1"
        # IP directa: no tocar

    def _apply_filters(_=None) -> None:
        selected = [filters[name] for name, cb in filter_checkboxes.items() if cb.value]
        if hasattr(engine, "filter_pipeline"):
            engine.filter_pipeline.replace(selected)
        elif hasattr(engine, "filters"):
            engine.filters[:] = selected
        if selected:
            status.value = _status_style(f"Filtros activos: {', '.join([f.name for f in selected])}", "ok")
        else:
            status.value = _status_style("Sin filtros: imagen normal.", "info")

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
                status.value = _status_style("Falta host para IP directa.", "warn")
                return

        was_running = engine.is_running
        if was_running:
            engine.stop()
        engine.update_config(host=host, port=port_input.value, udp_broadcast=udp_broadcast)
        if was_running:
            engine.start()
        status.value = _status_style(f"Red aplicada: {mode} → {host}:{port_input.value}", "ok")

    def apply_camera(_=None) -> None:
        source = engine.get_source()
        if not hasattr(source, "set_camera_index"):
            status.value = _status_style("Fuente actual no soporta cambio de cámara.", "warn")
            return
        was_running = engine.is_running
        if was_running:
            engine.stop()
        source.set_camera_index(int(camera_index.value))
        if was_running:
            engine.start()
        status.value = _status_style(f"Cámara cambiada a índice {camera_index.value}.", "ok")

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
        if render_mode.value == "ascii":
            engine.set_renderer(AsciiRenderer())
        else:
            engine.set_renderer(PassthroughRenderer())
        if was_running:
            engine.start()
        status.value = _status_style("Ajustes de vista aplicados.", "ok")

    def clear_filters(_=None) -> None:
        for cb in filter_checkboxes.values():
            cb.value = False
        _apply_filters()

    def start_engine(_=None) -> None:
        engine.start()
        status.value = _status_style("● Motor en marcha. El preview se actualiza en la celda de arriba.", "ok")

    def stop_engine(_=None) -> None:
        engine.stop()
        status.value = _status_style("○ Motor detenido.", "info")

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
            widgets.HTML("<b>Servidor en red</b>"),
            widgets.HTML("<small>Local = 127.0.0.1 · Broadcast/Multicast para UDP.</small>"),
            network_mode,
            widgets.HBox([host_input, port_input]),
            apply_net_btn,
        ],
        layout=Layout(padding="0 0 10px 0") if Layout else None,
    )

    engine_box = widgets.VBox(
        [
            widgets.HTML("<b>Motor</b>"),
            widgets.HTML("<small>Inicia para ver el preview en la celda de arriba.</small>"),
            widgets.HBox([start_btn, stop_btn]),
            widgets.HTML("<b>Cámara</b>"),
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
            widgets.HTML("<b>Filtros de imagen</b>"),
            widgets.HTML("<small>Se aplican antes del render (ASCII/RAW). Puedes combinar varios.</small>"),
            row1,
            row2,
            clear_filters_btn,
        ],
        layout=Layout(padding="0 0 10px 0") if Layout else None,
    )

    settings_box = widgets.VBox(
        [
            widgets.HTML("<b>Vista (ASCII / RAW)</b>"),
            widgets.HTML("<small>Video</small>"),
            fps_slider,
            widgets.HBox([grid_w_slider, grid_h_slider]),
            widgets.HTML("<small>Apariencia</small>"),
            charset_dd,
            widgets.HBox([contrast_slider, brightness_slider]),
            render_mode,
            widgets.HTML("<small>RAW (tamaño)</small>"),
            widgets.HBox([raw_use_size, raw_width, raw_height]),
            widgets.HBox([frame_buffer_slider, bitrate_text]),
            apply_settings_btn,
        ],
        layout=Layout(padding="0 0 10px 0") if Layout else None,
    )

    # Pestaña IA: detección (cara, manos, pose) y visualización overlay (MVP_03)
    try:
        from ..adapters.renderers import LandmarksOverlayRenderer
    except Exception:
        LandmarksOverlayRenderer = None

    # Sincronizar checkboxes con el estado real de los analyzers
    def _analyzer_enabled(name: str) -> bool:
        if not hasattr(engine, "analyzer_pipeline"):
            return False
        for a in engine.analyzer_pipeline.analyzers:
            if getattr(a, "name", "") == name:
                return getattr(a, "enabled", False)
        return False

    face_cb = widgets.Checkbox(value=_analyzer_enabled("face"), description="Detección cara (face)")
    hands_cb = widgets.Checkbox(value=_analyzer_enabled("hands"), description="Detección manos (hands)")
    pose_cb = widgets.Checkbox(value=_analyzer_enabled("pose"), description="Detección pose (pose)")
    ai_viz_dd = widgets.Dropdown(
        options=["Normal (según ASCII/RAW)", "Overlay landmarks"],
        value="Normal (según ASCII/RAW)",
        description="Visualización",
    )
    apply_ai_btn = widgets.Button(description="Aplicar IA")

    detector_status_html = widgets.HTML(
        value="<i>Estado: — Pulsa «Actualizar estado detector» con el engine en marcha.</i>"
    )
    refresh_detector_btn = widgets.Button(description="Actualizar estado detector")

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
            return "<i>Engine sin análisis.</i>"
        has_analyzers = (
            hasattr(engine, "analyzer_pipeline")
            and getattr(engine.analyzer_pipeline, "has_any", lambda: False)()
        )
        a = engine.get_last_analysis()
        lines = []
        for name, label in (("face", "Cara"), ("hands", "Manos"), ("pose", "Pose")):
            n = _count_points(a.get(name))
            lines.append(f"{label}: {n} pts" if n else f"{label}: —")
        out = "<b>Detector</b><br>" + " | ".join(lines)
        if has_analyzers and not a and engine.is_running:
            out += "<br><small>Sin datos aún (activa al menos una detección arriba).</small>"
        elif has_analyzers and not any(_count_points(a.get(k)) for k in ("face", "hands", "pose")):
            out += "<br><small>Todo en 0: verifica que los modelos ONNX estén en onnx_models/mediapipe/ y que haya una persona visible.</small>"
        elif not has_analyzers:
            out += "<br><small style='color:#856404'>No hay módulo de percepción. Arranca Jupyter con PYTHONPATH=python:cpp/build (tras cpp/build.sh).</small>"
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
        if LandmarksOverlayRenderer and ai_viz_dd.value == "Overlay landmarks":
            engine.set_renderer(LandmarksOverlayRenderer())
            status.value = _status_style("IA: overlay de landmarks activo. Activa cara/manos/pose y pulsa Actualizar estado detector.", "ok")
        else:
            if render_mode.value == "ascii":
                engine.set_renderer(AsciiRenderer())
            else:
                engine.set_renderer(PassthroughRenderer())
            status.value = _status_style("IA: visualización normal (según pestaña Vista).", "info")
        if was_running:
            engine.start()

    apply_ai_btn.on_click(apply_ai)
    apply_ai_btn.layout = Layout(width="120px") if Layout else None
    refresh_detector_btn.layout = Layout(width="200px") if Layout else None

    # Aplicar cambios de checkbox en tiempo real (sin necesidad de "Aplicar IA")
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
    ai_aviso = widgets.HTML(
        value=(
            '<div style="padding:8px; background:#fff3cd; border-radius:4px; font-size:12px; margin:4px 0;">'
            "<b>Sin módulo de percepción.</b> Arranca Jupyter con <code>PYTHONPATH=python:cpp/build</code> "
            "(tras <code>bash cpp/build.sh</code>) para que la detección y el overlay funcionen."
            "</div>"
        )
        if not _has_analyzers
        else ""
    )
    if _has_analyzers:
        ai_aviso = widgets.HTML(
            value='<div style="padding:6px; background:#f8f9fa; border-radius:4px; font-size:12px;">'
            "1) Activa cara/manos/pose · 2) Elige Overlay landmarks · 3) Aplicar IA · 4) Inicia el motor."
            "</div>"
        )

    ai_box = widgets.VBox(
        [
            widgets.HTML("<b>Percepción (IA)</b>"),
            ai_aviso,
            widgets.HBox([face_cb, hands_cb, pose_cb]),
            ai_viz_dd,
            apply_ai_btn,
            widgets.HTML("<b>Estado del detector</b>"),
            detector_status_html,
            refresh_detector_btn,
        ],
        layout=Layout(padding="0 0 10px 0") if Layout else None,
    )

    tabs = widgets.Tab(
        children=[network_box, engine_box, filters_box, settings_box, ai_box]
    )
    tabs.set_title(0, "Red")
    tabs.set_title(1, "Motor")
    tabs.set_title(2, "Filtros")
    tabs.set_title(3, "Vista")
    tabs.set_title(4, "IA")

    _apply_filters()
    display(widgets.HTML("<b>Estado</b>"))
    display(status)
    display(widgets.HTML("<b>Controles</b>"))
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
        "ia": {
            "face": face_cb,
            "hands": hands_cb,
            "pose": pose_cb,
            "viz": ai_viz_dd,
            "apply": apply_ai_btn,
            "detector_status": detector_status_html,
            "refresh_detector": refresh_detector_btn,
        },
        "status": status,
    }


def _get_device_info() -> Dict[str, Any]:
    """Recopila información de dispositivos de video y OpenCV (para uso en panel)."""
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
        # Redirigir fd 2 (stderr) para silenciar avisos de OpenCV en C++
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
    """Convierte _get_device_info() en HTML legible."""
    lines = ["<b>Dispositivos de video</b>"]
    if data["devices"]:
        for d in data["devices"]:
            if "error" in d:
                lines.append(f"  {d['path']}: error {d['error']}")
            else:
                lines.append(f"  {d['path']} (modo {d['mode']})")
    else:
        lines.append("  No hay /dev/video*")
    lines.append("<br><b>Grupo video</b>: " + ("sí" if data["in_video_group"] else "no"))
    lines.append("  groups: " + (data["groups"] or "—"))
    lines.append("<br><b>OpenCV</b> " + (data["cv2_version"] or "no disponible"))
    if data.get("cv2_error"):
        lines.append("  Error: " + data["cv2_error"])
    elif data["open_indices"]:
        for o in data["open_indices"]:
            s = f"  índice {o['index']}: ABRE"
            if o.get("shape") is not None:
                s += f" shape={o['shape']}"
            lines.append(s)
        if data.get("backend"):
            lines.append("  backend: " + data["backend"])
    else:
        lines.append("  Ningún índice 0..5 abre")
    return "<pre>" + "\n".join(lines) + "</pre>"


def build_diagnostics_panel(engine: Optional[StreamEngine] = None) -> Dict[str, Any]:
    """Panel para Jupyter: dispositivos conectados, latencia del proceso y benchmarking.

    - Dispositivos: lista /dev/video*, índices que abren con OpenCV, grupo video.
    - Latencia: FPS, frames procesados, latencia avg/min/max (requiere engine en marcha).
    - Benchmarking: botón para ejecutar N segundos con profiling y ver reporte.

    Args:
        engine: StreamEngine opcional. Si se pasa, se muestra latencia y se puede hacer benchmark.

    Returns:
        Dict con los widgets (devices_html, latency_html, refresh_btn, benchmark_btn, etc.).
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as exc:
        raise ImportError(
            "Instala ipywidgets e ipython para el panel: pip install ipywidgets ipython"
        ) from exc

    devices_html = widgets.HTML(value=_device_info_to_html(_get_device_info()))
    latency_html = widgets.HTML(value="<i>Inicia el engine para ver latencia en tiempo real.</i>")
    benchmark_output = widgets.Output()
    benchmark_seconds = widgets.IntText(value=5, description="Segundos")
    benchmark_btn = widgets.Button(description="Ejecutar benchmark")

    def refresh(_=None) -> None:
        data = _get_device_info()
        devices_html.value = _device_info_to_html(data)
        if engine is not None and engine.is_running:
            m = engine.metrics.get_summary()
            latency_html.value = (
                "<b>Latencia / métricas</b><br>"
                f"FPS: {m['fps']:.1f} | Frames: {m['frames_processed']} | "
                f"Latencia avg: {m['latency_avg']*1000:.1f} ms | "
                f"min: {m['latency_min']*1000:.1f} ms | max: {m['latency_max']*1000:.1f} ms<br>"
                f"Uptime: {m['uptime']:.1f} s | Errores: {m['total_errors']}"
            )
        else:
            latency_html.value = (
                "<i>Engine no en marcha.</i> Inicia el engine y pulsa Actualizar para ver latencia."
            )

    def run_benchmark(_=None) -> None:
        if engine is None:
            with benchmark_output:
                print("No hay engine asociado. Crea un StreamEngine y pásalo a build_diagnostics_panel(engine=...).")
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
                report = engine.get_profiling_report() if hasattr(engine, "get_profiling_report") else ""
                summary = engine.metrics.get_summary()
                with benchmark_output:
                    print("=== Benchmark {} s ===\n".format(secs))
                    print("Métricas: FPS={:.1f}  frames={}  latency_avg={:.2f} ms".format(
                        summary["fps"], summary["frames_processed"], summary["latency_avg"] * 1000
                    ))
                    if report:
                        print("\n" + report)
            except Exception as e:
                with benchmark_output:
                    print("Error en benchmark:", e)
            finally:
                benchmark_btn.disabled = False

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    refresh_btn = widgets.Button(description="Actualizar")
    refresh_btn.on_click(refresh)
    benchmark_btn.on_click(run_benchmark)

    section_devices = widgets.VBox([
        widgets.HTML("<b>Dispositivos conectados</b>"),
        devices_html,
        refresh_btn,
    ])
    section_latency = widgets.VBox([
        widgets.HTML("<b>Latencia del proceso</b>"),
        latency_html,
        widgets.HTML("<small>Pulsa Actualizar con el engine en marcha para refrescar.</small>"),
    ])
    section_benchmark = widgets.VBox([
        widgets.HTML("<b>Benchmarking</b>"),
        widgets.HBox([benchmark_seconds, widgets.HTML("s")]),
        benchmark_btn,
        benchmark_output,
    ])

    panel = widgets.VBox([
        widgets.HTML("<h3>Diagnóstico y benchmarking</h3>"),
        section_devices,
        widgets.HTML("<br>"),
        section_latency,
        widgets.HTML("<br>"),
        section_benchmark,
    ])
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


def build_engine_for_notebook(
    camera_index: int = 0,
    config: Optional[EngineConfig] = None,
) -> StreamEngine:
    """Crea un StreamEngine que muestra el video dentro del notebook (sin ventana de escritorio).

    La cámara se ve en un widget de imagen debajo de la celda. Usa NotebookPreviewSink
    en lugar de PreviewSink para que funcione cuando no hay display (Jupyter en navegador, etc.).
    Incluye pipeline de percepción (face, hands, pose) si está disponible; en la pestaña IA
    puedes activar detección y overlay de landmarks. Los filtros (incl. Invert C++) se eligen
    en la pestaña Filtros.

    Uso:
        engine = build_engine_for_notebook(0)
        display(engine.get_sink()._widget)  # opcional si no se mostró
        build_general_control_panel(engine)
        build_diagnostics_panel(engine)
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as exc:
        raise ImportError(
            "Instala ipywidgets e ipython: pip install ipywidgets ipython"
        ) from exc

    image_widget = widgets.Image(format="jpeg")
    display(widgets.HTML("<b>Preview (la imagen aparece al pulsar Start)</b>"))
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
        analyzers = AnalyzerPipeline([
            FaceLandmarkAnalyzer(),
            HandLandmarkAnalyzer(),
            PoseLandmarkAnalyzer(),
        ])
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
