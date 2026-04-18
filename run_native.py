#!/usr/bin/env python
"""Native desktop runner: Tkinter preview + Tkinter control panel.

No web server, no OpenCV window. Default camera index 2 on this machine.
Preview window keys: F = toggle fullscreen, ESC = exit fullscreen.
Closing the preview with X hides it (engine keeps running); use Exit on
the control panel to quit.
"""
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "python"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "cpp", "build"))

import tkinter as tk
from tkinter import ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

print("Loading engine...", flush=True)
from ascii_stream_engine.application.engine import StreamEngine
from ascii_stream_engine.adapters.sources.camera import OpenCVCameraSource
from ascii_stream_engine.adapters.renderers.passthrough_renderer import PassthroughRenderer
from ascii_stream_engine.adapters.processors.filters import ALL_FILTERS
from ascii_stream_engine.adapters.perception.hands import HandLandmarkAnalyzer
from ascii_stream_engine.domain.config import EngineConfig


class ResizingCameraSource:
    """Forces a target capture resolution, downscales if driver returns larger."""

    def __init__(self, camera_index=2, width=640, height=480):
        self._inner = OpenCVCameraSource(camera_index=camera_index)
        self._w = width
        self._h = height

    def open(self):
        requested = self._inner._camera_index
        self._inner.open()
        cap = self._inner._cap
        actual = self._inner._camera_index
        if actual != requested:
            print(
                f"WARNING: requested camera {requested} but opened camera {actual} via fallback",
                flush=True,
            )
        if cap is not None:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._h)

    def read(self):
        frame = self._inner.read()
        if frame is None:
            return None
        h, w = frame.shape[:2]
        if w != self._w or h != self._h:
            frame = cv2.resize(frame, (self._w, self._h), interpolation=cv2.INTER_AREA)
        return frame

    def close(self):
        self._inner.close()


class TkPreviewSink:
    """Preview sink backed by a Tkinter Toplevel — robust against close clicks."""

    def __init__(self, root: tk.Tk, title: str = "Spatial Engine — Preview"):
        self._root = root
        self._title = title
        self._window = None
        self._label = None
        self._photo = None
        self._latest_rgb = None
        self._lock = threading.Lock()
        self._is_open = False
        self._is_fullscreen = False
        self._output_size = None
        self._after_id = None

    def open(self, config, output_size):
        self._output_size = output_size
        self._is_open = True
        self._root.after(0, self._create_window)

    def _create_window(self):
        if self._window is not None and self._window.winfo_exists():
            self._window.deiconify()
            self._window.lift()
            return
        self._window = tk.Toplevel(self._root)
        self._window.title(self._title)
        w, h = self._output_size or (640, 480)
        self._window.geometry(f"{int(w * 1.5)}x{int(h * 1.5)}+40+40")
        self._window.configure(background="black")
        self._label = tk.Label(self._window, background="black")
        self._label.pack(fill="both", expand=True)
        # bind_all so the keys work regardless of which widget has focus.
        for seq in ("<KeyPress-f>", "<KeyPress-F>", "<F11>"):
            self._window.bind_all(seq, lambda e: self._toggle_fullscreen())
        self._window.bind_all("<Escape>", lambda e: self._exit_fullscreen())
        self._window.protocol("WM_DELETE_WINDOW", self._on_close_request)
        self._schedule_tick()

    def _toggle_fullscreen(self):
        if self._window is None:
            return
        if self._is_fullscreen:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def _enter_fullscreen(self):
        if self._window is None or self._is_fullscreen:
            return
        self._window.attributes("-fullscreen", True)
        self._is_fullscreen = True

    def _exit_fullscreen(self):
        if self._window is None or not self._is_fullscreen:
            return
        self._window.attributes("-fullscreen", False)
        self._is_fullscreen = False

    def _on_close_request(self):
        # Hide instead of destroy so engine can keep running; Exit button quits.
        if self._window is not None:
            self._window.withdraw()

    def write(self, frame):
        if not self._is_open:
            return
        image = frame.image if hasattr(frame, "image") else frame
        if isinstance(image, Image.Image):
            if image.mode != "RGB":
                image = image.convert("RGB")
            arr = np.asarray(image, dtype=np.uint8)
        else:
            arr = np.asarray(image, dtype=np.uint8)
            if arr.ndim == 2:
                arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
            else:
                arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        with self._lock:
            self._latest_rgb = arr

    def _schedule_tick(self):
        self._after_id = self._root.after(30, self._tick)

    def _tick(self):
        if not self._is_open or self._window is None or not self._window.winfo_exists():
            return
        with self._lock:
            frame = self._latest_rgb
        if frame is not None:
            cw = self._label.winfo_width()
            ch = self._label.winfo_height()
            # On first ticks label may report 1x1 until geometry settles; fall back
            # to the frame's native size so we always draw something.
            if cw <= 10 or ch <= 10:
                cw, ch = frame.shape[1], frame.shape[0]
            img = Image.fromarray(frame)
            if (img.width, img.height) != (cw, ch):
                img = img.resize((cw, ch), Image.BILINEAR)
            self._photo = ImageTk.PhotoImage(img)
            self._label.configure(image=self._photo)
        self._schedule_tick()

    def close(self):
        self._is_open = False
        if self._after_id is not None:
            try:
                self._root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def destroy(self):
        self.close()
        if self._window is not None:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None

    def is_open(self):
        return self._is_open

    def supports_multiple_clients(self):
        return False


