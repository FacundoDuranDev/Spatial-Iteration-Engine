---
name: spatial-iteration-engine-design
description: Use this skill to generate well-branded interfaces and assets for Spatial Iteration Engine — a Python + C++ real-time ASCII video streaming engine — either for production or throwaway prototypes/mocks. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping in the product's terminal-native, monospace, Spanish-language voice.
user-invocable: true
---

Read the `README.md` file within this skill, and explore the other available files.

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. Link `colors_and_type.css` for tokens. Pull UI kit components from `ui_kits/` — the Jupyter control panel and the ASCII stream viewer are the two real product surfaces.

If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand.

If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

Key reminders when designing:
- Spanish copy. Short, technical, direct. No emoji. No exclamation marks.
- Monospace everywhere. Black terminal base. Phosphor green accent used sparingly for live state.
- Unicode glyphs (`▶ ■ ● ○`) for controls — not SVG, not emoji.
- Crisp borders, minimal shadows, no gradients. This is a terminal, not a SaaS marketing page.
