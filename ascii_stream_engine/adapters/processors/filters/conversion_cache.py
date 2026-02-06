"""
Módulo de cache de conversiones para optimizar pipelines.

Este módulo proporciona un cache compartido de conversiones de color comunes
para evitar conversiones redundantes cuando múltiples filtros necesitan la misma
conversión en el mismo frame.
"""
import cv2
from typing import Dict, Optional, Tuple
import numpy as np


class ConversionCache:
    """
    Cache de conversiones de color para optimizar pipelines.
    
    Este cache permite que múltiples filtros compartan conversiones comunes
    (ej: BGR2GRAY) sin tener que convertir el mismo frame múltiples veces.
    """
    
    def __init__(self):
        # Cache: {(frame_id, conversion_code): converted_frame}
        self._cache: Dict[Tuple[int, int], np.ndarray] = {}
        self._current_frame_id: Optional[int] = None
    
    def get_conversion(
        self, 
        frame: np.ndarray, 
        conversion_code: int,
        frame_id: Optional[int] = None
    ) -> np.ndarray:
        """
        Obtiene una conversión cacheada o la realiza y la cachea.
        
        Args:
            frame: Frame original
            conversion_code: Código de conversión de OpenCV (ej: cv2.COLOR_BGR2GRAY)
            frame_id: ID único del frame (opcional, se usa id(frame) si no se proporciona)
            
        Returns:
            Frame convertido (cacheado o nuevo)
        """
        if frame_id is None:
            frame_id = id(frame)
        
        # Invalidar cache si cambió el frame
        if self._current_frame_id != frame_id:
            self._cache.clear()
            self._current_frame_id = frame_id
        
        cache_key = (frame_id, conversion_code)
        
        # Verificar si ya existe en cache
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Realizar conversión y cachearla
        converted = cv2.cvtColor(frame, conversion_code)
        self._cache[cache_key] = converted
        return converted
    
    def clear(self) -> None:
        """Limpia el cache de conversiones."""
        self._cache.clear()
        self._current_frame_id = None
    
    def has_conversion(self, frame_id: int, conversion_code: int) -> bool:
        """Verifica si una conversión está en cache."""
        return (frame_id, conversion_code) in self._cache


# Instancia global del cache (thread-safe para uso en el mismo thread)
_global_cache = ConversionCache()


def get_cached_conversion(
    frame: np.ndarray, 
    conversion_code: int,
    frame_id: Optional[int] = None
) -> np.ndarray:
    """
    Función helper para obtener una conversión cacheada.
    
    Args:
        frame: Frame original
        conversion_code: Código de conversión de OpenCV
        frame_id: ID único del frame (opcional)
        
    Returns:
        Frame convertido (cacheado o nuevo)
    """
    return _global_cache.get_conversion(frame, conversion_code, frame_id)


def clear_conversion_cache() -> None:
    """Limpia el cache global de conversiones."""
    _global_cache.clear()

