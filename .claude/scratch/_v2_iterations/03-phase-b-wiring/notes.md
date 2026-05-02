# Iteration 03 — phase B wiring

Timestamp: 2026-04-19T18:00Z
Branch: feat/web-dashboard-v3

## What landed

### Backend (subagent 1)
- `web_dashboard/registry.py` — declarative spec for 5 filters:
  - 3 wired: `temporal_scan` (DISTORT), `bc_cpp` (COLOR), `bloom` (COLOR)
  - 2 WIP: `chroma` (GLITCH), `invert` (STYLIZE)
  - 4 categories with Spanish names
  - Helpers: `find_filter`, `find_param`, `default_params`
- `web_dashboard/bridge.py` extended:
  - lazy `_ensure(fid)` instantiates filter on first toggle, adds to pipeline
  - `toggle_filter(fid, on)` thread-safe
  - `set_param(fid, pid, value)` thread-safe (value pre-clamped by ws.py)
  - `snapshot()` reads live params from instance (private attrs mapped per filter)
- `web_dashboard/ws.py` extended:
  - `toggle_filter` op with auth/wip/error code handling
  - `set_param` op with `_coerce_value` (kind-aware clamp)
- **Subagent caught two bugs in v2 spec**: Bloom/BC use private attrs
  (`_intensity`, `_brightness_delta`, etc.) and v2's setattr would have
  created phantom public attrs. Subagent fixed with explicit setter helpers.

### Frontend (subagent 2)
- `static/index.html` — 3-view shell (hub/cat/detail) with back button
- `static/v3.css` — +427 lines: drill-in views, slide animation, atoms
  (toggle, slider, dial, stepper, select), WIP badge
- `static/app.js` — +661 lines: REGISTRY const mirroring registry.py,
  nav stack (push/pop, animated), per-view renderers, widget binders
  with pointer events + setPointerCapture, 50 ms debounce on drag

### Post-merge fix (me)
- `app.js`: `render(snap)` was rebuilding the active view on every 1 Hz
  state tick, causing flicker mid-screenshot. Added `state.lastFiltersJson`
  diff so cat/detail views only rebuild on actual filter changes (and
  never mid-drag). `showView(view, animate)` now takes an explicit
  animate arg and skips re-trigger if target view didn't change.

## Validated end-to-end (via WS smoke test)

- Hub renders 4 categories with live counts (`X activos / N total`)
- Cat list (COLOR) lists Brillo/Contraste + Bloom · audio-reactivo
- Detail view (Bloom) renders all 3 sliders with cyan-glow theme
- `toggle_filter` op → `enabled=True` reflected in snapshot
- `set_param bloom.intensity=0.95` → applied=0.95
- Out-of-range `value=99` → clamped to 1.0
- `bc_cpp.brightness=50` applied
- WIP `chroma` toggle → `error code=wip_filter`
- Unknown `ghost` toggle → `error code=unknown_filter`
- start/stop continue to work, cv2 window opens/closes

## Known visual gaps (Phase C)

- Header title "Bloom · audio-reactivo" wraps to 3 lines in detail view
  → need to reduce title font-size in cat/detail views or truncate
- Some screenshots show "▶ Iniciar" floating mid-screen — looks like a
  Chromium screenshot artifact rather than a real DOM duplicate
  (`grep -c "Iniciar" dom.html` → 1)
- Cat card "Distorsión" still truncates to "Distorsió" at 390 px

## Files captured
- `snapshot/web_dashboard/` (full module tree, no pycache)

## Next (Phase C)
- Title-size step-down in cat/detail (use `--fs-md` not `--fs-lg`)
- Cat card name should shrink-to-fit (use `font-size: clamp` or `min(8vw, ...)`)
- Investigate the floating "Iniciar" screenshot artifact (probably
  unrelated to real UX, but worth confirming)
- Check pointer drag on touch (Playwright drag may differ from real touch)
