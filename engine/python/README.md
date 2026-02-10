# engine/python

Control-plane del runtime:

- define y valida el grafo (`RuntimeGraphSpec`),
- aplica updates de parámetros por frame,
- mantiene estado de alto nivel y políticas de clock,
- conversa con C++ mediante contratos de binding.

Regla: esta capa **no** procesa píxeles. Trabaja con descriptores, handles y
actualizaciones de parámetros.
