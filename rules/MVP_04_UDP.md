# MVP 04 — Network Output

Objetivo: Demostrar que el mismo pipeline puede emitirse por red.

Pipeline:
Camera
→ FilterPipeline (0 o 1 filtro)
→ Renderer
→ FfmpegUdpOutput

Configuración:
host=127.0.0.1
port=1234

Cliente:
VLC → udp://@127.0.0.1:1234

Criterio de éxito:
- Se ve el stream en VLC por 30+ segundos sin cortes

Este MVP convierte el motor en un sistema distribuido.
