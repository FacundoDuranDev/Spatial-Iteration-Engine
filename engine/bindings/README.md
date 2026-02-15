# engine/bindings

Puente entre control-plane Python y runtime C++.

API esperada:

- crear/reemplazar grafo,
- actualizar parámetros en caliente,
- ejecutar `tick` por frame,
- obtener estadísticas y handles de salida.

La interfaz debe ser estable y de bajo costo para sostener control interactivo
en tiempo real.
