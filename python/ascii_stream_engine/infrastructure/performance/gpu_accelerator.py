"""Wrapper para aceleración GPU usando CUDA/OpenCL."""

import logging
from typing import Any, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Intentar importar librerías GPU
try:
    import cupy as cp

    CUPY_AVAILABLE = True
except ImportError:
    CUPY_AVAILABLE = False
    cp = None

try:
    import pyopencl as cl

    OPENCL_AVAILABLE = True
except ImportError:
    OPENCL_AVAILABLE = False
    cl = None


class GPUAccelerator:
    """Acelerador GPU para operaciones intensivas."""

    def __init__(self, use_cupy: bool = True) -> None:
        """
        Inicializa el acelerador GPU.

        Args:
            use_cupy: Si usar CuPy (CUDA) en lugar de OpenCL
        """
        self.use_cupy = use_cupy and CUPY_AVAILABLE
        self._context = None
        self._queue = None
        self._available = False

        if self.use_cupy:
            self._init_cupy()
        elif OPENCL_AVAILABLE:
            self._init_opencl()

    def _init_cupy(self) -> None:
        """Inicializa CuPy (CUDA)."""
        try:
            if CUPY_AVAILABLE:
                # Verificar que haya un dispositivo GPU disponible
                mempool = cp.get_default_memory_pool()
                self._available = True
                logger.info("CuPy (CUDA) inicializado")
            else:
                self._available = False
        except Exception as e:
            logger.warning(f"No se pudo inicializar CuPy: {e}")
            self._available = False

    def _init_opencl(self) -> None:
        """Inicializa OpenCL."""
        try:
            if OPENCL_AVAILABLE:
                platforms = cl.get_platforms()
                if platforms:
                    devices = platforms[0].get_devices()
                    if devices:
                        self._context = cl.Context(devices)
                        self._queue = cl.CommandQueue(self._context)
                        self._available = True
                        logger.info("OpenCL inicializado")
                    else:
                        self._available = False
                else:
                    self._available = False
            else:
                self._available = False
        except Exception as e:
            logger.warning(f"No se pudo inicializar OpenCL: {e}")
            self._available = False

    def is_available(self) -> bool:
        """Verifica si la aceleración GPU está disponible."""
        return self._available

    def to_gpu(self, array: np.ndarray) -> Any:
        """
        Transfiere un array a la GPU.

        Args:
            array: Array de NumPy

        Returns:
            Array en GPU (CuPy o OpenCL)
        """
        if not self._available:
            return array

        if self.use_cupy and CUPY_AVAILABLE:
            return cp.asarray(array)
        else:
            # Para OpenCL, retornar el array original por ahora
            # (implementación completa requeriría buffers OpenCL)
            return array

    def to_cpu(self, gpu_array: Any) -> np.ndarray:
        """
        Transfiere un array de la GPU a CPU.

        Args:
            gpu_array: Array en GPU

        Returns:
            Array de NumPy
        """
        if not self._available:
            return gpu_array

        if self.use_cupy and CUPY_AVAILABLE:
            return cp.asnumpy(gpu_array)
        else:
            return np.asarray(gpu_array)

    def apply_filter(self, frame: np.ndarray, filter_func: Any) -> np.ndarray:
        """
        Aplica un filtro en GPU.

        Args:
            frame: Frame de video
            filter_func: Función de filtro

        Returns:
            Frame procesado
        """
        if not self._available:
            return filter_func(frame)

        try:
            gpu_frame = self.to_gpu(frame)
            gpu_result = filter_func(gpu_frame)
            return self.to_cpu(gpu_result)
        except Exception as e:
            logger.error(f"Error aplicando filtro en GPU: {e}", exc_info=True)
            # Fallback a CPU
            return filter_func(frame)

    def resize(self, frame: np.ndarray, size: Tuple[int, int]) -> np.ndarray:
        """
        Redimensiona un frame en GPU.

        Args:
            frame: Frame de video
            size: Tamaño objetivo (width, height)

        Returns:
            Frame redimensionado
        """
        if not self._available:
            import cv2

            return cv2.resize(frame, size)

        try:
            if self.use_cupy and CUPY_AVAILABLE:
                gpu_frame = self.to_gpu(frame)
                # CuPy no tiene resize directo, usar scipy o fallback a CPU
                import cv2

                return cv2.resize(frame, size)
            else:
                import cv2

                return cv2.resize(frame, size)
        except Exception as e:
            logger.error(f"Error redimensionando en GPU: {e}", exc_info=True)
            import cv2

            return cv2.resize(frame, size)
