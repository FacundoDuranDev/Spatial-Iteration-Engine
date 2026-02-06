from contextlib import contextmanager
import threading
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

import cv2
import numpy as np

from ..domain.config import EngineConfig


class AnalyzerPipeline:
    def __init__(self, analyzers: Optional[Iterable[object]] = None) -> None:
        self._analyzers: List[object] = list(analyzers) if analyzers else []
        self._lock = threading.Lock()

    @property
    def analyzers(self) -> List[object]:
        return self._analyzers

    def snapshot(self) -> List[object]:
        with self._lock:
            return list(self._analyzers)

    def append(self, analyzer: object) -> None:
        with self._lock:
            self._analyzers.append(analyzer)

    def extend(self, analyzers: Iterable[object]) -> None:
        with self._lock:
            self._analyzers.extend(analyzers)

    def insert(self, index: int, analyzer: object) -> None:
        with self._lock:
            self._analyzers.insert(index, analyzer)

    def remove(self, analyzer: object) -> None:
        with self._lock:
            self._analyzers.remove(analyzer)

    def pop(self, index: int = -1) -> object:
        with self._lock:
            return self._analyzers.pop(index)

    def clear(self) -> None:
        with self._lock:
            self._analyzers.clear()

    def replace(self, analyzers: Iterable[object]) -> None:
        with self._lock:
            self._analyzers = list(analyzers)

    def set_enabled(self, name: str, enabled: bool) -> bool:
        changed = False
        with self._lock:
            for analyzer in self._analyzers:
                analyzer_name = getattr(analyzer, "name", analyzer.__class__.__name__)
                if analyzer_name == name:
                    if hasattr(analyzer, "enabled"):
                        setattr(analyzer, "enabled", enabled)
                        changed = True
        return changed

    def has_any(self) -> bool:
        with self._lock:
            return bool(self._analyzers)

    def run(self, frame: np.ndarray, config: EngineConfig) -> Dict[str, object]:
        results: Dict[str, object] = {}
        for analyzer in self.snapshot():
            if hasattr(analyzer, "enabled") and not getattr(analyzer, "enabled"):
                continue
            name = getattr(analyzer, "name", analyzer.__class__.__name__)
            results[name] = analyzer.analyze(frame, config)
        return results

    @contextmanager
    def locked(self) -> Iterator[List[object]]:
        with self._lock:
            yield self._analyzers


class FilterPipeline:
    def __init__(self, filters: Optional[Iterable[object]] = None) -> None:
        self._filters: List[object] = list(filters) if filters else []
        self._lock = threading.Lock()
        # Cache de conversiones comunes para evitar conversiones redundantes
        # Estructura: {(conversion_code, frame_shape, frame_dtype): converted_frame}
        self._conversion_cache: Dict[Tuple[int, Tuple, np.dtype], np.ndarray] = {}
        # ID del frame actual para invalidar cache cuando cambia el frame
        self._current_frame_id: Optional[int] = None

    @property
    def filters(self) -> List[object]:
        return self._filters

    def snapshot(self) -> List[object]:
        with self._lock:
            return list(self._filters)

    def append(self, filter_obj: object) -> None:
        with self._lock:
            self._filters.append(filter_obj)

    def extend(self, filters: Iterable[object]) -> None:
        with self._lock:
            self._filters.extend(filters)

    def insert(self, index: int, filter_obj: object) -> None:
        with self._lock:
            self._filters.insert(index, filter_obj)

    def remove(self, filter_obj: object) -> None:
        with self._lock:
            self._filters.remove(filter_obj)

    def pop(self, index: int = -1) -> object:
        with self._lock:
            return self._filters.pop(index)

    def clear(self) -> None:
        with self._lock:
            self._filters.clear()

    def replace(self, filters: Iterable[object]) -> None:
        with self._lock:
            self._filters = list(filters)

    def set_enabled(self, name: str, enabled: bool) -> bool:
        changed = False
        with self._lock:
            for filter_obj in self._filters:
                filter_name = getattr(filter_obj, "name", filter_obj.__class__.__name__)
                if filter_name == name:
                    if hasattr(filter_obj, "enabled"):
                        setattr(filter_obj, "enabled", enabled)
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

    def apply(
        self, frame: np.ndarray, config: EngineConfig, analysis: Optional[dict] = None
    ) -> np.ndarray:
        # Optimización: si no hay filtros activos, retornar el frame original sin copias
        filters = self.snapshot()
        active_filters = [
            f for f in filters
            if not (hasattr(f, "enabled") and not getattr(f, "enabled"))
        ]
        
        if not active_filters:
            return frame
        
        # Limpiar cache de conversiones al inicio de cada frame
        # El cache global se maneja automáticamente por frame_id
        from ..adapters.filters.conversion_cache import clear_conversion_cache
        clear_conversion_cache()
        
        # Aplicar filtros secuencialmente
        # Nota: Cada filtro puede crear su propia copia si es necesario,
        # pero evitamos pasar el frame a través del pipeline si no hay filtros activos
        # Los filtros ahora usan el cache global de conversiones para evitar
        # conversiones redundantes cuando múltiples filtros necesitan la misma conversión
        processed = frame
        for filter_obj in active_filters:
            processed = filter_obj.apply(processed, config, analysis)
        
        return processed

    @contextmanager
    def locked(self) -> Iterator[List[object]]:
        with self._lock:
            yield self._filters
