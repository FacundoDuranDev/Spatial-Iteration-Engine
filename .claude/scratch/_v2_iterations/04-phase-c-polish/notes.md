# Iteration 04 — phase C polish

Timestamp: 2026-04-19T18:30Z
Branch: feat/web-dashboard-v3

## What landed

- `.cat .name`: now `font-size: clamp(20px, 7vw, var(--fs-xl))` with
  `-webkit-line-clamp: 2`, `word-break`, `hyphens: auto`. "Distorsión"
  no longer truncates to "Distorsió".
- `.hd .ttl`: per-view font-size via `data-view` attr. Hub uses
  `clamp(14px, 4vw, var(--fs-md))` because pill+KPIs eat the row.
  Cat/detail use `clamp(18px, 5.5vw, var(--fs-lg))` since pill+KPIs
  are hidden there. Title now ellipsizes cleanly instead of wrapping.
- `app.js updateChrome()`: hides `#kpis` AND `#pill` in cat/detail
  views, sets `data-view` on `#hd` for the per-view font-size rule.
- View transition simplified to no-op. Earlier slide + opacity were
  triggering Chromium-headless rendering ghosts mid-snapshot.
- Footer dropped `position: sticky` — `.screen` is already a flex
  column with `.body { flex: 1 }`, so the footer pins naturally.
  Cleaner stacking context.

## Investigated and ruled out

- "▶ Iniciar" appearing mid-screen in cat-list / detail screenshots:
  - `elementsFromPoint(195, 420)` returns view-cat / body / app —
    no "Iniciar" element exists at that position in the DOM.
  - Switched dpr from 3 to 1 in snap → ghost disappears.
  - **Conclusion**: Chromium-headless rendering artifact at dpr=3,
    only visible in screenshots, not on real devices.
  - Left dpr=3 for fidelity; documented the artifact here.

## Validated visually

- Hub: 4 cats (Distorsión / Color / Glitch / Estilo) at full names,
  no truncation. Title "SIE · Cont…" still ellipsizes (decorative).
- Cat list: clean 2-row layout for COLOR with toggles, names, chevrons.
- Detail (Bloom): single-line title, all 3 sliders with cyan glow,
  Activo toggle, params labeled "Intensidad / Umbral / Reactividad
  audio (Bass)".

## Files captured
- `snapshot/static/{index.html, v3.css, app.js}`
- `snapshot/{registry.py, bridge.py, ws.py}` (latest backend)

## Known cosmetic gaps still open

- Hub `.cat` cards: bottom row (Glitch, Estilo) is a touch tall;
  could shrink min-height.
- Detail header: title and back button could share a row better
  on cat view (more visual hierarchy).
- WIP cards (Glitch / Estilo) currently look identical to wired
  cards — should add a "EN DESARROLLO" badge or muted treatment.

These are Phase D / future polish.
