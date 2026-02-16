"""Sensor de profundidad para cámaras de profundidad (RealSense, Kinect, etc.)."""

import logging
from typing import Any, Dict, Optional

import numpy as np

from .base import BaseSensor

logger = logging.getLogger(__name__)

# Intentar importar librerías de profundidad
try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except ImportError:
    REALSENSE_AVAILABLE = False
    rs = None


class DepthSensor(BaseSensor):
    """Sensor de profundidad usando Intel RealSense u otras cámaras de profundidad."""

    name = "depth_sensor"
    sensor_type = "depth"

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        enabled: bool = True,
    ) -> None:
        """
        Inicializa el sensor de profundidad.

        Args:
            width: Ancho de la imagen de profundidad
            height: Alto de la imagen de profundidad
            fps: Frames por segundo
            enabled: Si el sensor está habilitado
        """
        super().__init__(enabled)

        if not REALSENSE_AVAILABLE:
            logger.warning(
                "Se requiere 'pyrealsense2' para usar DepthSensor. "
                "Instala con: pip install pyrealsense2"
            )

        self.width = width
        self.height = height
        self.fps = fps
        self._pipeline = None
        self._config = None
        self._last_depth_frame: Optional[np.ndarray] = None

    def _do_is_available(self) -> bool:
        """Verifica si el sensor de profundidad está disponible."""
        if not REALSENSE_AVAILABLE:
            return False

        try:
            ctx = rs.context()
            devices = ctx.query_devices()
            return len(devices) > 0
        except Exception:
            return False

    def _do_read(self) -> Dict[str, Any]:
        """Lee datos de profundidad."""
        if not REALSENSE_AVAILABLE:
            return {"error": "pyrealsense2 no está disponible"}

        if self._pipeline is None:
            self._initialize_pipeline()

        if self._pipeline is None:
            return {"error": "No se pudo inicializar el pipeline de profundidad"}

        try:
            frames = self._pipeline.wait_for_frames()
            depth_frame = frames.get_depth_frame()

            if depth_frame:
                depth_image = np.asanyarray(depth_frame.get_data())
                self._last_depth_frame = depth_image

                # Calcular métricas básicas
                valid_pixels = depth_image[depth_image > 0]
                if len(valid_pixels) > 0:
                    mean_depth = float(np.mean(valid_pixels))
                    min_depth = float(np.min(valid_pixels))
                    max_depth = float(np.max(valid_pixels))
                else:
                    mean_depth = min_depth = max_depth = 0.0

                return {
                    "depth_frame": depth_image,
                    "mean_depth": mean_depth,
                    "min_depth": min_depth,
                    "max_depth": max_depth,
                    "width": self.width,
                    "height": self.height,
                }
            else:
                return {"error": "No se recibió frame de profundidad"}
        except Exception as e:
            logger.error(f"Error leyendo sensor de profundidad: {e}", exc_info=True)
            return {"error": str(e)}

    def _initialize_pipeline(self) -> None:
        """Inicializa el pipeline de RealSense."""
        try:
            self._pipeline = rs.pipeline()
            self._config = rs.config()

            # Configurar streams
            self._config.enable_stream(rs.stream.depth, self.width, self.height, rs.format.z16, self.fps)
            self._config.enable_stream(rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps)

            # Iniciar pipeline
            self._pipeline.start(self._config)
            logger.info("Pipeline de RealSense iniciado")
        except Exception as e:
            logger.error(f"Error inicializando pipeline de RealSense: {e}", exc_info=True)
            self._pipeline = None
            self._config = None

    def _do_calibrate(self) -> bool:
        """Calibra el sensor de profundidad."""
        # Calibración básica: leer algunos frames para estabilizar
        try:
            for _ in range(10):
                self.read()
            return True
        except Exception as e:
            logger.error(f"Error en calibración de profundidad: {e}", exc_info=True)
            return False

    def close(self) -> None:
        """Cierra el pipeline de profundidad."""
        if self._pipeline:
            try:
                self._pipeline.stop()
            except Exception:
                pass
            self._pipeline = None
            self._config = None

