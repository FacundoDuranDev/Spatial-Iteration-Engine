# Decision: web dashboard v3 (FastAPI + WebSocket + vanilla SPA)

**Status**: accepted (2026-04-19)
**Branch of origin**: `feat/web-dashboard-v3`
**Supersedes (in spirit, not in code)**: the v1/v2 Gradio dashboards.
v1 (`run_dashboard_mobile.py`) and v2 (`run_dashboard_mobile_v2.py`)
remain in the tree as fallbacks.

## Context

The mobile control surface for live VJ use went through three iterations:

1. **v1** — flat list of widgets in Gradio. Functional but cramped at
   390 px.
2. **v2** — drill-in nav (hub → cat → detail) inside Gradio. Fought
   Gradio's Blocks chrome (gray Group backgrounds, `lg secondary` button
   classes overriding ours, "Built with Gradio" footer breaking the
   sticky bar, layout snapping at 390 px).
3. **mockup** in `design/ui_kits/gradio_remote/v2/` — pure HTML/CSS/JS,
   visually correct, drill-in nav working, but no engine wiring.

The user validated the **stage** theme of the mockup
(`?view=hub&theme=stage`) and asked for a working version of that exact
visual treatment, wired to the engine.

## Decision

Stop fighting Gradio. Build v3 as a small FastAPI app with a single
WebSocket endpoint and a vanilla HTML/CSS/JS shell. The web dashboard
is treated as an **output sink** (`adapters/outputs/web_dashboard/`),
analogous to NDI / RTSP / composite, not as part of the
`presentation/` layer (which `rules/ARCHITECTURE.md` reserves for
notebook UIs).

## Why no framework chrome

Every notebook framework (Gradio, Streamlit, Dash, Panel) ships with
chrome — a footer ("Built with X · Settings"), default fonts, default
spacings, default theme overlays. For our use case those choices fight
us:

1. **Live-performance product surface, not a framework demo.**
   The user is on a phone in a dark theatre/club, controlling video
   filters in real time. The view should look like a control surface,
   not like an unfinished notebook.
2. **The footer broke the sticky bottom bar.** v2's `Iniciar/Detener`
   primary action lived at the bottom; Gradio's footer pushed it off
   the safe area on iOS Safari.
3. **Distraction in low-light contexts.** Gray Gradio chrome on a
   black stage theme reads as visual noise.

So the v3 HTML carries this comment block (see `static/index.html`):

```
NOTA · Por qué este HTML NO incluye "Built with Gradio · Settings"
- Es un product surface mobile-first para uso en performance
  en vivo (VJ), no un demo de framework.
- El footer rompía el sticky-bar Iniciar/Detener al pie.
- Distrae visualmente del contexto en penumbra de teatro/club.
Si en el futuro se reintroduce algún framework con chrome propia,
esta nota debe actualizarse Y discutirse antes de mergear.
```

If a future contributor wants to put a framework back in front of this
UI, they should update both the HTML comment and this file before
merging.

## Architecture

```
Phone (Safari) ── HTTP ──> FastAPI/uvicorn :7861
              ── WS  ──>   ws://host:7861/ws?t=<token>&v=1
```

- Static `/` → `index.html` shell.
- Static `/static/{v3.css, app.js}` → tokens, atoms, nav stack, WS client.
- `/health` → JSON status.
- `/ws` → bidirectional JSON, contract frozen at `.claude/scratch/ws_protocol.md` (v=1).

Threading:
- uvicorn event loop in main thread.
- Engine in its own thread (existing).
- WS handlers (async) call sync `EngineBridge` directly for filter
  mutations (microsecond ops, lock-protected).
- `engine.start()` / `engine.stop()` go through `loop.run_in_executor(None, …)`
  because they block 500 ms - 2 s (camera open).

## Trade-offs

**For**:
- Zero framework lock-in; we own every CSS and JS line.
- Mobile-first: 64 px hit targets, 16 px font min, `touch-action`,
  `setPointerCapture`, safe-area insets — all configurable per-rule.
- WebSocket beats Gradio's polling; per-frame state pushes < 1 KB.
- One adapter, swap-in friendly: any future client (a desktop OSC
  controller, a 7" tablet kiosk) can speak the same WS contract.

**Against**:
- We now own a small SPA. ~1 600 LOC of HTML/CSS/JS to maintain.
- No off-the-shelf widgets — we re-implemented toggle / slider /
  dial / stepper / select in vanilla JS.
- Single-user-per-token auth only. Multi-user / role-based access
  would require a real session layer.

The team accepted these trade-offs because:
- The previous Gradio LOC count (theme overlays + widget kit) was
  comparable, and it was load-bearing CSS we couldn't share with the
  framework anyway.
- The widget kit was already a port of `mcp_v2`; vanilla JS is easier
  to evolve than Gradio web-component patches.

## Out of scope (this decision)

- Authentication beyond a per-boot token.
- TLS (LAN-only assumption; revisit before WAN exposure).
- Recording / preset save UI.
- Replacing v1/v2 dashboards in any active code path. They stay as
  documented fallbacks.

## See also

- `python/ascii_stream_engine/adapters/outputs/web_dashboard/` — code.
- `.claude/scratch/ws_protocol.md` — frozen WS contract v=1.
- `.claude/scratch/_v2_iterations/` — iteration history with snapshots
  and screenshots.
- `run_dashboard_mobile_v3.py` — entry point.
- `rules/ARCHITECTURE.md` — places `web_dashboard` under
  `adapters/outputs/`.
- `rules/PIPELINE_EXTENSION_RULES.md` — explains why outputs implement
  the OutputSink-like contract (the dashboard does not, because it
  doesn't consume frames; instead it consumes the engine's state
  snapshot via `EngineBridge`).