def probe_cameras(max_index=6):
    """Return list of (index, label) for cameras that actually deliver frames."""
    working = []
    for i in range(max_index + 1):
        try:
            cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = cap.get(cv2.CAP_PROP_FPS) or 0
                    working.append((i, f"cam {i}  {w}x{h} @ {fps:.0f}"))
            cap.release()
        except Exception:
            pass
    return working


def build_engine(tk_root, camera_index=2, width=640, height=480):
    source = ResizingCameraSource(camera_index=camera_index, width=width, height=height)
    renderer = PassthroughRenderer()
    sink = TkPreviewSink(tk_root)
    cfg = EngineConfig(fps=30, enable_temporal=True, enable_events=True)
    engine = StreamEngine(
        source=source, renderer=renderer, sink=sink,
        config=cfg, use_graph=True, enable_profiling=False,
    )
    try:
        engine.analyzer_pipeline.add(HandLandmarkAnalyzer(max_num_hands=2))
        print("Hand analyzer registered", flush=True)
    except Exception as e:
        print(f"  [skip HandLandmarkAnalyzer: {e}]", flush=True)

    # Per-filter default overrides for better out-of-the-box behavior.
    _filter_kwargs = {
        "HandFrameFilter": {"effect": "ascii"},
    }

    loaded = skipped = 0
    seen_classes = set()
    for cls in ALL_FILTERS.values():
        if cls in seen_classes:
            continue
        seen_classes.add(cls)
        try:
            kwargs = _filter_kwargs.get(cls.__name__, {})
            inst = cls(**kwargs)
            inst.enabled = False
            engine.filter_pipeline.add(inst)
            loaded += 1
        except Exception as e:
            skipped += 1
            print(f"  [skip {cls.__name__}: {e}]", flush=True)
    print(f"Loaded {loaded} filters ({skipped} skipped)", flush=True)
    return engine, sink


