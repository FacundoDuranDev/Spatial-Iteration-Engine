# Gradio Remote — Control Surface

El celular abre directamente la URL de Gradio. **Solo panel de control**, sin preview de video (el streaming embebido era el bottleneck).

## Variantes

Tres direcciones visuales divergentes, ninguna reutiliza los kits anteriores:

| Variante | Dirección | Cuándo sirve |
|---|---|---|
| **A — Paper Console** | Papel/tinta, instrumentos analógicos dibujados | Funciones íntimas, daytime, contextos curatoriales |
| **B — Industrial Minimal** | Gris cemento, un solo acento eléctrico, tipografía geométrica | Rigs profesionales, tour en vivo, VJ sessions |
| **C — High-Contrast Stage** | Negro profundo, blanco tipográfico XL, hit targets enormes | Teatro/club en penumbra, performer sin anteojos |

## Pantallas (6 por variante)

1. **Home** — estado del pipeline + 6 categorías de filtros
2. **Filter list** — filtros de una categoría, con activar/reordenar
3. **Filter detail** — parámetros de un filtro concreto (TemporalScan como ejemplo: dial + stepper + metadata)
4. **Presets** — grid de presets con recall, save-as, tags
5. **Config** — input source, resolución, codec, métricas en vivo
6. **Stopped** — estado pausado, recuperación, historial reciente

## Componentes portables

Cada variante define la estética, pero los componentes comparten contrato HTML. Para portarlos a Gradio (`presentation/widgets/static/`) se copia el snippet + el `tokens.css` correspondiente.

- `FilterRow` — item con toggle, nombre, hit target
- `Slider` — valor + track + label + unidad
- `Stepper` — −/+ con valor central
- `Toggle` — on/off pill
- `AngleDial` — rotación 0–360° (TemporalScan)
- `XYPad` — dos ejes simultáneos (Depth of Field, Lens Flare)
- `ColorWheel` — shadow tint / highlight tint (Color Grading)
- `PresetCard` — tarjeta con color stripe + nombre + tags
- `MetricPill` — FPS / latencia / RTT
