"""Pipeline para filtros de frames."""

import threading
from contextlib import contextmanager
from typing import Iterable, Iterator, List, Optional

import cv2
import numpy as np

from ...domain.config import EngineConfig
from ...ports.processors import Filter, ProcessorPipeline
from .filter_context import FilterContext


class FilterPipeline(ProcessorPipeline):
    """Pipeline para aplicar múltiples filtros en secuencia.

    Los filtros modifican el frame, aplicando transformaciones como ajustes
    de brillo, contraste, detección de bordes, etc.
    """

    def __init__(self, filters: Optional[Iterable[Filter]] = None) -> None:
        """
        Inicializa el pipeline de filtros.

        Args:
            filters: Lista inicial de filtros
        """
        self._filters: List[Filter] = list(filters) if filters else []
        self._lock = threading.Lock()
        # Cache de conversiones comunes para evitar conversiones redundantes
        # Estructura: {(conversion_code, frame_shape, frame_dtype): converted_frame}
        self._conversion_cache: dict = {}
        # ID del frame actual para invalidar cache cuando cambia el frame
        self._current_frame_id: Optional[int] = None

    @property
    def filters(self) -> List[Filter]:
        """Obtiene la lista de filtros."""
        return self._filters

    def snapshot(self) -> List[Filter]:
        """Obtiene una snapshot thread-safe de los filtros."""
        with self._lock:
            return list(self._filters)

    def add(self, processor: Filter) -> None:
        """Agrega un filtro al pipeline."""
        with self._lock:
            self._filters.append(processor)

    def remove(self, processor: Filter) -> None:
        """Remueve un filtro del pipeline."""
        with self._lock:
            self._filters.remove(processor)

    def append(self, filter_obj: Filter) -> None:
        """Agrega un filtro al pipeline."""
        self.add(filter_obj)

    def extend(self, filters: Iterable[Filter]) -> None:
        """Extiende el pipeline con múltiples filtros."""
        with self._lock:
            self._filters.extend(filters)

    def insert(self, index: int, filter_obj: Filter) -> None:
        """Inserta un filtro en una posición específica."""
        with self._lock:
            self._filters.insert(index, filter_obj)

    def pop(self, index: int = -1) -> Filter:
        """Remueve y retorna un filtro del pipeline."""
        with self._lock:
            return self._filters.pop(index)

    def clear(self) -> None:
        """Limpia todos los filtros del pipeline."""
        with self._lock:
            self._filters.clear()

    def replace(self, filters: Iterable[Filter]) -> None:
        """Reemplaza todos los filtros."""
        with self._lock:
            self._filters = list(filters)

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """
        Habilita o deshabilita un filtro por nombre.

        Args:
            name: Nombre del filtro
            enabled: Estado deseado

        Returns:
            True si se encontró y modificó el filtro
        """
        changed = False
        with self._lock:
            for filter_obj in self._filters:
                filter_name = getattr(filter_obj, "name", filter_obj.__class__.__name__)
                if filter_name == name:
                    if hasattr(filter_obj, "enabled"):
                        filter_obj.enabled = enabled
                        changed = True
        return changed

    def _get_cached_conversion(
        self, frame: np.ndarray, conversion_code: int, frame_id: int
    ) -> np.ndarray:
        """
        Obtiene una conversión cacheada o la realiza y la cachea.

        Args:
            frame: Frame original
            conversion_code: Código de conversión de OpenCV (ej: cv2.COLOR_BGR2GRAY)
            frame_id: ID único del frame para invalidar cache cuando cambia

        Returns:
            Frame convertido (cacheado o nuevo)
        """
        # Invalidar cache si cambió el frame
        if self._current_frame_id != frame_id:
            self._conversion_cache.clear()
            self._current_frame_id = frame_id

        # Crear clave de cache basada en conversión y características del frame
        cache_key = (conversion_code, frame.shape, frame.dtype)

        # Verificar si ya existe en cache
        if cache_key in self._conversion_cache:
            return self._conversion_cache[cache_key]

        # Realizar conversión y cachearla
        converted = cv2.cvtColor(frame, conversion_code)
        self._conversion_cache[cache_key] = converted
        return converted

    def _clear_conversion_cache(self) -> None:
        """Limpia el cache de conversiones."""
        self._conversion_cache.clear()
        self._current_frame_id = None

    def has_any(self) -> bool:
        """Verifica si hay filtros en el pipeline."""
        with self._lock:
            return bool(self._filters)

    def apply(
        self, frame: np.ndarray, config: EngineConfig, analysis: Optional[dict] = None
    ) -> np.ndarray:
        """
        Aplica todos los filtros activos en secuencia.

        Args:
            frame: Frame de video a filtrar
            config: Configuración del engine
            analysis: Resultados de análisis previos (opcional)

        Returns:
            Frame procesado
        """
        # Optimización: si no hay filtros activos, retornar el frame original sin copias
        filters = self.snapshot()
        active_filters = [
            f for f in filters if not (hasattr(f, "enabled") and not getattr(f, "enabled"))
        ]

        if not active_filters:
            return frame

        # Limpiar cache de conversiones al inicio de cada frame
        # El cache global se maneja automáticamente por frame_id
        try:
            from ...adapters.processors.filters.conversion_cache import clear_conversion_cache

            clear_conversion_cache()
        except ImportError:
            # Si no existe el módulo de cache global, continuar sin él
            pass

        # Extract temporal manager (injected by orchestrator)
        temporal = None
        if analysis and "temporal" in analysis:
            temporal = analysis.pop("temporal")

        context = FilterContext(analysis, temporal)

        # Aplicar filtros secuencialmente
        processed = frame
        for filter_obj in active_filters:
            processed = filter_obj.apply(processed, config, context)

        return processed

    def process(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        context: Optional[dict] = None,
    ) -> np.ndarray:
        """
        Procesa un frame a través de todos los filtros (alias de apply).

        Args:
            frame: Frame de video a filtrar
            config: Configuración del engine
            context: Contexto adicional (puede incluir análisis)

        Returns:
            Frame procesado
        """
        analysis = context.get("analysis") if context else None
        return self.apply(frame, config, analysis)

    @contextmanager
    def locked(self) -> Iterator[List[Filter]]:
        """Context manager para acceso thread-safe a los filtros."""
        with self._lock:
            yield self._filters
