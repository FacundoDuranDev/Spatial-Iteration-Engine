Spatial Iteration Engine
Vision AI Layer
1. Objetivo

Integrar un motor de visión por computadora basado en IA liviana dentro del pipeline en C++ del proyecto Spatial-Iteration-Engine, de manera que:

Procese frames en tiempo real

Genere mapas de percepción (saliency, motion, depth, edges)

Se integre directamente con el motor ASCII

Mantenga latencia total menor a 20 ms por frame

No dependa de Python

La IA debe correr 100% en C++.

2. Pipeline actual

El sistema ya implementado es:

Camera / Video
→ Frame Buffer (uint8_t*)
→ C++ Filters (edges, threshold, motion, etc)
→ ASCII Stream Engine
→ Terminal Renderer

Este pipeline ya funciona en tiempo casi real.

3. Nueva arquitectura con IA

Se agrega una capa de Vision AI entre el frame y el ASCII engine.

Frame (RGB o Gray)
→ Preprocessing (resize, normalize)
→ Neural Network (C++ inference)
→ Feature Maps (Saliency, Motion, Depth opcional)
→ Postprocessing
→ ASCII Engine + Filtros

4. Requisitos del motor de IA

La red debe cumplir:

Latencia: menor a 10 ms por frame
Tamaño: menor a 10 MB
CPU: soportado
GPU: no requerida
Runtime: C++

Tecnologías permitidas:

ONNX Runtime

NCNN

TensorFlow Lite

OpenVINO

No permitido:

PyTorch

Python

CUDA

5. Tipos de modelos permitidos

5.1 Saliency
Detecta qué zonas son visualmente importantes.

Salida:
float saliency[width * height] en rango 0 a 1

5.2 Depth (opcional)
Mapa de profundidad monocular.

Salida:
float depth[width * height]

5.3 Motion / Optical Flow
Movimiento entre frames.

Salida:
float motion[width * height]

6. Interfaz C++

Debe existir una clase estable:

class VisionModel

load(model_path)

process(rgb_frame, width, height)

getSaliencyMap()

getDepthMap()

getMotionMap()

Requisitos:

Thread safe

Sin new ni delete por frame

Buffers prealocados

Reutilización de memoria

7. Integración al loop principal

El loop debe ser:

capturar frame
procesar visión
obtener saliency
pasar a ASCII engine
renderizar

La IA no debe bloquear el render.

8. Uso de la IA en el ASCII Engine

El mapa de saliency debe modificar la conversión ASCII.

Regla base:

ascii_density = base_density multiplicado por saliency en esa posición

Zonas importantes deben tener más detalle ASCII.
Zonas irrelevantes deben simplificarse.

Puede afectar:

Densidad

Contraste

Elección de símbolos

9. Performance

El sistema debe medir:

Tiempo de inferencia

Tiempo total por frame

Si el total supera 20 ms debe loggear:

WARN Frame latency exceeded

10. Fases de implementación

Fase 1
Integrar runtime ONNX o NCNN
Cargar un modelo
Inferir una imagen estática

Fase 2
Conectar al stream de video
Mostrar saliency en ASCII

Fase 3
Fusionar con filtros C existentes
Ajustar calidad vs latencia

11. Objetivo final

El sistema debe comportarse como un motor de percepción.

No solo mostrar la imagen, sino decidir qué partes de la escena merecen más atención visual en ASCII, en tiempo real.

Si querés, ahora lo siguiente lógico es:
elegimos el modelo real (ONNX o NCNN) y lo bajamos con tamaño, resolución y latencia reales para tu máquina 💥
