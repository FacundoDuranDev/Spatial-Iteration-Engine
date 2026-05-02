# Iteration 02 — fastapi-shell (Phase A complete)

Timestamp: 2026-04-19T17:30Z
Branch: feat/web-dashboard-v3
Commit: (pending — will be `feat(web-dashboard): phase A foundation`)

## What landed

- `python/ascii_stream_engine/adapters/outputs/web_dashboard/`
  - `__init__.py`, `app.py`, `bridge.py`, `ws.py`, `protocol.py`
  - `static/index.html`, `static/v3.css`, `static/app.js`
- `run_dashboard_mobile_v3.py` (entry point)
- `.claude/scratch/ws_protocol.md` (frozen contract v=1)
- `.claude/scratch/_tools/snap_v3.py` (Playwright iPhone-14 capture)

## Validated

- `/health` returns `{"status":"ok","running":false,"version":"3.0.0","protocol":"1"}`
- WS bad token → close 4401 (Starlette returns 403 pre-handshake)
- WS bad version → close 1008
- WS good handshake → first `state` push, then 1 Hz ticks
- `op:start` → engine opens `/dev/video2`, cv2 window appears, `running=true`
- `op:stop` → engine releases, `running=false`
- `op:flubber` → `error code unknown_op` + close 1003
- Heartbeat ping/pong implemented (15s interval, 30s pong timeout)
- Mobile shell renders cleanly at iPhone 14 (390×844): theme stage
  (cyan + black + Space Grotesk), 2×2 hub grid, sticky header (KPIs +
  status pill), sticky cyan-glow Iniciar button.
- Pill flips OFFLINE → LIVE on start (cyan glow).
- Button flips primary "▶ Iniciar" → danger "■ Detener" on start.

## Known polish gaps (Phase C)

- "Distorsión" truncates ("Distorsió") in the cat card — name is
  bigger than the column width at 390 px.
- Title "SIE · Control" wraps to 2 lines, competing with KPIs for
  header width.
- Footer button glyph is centered vertically a touch low.

## Files captured
- `snapshot/run_dashboard_mobile_v3.py`
- `snapshot/web_dashboard/` (full module tree)

## How to retake screenshots
```
python run_dashboard_mobile_v3.py &        # in conda env
# grab token from stdout
python .claude/scratch/_tools/snap_v3.py 02-fastapi-shell <token>
```

## Next (Phase B)
Wire 3 deep filters (TemporalScan + Bloom + BC) + 2 stubs (Chroma, Invert).
Spawn 2 parallel subagents: backend (registry+bridge+ws dispatch) and
frontend (cat list + detail + widget bindings).
