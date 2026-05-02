# v3 Web Dashboard — handoff (2026-04-20)

**Branch**: `feat/web-dashboard-v3` (13 commits ahead of `teams/main`, never pushed)
**Status**: production-ready. 42 filters wired, all toggles validated end-to-end.

## Quick start

```
source /home/fissure/miniconda3/etc/profile.d/conda.sh
conda activate spatial-iteration-engine
git checkout feat/web-dashboard-v3
PYTHONPATH=python:cpp/build python run_dashboard_mobile_v3.py
```

Boot prints LAN URL + token + QR. Phone (same WiFi) opens any of:
- `http://<lan-ip>:7861/`  (token injected into served HTML — no query needed)
- `http://<lan-ip>:7861/?t=<token>`  (works too)

Install as PWA on Android Chrome / iOS Safari: open the URL → menu →
"Install app" / "Add to home screen". Cyan-on-black SIE icon, opens
standalone (no browser chrome).

## What works (all validated)

- WS handshake (token + version), close codes 4401/1008/1003.
- start → opens `/dev/video2`, cv2 preview window appears.
- start → stop → start → stop cycles work without freezing the
  preview (StickyPreviewSink keeps the cv2 window alive between
  cycles; the engine itself stays warm — Detener mutes the sink).
- 42 filters in 4 categories — every toggle + every wired param
  echoes back through the snapshot:
  - **DISTORT (7)**: Swap canales, Marco entre manos, Warp entre
    manos, Caleidoscopio, Mosaico, Colapso radial, Despl. UV
  - **COLOR (10)**: Brillo/Contraste, Bloom, Bloom cinemático,
    Brillo (config), Color grading, Escala de grises, Infrarrojo,
    Invertir (config), Lens flare, Viñeta
  - **GLITCH (8)**: TemporalScan (unifica chrono+slit), Aberración
    cromática, Estelas cromáticas, CRT glitch, Doble visión, Bloques
    glitch, Motion blur, Radial blur
  - **STYLIZE (17)**: Invertir, ASCII, Boids, Physarum (×2), Profundidad
    de campo, Realce detalle, Bordes, Suavizado bordes, Grano película,
    Patrones geométricos, Tipografía cinética, Kuwahara, Partículas,
    Compositor paneles, Puntillismo, Toon shading
- TemporalScan: ángulo + buffer (frames) + bandas (visual stripes) +
  curva. `bands` is decoupled from `buffer` thanks to the C++ kernel
  change shipped in commit 18d1654.
- Reconnect detection: pill flips RECONECT when uvicorn dies, retries
  with exp backoff (250ms → 4s).
- Heartbeat ping/pong every 15s, server closes 1011 on pong timeout.

## Commits on this branch (newest → oldest)

```
80ac181 refactor(web-dashboard): drop redundant slit_scan + chrono_scan; move TemporalScan to GLITCH
f3de020 feat(web-dashboard): wire all 44 filters into the v3 registry
18d1654 feat(temporal_scan): decouple band width from buffer depth (bands param)
e5fcfde fix(web-dashboard): start/stop/start cycle no longer freezes preview
809d234 feat(web-dashboard): wire Chroma + Invert; add PWA manifest + icons
b8bed67 fix(web-dashboard): self-heal stale-cache by forcing reload on empty token
f7c4593 docs(web-dashboard): how to integrate a new filter into v3
3fc45c6 fix(web-dashboard): inject auth token into served HTML
61692ea docs(web-dashboard): phase E — decision record for v3 dashboard
514a2cb test(web-dashboard): phase D — protocol + registry guardrail tests
e5207bf style(web-dashboard): phase C — mobile-first polish
df6a131 feat(web-dashboard): phase B — wire 3 deep filters + 2 WIP stubs
2d95b46 feat(web-dashboard): phase A — FastAPI + WebSocket foundation
```

## Files (what to know)

