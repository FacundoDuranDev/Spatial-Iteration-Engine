---
name: mobile-web-first
description: Use when designing, building, or debugging the Gradio mobile control surface (run_dashboard_mobile.py, presentation/widgets/) — touch UX, viewport, hit targets, scroll behavior, iOS Safari quirks, drill-in navigation, and any phone-facing HTML/CSS/JS in this repo.
---

# Mobile-First Web Development — Spatial-Iteration-Engine

> **FIRST:** read `.claude/skills/shared/AGENT_RULES.md` if it exists.
> Read `python/ascii_stream_engine/presentation/widgets/README.md` to understand the widget kit contract before changing components.

The phone is the primary target for `run_dashboard_mobile.py`. The user opens the Gradio URL on their phone via LAN — no native app, no iframe, no preview embedding. Build for one finger in motion.

## Hard constraints in this repo

- **Stack:** Gradio Blocks (Python) + custom widgets (`presentation/widgets/`) that ship vanilla SVG/JS. No React, no Vue, no build step.
- **CSS scope:** every visual primitive lives under `.sie-root`. Tokens are CSS custom properties prefixed `--sie-*`. Themes (`paper`, `industrial`, `stage`) override these tokens — never the structure.
- **Page width is locked to 440px** in `run_dashboard_mobile.py` via `.gradio-container { max-width: 440px }`. Don't design wider layouts; assume one column.
- **No live preview during iteration.** You can't open the dashboard yourself. State your assumptions in the chat and ask the user to verify on their phone before you over-iterate.
- **No JS frameworks.** Touch handling is pointer events + `touch-action: none` + `setPointerCapture`. Pattern is in `static/angle_dial.js`.

## Touch UX rules

1. **Hit targets ≥ 48×48 CSS px.** The `stage` theme bumps to 64px+; the default and `industrial` themes use 48–56px (`--sie-row-h: 64px` in widgets.css). Never rely on a 24px icon being tappable on its own — wrap it in a 48px container.
2. **Spacing between targets ≥ 8px.** Adjacent toggles must not allow accidental fat-finger crossover.
3. **`touch-action: manipulation`** on tap-only elements (toggles, buttons) to kill the 300ms double-tap-to-zoom delay.
4. **`touch-action: none`** on draggable elements (sliders, dials, XY pads) — otherwise the browser hijacks the gesture for scroll.
5. **Use `pointer-*` events**, not `mouse-*` or `touch-*`. Pointer Events normalize across mouse/touch/pen and bubble correctly.
6. **`setPointerCapture(e.pointerId)` on `pointerdown`** so the gesture keeps reporting deltas even if the finger leaves the element.
7. **`-webkit-tap-highlight-color: transparent`** on the root — kills the gray flash on tap. Already set in `widgets.css` and every theme file.
8. **Scroll lock during a drag** is implicit when you `setPointerCapture` + `touch-action: none`. Don't add manual `e.preventDefault()` unless you've measured it's needed.

## Viewport / layout

1. The Gradio app already injects `<meta name="viewport" content="width=device-width, initial-scale=1">`. Don't add a second one.
2. Use **logical units** (`rem`, `%`, `vw`, `clamp()`) over fixed pixels for fluid type. Hit targets stay in px because they're physical (finger size).
3. **Avoid `100vh`** on iOS Safari — the URL bar moves and the viewport shrinks/grows. Prefer `min-height: 100dvh` (dynamic viewport height, supported in iOS 15.4+) or just let content flow.
4. **`overscroll-behavior: contain`** on scrollable card bodies prevents the parent (page) from rubber-banding when you scroll inside.
5. **Sticky footer pattern** (Start/Stop bar): `position: sticky; bottom: 0; padding-bottom: env(safe-area-inset-bottom)` to clear the iPhone home indicator.
6. **Safe-area insets** matter on notched/Dynamic-Island phones. Use `env(safe-area-inset-top/bottom/left/right)`.

## iOS Safari quirks (the ones that bite)

