# Arquitectura hexagonal (Ports & Adapters)

Objetivo:
- Separar el core de negocio de dependencias externas.
- Facilitar pruebas y reemplazo de tecnologia.
- Mantener limites claros entre capas.

Capas:
1. domain: modelos puros (EngineConfig, RenderFrame).
2. application: casos de uso (StreamEngine, pipelines).
3. ports: contratos que necesita la aplicacion (FrameSource, FrameRenderer, OutputSink).
4. adapters: implementaciones concretas (OpenCVCameraSource, AsciiRenderer, FfmpegUdpOutput).
5. presentation: UI y notebooks.

Regla de dependencias:
- domain no depende de nadie.
- application depende de domain y ports.
- ports depende de domain.
- adapters depende de ports y domain.
- presentation depende de application y adapters (o solo public API).

Ventajas:
- Cambios tecnologicos localizados en adapters.
- Tests del core sin dependencias externas.
- Mayor mantenibilidad y claridad.

Ejemplo de reemplazo:
- Cambiar la fuente de camara a video file implica crear un adapter
  que implemente FrameSource sin tocar el engine.

Empaquetado recomendado:
- Exponer en ascii_stream_engine/__init__.py los elementos de uso publico.
- Mantener paths internos para desarrollo y tests.
