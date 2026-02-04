from typing import Dict, List, Optional

from ..core.engine import StreamEngine


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
        from ..filters import BrightnessFilter, DetailBoostFilter, EdgeFilter, InvertFilter
    except Exception:
        BrightnessFilter = None
        DetailBoostFilter = None
        EdgeFilter = None
        InvertFilter = None

    cfg = engine.get_config()

    def _default_network_mode() -> str:
        if cfg.udp_broadcast:
            return "Broadcast"
        if cfg.host.startswith("239."):
            return "Multicast"
        if cfg.host in {"127.0.0.1", "localhost"}:
            return "Local"
        return "IP directa"

    status = widgets.HTML()

    # Network controls
    network_mode = widgets.Dropdown(
        options=["Local", "Broadcast", "Multicast", "IP directa"],
        value=_default_network_mode(),
        description="Red",
    )
    host_input = widgets.Text(value=cfg.host, description="Host")
    port_input = widgets.IntText(value=cfg.port, description="Puerto")
    apply_net_btn = widgets.Button(description="Aplicar red")

    # Camera controls
    camera_index = widgets.IntText(value=0, description="Camara")
    apply_camera_btn = widgets.Button(description="Aplicar camara")

    # Filters
    if filters is None:
        filters = {}
        if EdgeFilter:
            filters["Edges"] = EdgeFilter(60, 120)
        if BrightnessFilter:
            filters["Brightness/Contrast"] = BrightnessFilter()
        if InvertFilter:
            filters["Invert"] = InvertFilter()
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

    apply_settings_btn = widgets.Button(description="Aplicar ajustes")
    clear_filters_btn = widgets.Button(description="Quitar filtros")
    start_btn = widgets.Button(description="Start")
    stop_btn = widgets.Button(description="Stop")

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
            status.value = f"Filtros activos: {', '.join([f.name for f in selected])}"
        else:
            status.value = "Sin filtros: imagen normal (sin efectos)."

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
                status.value = "Falta host para IP directa."
                return

        was_running = engine.is_running
        if was_running:
            engine.stop()
        engine.update_config(host=host, port=port_input.value, udp_broadcast=udp_broadcast)
        if was_running:
            engine.start()
        status.value = f"Red aplicada: {mode} -> {host}:{port_input.value}"

    def apply_camera(_=None) -> None:
        source = engine.get_source()
        if not hasattr(source, "set_camera_index"):
            status.value = "Fuente actual no soporta cambio de camara."
            return
        was_running = engine.is_running
        if was_running:
            engine.stop()
        source.set_camera_index(int(camera_index.value))
        if was_running:
            engine.start()
        status.value = f"Camara cambiada a {camera_index.value}."

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
        status.value = "Ajustes aplicados (puede requerir reconectar VLC)."

    def clear_filters(_=None) -> None:
        for cb in filter_checkboxes.values():
            cb.value = False
        _apply_filters()

    def start_engine(_=None) -> None:
        engine.start()
        status.value = "Engine corriendo."

    def stop_engine(_=None) -> None:
        engine.stop()
        status.value = "Engine detenido."

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
            network_mode,
            widgets.HBox([host_input, port_input]),
            apply_net_btn,
        ]
    )

    engine_box = widgets.VBox(
        [
            widgets.HBox([start_btn, stop_btn]),
            widgets.HBox([camera_index, apply_camera_btn]),
            status,
        ]
    )

    filters_box = widgets.VBox(
        [widgets.HTML("<b>Filtros (antes de ASCII)</b>")]
        + list(filter_checkboxes.values())
        + [clear_filters_btn]
    )

    settings_box = widgets.VBox(
        [
            widgets.HTML("<b>ASCII / RAW</b>"),
            fps_slider,
            grid_w_slider,
            grid_h_slider,
            charset_dd,
            contrast_slider,
            brightness_slider,
            frame_buffer_slider,
            bitrate_text,
            render_mode,
            raw_use_size,
            widgets.HBox([raw_width, raw_height]),
            apply_settings_btn,
        ]
    )

    tabs = widgets.Tab(children=[network_box, engine_box, filters_box, settings_box])
    tabs.set_title(0, "Red")
    tabs.set_title(1, "Engine")
    tabs.set_title(2, "Filtros")
    tabs.set_title(3, "ASCII/RAW")

    _apply_filters()
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
