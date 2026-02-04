# Overview

ascii_stream_engine es un motor modular para streaming ASCII en tiempo real.
Su objetivo es capturar frames de una fuente, aplicar analisis y filtros,
renderizar a ASCII (o RAW) y enviar el resultado a una salida como UDP.

Flujo principal:
1. Source captura el frame (camara u otra fuente).
2. Analyzer pipeline calcula metadata (rostros, manos, etc).
3. Filter pipeline transforma el frame.
4. Renderer genera imagen ASCII o RAW.
5. Output envia el frame (UDP, recorder, etc).

Componentes clave:
- domain: modelos puros (config, types).
- application: engine y pipelines.
- ports: contratos (interfaces).
- adapters: implementaciones concretas.
- presentation: paneles y notebooks.

Instalacion:
```
python -m pip install -r ascii_stream_engine/requirements.txt
```

Ejecutar un stream basico:
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
