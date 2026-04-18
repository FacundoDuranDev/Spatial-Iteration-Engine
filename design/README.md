# Spatial Iteration Engine — Design System

A design system for **Diseño Spatial Iteration Engine** (`FacundoDuranDev/Spatial-Iteration-Engine`) — a Python + C++ engine for real-time ASCII video streaming, perception, and style transfer. The product is engineering-first: its "UI" is a Jupyter notebook control panel and a VLC window receiving a UDP stream of ASCII art.

This design system codifies that terminal-native, monospace-first, hacker-engineer aesthetic so agents can produce on-brand slides, documentation, control panels, and throwaway mocks.

## Sources

- **Codebase (public):** https://github.com/FacundoDuranDev/Spatial-Iteration-Engine
  - `README.md` — top-level product blurb (Spanish)
  - `docs/mvp_ideas.md` — product voice and step-by-step MVP reasoning
  - `python/ascii_stream_engine/README.md` — module-level docs
  - `python/ascii_stream_engine/presentation/notebook_api.py` — the ONE real UI surface (ipywidgets tabbed control panel)
  - `python/ascii_stream_engine/adapters/renderers/ascii.py` — ASCII renderer, charset defaults, render contract
  - `CHANGELOG.md`, `GITFLOW.md` — workflow tone
- **Design context inputs given by user:** GitHub repo only. No Figma, no deck, no brand guide. Visual identity is inferred from code, terminal output, and documentation tone.

## Product context

Spatial Iteration Engine is a modular real-time streaming engine with **Ports & Adapters (hexagonal)** architecture. The pipeline runs:

```
Source → Perception → Semantic/Transform → Filters → Renderer → Output
```

- **Source:** webcam via OpenCV
- **Perception (opt):** face / hands / pose landmarks (MediaPipe stubs + ONNX)
- **Filters:** Python + C++ (pybind11) — blur, edge, invert, brightness/contrast, posterize, threshold, sharpen, channel swap
- **Renderer:** `AsciiRenderer` (grid of chars), `PassthroughRenderer` (raw), `LandmarksOverlayRenderer`
- **Output:** `FfmpegUdpOutput` → VLC at `udp://@127.0.0.1:1234`, `NotebookPreviewSink` → ipywidgets image

There is **no marketing website, no mobile app, no CLI TUI**. The two real product surfaces are:

1. **Jupyter control panel** (`build_general_control_panel`) — tabs for Red / Motor / Filtros / Vista / IA
2. **The ASCII stream itself** — black background, monospace white/green chars, received in VLC

## CONTENT FUNDAMENTALS

**Language: Spanish (Argentine/neutral).** All product copy is in Spanish. Keep Spanish when writing app-shell copy; English is fine for developer-facing design docs.

**Voice:** technical, direct, second-person informal (`tú`/`usa`/`pulsa`). Terse but helpful. Reads like a README written by someone who ships:

- `"Listo. Usa las pestañas y pulsa Start en Motor."`
- `"Sin filtros: imagen normal."`
- `"Motor en marcha. El preview se actualiza en la celda de arriba."`
- `"Todo en 0: los stubs C++ no devuelven puntos. Con modelos reales verás datos aquí."`

**Casing:** `Sentence case` for labels, `Title Case` only for proper nouns (`MVP_02`, `C++`, `VLC`). Never screaming all-caps for prose. UPPERCASE is reserved for monospace `.t-label` micro-labels.

**Tone rules:**

- **No emoji.** The codebase uses `▶`, `■`, `●`, `○` as controls — glyphs, not emoji.
- **No marketing puff.** `"Motor modular para streaming ASCII en tiempo real"` is the full product tagline. No "revolutionary," "next-gen," etc.
- **No exclamation points.** Observed zero in the codebase copy.
- **Technical terms stay in English:** `buffer`, `grid`, `FPS`, `charset`, `bitrate`, `host`, `multicast`, `broadcast`, `pipeline`. Don't translate.
- **Short status strings.** Format: `"{subject}: {state}."` (`"Red aplicada: Local → 127.0.0.1:1234"`)
- **Spanish engineering slang is OK:** `"Aviso"`, `"Aplicar"`, `"Iniciar"`, `"Detener"`, `"Motor"`, `"Vista"`.

**Examples from the source (keep as a reference pile):**

| Context | String |
|---|---|
| Idle status | `Listo. Usa las pestañas y pulsa Start en Motor.` |
| Success | `Red aplicada: Local → 127.0.0.1:1234` |
| Warning | `Sin módulo de percepción. Arranca Jupyter con PYTHONPATH=python:cpp/build` |
| Empty state | `Engine no en marcha. Inicia el engine y pulsa Actualizar para ver latencia.` |
| Button primary | `▶ Iniciar` / `■ Detener` |
| Button secondary | `Aplicar red` / `Aplicar ajustes` / `Actualizar` |
| Tab titles | `Red · Motor · Filtros · Vista · IA` |
| Section label | `<b>Servidor en red</b>` |
| Helper text | `<small>Local = 127.0.0.1 · Broadcast/Multicast para UDP.</small>` |

