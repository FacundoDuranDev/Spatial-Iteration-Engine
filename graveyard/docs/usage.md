# Casos de uso

## 1) Stream ASCII por UDP (local)
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

## 2) Broadcast en LAN
```python
config = EngineConfig(host="255.255.255.255", port=1234, udp_broadcast=True)
```
VLC en otros equipos: `udp://@0.0.0.0:1234`

## 3) Multicast
```python
config = EngineConfig(host="239.0.0.1", port=1234)
```
VLC: `udp://@239.0.0.1:1234`

## 4) Modo RAW (sin ASCII)
```python
config = EngineConfig(render_mode="raw", raw_width=640, raw_height=360)
```

## 5) Filtros en cadena
```python
from ascii_stream_engine import FilterPipeline
from ascii_stream_engine.adapters.processors import BrightnessFilter, InvertFilter

filters = FilterPipeline([BrightnessFilter(), InvertFilter()])
engine = StreamEngine(..., filters=filters)
```

## 6) Analizadores (ej: rostros)
```python
from ascii_stream_engine import AnalyzerPipeline
from ascii_stream_engine.adapters.processors import FaceHaarAnalyzer

analyzers = AnalyzerPipeline([FaceHaarAnalyzer()])
engine = StreamEngine(..., analyzers=analyzers)
```

## 7) Panel de control en Jupyter
```python
from ascii_stream_engine import build_general_control_panel
build_general_control_panel(engine)
```

## 8) Recorder ASCII a archivo
```python
from ascii_stream_engine.adapters.outputs import AsciiFrameRecorder

recorder = AsciiFrameRecorder(path="frames.txt", flush_every=10)
engine = StreamEngine(..., sink=recorder)
```
