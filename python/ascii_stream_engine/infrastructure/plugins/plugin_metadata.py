"""Sistema de metadatos estructurados para plugins."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class PluginMetadata:
    """Metadatos estructurados de un plugin."""

    # Información básica
    name: str
    version: str
    description: str = ""
    author: str = ""

    # Información técnica
    plugin_type: str = "unknown"  # filter, analyzer, renderer, tracker
    entry_point: Optional[str] = None  # Nombre de la clase del plugin
    module_path: Optional[str] = None  # Ruta al módulo

    # Dependencias
    dependencies: List[str] = field(default_factory=list)
    optional_dependencies: List[str] = field(default_factory=list)
    python_version: Optional[str] = None  # Requisito de versión de Python

    # Capacidades y características
    capabilities: Set[str] = field(default_factory=set)
    tags: List[str] = field(default_factory=list)

    # Configuración
    default_config: Dict[str, Any] = field(default_factory=dict)
    config_schema: Optional[Dict[str, Any]] = None  # JSON Schema

    # Información adicional
    homepage: Optional[str] = None
    license: Optional[str] = None
    keywords: List[str] = field(default_factory=list)

    # Metadatos del sistema
    loaded_from: Optional[str] = None  # Ruta desde donde se cargó
    load_time: Optional[float] = None  # Timestamp de carga

    def to_dict(self) -> Dict[str, Any]:
        """Convierte los metadatos a diccionario."""
        data = asdict(self)
        # Convertir set a list para JSON
        data["capabilities"] = list(self.capabilities)
        return data

    def to_json(self, indent: int = 2) -> str:
        """Convierte los metadatos a JSON."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginMetadata":
        """Crea metadatos desde un diccionario."""
        # Convertir list a set para capabilities
        if "capabilities" in data and isinstance(data["capabilities"], list):
            data["capabilities"] = set(data["capabilities"])
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "PluginMetadata":
        """Crea metadatos desde JSON."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, file_path: str) -> Optional["PluginMetadata"]:
        """Carga metadatos desde un archivo JSON."""
        try:
            path = Path(file_path)
            if not path.exists():
                return None
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception:
            return None

    def save_to_file(self, file_path: str) -> bool:
        """Guarda los metadatos en un archivo JSON."""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.to_json())
            return True
        except Exception:
            return False

    def validate(self) -> bool:
        """Valida que los metadatos sean correctos."""
        if not self.name or not self.version:
            return False
        if self.plugin_type not in ("filter", "analyzer", "renderer", "tracker", "unknown"):
            return False
        return True

    def merge(self, other: "PluginMetadata") -> "PluginMetadata":
        """Fusiona metadatos con otros, dando prioridad a 'other'."""
        merged = self.to_dict()
        other_dict = other.to_dict()

        # Listas y sets que deben fusionarse (no sobrescribirse)
        merge_keys = ("dependencies", "optional_dependencies", "tags", "keywords", "capabilities")

        # Actualizar otros campos con valores de 'other' si existen
        for key, value in other_dict.items():
            if key in merge_keys:
                # Fusionar listas y sets
                if key == "capabilities":
                    merged[key] = list(set(merged.get(key, [])) | set(other_dict.get(key, [])))
                else:
                    merged[key] = list(set(merged.get(key, []) + other_dict.get(key, [])))
            elif value is not None and value != [] and value != {}:
                # Sobrescribir otros campos
                merged[key] = value

        return self.from_dict(merged)


def extract_metadata_from_plugin(plugin: Any, plugin_type: Optional[str] = None) -> PluginMetadata:
    """
    Extrae metadatos de una instancia de plugin.

    Args:
        plugin: Instancia del plugin
        plugin_type: Tipo del plugin (se infiere si no se proporciona)

    Returns:
        Metadatos extraídos
    """
    # Inferir tipo si no se proporciona
    if plugin_type is None:
        from .plugin_interface import (
            AnalyzerPlugin,
            FilterPlugin,
            RendererPlugin,
            TrackerPlugin,
        )

        if isinstance(plugin, FilterPlugin):
            plugin_type = "filter"
        elif isinstance(plugin, AnalyzerPlugin):
            plugin_type = "analyzer"
        elif isinstance(plugin, RendererPlugin):
            plugin_type = "renderer"
        elif isinstance(plugin, TrackerPlugin):
            plugin_type = "tracker"
        else:
            plugin_type = "unknown"

    # Extraer información básica
    name = getattr(plugin, "name", plugin.__class__.__name__)
    version = getattr(plugin, "version", "1.0.0")
    description = getattr(plugin, "description", "")
    author = getattr(plugin, "author", "")

    # Extraer metadatos adicionales si existen
    metadata_dict = getattr(plugin, "metadata", None)
    if isinstance(metadata_dict, dict):
        # Si el plugin tiene un atributo metadata, usarlo
        enriched = dict(metadata_dict)
        enriched.setdefault("name", name)
        enriched.setdefault("version", version)
        base_metadata = PluginMetadata.from_dict(enriched)
    else:
        base_metadata = PluginMetadata(
            name=name,
            version=version,
            description=description,
            author=author,
            plugin_type=plugin_type,
            entry_point=plugin.__class__.__name__,
            module_path=getattr(plugin, "__module__", None),
        )

    # Asegurar que el tipo sea correcto
    base_metadata.plugin_type = plugin_type

    return base_metadata
