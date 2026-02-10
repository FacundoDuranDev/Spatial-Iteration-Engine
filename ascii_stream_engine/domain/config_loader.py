"""Sistema de carga de configuración desde archivos YAML/JSON y perfiles predefinidos."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .config import EngineConfig, ConfigValidationError

# Intentar importar YAML, pero no es obligatorio
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class ConfigLoadError(Exception):
    """Excepción lanzada cuando hay un error al cargar la configuración."""

    pass


# Perfiles predefinidos
PREDEFINED_PROFILES: Dict[str, Dict[str, Any]] = {
    "low_latency": {
        "fps": 30,
        "grid_w": 80 ,
        "grid_h": 40,
        "frame_buffer_size": 1,
        "sleep_on_empty": 0.005,
        "parallel_workers": 0,
        "gpu_enabled": False,
        "bitrate": "1000k",
    },
    "high_quality": {
        "fps": 20,
        "grid_w": 200,
        "grid_h": 100,
        "frame_buffer_size": 3,
        "sleep_on_empty": 0.01,
        "parallel_workers": 2,
        "gpu_enabled": True,
        "bitrate": "3000k",
        "contrast": 1.5,
        "charset": " .:-=+*#%@",
    },
    "balanced": {
        "fps": 25,
        "grid_w": 120,
        "grid_h": 60,
        "frame_buffer_size": 2,
        "sleep_on_empty": 0.01,
        "parallel_workers": 1,
        "gpu_enabled": False,
        "bitrate": "1500k",
    },
    "performance": {
        "fps": 60,
        "grid_w": 100,
        "grid_h": 50,
        "frame_buffer_size": 2,
        "sleep_on_empty": 0.005,
        "parallel_workers": 4,
        "gpu_enabled": True,
        "bitrate": "2000k",
    },
    "minimal": {
        "fps": 15,
        "grid_w": 60,
        "grid_h": 30,
        "frame_buffer_size": 1,
        "sleep_on_empty": 0.01,
        "parallel_workers": 0,
        "gpu_enabled": False,
        "bitrate": "500k",
    },
}


def get_predefined_profile(profile_name: str) -> Dict[str, Any]:
    """Obtiene un perfil predefinido por nombre.

    Args:
        profile_name: Nombre del perfil (low_latency, high_quality, balanced, etc.)

    Returns:
        Diccionario con la configuración del perfil.

    Raises:
        ConfigLoadError: Si el perfil no existe.
    """
    if profile_name not in PREDEFINED_PROFILES:
        available = ", ".join(PREDEFINED_PROFILES.keys())
        raise ConfigLoadError(
            f"Perfil '{profile_name}' no encontrado. Perfiles disponibles: {available}"
        )
    return PREDEFINED_PROFILES[profile_name].copy()


def list_predefined_profiles() -> list[str]:
    """Lista todos los perfiles predefinidos disponibles.

    Returns:
        Lista de nombres de perfiles.
    """
    return list(PREDEFINED_PROFILES.keys())


def load_config_from_dict(config_dict: Dict[str, Any]) -> EngineConfig:
    """Crea un EngineConfig desde un diccionario.

    Args:
        config_dict: Diccionario con los valores de configuración.

    Returns:
        Instancia de EngineConfig.

    Raises:
        ConfigValidationError: Si la configuración no es válida.
    """
    # Filtrar solo los campos válidos de EngineConfig
    valid_fields = {
        "fps",
        "grid_w",
        "grid_h",
        "charset",
        "render_mode",
        "raw_width",
        "raw_height",
        "invert",
        "contrast",
        "brightness",
        "host",
        "port",
        "pkt_size",
        "bitrate",
        "udp_broadcast",
        "frame_buffer_size",
        "sleep_on_empty",
        "enable_events",
        "parallel_workers",
        "gpu_enabled",
        "controller_config",
        "sensor_config",
        "plugin_paths",
    }

    filtered_dict = {k: v for k, v in config_dict.items() if k in valid_fields}

    return EngineConfig(**filtered_dict)


def load_config_from_file(file_path: str) -> EngineConfig:
    """Carga una configuración desde un archivo YAML o JSON.

    Args:
        file_path: Ruta al archivo de configuración (.yaml, .yml, o .json).

    Returns:
        Instancia de EngineConfig.

    Raises:
        ConfigLoadError: Si hay un error al cargar o parsear el archivo.
        ConfigValidationError: Si la configuración no es válida.
    """
    path = Path(file_path)

    if not path.exists():
        raise ConfigLoadError(f"El archivo de configuración no existe: {file_path}")

    if not path.is_file():
        raise ConfigLoadError(f"La ruta no es un archivo: {file_path}")

    # Determinar el formato por extensión
    ext = path.suffix.lower()
    is_yaml = ext in (".yaml", ".yml")
    is_json = ext == ".json"

    if not (is_yaml or is_json):
        raise ConfigLoadError(
            f"Formato de archivo no soportado: {ext}. Use .yaml, .yml o .json"
        )

    try:
        with open(path, "r", encoding="utf-8") as f:
            if is_yaml:
                if not YAML_AVAILABLE:
                    raise ConfigLoadError(
                        "PyYAML no está instalado. Instálelo con: pip install pyyaml"
                    )
                config_dict = yaml.safe_load(f)
            else:  # JSON
                config_dict = json.load(f)

        if not isinstance(config_dict, dict):
            raise ConfigLoadError(
                f"El archivo debe contener un objeto/diccionario, se encontró: {type(config_dict)}"
            )

        return load_config_from_dict(config_dict)

    except yaml.YAMLError as e:
        raise ConfigLoadError(f"Error al parsear YAML: {e}") from e
    except json.JSONDecodeError as e:
        raise ConfigLoadError(f"Error al parsear JSON: {e}") from e
    except Exception as e:
        raise ConfigLoadError(f"Error al leer el archivo: {e}") from e


def load_config_from_profile(
    profile_name: str, overrides: Optional[Dict[str, Any]] = None
) -> EngineConfig:
    """Carga una configuración desde un perfil predefinido con opciones de sobrescritura.

    Args:
        profile_name: Nombre del perfil predefinido.
        overrides: Diccionario opcional con valores para sobrescribir el perfil.

    Returns:
        Instancia de EngineConfig.

    Raises:
        ConfigLoadError: Si el perfil no existe.
        ConfigValidationError: Si la configuración no es válida.
    """
    profile_dict = get_predefined_profile(profile_name)

    # Aplicar sobrescrituras si se proporcionan
    if overrides:
        profile_dict.update(overrides)

    return load_config_from_dict(profile_dict)


def merge_configs(
    base: EngineConfig, overrides: Dict[str, Any]
) -> EngineConfig:
    """Combina una configuración base con valores de sobrescritura.

    Args:
        base: Configuración base.
        overrides: Diccionario con valores para sobrescribir.

    Returns:
        Nueva instancia de EngineConfig con los valores combinados.
    """
    # Convertir la configuración base a diccionario
    base_dict = {
        "fps": base.fps,
        "grid_w": base.grid_w,
        "grid_h": base.grid_h,
        "charset": base.charset,
        "render_mode": base.render_mode,
        "raw_width": base.raw_width,
        "raw_height": base.raw_height,
        "invert": base.invert,
        "contrast": base.contrast,
        "brightness": base.brightness,
        "host": base.host,
        "port": base.port,
        "pkt_size": base.pkt_size,
        "bitrate": base.bitrate,
        "udp_broadcast": base.udp_broadcast,
        "frame_buffer_size": base.frame_buffer_size,
        "sleep_on_empty": base.sleep_on_empty,
        "enable_events": base.enable_events,
        "parallel_workers": base.parallel_workers,
        "gpu_enabled": base.gpu_enabled,
        "controller_config": base.controller_config.copy(),
        "sensor_config": base.sensor_config.copy(),
        "plugin_paths": base.plugin_paths.copy(),
    }

    # Aplicar sobrescrituras
    base_dict.update(overrides)

    return load_config_from_dict(base_dict)


def save_config_to_file(config: EngineConfig, file_path: str, format: str = "yaml") -> None:
    """Guarda una configuración a un archivo YAML o JSON.

    Args:
        config: Instancia de EngineConfig a guardar.
        file_path: Ruta donde guardar el archivo.
        format: Formato de salida: "yaml" o "json" (por defecto: "yaml").

    Raises:
        ConfigLoadError: Si hay un error al guardar el archivo.
    """
    path = Path(file_path)

    # Convertir configuración a diccionario
    config_dict = {
        "fps": config.fps,
        "grid_w": config.grid_w,
        "grid_h": config.grid_h,
        "charset": config.charset,
        "render_mode": config.render_mode,
        "raw_width": config.raw_width,
        "raw_height": config.raw_height,
        "invert": config.invert,
        "contrast": config.contrast,
        "brightness": config.brightness,
        "host": config.host,
        "port": config.port,
        "pkt_size": config.pkt_size,
        "bitrate": config.bitrate,
        "udp_broadcast": config.udp_broadcast,
        "frame_buffer_size": config.frame_buffer_size,
        "sleep_on_empty": config.sleep_on_empty,
        "enable_events": config.enable_events,
        "parallel_workers": config.parallel_workers,
        "gpu_enabled": config.gpu_enabled,
        "controller_config": config.controller_config,
        "sensor_config": config.sensor_config,
        "plugin_paths": config.plugin_paths,
    }

    # Eliminar valores None para mantener el archivo limpio
    config_dict = {k: v for k, v in config_dict.items() if v is not None}

    try:
        with open(path, "w", encoding="utf-8") as f:
            if format.lower() == "json":
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            else:  # YAML
                if not YAML_AVAILABLE:
                    raise ConfigLoadError(
                        "PyYAML no está instalado. Instálelo con: pip install pyyaml"
                    )
                yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)

    except Exception as e:
        raise ConfigLoadError(f"Error al guardar el archivo: {e}") from e

