# engine/core

Runtime C++ de frames en tiempo real.

Responsabilidades:

- scheduler determinista por frame,
- gestión de pools de buffers/texturas,
- ejecución de nodos (dispatch a GPU),
- manejo explícito de feedback temporal,
- coordinación con I/O y sincronización de clock.

Prohibido en esta capa:

- re-alocar recursos por frame salvo cambios de formato/resolución,
- bloqueos largos en el camino crítico de render.