- **`<input>` inside a form auto-zooms when font-size < 16px.** All `--sie-fs-*` tokens for inputs must be ≥16px on iOS, or set `font-size: max(16px, var(--sie-fs-row))`.
- **`position: fixed` jitters during scroll** in older iOS. Use `position: sticky` when possible.
- **`pointer-events: none` on a parent kills its children.** Already a footgun in our `.sie-toggle.sie-disabled`. If you need a child to remain interactive, override with `pointer-events: auto` explicitly.
- **`backdrop-filter` is unreliable** in Gradio iframes. The design rules already say "no frosted glass" — keep it that way.
- **`100vh + keyboard open`**: when an input gets focus, iOS does NOT shrink `100vh`. Use `dvh` or measure `window.innerHeight` if you must.
- **`overflow: hidden` on body locks scroll on Android but not always on iOS.** Use `position: fixed; width: 100%` with stored scroll position if you really need a modal lock.

## Performance on phones

- **Re-render is more expensive than re-style.** Mutate CSS custom properties or `transform` instead of swapping innerHTML.
- **Avoid `box-shadow` with large blur radius** — kills scroll perf on mid-range Androids. The `paper` theme drops glows for this reason; the `stage` theme keeps them but also bumps row height so fewer rows are on-screen.
- **`will-change: transform` only on actively animating elements** — leaving it on idle elements bloats the compositor.
- **One large repaint > many small ones.** Batch DOM writes (read all, then write all).
- **Throttle pointermove handlers** to `requestAnimationFrame` for sliders/dials. The angle dial pattern in `angle_dial.js` is the reference.
- **Network LAN latency**: WebSocket round-trip phone↔PC is typically 5–40 ms. Don't optimistic-update sliders unless the engine is the bottleneck — let Gradio's `change` event drive truth.

## Drill-in navigation in Gradio

Gradio doesn't have a router. Three patterns work:

1. **Nested `gr.Accordion`** — outer per category, inner per filter. Tap to expand in place. **Best for our case** because it keeps state visible and one tap deep. Use `open=False` by default.
2. **`gr.Tabs` at the top + Accordion per filter** — works but tabs eat 48px of vertical real estate persistently.
3. **JS-driven SPA-like swap inside one Blocks** — `gr.HTML` panels with `visible=` toggled on a state var. More flexible but more wiring; reserve for cases where Accordion's UX feels wrong.

**For the SIE mobile dashboard, default to nested Accordion.** Pattern:
```python
with gr.Accordion("COLOR · 7", open=False, elem_classes=["sie-cat-card"]):
    with gr.Accordion("Bloom", open=False, elem_classes=["sie-row"]):
        toggle(...); slider_row(...); slider_row(...)
```

Style the accordion header with `.sie-cat-card` and the inner with `.sie-row` so they inherit the theme. Override `.label-wrap` selectors to hit Gradio's accordion arrow.

## Adding parameters to a filter that "has none"

If `data.js` says a filter has no params (e.g. Brightness/Contrast in the inventory has `params: []` but the Python class accepts brightness + contrast), expose the Python class's actual constructor params with their defaults. **The inventory in `data.js` is incomplete; the Python source is truth.** Mirror the constructor's defaults into the widget's `value=` so the user starts at the same look the filter has when added with no overrides.

## Iteration protocol (no preview = ask)

1. Make a focused change.
2. Tell the user **exactly what to look at on the phone** ("tap COLOR card → tap Bloom row → drag the Threshold slider — does the engine react under 100ms?").
3. Ask for one specific observation, not "how does it look?".
4. Wait for feedback before iterating. Don't speculatively rebuild.

## Files in scope

```
run_dashboard_mobile.py                                       # the entry point
python/ascii_stream_engine/presentation/widgets/__init__.py   # bundler + set_theme()
python/ascii_stream_engine/presentation/widgets/static/
    widgets.css                                                # base tokens + components
    themes/{paper,industrial,stage}.css                        # token overlays
    {angle_dial,slider_row,stepper,toggle}.js                  # touch-aware widgets
design/ui_kits/gradio_remote/                                  # design source (read-only)
```

## Out of scope for this skill

- Notebook UI (use `presentation-development`)
- Filter implementation (use `filter-development`)
- C++ widget bindings or perf tuning at the engine level
- The native cv2 preview window (it's not on the phone)

## When in doubt

- Bigger hit targets, fewer per screen.
- Spanish copy for UI, English for code/comments (matches the rest of the dashboard).
- One column, one focus per screen, sticky controls at the bottom.
- If a tap doesn't feel instant on the phone, something's wrong — investigate `touch-action`, `pointer-events`, and the 300ms zoom delay first.
