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


class OutputLatency(Enum):
    """Niveles de latencia estimados."""

    VERY_HIGH = "very_high"  # >500ms
    HIGH = "high"  # 200-500ms
    MEDIUM = "medium"  # 100-200ms
    LOW = "low"  # 50-100ms
    VERY_LOW = "very_low"  # <50ms


class OutputCapabilities:
    """Información de capacidades de un backend de salida."""

    def __init__(
        self,
        capabilities: OutputCapability,
        estimated_latency_ms: Optional[float] = None,
        supported_qualities: Optional[list[OutputQuality]] = None,
        max_clients: Optional[int] = None,
        min_bitrate: Optional[str] = None,
        max_bitrate: Optional[str] = None,
        protocol_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Inicializa las capacidades de un backend.

        Args:
            capabilities: Flags de capacidades soportadas
            estimated_latency_ms: Latencia estimada en milisegundos
            supported_qualities: Lista de calidades soportadas
            max_clients: Número máximo de clientes simultáneos (None = ilimitado)
            min_bitrate: Bitrate mínimo soportado (ej: "500k")
            max_bitrate: Bitrate máximo soportado (ej: "10m")
            protocol_name: Nombre del protocolo (ej: "UDP", "NDI", "WebRTC")
            metadata: Metadatos adicionales específicos del backend
        """
        self.capabilities = capabilities
        self.estimated_latency_ms = estimated_latency_ms
        self.supported_qualities = supported_qualities or list(OutputQuality)
        self.max_clients = max_clients
        self.min_bitrate = min_bitrate
        self.max_bitrate = max_bitrate
        self.protocol_name = protocol_name
        self.metadata = metadata or {}

    def has_capability(self, capability: OutputCapability) -> bool:
        """Verifica si el backend tiene una capacidad específica."""
        return (self.capabilities & capability) == capability

    def get_latency_category(self) -> OutputLatency:
        """Obtiene la categoría de latencia basada en la latencia estimada."""
        if self.estimated_latency_ms is None:
            return OutputLatency.MEDIUM

        if self.estimated_latency_ms < 50:
            return OutputLatency.VERY_LOW
        elif self.estimated_latency_ms < 100:
            return OutputLatency.LOW
        elif self.estimated_latency_ms < 200:
            return OutputLatency.MEDIUM
        elif self.estimated_latency_ms < 500:
            return OutputLatency.HIGH
        else:
            return OutputLatency.VERY_HIGH

    def supports_quality(self, quality: OutputQuality) -> bool:
        """Verifica si el backend soporta un nivel de calidad específico."""
        return quality in self.supported_qualities

    def to_dict(self) -> Dict[str, Any]:
        """Convierte las capacidades a un diccionario."""
        return {
            "capabilities": list(self.capabilities),
            "estimated_latency_ms": self.estimated_latency_ms,
            "latency_category": self.get_latency_category().value,
            "supported_qualities": [q.value for q in self.supported_qualities],
            "max_clients": self.max_clients,
            "min_bitrate": self.min_bitrate,
            "max_bitrate": self.max_bitrate,
            "protocol_name": self.protocol_name,
            "metadata": self.metadata,
        }

