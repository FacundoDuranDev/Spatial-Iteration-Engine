"""Gestor de buffer de frames."""

import logging
import threading
import time
from collections import deque
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class FrameBuffer:
    """Gestiona un buffer thread-safe de frames con timestamps."""

    def __init__(self, max_size: int = 2) -> None:
        """
        Inicializa el buffer de frames.

        Args:
            max_size: Tamaño máximo del buffer
        """
        self._max_size = max_size
        self._buffer: deque = deque(maxlen=max_size)
        self._lock = threading.Lock()

    @property
    def max_size(self) -> int:
        """Obtiene el tamaño máximo del buffer."""
        return self._max_size

    def set_max_size(self, max_size: int) -> None:
        """
        Establece un nuevo tamaño máximo del buffer.

        Args:
            max_size: Nuevo tamaño máximo
        """
        with self._lock:
            self._max_size = max_size
            # Crear nuevo deque con el nuevo tamaño máximo
            old_buffer = list(self._buffer)
            self._buffer = deque(old_buffer, maxlen=max_size)

    def add(self, frame: np.ndarray, timestamp: Optional[float] = None) -> None:
        """
        Agrega un frame al buffer.

        Args:
            frame: Frame a agregar
            timestamp: Timestamp del frame (si None, se usa time.time())
        """
        if timestamp is None:
            timestamp = time.time()

        with self._lock:
            self._buffer.append((frame, timestamp))

    def get_latest(self) -> Optional[Tuple[np.ndarray, float]]:
        """
        Obtiene el frame más reciente del buffer y lo remueve.

        Returns:
            Tupla (frame, timestamp) o None si el buffer está vacío
        """
        with self._lock:
            if not self._buffer:
                return None
            frame, timestamp = self._buffer.pop()
            # Limpiar el buffer para mantener solo el más reciente
            self._buffer.clear()
            return frame, timestamp

    def peek_latest(self) -> Optional[Tuple[np.ndarray, float]]:
        """
        Obtiene el frame más reciente sin removerlo del buffer.

        Returns:
            Tupla (frame, timestamp) o None si el buffer está vacío
        """
        with self._lock:
            if not self._buffer:
                return None
            return self._buffer[-1]

    def clear(self) -> None:
        """Limpia el buffer."""
        with self._lock:
            self._buffer.clear()

    def size(self) -> int:
        """
        Obtiene el tamaño actual del buffer.

        Returns:
            Número de frames en el buffer
        """
        with self._lock:
            return len(self._buffer)

    def is_empty(self) -> bool:
        """
        Verifica si el buffer está vacío.

        Returns:
            True si está vacío, False en caso contrario
        """
        with self._lock:
            return len(self._buffer) == 0

    def is_full(self) -> bool:
        """
        Verifica si el buffer está lleno.

        Returns:
            True si está lleno, False en caso contrario
        """
        with self._lock:
            return len(self._buffer) >= self._max_size
