# Guía de Desarrollo de Plugins

Esta guía explica cómo crear y desarrollar plugins para el Spatial Iteration Engine.

## Índice

1. [Introducción](#introducción)
2. [Tipos de Plugins](#tipos-de-plugins)
3. [Crear un Plugin Básico](#crear-un-plugin-básico)
4. [Metadatos de Plugins](#metadatos-de-plugins)
5. [Auto-descubrimiento](#auto-descubrimiento)
6. [Hot-reload](#hot-reload)
7. [Mejores Prácticas](#mejores-prácticas)

## Introducción

El sistema de plugins permite extender el motor con nuevas funcionalidades sin modificar el código principal. Los plugins pueden ser:

- **Filtros**: Transforman frames de video
- **Analizadores**: Extraen información de frames
- **Renderers**: Generan salidas visuales
- **Trackers**: Rastrean objetos en el tiempo

## Tipos de Plugins

### FilterPlugin

Los filtros transforman frames de video. Deben implementar el método `apply`:

```python
from ascii_stream_engine.infrastructure.plugins import FilterPlugin
from ascii_stream_engine.domain.config import EngineConfig
import numpy as np

class MiFiltro(FilterPlugin):
    name = "mi_filtro"
    version = "1.0.0"
    description = "Un filtro personalizado"
    author = "Tu Nombre"
    
    def apply(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        analysis: Optional[dict] = None
    ) -> np.ndarray:
        # Procesar el frame
        # frame es un array numpy de OpenCV (BGR)
        processed_frame = frame.copy()  # Tu lógica aquí
        return processed_frame
```

### AnalyzerPlugin

Los analizadores extraen información de frames:

```python
from ascii_stream_engine.infrastructure.plugins import AnalyzerPlugin
from ascii_stream_engine.domain.config import EngineConfig
import numpy as np
from typing import Dict, Any

class MiAnalizador(AnalyzerPlugin):
    name = "mi_analizador"
    version = "1.0.0"
    description = "Un analizador personalizado"
    author = "Tu Nombre"
    
    def analyze(
        self,
        frame: np.ndarray,
        config: EngineConfig
    ) -> Dict[str, Any]:
        # Analizar el frame
        results = {
            "detections": [],
            "metadata": {}
        }
        return results
```

### RendererPlugin

Los renderers generan salidas visuales:

```python
from ascii_stream_engine.infrastructure.plugins import RendererPlugin
from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame
import numpy as np
from typing import Optional

class MiRenderer(RendererPlugin):
    name = "mi_renderer"
    version = "1.0.0"
    description = "Un renderer personalizado"
    author = "Tu Nombre"
    
    def render(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        analysis: Optional[dict] = None
    ) -> RenderFrame:
        # Renderizar el frame
        # Retornar un RenderFrame
        pass
    
    def output_size(self, config: EngineConfig) -> tuple:
        return (config.width, config.height)
```

### TrackerPlugin

Los trackers rastrean objetos en el tiempo:

```python
from ascii_stream_engine.infrastructure.plugins import TrackerPlugin
from ascii_stream_engine.domain.config import EngineConfig
import numpy as np
from typing import Dict, Any

class MiTracker(TrackerPlugin):
    name = "mi_tracker"
    version = "1.0.0"
    description = "Un tracker personalizado"
    author = "Tu Nombre"
    
    def track(
        self,
        frame: np.ndarray,
        detections: dict,
        config: EngineConfig
    ) -> Dict[str, Any]:
        # Trackear objetos
        tracking_data = {}
        return tracking_data
    
    def reset(self) -> None:
        # Resetear el estado del tracker
        pass
```

## Crear un Plugin Básico

### Paso 1: Crear el archivo del plugin

Crea un archivo Python con tu plugin:

```python
# mi_plugin.py
from ascii_stream_engine.infrastructure.plugins import FilterPlugin
from ascii_stream_engine.domain.config import EngineConfig
import numpy as np
from typing import Optional

class MiPlugin(FilterPlugin):
    name = "mi_plugin"
    version = "1.0.0"
    description = "Mi primer plugin"
    author = "Tu Nombre"
    
    def apply(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        analysis: Optional[dict] = None
    ) -> np.ndarray:
        # Tu lógica aquí
        return frame
```

### Paso 2: Cargar el plugin

```python
from ascii_stream_engine.infrastructure.plugins import PluginManager

# Crear el gestor de plugins
manager = PluginManager(plugin_paths=["/ruta/a/tus/plugins"])

# O cargar manualmente
manager.load_from_file("/ruta/a/mi_plugin.py")

# Usar el plugin
plugin = manager.get_plugin("mi_plugin")
if plugin:
    processed_frame = plugin.apply(frame, config)
```

## Metadatos de Plugins

Los plugins pueden incluir metadatos estructurados para proporcionar más información:

### Metadatos Básicos

```python
class MiPlugin(FilterPlugin):
    name = "mi_plugin"
    version = "1.0.0"
    description = "Un plugin con metadatos"
    author = "Tu Nombre"
    
    # Metadatos estructurados
    metadata = {
        "dependencies": ["numpy", "opencv-python"],
        "optional_dependencies": ["cupy"],
        "python_version": ">=3.8",
        "capabilities": ["gpu_acceleration", "real_time"],
        "tags": ["filter", "image_processing"],
        "default_config": {
            "intensity": 0.5
        }
    }
```

### Archivo de Metadatos JSON

También puedes crear un archivo JSON con metadatos:

```json
{
  "name": "mi_plugin",
  "version": "1.0.0",
  "description": "Un plugin con metadatos",
  "author": "Tu Nombre",
  "plugin_type": "filter",
  "dependencies": ["numpy"],
  "capabilities": ["real_time"],
  "tags": ["filter"]
}
```

Guarda este archivo como `mi_plugin.json` junto a `mi_plugin.py`. El sistema lo cargará automáticamente.

### Usar PluginMetadata

```python
from ascii_stream_engine.infrastructure.plugins import PluginMetadata

metadata = PluginMetadata(
    name="mi_plugin",
    version="1.0.0",
    description="Un plugin",
    author="Tu Nombre",
    plugin_type="filter",
    dependencies=["numpy"],
    capabilities={"gpu_acceleration", "real_time"},
    tags=["filter", "image_processing"]
)

# Guardar metadatos
metadata.save_to_file("mi_plugin.json")

# Cargar metadatos
loaded_metadata = PluginMetadata.from_file("mi_plugin.json")
```

## Auto-descubrimiento

El sistema puede descubrir plugins automáticamente usando entry points de Python.

### Configurar Entry Points

En tu `setup.py` o `pyproject.toml`:

```python
# setup.py
from setuptools import setup

setup(
    name="mi-paquete-plugins",
    # ...
    entry_points={
        "ascii_stream_engine.plugins": [
            "mi_plugin = mi_paquete.plugins:MiPlugin",
        ],
    },
)
```

```toml
# pyproject.toml
[project.entry-points."ascii_stream_engine.plugins"]
mi_plugin = "mi_paquete.plugins:MiPlugin"
```

El sistema descubrirá automáticamente estos plugins cuando se inicialice el `PluginRegistry`.

## Hot-reload

El sistema de hot-reload permite recargar plugins automáticamente cuando se modifican sus archivos, sin reiniciar el engine.

### Habilitar Hot-reload

```python
from ascii_stream_engine.infrastructure.plugins import PluginManager

# Crear gestor con hot-reload habilitado
manager = PluginManager(
    plugin_paths=["/ruta/a/plugins"],
    enable_hot_reload=True,
    hot_reload_debounce=0.5  # Esperar 0.5 segundos antes de recargar
)

# Hot-reload se inicia automáticamente
# Los cambios en archivos .py se detectan y recargan automáticamente
```

### Control Manual

```python
# Iniciar hot-reload manualmente
manager.start_hot_reload()

# Verificar si está activo
if manager.is_hot_reload_active():
    print("Hot-reload activo")

# Detener hot-reload
manager.stop_hot_reload()
```

### Requisitos

Hot-reload requiere la librería `watchdog`:

```bash
pip install watchdog
```

## Mejores Prácticas

### 1. Validación

Siempre valida tus plugins:

```python
plugin = MiPlugin()
if plugin.validate():
    print("Plugin válido")
```

### 2. Manejo de Errores

Maneja errores apropiadamente:

```python
def apply(self, frame, config, analysis=None):
    try:
        # Tu lógica
        return processed_frame
    except Exception as e:
        logger.error(f"Error en plugin {self.name}: {e}")
        return frame  # Retornar frame original en caso de error
```

### 3. Documentación

Documenta tus plugins:

```python
class MiPlugin(FilterPlugin):
    """
    Un plugin que hace algo interesante.
    
    Args:
        intensity: Intensidad del efecto (0.0-1.0)
    """
    name = "mi_plugin"
    # ...
```

### 4. Testing

Crea tests para tus plugins:

```python
import unittest
from mi_plugin import MiPlugin

class TestMiPlugin(unittest.TestCase):
    def test_apply(self):
        plugin = MiPlugin()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = plugin.apply(frame, config)
        self.assertIsNotNone(result)
```

### 5. Versionado

Usa versionado semántico:

```python
version = "1.2.3"  # MAJOR.MINOR.PATCH
```

### 6. Dependencias

Especifica claramente las dependencias:

```python
metadata = {
    "dependencies": ["numpy>=1.20.0"],
    "optional_dependencies": ["cupy"],
}
```

### 7. Configuración

Usa configuración por defecto:

```python
metadata = {
    "default_config": {
        "threshold": 0.5,
        "enabled": True
    }
}
```

## Ejemplos Completos

### Ejemplo: Filtro de Brillo

```python
from ascii_stream_engine.infrastructure.plugins import FilterPlugin
from ascii_stream_engine.domain.config import EngineConfig
import numpy as np
import cv2
from typing import Optional

class BrightnessFilter(FilterPlugin):
    name = "brightness_filter"
    version = "1.0.0"
    description = "Ajusta el brillo de los frames"
    author = "Ejemplo"
    
    metadata = {
        "dependencies": ["opencv-python", "numpy"],
        "tags": ["filter", "brightness"],
        "default_config": {
            "brightness_factor": 1.2
        }
    }
    
    def __init__(self):
        super().__init__()
        self.brightness_factor = 1.2
    
    def apply(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        analysis: Optional[dict] = None
    ) -> np.ndarray:
        # Ajustar brillo
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hsv[:, :, 2] = cv2.multiply(hsv[:, :, 2], self.brightness_factor)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
```

### Ejemplo: Analizador de Movimiento

```python
from ascii_stream_engine.infrastructure.plugins import AnalyzerPlugin
from ascii_stream_engine.domain.config import EngineConfig
import numpy as np
import cv2
from typing import Dict, Any

class MotionAnalyzer(AnalyzerPlugin):
    name = "motion_analyzer"
    version = "1.0.0"
    description = "Detecta movimiento en frames"
    author = "Ejemplo"
    
    def __init__(self):
        super().__init__()
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2()
    
    def analyze(
        self,
        frame: np.ndarray,
        config: EngineConfig
    ) -> Dict[str, Any]:
        # Detectar movimiento
        fg_mask = self.background_subtractor.apply(frame)
        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        return {
            "motion_detected": len(contours) > 0,
            "motion_areas": [cv2.contourArea(c) for c in contours],
            "contour_count": len(contours)
        }
```

## Recursos Adicionales

- Ver código fuente de plugins existentes en `ascii_stream_engine/adapters/`
- Consultar la documentación de la API en el código fuente
- Revisar tests en `tests/` para ejemplos de uso

