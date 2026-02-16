# MVP 01 — Live Preview Canonical Path

Objetivo: Tener un único flujo vivo y visible que represente al sistema.

Pipeline:
Camera
→ FilterPipeline (0 o 1 filtro Python)
→ PassthroughRenderer
→ PreviewSink (ventana)

Script canónico:
python/ascii_stream_engine/examples/stream_camera_preview_only.py

Comando:
PYTHONPATH=python python python/ascii_stream_engine/examples/stream_camera_preview_only.py

Criterio de éxito:
- Se abre una ventana
- La cámara se ve en tiempo real
- Si agrego un filtro (Invert, Brightness, etc.), el efecto se ve

Este MVP es el “golden path” del proyecto.
Si esto no funciona, el sistema está roto.
