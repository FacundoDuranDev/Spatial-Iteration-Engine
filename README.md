# Spatial-Iteration-Engine

Motor para streaming ASCII en tiempo real. Este repo contiene dos paquetes:

- `ascii_stream_engine/`: motor modular (sources, filters, renderer, outputs).
- `ascii_stream/`: streamer compacto con CLI y control en vivo.

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
```
python -m ascii_stream.streamer --host 127.0.0.1 --port 1234
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
Para mas detalles, ver:
- `ascii_stream_engine/README.md`
- `ascii_stream/README.md`
