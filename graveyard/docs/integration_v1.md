# Integración Python ↔ C++ (V1)

Contrato de datos entre el pipeline Python (orquestación, IA) y el módulo C++ (render deformado, geometría).

## Objetivo

- Python orquesta captura, análisis, filtros y estilo; opcionalmente delega el render final a C++.
- C++ recibe buffers de frame (y opcionalmente máscara/geometría) y devuelve buffer de salida (mismo tamaño o definido).
- Interfaz vía pybind11 con buffers NumPy para evitar copias innecesarias.

## Formato de buffers

- **Frame de entrada/salida:** `numpy.ndarray` C-contiguous, dtype `uint8` (RGB o BGR, convención fija en el contrato), shape `(height, width, 3)`.
- **Máscara (opcional):** `numpy.ndarray` C-contiguous, dtype `uint8`, shape `(height, width)` (0 = fondo, 255 = persona/región activa).
- **Geometría (futuro):** structs con `width`, `height`, `stride`; en C++ recibir puntero + dimensiones para evitar ownership ambiguo.

## Reglas de memoria

- **Propiedad:** Python es dueño de los arrays; C++ recibe puntero de solo lectura (entrada) o escribe en buffer proporcionado por Python (salida).
- **Lifetime:** No guardar referencias a buffers NumPy en C++ más allá de la duración de la llamada; no almacenar punteros cuando el GIL se suelta.
- **Salida:** Preferir que Python preasigne el array de salida y lo pase a C++ para escribir (in-place), o que C++ devuelva un nuevo array creado con pybind11 (por ejemplo `py::array_t<uint8_t>`), documentando quién libera.

## API stub del bridge (pybind11)

- `send_frame(frame: np.ndarray) -> None` — Envía frame al render C++ (stub: no-op o copia a buffer interno).
- `get_output_shape() -> (width, height)` — Devuelve tamaño de salida (stub: mismo que entrada).
- `render(frame: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray` — Render deformado; entrada y salida C-contiguous; stub: devuelve copia del frame.

## Ejemplo de uso desde Python (cuando exista el módulo)

```python
# try:
#     from spatial_render import render_bridge
# except ImportError:
#     render_bridge = None

# if render_bridge:
#     out = render_bridge.render(frame, person_mask)
# else:
#     out = frame
```

## Uso desde Python (orquestación)

- **Como filtro:** `CppImageModifierFilter` en `adapters/processors/filters/cpp_modifier.py`. Se añade al `FilterPipeline`; recibe frame y `analysis`, extrae `silhouette_segmentation.person_mask` y llama a `render_bridge.render(frame, mask)`.
- **Como renderer:** `CppDeformedRenderer` en `adapters/renderers/cpp_renderer.py`. Implementa `FrameRenderer`: recibe frame y analysis, llama al bridge, convierte el resultado a `RenderFrame` (PIL Image). Si el bridge no está disponible, hace passthrough del frame.

En ambos casos, si el módulo `render_bridge` no está instalado, el comportamiento es seguro (frame sin modificar o imagen de passthrough).

## Conceptos del C++ (qué hace el código)

Ver [cpp_concepts.md](cpp_concepts.md): deformación geométrica, composición por máscara, efectos por región. El contrato actual es único: `render(frame, mask) -> frame`.

## Compilación C++

- CMake + pybind11; construir extensión con `pip install -e .` desde `cpp/` o `python/` según cómo se empaquete.
- Ver `cpp/CMakeLists.txt` y `cpp/src/bridge/pybind_bridge.cpp` para stubs.
