# Módulos C++ (filters_cpp, render_bridge)

## Cómo tener compilador y CMake

El proyecto es Python pero los módulos C++ necesitan **CMake** y un **compilador C++** (g++, clang++). Tienes dos formas de tenerlos:

### Opción A – Entorno Conda (recomendado si no tienes nada instalado)

Todo (Python + CMake + compilador) queda dentro del env, sin tocar el sistema:

```bash
# Desde la raíz del repo
conda env create -f environment.yml
conda activate spatial-iteration-engine
pip install -r python/requirements.txt
./cpp/build.sh
```

### Opción B – Venv de Python + sistema

1. **CMake en el venv** (solo el binario, no el compilador):

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # en Windows: .venv\Scripts\activate
   pip install -r requirements-build.txt
   ```

2. **Compilador C++ en el sistema** (una sola vez):

   - **Debian/Ubuntu:** `sudo apt install build-essential`
   - **Fedora:** `sudo dnf install @development-tools`
   - **macOS:** `xcode-select --install` o Xcode / Command Line Tools

3. **Compilar:**

   ```bash
   ./cpp/build.sh
   ```

## Build (una vez que tienes cmake y compilador)

```bash
cd cpp
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build .
```

O desde la raíz: `./cpp/build.sh`

Los módulos se generan en `cpp/build/`:
- `filters_cpp.cpython-3XX-...so`
- `render_bridge.cpython-3XX-...so`

Para usarlos desde Python:

```bash
export PYTHONPATH="/path/to/Spatial-Iteration-Engine/cpp/build:$PYTHONPATH"
```

## filters_cpp — Filtros de imagen

Interfaz: buffer NumPy C-contiguous, uint8, shape `(height, width, 3)` (BGR). Todas las funciones modifican el array **in-place**.

### Fase 1 (implementados)

| Función | Descripción |
|--------|-------------|
| `apply_brightness_contrast(frame, brightness_delta=0, contrast_factor=1.0)` | Brillo y contraste lineal |
| `apply_invert(frame)` | Negative: pixel = 255 - pixel |
| `apply_grayscale(frame)` | Luma; salida sigue 3 canales |
| `apply_channel_swap(frame, dst_for_b=2, dst_for_g=1, dst_for_r=0)` | Permutación BGR; (2,1,0) = BGR→RGB |

### Fase 2 (stubs, interfaz lista)

| Función | Parámetros | Estado |
|--------|------------|--------|
| `apply_threshold(frame, threshold=127)` | Umbral binario | Stub |
| `apply_edge(frame)` | Bordes (Sobel/Laplacian) | Stub |
| `apply_blur(frame, kernel_size=5)` | Gaussian blur | Stub |
| `apply_posterize(frame, levels=4)` | Cuantización color | Stub |
| `apply_sharpen(frame, strength=1.0)` | Sharpen / unsharp | Stub |

## render_bridge

Stub para render deformado (frame + máscara → frame modificado). Ver `docs/integration_v1.md` y `docs/cpp_concepts.md`.