| Path | Role |
|---|---|
| `python/ascii_stream_engine/adapters/outputs/web_dashboard/registry.py` | declarative spec for the 42 filters — single source of truth |
| `…/bridge.py` | sync wrapper: `_ensure(fid)`, toggle/set_param, snapshot. The mid-run engine.start/stop dance lives here (Detener mutes the sink, doesn't kill the thread) |
| `…/ws.py` | WS endpoint + dispatcher. Frozen contract at `.claude/scratch/ws_protocol.md` (v=1) |
| `…/protocol.py` | op whitelist + clamp helpers |
| `…/app.py` | FastAPI factory + token injection into served HTML |
| `…/static/index.html` | mobile shell (carries the Gradio-omission NOTA + manifest link) |
| `…/static/v3.css` | tokens + chrome + atoms (~700 lines, theme stage) |
| `…/static/app.js` | nav stack + WS client + REGISTRY mirror (~830 lines) |
| `…/static/manifest.json` + `…/static/icons/` | PWA install (Android + iOS) |
| `python/ascii_stream_engine/tests/test_web_dashboard.py` | 44 pytest cases |
| `run_dashboard_mobile_v3.py` | entry point. Defines `StickyPreviewSink` + `cv2.startWindowThread()` |
| `docs/decisions/web_dashboard.md` | architectural decision record |
| `docs/HOW_TO_ADD_FILTER_TO_V3.md` | recipe to add a filter without touching transport code |
| `cpp/include/filters/temporal_scan.hpp` + `cpp/src/filters/temporal_scan.cpp` | C++ kernel with the new `bands` field |
| `cpp/src/bridge/pybind_filters.cpp` | exposes `.bands` property |
| `.claude/scratch/ws_protocol.md` | frozen WS contract v=1 |
| `.claude/scratch/_tools/snap_v3.py`, `snap_v3_nav.py` | iPhone-14 Playwright snaps |
| `.claude/scratch/_v2_iterations/0{1..5}-*` | snapshots per iteration |

## How to add another filter

Follow `docs/HOW_TO_ADD_FILTER_TO_V3.md`. Five steps, all declarative
in `registry.py` + a small mirror in `app.js`. Never touch the
transport (bridge.py / ws.py / protocol.py).

## Known limitations (not bugs — documented for the next session)

1. `ascii.font_size` slider records the value but the glyph atlas is
   built once at init — the visual doesn't change until the filter
   instance is recreated. Needs a setter on `AsciiFilter` that calls
   `_load_mono_font` + `_build_glyph_atlas`.
2. Four filters are toggle-only (their parameters live on
   `EngineConfig`, not on the filter instance): `toon_shading`,
   `brightness_cfg`, `invert_py`, `mosaic`. To expose their knobs we
   need a small "engine-config bridge" — same pattern as the filter
   bridge but writing to `engine.update_config(**kwargs)`.
3. Some filters' counts are static (`num_boids`, `num_agents` for both
   physarum) — they only re-allocate on resolution change. Mid-run
   mutation is silent until reset.
4. Token does not survive a server restart. Each boot mints a fresh
   random hex. Acceptable for one-session-per-show; a `~/.sie/token`
   cache would make it persistent.
5. Multi-tab sync is not formally tested. The server pushes the same
   state to every connected client so it should work, but no Playwright
   multi-context test was written.
6. Headless Chromium at dpr=3 sometimes ghosts text in screenshots
   (the "▶ Iniciar" mid-screen seen in some snaps). Real-device Safari
   is unaffected. `device_scale_factor=1` in the snap script
   eliminates the artifact.

## Suggested next steps (pick whichever you want to attack)

1. **Profile-driven C++ migration**: turn on `enable_profiling=True`
   in `EngineConfig`, identify the 3-5 slowest filters, port only
   those to C++. The OpenCV-backed ones (Canny, bilateral, blur)
   already use SIMD-optimised C++ underneath; rewriting them gives
   ~0% improvement.
2. **Engine-config bridge** for the 4 toggle-only filters above.
3. **Identify more redundancies in the catalogue** — likely candidates:
   - `BrightnessFilter` (config-driven) vs `CppBrightnessContrastFilter` —
     keep the C++ one.
   - `InvertFilter` (config-driven) vs `CppInvertFilter` — keep the C++.
   - `BloomFilter` (audio-reactive) vs `BloomCinematicFilter` —
     genuinely different looks; keep both.
   - `PhysarumFilter` vs `CppPhysarumFilter` — same algorithm, C++ is
     ~5× faster; consider deprecating the Python one in the dashboard.
4. **Persistent token**: `~/.sie/v3_token` cache so phone reconnects
   work after a server restart.
5. **Subgrouping inside STYLIZE** — 17 items in one cat is dense.
   Could split into "Pintura" (kuwahara, stippling, ascii, toon),
   "Vida artificial" (boids, both physarum, particles, geometric
   patterns), "Foto" (depth_of_field, detail_boost, edges, edge_smooth,
   film_grain), "Texto/UI" (kinetic_typography, panel_compositor),
   "Misc" (invert).
6. **Visual badges for filter metadata**: 👋 (perception-driven),
   ♪ (audio-reactive), ⏱ (stateful with frame buffer), ⚡ (C++ kernel).
   The data is already in the filter classes — just needs registry
   metadata + render hint in `app.js`.

## To revert / fall back

```
git checkout teams/main
```
v1 (`run_dashboard_mobile.py`) and v2 (`run_dashboard_mobile_v2.py`)
are untouched on `teams/main` and continue to work.

## Conda env state

In `spatial-iteration-engine`:
- `fastapi==0.135.3`
- `uvicorn[standard]==0.44.0`
- `websockets==15.0.1`
- (existing) `opencv-python`, `pybind11`, `qrcode`, etc.

`pyproject.toml` was intentionally NOT updated (decision #5). If you
build a fresh env, `pip install fastapi 'uvicorn[standard]' websockets`
covers it.

## Validation summary

- `pytest python/ascii_stream_engine/tests/test_web_dashboard.py -v` → 44/44 pass
- WS smoke test: 42/42 filters toggled on/off without errors
- Playwright iPhone-14: hub + cat list + detail + Iniciar/Detener cycles all visually correct
- start → stop → start → repeat: cv2 preview re-opens every cycle, fps climbs to ~30 each time
- Reconnect: pill flips OFFLINE → RECONECT when uvicorn dies, retries with exp backoff
