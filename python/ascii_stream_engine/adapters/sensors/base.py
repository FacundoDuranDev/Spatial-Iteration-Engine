"""Clase base para sensores."""

import logging
import time
from typing import Any, Dict

from ...domain.events import SensorEvent

logger = logging.getLogger(__name__)


class BaseSensor:
    """Clase base para implementaciones de sensores."""

    name = "base_sensor"
    sensor_type = "generic"

    def __init__(self, enabled: bool = True) -> None:
        """
        Inicializa el sensor.

        Args:
            enabled: Si el sensor está habilitado
        """
        self.enabled = enabled
        self._calibrated = False
        self._event_bus = None

    def read(self) -> Dict[str, Any]:
        """
        Lee datos del sensor.

        Returns:
            Diccionario con datos del sensor
        """
        if not self.enabled:
            return {}

        if not self.is_available():
            logger.warning(f"Sensor '{self.name}' no está disponible")
            return {}

        try:
            data = self._do_read()
            self._publish_event(data)
            return data
        except Exception as e:
            logger.error(f"Error leyendo sensor '{self.name}': {e}", exc_info=True)
            return {}

    def calibrate(self) -> bool:
        """
        Calibra el sensor.

        Returns:
            True si la calibración fue exitosa
        """
        if not self.is_available():
            logger.warning(f"Sensor '{self.name}' no está disponible para calibrar")
            return False

        try:
            self._calibrated = self._do_calibrate()
            if self._calibrated:
                logger.info(f"Sensor '{self.name}' calibrado exitosamente")
            return self._calibrated
        except Exception as e:
            logger.error(f"Error calibrando sensor '{self.name}': {e}", exc_info=True)
            return False

    def is_available(self) -> bool:
        """
        Verifica si el sensor está disponible.

        Returns:
            True si el sensor está disponible
        """
        return self._do_is_available()

    def is_calibrated(self) -> bool:
        """Verifica si el sensor está calibrado."""
        return self._calibrated

    def set_event_bus(self, event_bus) -> None:
        """Establece el bus de eventos para publicar eventos."""
        self._event_bus = event_bus

    def _publish_event(self, data: Dict[str, Any]) -> None:
        """
        Publica un evento de sensor.

        Args:
            data: Datos del sensor
        """
        if self._event_bus:
            event = SensorEvent(
                sensor_name=self.name,
                sensor_data=data,
                sensor_type=self.sensor_type,
            )
            self._event_bus.publish(event, "sensor_data")

    def _do_read(self) -> Dict[str, Any]:
        """Implementación específica de lectura (debe ser sobrescrita)."""
        raise NotImplementedError("_do_read debe ser implementado por la subclase")

    def _do_calibrate(self) -> bool:
        """Implementación específica de calibración (debe ser sobrescrita)."""
        return True  # Por defecto, calibración exitosa

    def _do_is_available(self) -> bool:
        """Implementación específica de verificación de disponibilidad (debe ser sobrescrita)."""
        return True  # Por defecto, disponible
