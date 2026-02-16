# Python stdlib (modulos usados)

Este documento resume los modulos de la libreria standard usados en el proyecto.

## dataclasses
Uso: definir modelos simples (EngineConfig, RenderFrame).
Ventaja: menos boilerplate y defaults claros.

Ejemplo:
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    fps: int = 30
    host: str = "127.0.0.1"
    port: int = 1234
    raw_width: Optional[int] = None
```

Buenas practicas:
- Usar tipos opcionales para valores que pueden ser None.
- Mantener defaults razonables.

## typing
Uso: contratos y tipos (Protocol, Optional, Tuple, List, Dict).

Ejemplo:
```python
from typing import Optional, Protocol, Tuple

class FrameSource(Protocol):
    def read(self) -> Optional[object]:
        ...
```

Buenas practicas:
- Usar Protocol para puertos.
- Mantener tipos simples en la API publica.

## threading
Uso: loop de engine y captura en paralelo.

Ejemplo:
```python
import threading

event = threading.Event()
lock = threading.Lock()
```

Buenas practicas:
- Usar Event para detener hilos.
- No hacer trabajo pesado dentro de locks.

## contextlib
Uso: contextmanager para exponer listas protegidas por lock.

Ejemplo:
```python
from contextlib import contextmanager

@contextmanager
def locked(lock, data):
    with lock:
        yield data
```

## collections.deque
Uso: buffer circular de frames.

Ejemplo:
```python
from collections import deque

buffer = deque(maxlen=2)
```

## time
Uso: timestamps y sleep para controlar fps.

Ejemplo:
```python
import time

start = time.perf_counter()
time.sleep(0.01)
```

## subprocess
Uso: lanzar ffmpeg para salida UDP.

Ejemplo:
```python
import subprocess

proc = subprocess.Popen(["ffmpeg", "-i", "-", "..."])
proc.stdin.write(b"...")
```

Buenas practicas:
- Cerrar stdin antes de terminar.
- Manejar timeouts al cerrar.

## os y sys
Uso: rutas, fonts, path del repo.

Ejemplo:
```python
import os, sys

repo_root = os.path.abspath(os.path.join(os.getcwd(), "../.."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
```

## unittest y unittest.mock
Uso: tests unitarios y mocks de dependencias.

Ejemplo:
```python
import unittest
from unittest.mock import patch

class TestFoo(unittest.TestCase):
    def test_bar(self):
        with patch("mod.func") as mock:
            ...
```

## tempfile
Uso: archivos temporales en tests.

Ejemplo:
```python
import tempfile

with tempfile.TemporaryDirectory() as tmpdir:
    ...
```

## importlib.util
Uso: detectar si un modulo esta disponible.

Ejemplo:
```python
import importlib.util

def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None
```
