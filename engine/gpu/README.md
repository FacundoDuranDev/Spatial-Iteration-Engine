# engine/gpu

Biblioteca de kernels/shaders del runtime.

MVP inicial:

- `warp` (affine/perspective),
- `blur` (gaussian separable),
- `feedback` (mix con frame previo y decay).

Principios:

- todos los nodos operan sobre texturas/buffers GPU,
- sin roundtrip a CPU en ruta de tiempo real,
- formatos y bindings estables para evitar churn de recursos.
