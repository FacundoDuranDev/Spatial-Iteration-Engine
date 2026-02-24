"""Fusión de datos de múltiples sensores."""

import logging
import time
from typing import Any, Dict, List

from .base import BaseSensor

logger = logging.getLogger(__name__)


class SensorFusion(BaseSensor):
    """Fusiona datos de múltiples sensores."""

    name = "sensor_fusion"
    sensor_type = "fusion"

    def __init__(self, sensors: List[BaseSensor], enabled: bool = True) -> None:
        """
        Inicializa la fusión de sensores.

        Args:
            sensors: Lista de sensores a fusionar
            enabled: Si la fusión está habilitada
        """
        super().__init__(enabled)
        self._sensors = sensors
        self._fusion_strategy = "weighted_average"  # Por defecto

    def _do_is_available(self) -> bool:
        """Verifica si al menos un sensor está disponible."""
        return any(sensor.is_available() for sensor in self._sensors)

    def _do_read(self) -> Dict[str, Any]:
        """Lee y fusiona datos de todos los sensores."""
        all_data: Dict[str, Any] = {
            "timestamp": time.time(),
            "sensors": {},
            "fused": {},
        }

        # Leer de todos los sensores
        for sensor in self._sensors:
            if sensor.enabled and sensor.is_available():
                try:
                    data = sensor.read()
                    all_data["sensors"][sensor.name] = data
                except Exception as e:
                    logger.error(f"Error leyendo sensor '{sensor.name}': {e}", exc_info=True)

        # Aplicar estrategia de fusión
        if self._fusion_strategy == "weighted_average":
            all_data["fused"] = self._weighted_average_fusion(all_data["sensors"])
        elif self._fusion_strategy == "max":
            all_data["fused"] = self._max_fusion(all_data["sensors"])
        elif self._fusion_strategy == "min":
            all_data["fused"] = self._min_fusion(all_data["sensors"])
        else:
            all_data["fused"] = all_data["sensors"]

        return all_data

    def _weighted_average_fusion(self, sensor_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Fusiona datos usando promedio ponderado."""
        fused: Dict[str, Any] = {}
        numeric_keys = set()

        # Identificar claves numéricas
        for data in sensor_data.values():
            for key, value in data.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    numeric_keys.add(key)

        # Calcular promedios ponderados
        for key in numeric_keys:
            values = []
            for data in sensor_data.values():
                if key in data:
                    values.append(data[key])
            if values:
                fused[key] = sum(values) / len(values)

        return fused

    def _max_fusion(self, sensor_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Fusiona datos usando el máximo."""
        fused: Dict[str, Any] = {}
        numeric_keys = set()

        for data in sensor_data.values():
            for key, value in data.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    numeric_keys.add(key)

        for key in numeric_keys:
            values = []
            for data in sensor_data.values():
                if key in data:
                    values.append(data[key])
            if values:
                fused[key] = max(values)

        return fused

    def _min_fusion(self, sensor_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Fusiona datos usando el mínimo."""
        fused: Dict[str, Any] = {}
        numeric_keys = set()

        for data in sensor_data.values():
            for key, value in data.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    numeric_keys.add(key)

        for key in numeric_keys:
            values = []
            for data in sensor_data.values():
                if key in data:
                    values.append(data[key])
            if values:
                fused[key] = min(values)

        return fused

    def set_fusion_strategy(self, strategy: str) -> None:
        """
        Establece la estrategia de fusión.

        Args:
            strategy: Estrategia ("weighted_average", "max", "min")
        """
        if strategy in ["weighted_average", "max", "min"]:
            self._fusion_strategy = strategy
        else:
            logger.warning(f"Estrategia de fusión desconocida: {strategy}")

    def add_sensor(self, sensor: BaseSensor) -> None:
        """
        Agrega un sensor a la fusión.

        Args:
            sensor: Sensor a agregar
        """
        if sensor not in self._sensors:
            self._sensors.append(sensor)
            logger.debug(f"Sensor '{sensor.name}' agregado a la fusión")

    def remove_sensor(self, sensor_name: str) -> None:
        """
        Remueve un sensor de la fusión.

        Args:
            sensor_name: Nombre del sensor a remover
        """
        self._sensors = [s for s in self._sensors if s.name != sensor_name]
        logger.debug(f"Sensor '{sensor_name}' removido de la fusión")
