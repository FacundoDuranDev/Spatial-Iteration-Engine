# ascii_stream_engine

Motor modular para streaming ASCII en tiempo real.

## Objetivo
- Capturar video de camara
- Analizar (rostros/manos opcional)
- Aplicar filtros en vivo
- Render ASCII
- Enviar a VLC por UDP (ffmpeg)

## Requisitos
- Python 3.8+
- ffmpeg
- Paquetes: opencv-python, numpy, pillow, ipywidgets, ipython

Instalacion (ejemplo):
```
python -m pip install -r ascii_stream_engine/requirements.txt
```

Opcional (manos con MediaPipe):
```
python -m pip install mediapipe
```

## Ejemplo rapido (UDP + VLC)
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

VLC:
```
udp://@127.0.0.1:1234
```

## Filtros y analizadores
```python
from ascii_stream_engine import AnalyzerPipeline, FilterPipeline
from ascii_stream_engine.filters import BrightnessFilter, InvertFilter
from ascii_stream_engine.analyzers import FaceHaarAnalyzer

filters = FilterPipeline([BrightnessFilter(), InvertFilter()])
analyzers = AnalyzerPipeline([FaceHaarAnalyzer()])
```

## Tip: fuente monoespaciada (mejor alineado)
Si ves el ASCII pegado a la izquierda, usa una fuente monoespaciada:
```python
from ascii_stream_engine.renderer import AsciiRenderer

renderer = AsciiRenderer(font_path="/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
```

## Control en Jupyter
Si corres el notebook dentro de `ascii_stream_engine/examples`, agrega el path
del repo para que Python encuentre el paquete:
```python
import os
import sys

repo_root = os.path.abspath(os.path.join(os.getcwd(), "../.."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
```

```python
from ascii_stream_engine import build_control_panel

build_control_panel(engine)
```

Panel general (red, camara, filtros, ASCII/RAW):
```python
from ascii_stream_engine import build_general_control_panel

build_general_control_panel(engine)
```

Notebook general: `ascii_stream_engine/examples/ascii_stream_engine_general.ipynb`

## Modo RAW (sin ASCII)
Para enviar imagen sin ASCII, usa `render_mode="raw"`:
```python
config = EngineConfig(render_mode="raw", raw_width=640, raw_height=360)
```

## Notas
- Cambios en grid_w/grid_h/host/port requieren reiniciar el engine.
- Para broadcast en LAN:
  ```python
  config = EngineConfig(host="192.168.1.255", udp_broadcast=True)
  ```
