# Iconography

## Rules

1. **Prefer Unicode glyphs.** The product already uses `▶`, `■`, `●`, `○`, `·`, `→`, `←` as its icon vocabulary. These render in any monospace font and align perfectly in terminal UIs.
2. **No emoji.** Ever. Zero emoji appear in the codebase.
3. **No custom SVG icons.** Don't hand-draw. If you genuinely need a non-Unicode pictogram, use Lucide from CDN.
4. **Lucide** (stroke 1.5px) is the fallback system when a Unicode char doesn't exist:
   `https://unpkg.com/lucide@latest`
5. **Icon color follows text color.** No colored icons unless the glyph IS the status (e.g. a phosphor-green `●` = live).

## Glyph reference (copy-paste these)

| Meaning | Glyph | Where used |
|---|---|---|
| Play / Start | `▶` | `▶ Iniciar` button |
| Stop | `■` | `■ Detener` button |
| Live / active | `●` | Status dot, phosphor green |
| Idle / inactive | `○` | Status dot, fg-2 |
| List bullet | `·` | Inline separators: `Local · Broadcast · Multicast` |
| Arrow flow | `→` | `Red aplicada: Local → 127.0.0.1:1234` |
| Reverse arrow | `←` | Inbound data |
| Pipe / branch | `│ ├ └ ─` | ASCII architecture diagrams |
| ASCII ramp | `.` `:` `-` `=` `+` `*` `#` `%` `@` | The renderer's own charset; never use as decoration for content that isn't ASCII art |

## Flagged substitution

- Lucide is NOT in the Spatial Iteration Engine codebase. It's a CDN addition for the design system's UI kits only (e.g. a network tower icon for the Red tab header). If the user prefers Feather, Tabler, or a custom set, swap here and update UI kit JSX.