class ControlPanel:
    def __init__(self, root, engine, preview_sink, cameras, current_camera_index):
        self.engine = engine
        self.preview_sink = preview_sink
        self._cameras = cameras  # list of (index, label)
        self._current_cam = current_camera_index
        self.root = root
        self.root.title("Spatial Engine — Control")
        screen_w = self.root.winfo_screenwidth()
        panel_w = 460
        self.root.geometry(f"{panel_w}x740+{max(0, screen_w - panel_w - 20)}+40")

        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")
        self.start_btn = ttk.Button(top, text="▶ Start", command=self.toggle_running)
        self.start_btn.pack(side="left")
        self.show_btn = ttk.Button(top, text="Show preview", command=self.show_preview)
        self.show_btn.pack(side="left", padx=4)
        self.stats_lbl = ttk.Label(top, text="— FPS | 0 active", anchor="e")
        self.stats_lbl.pack(side="right", fill="x", expand=True)

        cam_row = ttk.Frame(self.root, padding=(8, 0, 8, 4))
        cam_row.pack(fill="x")
        ttk.Label(cam_row, text="Camera:").pack(side="left")
        labels = [lbl for _, lbl in cameras] or ["cam 0"]
        current_label = next(
            (lbl for idx, lbl in cameras if idx == current_camera_index),
            labels[0],
        )
        self.cam_var = tk.StringVar(value=current_label)
        self.cam_combo = ttk.Combobox(
            cam_row, values=labels, textvariable=self.cam_var, state="readonly"
        )
        self.cam_combo.pack(side="left", fill="x", expand=True, padx=4)
        self.cam_combo.bind("<<ComboboxSelected>>", self._on_camera_change)

        search_row = ttk.Frame(self.root, padding=(8, 0))
        search_row.pack(fill="x")
        ttk.Label(search_row, text="Filter:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.apply_search())
        ttk.Entry(search_row, textvariable=self.search_var).pack(
            side="left", fill="x", expand=True, padx=4
        )

        container = ttk.Frame(self.root)
        container.pack(fill="both", expand=True, padx=8, pady=4)
        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.inner = ttk.Frame(canvas)
        self.inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        self._rows = []
        # Filters that expose a single string `effect`/`mode` param worth picking in UI.
        _mode_options = {
            "hand_frame": ("effect", ["ascii", "invert", "blur", "pixelate", "edge", "tint"]),
            "infrared": (
                "colormap",
                ["inferno", "magma", "plasma", "viridis", "jet", "turbo", "hot", "cool", "bone"],
            ),
        }
        for f in sorted(self.engine.filter_pipeline.filters, key=lambda x: x.name):
            row = ttk.Frame(self.inner)
            row.pack(fill="x", anchor="w", padx=4, pady=1)

            var = tk.BooleanVar(value=f.enabled)

            def _toggle(v=var, fobj=f):
                fobj.enabled = v.get()

            cb = ttk.Checkbutton(row, text=f.name, variable=var, command=_toggle)
            cb.pack(side="left")

            mode_cfg = _mode_options.get(f.name)
            if mode_cfg is not None:
                attr, values = mode_cfg
                current = getattr(f, attr, values[0])
                mode_var = tk.StringVar(value=current)

                def _on_mode(_e=None, fobj=f, mvar=mode_var, a=attr):
                    setattr(fobj, a, mvar.get())

                combo = ttk.Combobox(
                    row, values=values, textvariable=mode_var, width=10, state="readonly"
                )
                combo.pack(side="right", padx=4)
                combo.bind("<<ComboboxSelected>>", _on_mode)

            self._rows.append((f, var, row))

        bottom = ttk.Frame(self.root, padding=8)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Enable all", command=self._set_all(True)).pack(side="left")
        ttk.Button(bottom, text="Disable all", command=self._set_all(False)).pack(
            side="left", padx=4
        )
        ttk.Button(bottom, text="Exit", command=self.on_close).pack(side="right")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(500, self.refresh_stats)

    def _set_all(self, value):
        def _apply():
            for f, var, _ in self._rows:
                f.enabled = value
                var.set(value)

        return _apply

    def apply_search(self):
        q = self.search_var.get().strip().lower()
        for f, _, widget in self._rows:
            if not q or q in f.name.lower():
                widget.pack(fill="x", anchor="w", padx=4, pady=1)
            else:
                widget.pack_forget()

    def toggle_running(self):
        if self.engine.is_running:
            self.engine.stop()
            self.start_btn.configure(text="▶ Start")
        else:
            self.engine.start()
            self.start_btn.configure(text="■ Stop")

    def show_preview(self):
        # Re-create / deiconify preview if the user hid it via X.
        self.preview_sink._create_window()

    def _on_camera_change(self, _event=None):
        label = self.cam_var.get()
        new_index = next(
            (idx for idx, lbl in self._cameras if lbl == label), None
        )
        if new_index is None or new_index == self._current_cam:
            return
        # Prevent re-entry while swapping; run the blocking stop/start in a
        # background thread so the Tk main loop keeps pumping and the preview
        # does not freeze.
        self.cam_combo.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self._current_cam = new_index

        def _worker(idx=new_index):
            was_running = self.engine.is_running
            ended_running = was_running
            try:
                print(f"[cam-switch] was_running={was_running} -> cam {idx}", flush=True)
                if was_running:
                    self.engine.stop()
                    print("[cam-switch] engine stopped", flush=True)
                # Probe the target index BEFORE swapping so we fail fast
                # instead of silently landing in a bad state.
                probe = cv2.VideoCapture(idx, cv2.CAP_V4L2)
                ok = probe.isOpened()
                if ok:
                    ret, _ = probe.read()
                    ok = bool(ret)
                probe.release()
                if not ok:
                    print(f"[cam-switch] probe FAILED for cam {idx} — keeping old source", flush=True)
                    ended_running = False
                else:
                    self.engine.set_source(
                        ResizingCameraSource(camera_index=idx, width=640, height=480)
                    )
                    print("[cam-switch] source swapped", flush=True)
                    if was_running:
                        self.engine.start()
                        print(f"[cam-switch] engine started, is_running={self.engine.is_running}", flush=True)
                        ended_running = self.engine.is_running
            except Exception as e:
                print(f"[cam-switch] ERROR: {e}", flush=True)
                ended_running = False
            finally:
                self.root.after(0, self._after_camera_change, ended_running)

        threading.Thread(target=_worker, daemon=True).start()

    def _after_camera_change(self, was_running):
        self.cam_combo.configure(state="readonly")
        self.start_btn.configure(
            state="normal", text="■ Stop" if was_running else "▶ Start"
        )

    def refresh_stats(self):
        fps = None
        try:
            fps = self.engine._metrics.get_fps()
        except Exception:
            pass
        n_on = sum(1 for f, _, _ in self._rows if f.enabled)
        fps_text = f"{fps:.1f} FPS" if fps is not None else "— FPS"
        self.stats_lbl.configure(text=f"{fps_text}  |  {n_on} active")
        self.root.after(500, self.refresh_stats)

    def on_close(self):
        try:
            if self.engine.is_running:
                self.engine.stop()
        except Exception:
            pass
        try:
            self.preview_sink.destroy()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    print("Probing cameras...", flush=True)
    cameras = probe_cameras()
    for idx, lbl in cameras:
        print(f"  {lbl}", flush=True)
    preferred = 2 if any(i == 2 for i, _ in cameras) else (cameras[0][0] if cameras else 0)
    root = tk.Tk()
    engine, preview_sink = build_engine(root, camera_index=preferred, width=640, height=480)
    panel = ControlPanel(root, engine, preview_sink, cameras, preferred)
    print(f"Control panel up. Default camera: {preferred}. Click Start.", flush=True)
    root.mainloop()
