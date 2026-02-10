# Runtime Engine (Python + C++ + GPU)

Este directorio define la evolución del motor hacia un runtime audiovisual
en tiempo real con separación estricta de responsabilidades:

- `python/`: control-plane (topología, parámetros, estado, feedback, IA futura)
- `core/`: runtime de frame en C++ (scheduler, buffers, ejecución de nodos)
- `gpu/`: shaders/kernels (warp, blur, feedback, mixing)
- `io/`: ingest/egress live con FFmpeg
- `bindings/`: puente Python <-> C++

Regla principal: **Python no procesa píxeles en la ruta runtime objetivo**.
