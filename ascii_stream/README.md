# ASCII stream a VLC (tiempo real)

Este modulo genera un stream ASCII desde camara y lo envia por UDP para verlo
en VLC. Incluye un modo CLI y control en vivo desde Jupyter.

## Requisitos
- Python 3.8+
- ffmpeg
- Paquetes: opencv-python, pillow, numpy, ipywidgets (para notebook)

Instalacion (ejemplo):
```
python -m pip install opencv-python pillow numpy ipywidgets
```

## Ejecutar local (misma maquina)
```
python -m ascii_stream.streamer --host 127.0.0.1 --port 1234
```

VLC:
```
udp://@127.0.0.1:1234
```

## Broadcast LAN (cualquiera en la red)
```
python -m ascii_stream.streamer --host 255.255.255.255 --port 1234
```

VLC en cualquier equipo:
```
udp://@0.0.0.0:1234
```

## Multicast (alternativa)
```
python -m ascii_stream.streamer --host 239.0.0.1 --port 1234
```

VLC:
```
udp://@239.0.0.1:1234
```

## Control en vivo desde Jupyter
Ejemplo minimo:
```python
from ascii_stream import AsciiStreamer

streamer = AsciiStreamer()
streamer.start()

# Ajustes en vivo
streamer.update_config(contrast=1.6, brightness=10, invert=True)

# Detener
streamer.stop()
```

Ejemplo con sliders (ipywidgets):
```python
import ipywidgets as widgets
from ascii_stream import AsciiStreamer

streamer = AsciiStreamer()
streamer.start()

contrast = widgets.FloatSlider(value=1.2, min=0.5, max=3.0, step=0.1)
brightness = widgets.IntSlider(value=0, min=-50, max=50, step=1)
invert = widgets.Checkbox(value=False)

def on_change(_):
    streamer.update_config(
        contrast=contrast.value,
        brightness=brightness.value,
        invert=invert.value,
    )

for w in [contrast, brightness, invert]:
    w.observe(on_change, names="value")

display(contrast, brightness, invert)
```

## Filtros y procesamiento (extensible)
La gestion de imagen vive en `AsciiImageProcessor` y acepta filtros encadenables.

```python
import cv2
from ascii_stream import AsciiImageProcessor, AsciiStreamer, FrameFilter


class EdgeFilter:
    def apply(self, frame, config):
        gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.Canny(gray, 80, 160)


processor = AsciiImageProcessor()
processor.add_filter(EdgeFilter())

streamer = AsciiStreamer(image_processor=processor)
streamer.start()
```

La lista de filtros es mutable en el gestor principal:
```python
from ascii_stream import AsciiStreamer

streamer = AsciiStreamer()
streamer.start()

# Agregar o quitar filtros en caliente
streamer.filters.append(EdgeFilter())
streamer.filters.pop()
```

Si queres sincronizacion, usa el pipeline con lock:
```python
with streamer.pipeline.locked() as filters:
    filters.append(EdgeFilter())
```

## Analizadores (rostros y manos)
El streamer tambien expone una lista mutable de analizadores para obtener datos
en tiempo real (rostros, manos, etc.):

```python
from ascii_stream import AsciiStreamer, FaceHaarAnalyzer, MediaPipeHandAnalyzer

streamer = AsciiStreamer()
streamer.start()

# Deteccion de rostros (OpenCV)
streamer.analyzers.append(FaceHaarAnalyzer())

# Manos con MediaPipe (requiere install opcional)
streamer.analyzers.append(MediaPipeHandAnalyzer())

print(streamer.get_last_analysis())
```

Para manos:
```
python -m pip install mediapipe
```

## Arquitectura modular (StreamEngine)
Si queres extender el proceso completo, podes usar el motor modular:

```python
from ascii_stream import (
    StreamEngine,
    OpenCVCameraSource,
    AsciiRenderer,
    UdpFfmpegSink,
    AnalyzerPipeline,
    FaceHaarAnalyzer,
)

engine = StreamEngine(
    source=OpenCVCameraSource(0),
    renderer=AsciiRenderer(),
    sink=UdpFfmpegSink(),
    analyzers=AnalyzerPipeline([FaceHaarAnalyzer()]),
)
engine.start()
```

Nota: cambios en grid_w/grid_h/host/port/fps requieren reiniciar el stream.
