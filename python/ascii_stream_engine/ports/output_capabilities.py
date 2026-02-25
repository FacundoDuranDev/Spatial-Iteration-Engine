"""Definición de capacidades de los backends de salida."""

from enum import Enum, Flag, auto
from typing import Any, Dict, Optional


class OutputCapability(Flag):
    """Capacidades que puede tener un backend de salida."""

    # Capacidades básicas
    STREAMING = auto()  # Soporta streaming en tiempo real
    RECORDING = auto()  # Soporta grabación a archivo
    MULTI_CLIENT = auto()  # Soporta múltiples clientes simultáneos
    BROADCAST = auto()  # Soporta broadcast (UDP broadcast, multicast, etc.)

    # Características de calidad
    HIGH_QUALITY = auto()  # Soporta alta calidad de video
    ADAPTIVE_QUALITY = auto()  # Puede adaptar calidad dinámicamente
    CUSTOM_BITRATE = auto()  # Permite configurar bitrate

    # Características de latencia
    LOW_LATENCY = auto()  # Optimizado para baja latencia
    ULTRA_LOW_LATENCY = auto()  # Latencia ultra baja (<100ms)

    # Características de protocolo
    UDP = auto()  # Soporta UDP
    TCP = auto()  # Soporta TCP
    HTTP = auto()  # Soporta HTTP/HTTPS
    RTSP = auto()  # Soporta RTSP
    NDI = auto()  # Soporta NDI
    WEBRTC = auto()  # Soporta WebRTC


class OutputQuality(Enum):
    """Niveles de calidad predefinidos."""

    LOW = "low"  # Baja calidad, alta velocidad
    MEDIUM = "medium"  # Calidad balanceada
    HIGH = "high"  # Alta calidad
    ULTRA = "ultra"  # Calidad máxima


class OutputCapabilities:
    """Información de capacidades de un backend de salida."""

    def __init__(
        self,
        capabilities: OutputCapability,
        supported_qualities: Optional[list[OutputQuality]] = None,
        max_clients: Optional[int] = None,
        min_bitrate: Optional[str] = None,
        max_bitrate: Optional[str] = None,
        protocol_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.capabilities = capabilities
        self.supported_qualities = supported_qualities or list(OutputQuality)
        self.max_clients = max_clients
        self.min_bitrate = min_bitrate
        self.max_bitrate = max_bitrate
        self.protocol_name = protocol_name
        self.metadata = metadata or {}

    def has_capability(self, capability: OutputCapability) -> bool:
        """Verifica si el backend tiene una capacidad específica."""
        return (self.capabilities & capability) == capability

    def supports_quality(self, quality: OutputQuality) -> bool:
        """Verifica si el backend soporta un nivel de calidad específico."""
        return quality in self.supported_qualities

    def to_dict(self) -> Dict[str, Any]:
        """Convierte las capacidades a un diccionario."""
        return {
            "capabilities": list(self.capabilities),
            "supported_qualities": [q.value for q in self.supported_qualities],
            "max_clients": self.max_clients,
            "min_bitrate": self.min_bitrate,
            "max_bitrate": self.max_bitrate,
            "protocol_name": self.protocol_name,
            "metadata": self.metadata,
        }
