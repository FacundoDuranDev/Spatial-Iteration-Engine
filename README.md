# Spatial-Iteration-Engine

Motor para streaming ASCII en tiempo real. Este repo contiene el paquete
`ascii_stream_engine/`, con una arquitectura modular (ports & adapters).

## Requisitos
- Python 3.8+
- ffmpeg
- Paquetes: opencv-python, numpy, pillow, ipywidgets, ipython
- Opcional: mediapipe (deteccion de manos)

## Instalacion
```
python -m pip install -r ascii_stream_engine/requirements.txt
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

## Ejemplo con el motor modular
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

## Notebooks
Los ejemplos viven en `ascii_stream_engine/examples/`.
Para mas detalles, ver `ascii_stream_engine/README.md`.
