# Extensiones sugeridas

## Nuevas fuentes (FrameSource)
- Video file (cv2.VideoCapture con path).
- Screen capture (mss o similar).
- RTSP/HTTP stream.

## Nuevos renderers (FrameRenderer)
- Renderer ASCII con color.
- Renderer que dibuje bounding boxes de analizadores.

## Nuevos outputs (OutputSink)
- MJPEG sobre HTTP.
- WebSocket para web client.
- Guardado a video file con ffmpeg.

## Nuevos filtros
- Blur/Sharpen dinamico.
- Deteccion de bordes configurable.
- LUTs para estilos.

## Nuevos analizadores
- Manos con mediapipe.
- Detector de movimiento simple.
- Contador de objetos basico.

## CLI y configuracion
- CLI con argparse para iniciar streams rapidos.
- Config en YAML/JSON con presets.
- Soporte de perfiles (low latency / quality).
