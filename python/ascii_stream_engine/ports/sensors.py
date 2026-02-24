"""Protocolo para sensores."""

from typing import Any, Dict, Protocol


class Sensor(Protocol):
    """Protocolo para sensores."""

    def read(self) -> Dict[str, Any]:
        """
        Lee datos del sensor.

        Returns:
            Diccionario con datos del sensor
        """
        ...

    def calibrate(self) -> bool:
        """
        Calibra el sensor.

        Returns:
            True si la calibración fue exitosa
        """
        ...

    def is_available(self) -> bool:
        """
        Verifica si el sensor está disponible.

        Returns:
            True si el sensor está disponible
        """
        ...
