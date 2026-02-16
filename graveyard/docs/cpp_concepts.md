# Conceptos del módulo C++ — Modificación de imagen

Documento de diseño: **qué hace** el código C++ en el pipeline. El C++ no orquesta; recibe buffers y **modifica la imagen** según parámetros. Python orquesta cuándo llamar y con qué datos.

## Rol del C++

- **Entrada:** Frame (imagen) + opcionalmente máscara o datos de control.
- **Salida:** Imagen modificada (mismo tamaño o definido por el backend).
- **Responsabilidad:** Operaciones que benefician de rendimiento en C++/GPU: deformación geométrica, composición, efectos por región. Sin lógica de negocio ni orquestación.

## Conceptos (qué puede hacer el C++)

### 1. Deformación geométrica (warp)

- **Qué hace:** Aplica una transformación geométrica a la imagen (warp, mesh deform).
- **Entradas:** Frame RGB; opcional: máscara (región a deformar), mapa de desplazamiento (displacement map) o parámetros (fuerza, centro).
- **Salida:** Frame con la región deformada (ej. efecto “espejo líquido”, bulge en zona de la persona).
- **Ejemplo de uso:** Máscara de persona → deformar solo esa región; resto de la imagen intacto.

### 2. Composición por capas (blend / mask)

- **Qué hace:** Combina dos imágenes usando una máscara (alpha blend, overlay).
- **Entradas:** Frame base, frame o capa secundaria, máscara (qué región mezclar).
- **Salida:** Un solo frame compuesto.
- **Ejemplo de uso:** Fondo + capa estilizada solo donde la máscara es 255; útil para “estilo solo en la persona”.

### 3. Efectos por región (opcional)

- **Qué hace:** Aplica un efecto visual (blur, colorización, distorsión) solo donde la máscara lo indica.
- **Entradas:** Frame, máscara, tipo de efecto y parámetros (radio de blur, intensidad, etc.).
- **Salida:** Frame con el efecto aplicado solo en la región enmascarada.
- **Ejemplo de uso:** Blur de fondo, color diferente en la silueta.

### 4. Salida final (buffer listo para enviar)

- **Qué hace:** Asegura el formato de salida (resolución, layout, color) del buffer que Python enviará al sink (pantalla, UDP, archivo). No cambia el contenido semántico; solo “empaqueta” la imagen ya modificada.
- **Entradas:** Frame ya procesado (por los pasos anteriores o por Python).
- **Salida:** Buffer en el formato acordado (ej. RGB C-contiguous, tamaño fijo).

---

## Contrato único para V1 (simplificado)

Para no sobrecargar la primera versión, el bridge puede exponer **una sola función** que “modifica la imagen”:

- **`render(frame, mask=None) -> frame_out`**
  - `frame`: imagen RGB (H, W, 3), uint8.
  - `mask`: opcional, (H, W), uint8; 255 = región activa (persona, zona a deformar/componer).
  - `frame_out`: imagen modificada, mismo shape que `frame`.

**Interpretación en C++ (a implementar):**

- Si `mask` es válida: puede aplicar **deformación** en la región de la máscara, o **composición** (p. ej. mezclar con una capa interna), o **efecto por región** (blur/color). La decisión concreta se implementa en C++ según el primer efecto que se quiera tener.
- Si `mask` es None o vacía: copiar frame a salida (passthrough) o aplicar efecto global suave.

Así Python solo orquesta: “aquí está el frame y la máscara de persona; devuélveme la imagen modificada”. El “cómo” (warp vs blend vs efecto) queda dentro del módulo C++.

---

## Dónde se usa en el pipeline

- **Como Filter (Python):** Un filtro que recibe frame + `analysis` (con máscara de segmentación), llama a `render(frame, mask)` y devuelve el frame modificado. El resto del pipeline (más filtros, renderer ASCII/raw, sink) sigue igual.
- **Como Renderer (Python):** Un renderer que recibe frame + analysis, llama a C++ para obtener la imagen modificada y la empaqueta en `RenderFrame` (para enviar por UDP, archivo, etc.) sin pasar por ASCII.

Ambos puntos ya están preparados en Python (adapters que llaman al bridge cuando está disponible). Ver `adapters/processors/filters/cpp_modifier.py` y `adapters/renderers/cpp_renderer.py`.

---

## Resumen para implementación C++

| Concepto              | Entrada           | Salida    | Notas                          |
|-----------------------|-------------------|-----------|--------------------------------|
| Deformación geométrica| frame, mask/params| frame     | Warp en región de la máscara   |
| Composición           | frame, layer, mask| frame     | Blend por máscara              |
| Efectos por región    | frame, mask, params | frame   | Blur, color, etc. en la máscara |
| Buffer de salida      | frame             | buffer    | Formato final para el sink     |

En V1 se puede implementar **solo uno** (p. ej. deformación o passthrough) y ampliar después. El contrato `render(frame, mask) -> frame` sigue igual.
