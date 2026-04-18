# Mobile Control Panel — Spatial Iteration Engine

Phone-only (390×844), cyberpunk neon. Gradio web app served from the PC on `0.0.0.0:7860`; opened from phone over LAN. No video on the phone — only controls. Every tweak travels as a small WebSocket event back to the PC pipeline.

## Deliverables

Four mockups are rendered side-by-side by `index.html`:

1. **Hub / Home** — sticky header + 6 category cards (2×3) + sticky footer (Start/Stop + preset).
2. **Distort detail** — filter list with `TemporalScan` (angle dial) and `Depth of Field` (XY pad) expanded inline.
3. **Color detail** — `Color Grading` expanded with dual color wheels + sliders + toggle.
4. **Spec sheet** — palette, type scale, spacing, component states (toggle default/on/pressed/disabled, START/STOP/disabled buttons, slider track).

## Files

- `mcp.css` — scoped cyberpunk tokens (`--mcp-*`). Black `#05060b`, cyan `#00fff2`, magenta `#ff2bd6`.
- `Shell.jsx` — `MobileFrame`, `Header`, `Footer`, `StatusPill`, `CategoryCard`, `PreviewChip`.
- `Controls.jsx` — `Slider`, `Toggle`, `AngleDial`, `XYPad`, `ColorWheel`, `Stepper`, `PresetChips`, `FilterRow`.
- `Screens.jsx` — `HubScreen`, `DistortScreen`, `ColorScreen`, `SpecScreen`.
- `index.html` — renders all four.

## Design decisions

- **Tokens scoped locally** so the neon palette doesn't override the global phosphor-terminal system.
- **Mono for all numbers** (`.mcp-num`), sans for labels (`.mcp-label`). Never both on the same control.
- **Glow-on-state only**: cyan glow means "this is active". Magenta glow only on destructive (STOP). Max 2 animated glows per screen — fine because the app is static.
- **Expand-inline filter rows** — no deep nav, keeps performance flow fast.
- **60px tap targets** minimum on every interactive element.
- **Scanlines** are a subtle 1.5%-alpha repeating gradient on the frame, below text z-index.
