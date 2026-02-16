# Roadmap de filtros C++ (filters_cpp)

Integración de filtros de imagen en C++ con el FilterPipeline de Python vía pybind11 y buffers NumPy C-contiguous.

## Interfaz C++

```cpp
namespace filters {
class Filter {
 public:
  virtual void apply(std::uint8_t* frame, int width, int height, int channels) = 0;
};
}
```

- Buffer: C-contiguous, `uint8`, layout `(height, width, channels)` (típicamente 3 = BGR).
- Modificación **in-place** para evitar copias.

## Fases

### Fase 1 – Filtros básicos (implementados)

| Filtro | Clase C++ | Binding Python | Adapter FilterPipeline |
|--------|-----------|----------------|------------------------|
| Brightness / Contraste | `BrightnessContrastFilter` | `apply_brightness_contrast(frame, delta, factor)` | `CppBrightnessContrastFilter` |
| Invert / Negative | `InvertFilter` | `apply_invert(frame)` | `CppInvertFilter` |
| Grayscale / Luma | `GrayscaleFilter` | `apply_grayscale(frame)` | `CppGrayscaleFilter` |
| Channel Swap | `ChannelSwapFilter` | `apply_channel_swap(frame, dst_b, dst_g, dst_r)` | `CppChannelSwapFilter` |

### Fase 2 – Filtros intermedios (stubs)

| Filtro | Binding | Estado |
|--------|---------|--------|
| Threshold / Binary | `apply_threshold(frame, threshold)` | Stub |
| Edge (Sobel/Laplacian) | `apply_edge(frame)` | Stub |
| Blur / Gaussian | `apply_blur(frame, kernel_size)` | Stub |
| Posterize / Quantization | `apply_posterize(frame, levels)` | Stub |
| Sharpen / Unsharp | `apply_sharpen(frame, strength)` | Stub |

### Fase 3 – Avanzados (opcional)

- Brightness modulator / oscillator (patrón cíclico).
- Warp geométrico simple (rotación, escala).
- Pipeline de filtros dentro de C++ (encadenar varios filtros).

## Uso desde Python

Añadir al `FilterPipeline` igual que cualquier otro filtro:

```python
from ascii_stream_engine.application.pipeline import FilterPipeline
from ascii_stream_engine.adapters.processors.filters import (
    CppBrightnessContrastFilter,
    CppInvertFilter,
    CppGrayscaleFilter,
    CppChannelSwapFilter,
)

filters = FilterPipeline([
    CppBrightnessContrastFilter(),  # usa config.brightness y config.contrast
    CppInvertFilter(),
    CppGrayscaleFilter(),
    CppChannelSwapFilter(dst_for_b=2, dst_for_g=1, dst_for_r=0),  # BGR -> RGB
])
```

Si el módulo `filters_cpp` no está compilado o no está en `PYTHONPATH`, cada adapter devuelve el frame sin modificar (fallback seguro).

## Build

Ver `cpp/README.md` para compilar los módulos C++.
