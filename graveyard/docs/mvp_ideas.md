# Ideas de MVP — Recuperar el control del proceso

Objetivo: tener algo **mínimo, estable y bajo tu control** para iterar sin depender de toda la arquitectura a la vez.

---

## Estado actual (resumen)

| Qué | Estado |
|-----|--------|
| **Pipeline conceptual** | 6 capas: Source → Perception → Semantic/Transform → Filters → Renderer → Output |
| **Lo que ya corre** | `stream_camera_preview_only.py`: cámara → PassthroughRenderer → PreviewSink (ventana), sin filtros |
| **Scripts de entrada** | `run_preview.sh`, `run_basic_stream.sh`, `run_preview_raw.sh` (usan `PYTHONPATH=python:cpp/build`) |
| **C++** | Opcional: filtros y render bridge; si no compilas, el motor funciona en modo Python (Passthrough/ASCII) |
| **Perception / Style** | Stubs en `python/perception/` y `python/style/`; no obligatorios para un MVP |

---

## MVP 1: “Un solo camino que funcione” (recomendado para recuperar control)

**Objetivo:** Un único flujo que puedas ejecutar de punta a punta y modificar sin tocar el resto.

- **Fuente:** cámara (OpenCVCameraSource).
- **Procesamiento:** ningún analizador; FilterPipeline con **0 o 1 filtro** (p. ej. BrightnessFilter o InvertFilter).
- **Render:** PassthroughRenderer (o AsciiRenderer si quieres ver ASCII).
- **Salida:** PreviewSink (ventana) **o** FfmpegUdpOutput (VLC: `udp://@127.0.0.1:1234`).

**Criterio de éxito:**  
`PYTHONPATH=python python python/ascii_stream_engine/examples/stream_camera_preview_only.py` abre la ventana; al añadir un filtro al `FilterPipeline`, ves el cambio en pantalla.

**Control que ganas:**  
Un solo script (o dos: preview y UDP) que representan “el camino feliz”. Cualquier cambio de arquitectura lo validas contra ese camino.

---

## MVP 2: “Preview + un filtro C++”

**Objetivo:** Mismo flujo que MVP 1, pero con **un** filtro implementado en C++ (p. ej. brillo/contraste o invert) en el FilterPipeline.

- Partes: cámara → FilterPipeline (1 filtro C++) → PassthroughRenderer → PreviewSink.
- Requiere: `./cpp/build.sh` y `PYTHONPATH=python:cpp/build`.
- Ejemplo de referencia: `stream_with_preview.py` / `run_preview.sh`.

**Criterio de éxito:**  
El preview muestra el efecto del filtro C++; si comentas el filtro, ves la imagen sin efecto.

**Control que ganas:**  
Confirmar que el contrato Python ↔ C++ (buffer in/out) funciona en un caso real y que puedes enchufar/quitar el filtro sin romper el motor.

---

## MVP 3: “Un analizador en el pipeline”

**Objetivo:** Incluir **una** capa de percepción sin cambiar render ni salida.

- Añadir **un** analizador al `AnalyzerPipeline` (p. ej. FaceHaarAnalyzer, o un stub que devuelva un bounding box fijo).
- El resultado de análisis puede no usarse aún en filtros ni en C++; solo que el engine llame al analizador y que no falle.

**Criterio de éxito:**  
El mismo script de MVP 1 (preview solo) corre con `analyzers=AnalyzerPipeline([FaceHaarAnalyzer()])` y la ventana sigue mostrando el mismo video (el análisis no tiene por qué verse todavía).

**Control que ganas:**  
Validar que la capa “Perception” está integrada en el flujo y que puedes añadir más analizadores más adelante.

---

## MVP 4: “Salida de red estable (UDP)”

**Objetivo:** Mismo flujo mínimo (cámara → passthrough o 1 filtro → render → **UDP**), consumido por VLC u otra app.

- Usar `FfmpegUdpOutput` con `EngineConfig(host="127.0.0.1", port=1234)`.
- En VLC: Abrir red → `udp://@127.0.0.1:1234`.

**Criterio de éxito:**  
Ves el mismo contenido que en la ventana de preview, pero en VLC vía UDP, durante al menos 30–60 segundos sin cortes.

**Control que ganas:**  
Un “modo headless” útil para pruebas y para conectar con NDI/RTSP/otros más adelante.

---

## Checklist para recuperar el control

Usa esto como lista de comprobación; no hace falta hacerlo todo el primer día.

1. **Entorno**
   - [ ] `cd /home/fissure/repos/Spatial-Iteration-Engine`
   - [ ] `export PYTHONPATH=python` (o `python:cpp/build` si usas C++)
   - [ ] `pip install -r python/requirements.txt` (o `python/ascii_stream_engine/requirements.txt` según tu estructura)

2. **MVP 1 — Un camino que funcione**
   - [ ] Ejecutar: `python python/ascii_stream_engine/examples/stream_camera_preview_only.py`
   - [ ] Ver ventana de preview; cerrar con Ctrl+C.
   - [ ] Añadir un filtro (p. ej. `InvertFilter()`) a `FilterPipeline` en ese script y volver a ejecutar; comprobar que el efecto se ve.

3. **Opcional: C++**
   - [ ] `./cpp/build.sh` (o seguir `cpp/README.md`)
   - [ ] Ejecutar `./run_preview.sh` y comprobar preview con filtros C++.

4. **Opcional: UDP**
   - [ ] Cambiar en un ejemplo el sink a `FfmpegUdpOutput()` y configurar host/port.
   - [ ] Abrir VLC → udp://@127.0.0.1:1234 y comprobar que hay imagen.

5. **Documentar “el camino feliz”**
   - [ ] Dejar anotado en README o en este doc: “El MVP que uso es: script X, comando Y, salida Z.” Así siempre tienes un punto de referencia.

---

## Orden sugerido

1. **MVP 1** (preview solo, con/sin un filtro Python): base de control.
2. **MVP 4** (UDP): mismo flujo, otra salida; refuerza que el pipeline es estable.
3. **MVP 2** (un filtro C++) si quieres validar el bridge.
4. **MVP 3** (un analizador) cuando quieras integrar percepción sin tocar aún estilo ni C++.

Cuando tengas MVP 1 estable, cualquier cambio (nuevo filtro, nuevo analizador, nuevo sink) puedes probarlo sobre ese mismo camino y recuperar el control del proceso paso a paso.
