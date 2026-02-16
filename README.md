# Spatial-Iteration-Engine

Motor para streaming en tiempo real con arquitectura modular (ports & adapters). Incluye núcleo Python (`ascii_stream_engine`), módulos de percepción y estilo (stubs), y espacio para render C++ y modelos ONNX.

## Estructura

- `python/` — IA y orquestación: `ascii_stream_engine` (núcleo), `perception/` (detección, pose, segmentación), `style/` (Style Encoder, Stylizer).
- `cpp/` — Render y geometría en tiempo real (stubs con pybind11).
- `onnx_models/` — Modelos optimizados (ver `onnx_models/README.md`).
- `data/` — Obras, máscaras, vectores (ver `data/README.md`).
- `docs/` — Arquitectura, benchmarks, integración Python–C++.

## Requisitos

- Python 3.8+
- ffmpeg
- Paquetes: opencv-python, numpy, pillow, ipywidgets, ipython, watchdog, pyyaml (ver `python/requirements.txt`)
- Opcional: mediapipe (detección de manos)
- Para compilar los módulos C++ (filtros, render bridge): CMake y compilador C++; ver abajo.

## Instalación

Desde la raíz del repo, instalar dependencias Python desde `python/`:

```bash
python -m pip install -r python/requirements.txt
```

Para importar el paquete, ejecutar con `PYTHONPATH` apuntando a `python/`:

```bash
export PYTHONPATH=python  # Linux/macOS
# o: set PYTHONPATH=python  # Windows
```

O instalar en modo editable desde `python/`:

```bash
cd python && pip install -e .  # si existe setup.py/pyproject.toml
# Si no, usar: PYTHONPATH=/path/to/repo/python python ...
```

### Compilar módulos C++ (filters_cpp, render_bridge)

Si no tienes CMake ni compilador instalados, la opción más simple es un **env de Conda** (todo dentro del env):

```bash
conda env create -f environment.yml
conda activate spatial-iteration-engine
pip install -r python/requirements.txt
./cpp/build.sh
```

Con **venv**: `pip install -r requirements-build.txt` (instala CMake) y en el sistema instala `build-essential` (Linux) o las Command Line Tools (macOS). Luego `./cpp/build.sh`. Detalles en `cpp/README.md`.

## Ejemplo rápido (UDP + VLC)

```python
from ascii_stream_engine import (
    EngineConfig,
    StreamEngine,
    OpenCVCameraSource,
    AsciiRenderer,
    FfmpegUdpOutput,
)

config = EngineConfig(host="127.0.0.1", port=1234)
engine = StreamEngine(
    source=OpenCVCameraSource(0),
    renderer=AsciiRenderer(),
    sink=FfmpegUdpOutput(),
    config=config,
)
engine.start()
```

VLC: `udp://@127.0.0.1:1234`

## Notebooks y ejemplos

Los ejemplos están en `python/ascii_stream_engine/examples/`. Añade el path para que Python encuentre el paquete:

```python
import sys, os
repo_root = os.path.abspath(os.path.join(os.getcwd(), "../.."))
python_root = os.path.join(repo_root, "python")
if python_root not in sys.path:
    sys.path.insert(0, python_root)
```

## Documentación

- `docs/README.md` — Guía general, arquitectura, tecnologías.
- `docs/integration_v1.md` — Contrato de datos Python ↔ C++.
- `docs/benchmarks.md` — Checklist de benchmarks y métricas.
- `docs/neural_architecture.md` — Diseño neural (Style Encoder, Stylizer, Intel UHD 620).
