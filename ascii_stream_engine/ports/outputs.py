from typing import Optional, Protocol, Tuple

from ..domain.config import EngineConfig
from ..domain.types import RenderFrame
from .output_capabilities import OutputCapabilities


class OutputSink(Protocol):
    """
    Protocolo para backends de salida de frames.

    Define la interfaz que deben implementar todos los backends de salida,
    incluyendo métodos básicos de escritura y métodos opcionales para consultar
    capacidades y características del backend.
    """

    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        """
        Abre el backend de salida con la configuración especificada.

        Args:
            config: Configuración del engine
            output_size: Tamaño de salida (width, height)
        """
        ...

    def write(self, frame: RenderFrame) -> None:
        """
        Escribe un frame al backend de salida.

        Args:
            frame: Frame renderizado a escribir
        """
        ...

    def close(self) -> None:
        """Cierra el backend de salida y libera recursos."""
        ...

    def get_capabilities(self) -> OutputCapabilities:
        """
        Obtiene las capacidades del backend de salida.

        Este método es opcional pero recomendado. Si no se implementa,
        se puede usar un método por defecto que retorna capacidades básicas.

        Returns:
            OutputCapabilities: Información sobre las capacidades del backend
        """
        ...

    def is_open(self) -> bool:
        """
        Verifica si el backend está abierto y listo para escribir.

        Returns:
            bool: True si está abierto, False en caso contrario
        """
        ...

    def get_estimated_latency_ms(self) -> Optional[float]:
        """
        Obtiene la latencia estimada del backend en milisegundos.

        Returns:
            Latencia estimada en ms, o None si no se puede determinar
        """
        ...

    def supports_multiple_clients(self) -> bool:
        """
        Indica si el backend soporta múltiples clientes simultáneos.

        Returns:
            bool: True si soporta múltiples clientes, False en caso contrario
        """
        ...
