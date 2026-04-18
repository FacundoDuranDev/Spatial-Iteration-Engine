"""Interfaces base para plugins."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import numpy as np

from ...domain.config import EngineConfig
from ...domain.types import RenderFrame
from .plugin_metadata import PluginMetadata, extract_metadata_from_plugin


class Plugin(ABC):
    """Clase base para todos los plugins."""

    name: str = "plugin"
    version: str = "1.0.0"
    description: str = ""
    author: str = ""

    # Metadatos estructurados (opcional, puede ser un dict o PluginMetadata)
    metadata: Optional[Dict[str, Any]] = None

    def __init__(self) -> None:
        """Inicializa el plugin."""
        pass

    def get_info(self) -> Dict[str, Any]:
        """Obtiene información del plugin."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
        }

    def get_metadata(self) -> PluginMetadata:
        """
        Obtiene los metadatos estructurados del plugin.

        Returns:
            Metadatos del plugin
        """
        return extract_metadata_from_plugin(self)

    def validate(self) -> bool:
        """
        Valida que el plugin esté correctamente configurado.

        Returns:
            True si el plugin es válido
        """
        if not bool(self.name and self.version):
            return False

        # Validar metadatos si existen
        if self.metadata:
            try:
                if isinstance(self.metadata, dict):
                    enriched = dict(self.metadata)
                    enriched.setdefault("name", self.name)
                    enriched.setdefault("version", self.version)
                    metadata_obj = PluginMetadata.from_dict(enriched)
                else:
                    metadata_obj = self.metadata
                if not metadata_obj.validate():
                    return False
            except Exception:
                return False

        return True


class FilterPlugin(Plugin):
    """Plugin para filtros de video."""

    @abstractmethod
    def apply(
        self, frame: np.ndarray, config: EngineConfig, analysis: Optional[dict] = None
    ) -> np.ndarray:
        """
        Aplica el filtro al frame.

        Args:
            frame: Frame de video
            config: Configuración del engine
            analysis: Resultados de análisis (opcional)

        Returns:
            Frame procesado
        """
        pass


class AnalyzerPlugin(Plugin):
    """Plugin para analizadores de video."""

    @abstractmethod
    def analyze(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, Any]:
        """
        Analiza el frame.

        Args:
            frame: Frame de video
            config: Configuración del engine

        Returns:
            Diccionario con resultados del análisis
        """
        pass


class RendererPlugin(Plugin):
    """Plugin para renderers de video."""

    @abstractmethod
    def render(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        analysis: Optional[dict] = None,
    ) -> RenderFrame:
        """
        Renderiza el frame.

        Args:
            frame: Frame de video
            config: Configuración del engine
            analysis: Resultados de análisis (opcional)

        Returns:
            RenderFrame con el resultado
        """
        pass

    @abstractmethod
    def output_size(self, config: EngineConfig) -> tuple:
        """
        Calcula el tamaño de salida.

        Args:
            config: Configuración del engine

        Returns:
            Tupla (width, height)
        """
        pass


class TrackerPlugin(Plugin):
    """Plugin para trackers de objetos."""

    @abstractmethod
    def track(self, frame: np.ndarray, detections: dict, config: EngineConfig) -> Dict[str, Any]:
        """
        Trackea objetos en el frame.

        Args:
            frame: Frame de video
            detections: Detecciones de analizadores
            config: Configuración del engine

        Returns:
            Diccionario con datos de tracking
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Resetea el estado del tracker."""
        pass