## VISUAL FOUNDATIONS

**Palette.** Black terminal base (`#0a0c0d`), warm paper off-white for foreground (`#f2efe8`). Four accents, each with a role:

- **Phosphor green `#9dff4e`** — primary accent, live/OK state, the ASCII renderer's default foreground. Use sparingly; it SHOULDS mean "live signal."
- **CRT amber `#ffb454`** — processing / warning / filter active.
- **Signal cyan `#5ecfff`** — network, UDP, host, port.
- **Perception magenta `#ff6ac1`** — IA, landmarks, style transfer.

No gradients in product UI. No bluish-purple. No pastels. The only "gradient" permissible is the ASCII charset ramp itself (`" .:-=+*#%@"`).

**Typography.** Monospace-first — everything in the control panel, all headings, all code, all labels. `JetBrains Mono` is the primary face; `DejaVu Sans Mono` is the original render font (see `ascii.py`). `Inter` is the narrow-use fallback for body copy in long docs only. **Flagged substitution:** no brand TTF exists; fonts loaded from Google Fonts CDN. Ask user for a `.ttf` if they want something else.

**Spacing.** 4px grid (`--sp-1` = 4, up to `--sp-8` = 64). UI density is HIGH — closer to a terminal or IDE than a marketing page.

**Backgrounds.** Flat black `#0a0c0d`. No images, no full-bleed photos, no textures. When a background motif is needed, use the ASCII charset itself as a repeating pattern — render dim (`#3a3731`) behind content. No hand-drawn illustrations.

**Animation.** Minimal. Fades at 120–180ms with `ease-out`. No bounces, no springs, no micro-interactions with personality. The cursor blink (step-end, 1.06s) is the only "idle" animation that matches the brand. A subtle phosphor flicker is acceptable on live data.

**Hover states.** Opacity shift to 0.8, or swap `--bg-1` → `--bg-2`. On accent buttons, swap to `--accent-dim`. No lifts, no scale changes.

**Press states.** Darker fill (`--bg-3`). No shrink/scale — terminals don't squish.

**Borders.** 1px hairline (`--bg-3`) is default. 1px dashed is acceptable for drop zones and "pending" content. Accent borders only for focused inputs and active filter chips.

**Shadows.** Avoid. A 0 1px 0 hairline under cards at most. For the rare case of elevation (e.g. a floating menu), use `0 4px 12px rgba(0,0,0,0.4)`. One exception: `--shadow-glow` — a dim phosphor halo around "live" indicators.

**Transparency & blur.** Mostly avoid. `--accent-soft` (12% opacity tint) is used as a subtle background on active states. No frosted glass / backdrop-filter.

**Corner radii.** Crisp. `--radius-1` = 2px default. `--radius-2` = 4px for cards. `0` is totally acceptable. Pill radius only for status dots.

**Cards.** `background: var(--bg-1)`, `border: 1px solid var(--bg-3)`, `radius: 4px`, no shadow. Section-titled cards use a `.t-label` uppercase header with `--tracking-widest`.

**Imagery.** Warm-to-neutral. When real imagery must appear (e.g. showing a video frame), keep it B&W or low-saturation. Raw frames in the actual product are either ASCII (pure black & white type) or the webcam feed (as-shot).

**Layout rules.** Fixed widths for control panels (matches ipywidgets' natural behavior). Generous gutters between tabs. Left-aligned text almost always. Center-align only for hero ASCII banners.

## ICONOGRAPHY

See `ICONOGRAPHY.md`. TL;DR: the codebase uses **Unicode glyphs** (`▶ ■ ● ○ · → ←`) not SVG icons, not an icon font. Lucide is loaded from CDN as a supplement for UI chrome where a Unicode char doesn't exist. Never draw custom SVGs; never use emoji.

## Index

| Path | What it is |
|---|---|
| `README.md` | This file — product context, voice, visual foundations |
| `colors_and_type.css` | CSS tokens (colors, type, spacing, radii, shadows, motion) |
| `ICONOGRAPHY.md` | Iconography rules — Unicode glyphs, no emoji |
| `SKILL.md` | Claude Skill manifest (cross-compatible with Agent Skills) |
| `assets/logo-ascii.txt` | Inferred ASCII wordmark |
| `preview/` | 14 design system specimen cards (colors, type, spacing, components, brand) |
| `ui_kits/jupyter_control_panel/` | Recreation of the ipywidgets tabbed panel (the control surface) |
| `ui_kits/ascii_stream_viewer/` | Recreation of the VLC stream + ASCII renderer output |
| `fonts/` | Font files (currently CDN-loaded; flagged substitution) |

## Caveats

- No brand fonts shipped — using JetBrains Mono + Inter via CDN. If the team has a preferred monospace, drop it into `fonts/` and update `@font-face`.
- No logo was provided. The ASCII wordmark in `assets/logo-ascii.txt` is an inferred mark — swap it if there's an official one.
- No Figma / design doc was attached — everything below is inferred from the codebase, code comments, and the user-facing strings in `notebook_api.py`.
