# Iteration 05 — phase D validation

Timestamp: 2026-04-19T18:45Z
Branch: feat/web-dashboard-v3

## What was validated

### pytest (40 tests, all pass)
- `protocol.is_allowed_op` — 10 cases (whitelist)
- `protocol.clamp_float` — 5 cases (in range, below, above, bad input, string coerce)
- `protocol.clamp_int` — 3 cases (snap to step, default, bound clamp)
- `protocol.coerce_bool` — 10 cases (bool, int, string, None)
- `registry.FILTERS` — 5 filters present, factories on wired ones, factory=None on WIP
- `registry.find_filter` / `find_param` — known + unknown
- `registry.default_params` — id→default map; empty for WIP
- Param spec sanity — required keys; min/max/step on slider/stepper; options on select

Run:
```
PYTHONPATH=python:cpp/build python -m pytest \
    python/ascii_stream_engine/tests/test_web_dashboard.py -v
```

### WS smoke test (live server)
- handshake auth ok / bad token (close 4401) / bad version (close 1008)
- start → engine opens /dev/video2 + cv2 window, snapshot.running=True
- stop → camera released, snapshot.running=False
- toggle_filter bloom on → enabled=True in next snapshot
- set_param bloom.intensity=0.95 → applied=0.95
- set_param value=99 → clamped to 1.0
- bc_cpp.brightness=50 → applied=50
- toggle WIP chroma → error code=wip_filter
- toggle unknown ghost → error code=unknown_filter
- bad json / bad op → close 1003

### Playwright visual (iPhone 14 viewport)
- hub: 4 categories Distorsión / Color / Glitch / Estilo with counts
- cat (COLOR): Brillo/Contraste + Bloom · audio-reactivo rows
- detail (Bloom): Activo toggle + Intensidad + Umbral + Reactividad audio
  sliders, all with cyan glow
- back nav works
- pill flips OFFLINE↔LIVE on start/stop

### Reconnect detection
- killing uvicorn → pill goes from OFFLINE to RECONECT in ~250 ms
- client retries with exponential backoff (250 ms → 4 s cap)

## Known limitations (out of session scope)

- Token does not survive server restart → reconnect to a new server
  fails auth. Acceptable for live performance use (one boot = one
  session). Persistent tokens need a small `~/.sie/token` cache.
- Multi-tab sync not formally tested. The server pushes the same
  state to every connected client so it should work, but no Playwright
  multi-context test was written.
- No test for the case where set_param fires while engine is running
  → confirmed via cv2 visually but not automated.

## Files
- `python/ascii_stream_engine/tests/test_web_dashboard.py` (NEW, 40 tests)

## Coverage / footprint summary
- Backend: registry.py (222 LOC), bridge.py (~248 LOC), ws.py (~235 LOC),
  app.py (~70 LOC), protocol.py (~50 LOC) → ~825 LOC total.
- Frontend: index.html (87 LOC), v3.css (~700 LOC), app.js (~790 LOC) → ~1577 LOC.
- Tests: test_web_dashboard.py (~150 LOC).
- Plus: run_dashboard_mobile_v3.py (~125 LOC entry point).

Everything sits under `adapters/outputs/web_dashboard/` per ARCHITECTURE.md.
v1 (run_dashboard_mobile.py) and v2 (run_dashboard_mobile_v2.py) untouched.
