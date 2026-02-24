"""
Composite OutputSink que permite escribir a múltiples backends simultáneamente.

Útil para enviar el mismo stream a múltiples destinos (ej: UDP + NDI + archivo).
"""

import logging
from typing import List, Optional, Tuple

from ...domain.config import EngineConfig
from ...domain.types import RenderFrame
from ...ports.output_capabilities import (
    OutputCapabilities,
    OutputCapability,
    OutputQuality,
)
from ...ports.outputs import OutputSink

logger = logging.getLogger(__name__)


class CompositeOutputSink:
    """
    Backend de salida compuesto que escribe a múltiples backends simultáneamente.

    Permite enviar el mismo frame a varios backends (ej: UDP, NDI, archivo).
    Si un backend falla, los demás continúan funcionando.
    """

    def __init__(self, sinks: List[OutputSink]) -> None:
        """
        Inicializa el composite sink con una lista de backends.

        Args:
            sinks: Lista de backends de salida a los que escribir
        """
        if not sinks:
            raise ValueError("Debe proporcionar al menos un sink")
        self._sinks = sinks
        self._is_open = False

    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        """
        Abre todos los backends de salida.

        Si algún backend falla al abrir, se registra un error pero se continúa
        con los demás.
        """
        self.close()
        opened_sinks = []
        for i, sink in enumerate(self._sinks):
            try:
                sink.open(config, output_size)
                opened_sinks.append(sink)
                logger.debug(f"Sink {i} ({type(sink).__name__}) abierto correctamente")
            except Exception as e:
                logger.error(
                    f"Error al abrir sink {i} ({type(sink).__name__}): {e}. "
                    "Continuando con los demás sinks."
                )

        if not opened_sinks:
            raise RuntimeError("No se pudo abrir ningún sink")
        self._is_open = True

    def write(self, frame: RenderFrame) -> None:
        """
        Escribe el frame a todos los backends abiertos.

        Si un backend falla, se registra un error pero se continúa con los demás.
        """
        if not self._is_open:
            logger.warning("Intento de escribir a composite sink cerrado")
            return

        for i, sink in enumerate(self._sinks):
            try:
                if hasattr(sink, "is_open") and not sink.is_open():
                    continue
                sink.write(frame)
            except Exception as e:
                logger.warning(
                    f"Error al escribir a sink {i} ({type(sink).__name__}): {e}. "
                    "Continuando con los demás sinks."
                )

    def close(self) -> None:
        """Cierra todos los backends de salida."""
        for i, sink in enumerate(self._sinks):
            try:
                sink.close()
            except Exception as e:
                logger.warning(f"Error al cerrar sink {i} ({type(sink).__name__}): {e}")
        self._is_open = False

    def get_capabilities(self) -> OutputCapabilities:
        """
        Obtiene las capacidades combinadas de todos los backends.

        Las capacidades se combinan usando OR lógico (si algún backend tiene
        una capacidad, el composite la tiene). La latencia es la máxima de
        todos los backends.
        """
        combined_capabilities = OutputCapability(0)
        max_latency = 0.0
        all_qualities = set()
        max_clients = None
        min_bitrate = None
        max_bitrate = None
        protocol_names = []

        for sink in self._sinks:
            if hasattr(sink, "get_capabilities"):
                try:
                    caps = sink.get_capabilities()
                    combined_capabilities |= caps.capabilities
                    if caps.estimated_latency_ms:
                        max_latency = max(max_latency, caps.estimated_latency_ms)
                    all_qualities.update(caps.supported_qualities)
                    if caps.max_clients is not None:
                        if max_clients is None:
                            max_clients = caps.max_clients
                        else:
                            max_clients = max(max_clients, caps.max_clients)
                    if caps.protocol_name:
                        protocol_names.append(caps.protocol_name)
                except Exception as e:
                    logger.warning(
                        f"Error al obtener capacidades de sink {type(sink).__name__}: {e}"
                    )

        return OutputCapabilities(
            capabilities=combined_capabilities,
            estimated_latency_ms=max_latency if max_latency > 0 else None,
            supported_qualities=list(all_qualities) if all_qualities else None,
            max_clients=max_clients,
            min_bitrate=min_bitrate,
            max_bitrate=max_bitrate,
            protocol_name=", ".join(protocol_names) if protocol_names else "Composite",
            metadata={
                "num_sinks": len(self._sinks),
                "sink_types": [type(s).__name__ for s in self._sinks],
            },
        )

    def is_open(self) -> bool:
        """Verifica si al menos un backend está abierto."""
        if not self._is_open:
            return False
        # Verificar si al menos un sink está abierto
        for sink in self._sinks:
            if hasattr(sink, "is_open"):
                if sink.is_open():
                    return True
            else:
                # Si no tiene método is_open, asumimos que está abierto si
                # el composite está marcado como abierto
                return True
        return False

    def get_estimated_latency_ms(self) -> Optional[float]:
        """
        Obtiene la latencia estimada máxima de todos los backends.

        La latencia del composite es la máxima de todos los backends, ya que
        el frame debe escribirse a todos antes de continuar.
        """
        max_latency = 0.0
        for sink in self._sinks:
            if hasattr(sink, "get_estimated_latency_ms"):
                try:
                    latency = sink.get_estimated_latency_ms()
                    if latency is not None:
                        max_latency = max(max_latency, latency)
                except Exception:
                    pass
        return max_latency if max_latency > 0 else None

    def supports_multiple_clients(self) -> bool:
        """
        Indica si al menos un backend soporta múltiples clientes.

        Si algún backend soporta múltiples clientes, el composite también.
        """
        for sink in self._sinks:
            if hasattr(sink, "supports_multiple_clients"):
                try:
                    if sink.supports_multiple_clients():
                        return True
                except Exception:
                    pass
        return False

    def add_sink(self, sink: OutputSink) -> None:
        """
        Agrega un nuevo sink al composite.

        Args:
            sink: Backend de salida a agregar

        Raises:
            RuntimeError: Si se intenta agregar un sink mientras está abierto
        """
        if self._is_open:
            raise RuntimeError(
                "No se puede agregar un sink mientras el composite está abierto. "
                "Cierre primero el composite."
            )
        self._sinks.append(sink)

    def remove_sink(self, sink: OutputSink) -> None:
        """
        Remueve un sink del composite.

        Args:
            sink: Backend de salida a remover

        Raises:
            RuntimeError: Si se intenta remover un sink mientras está abierto
            ValueError: Si el sink no está en la lista
        """
        if self._is_open:
            raise RuntimeError(
                "No se puede remover un sink mientras el composite está abierto. "
                "Cierre primero el composite."
            )
        if sink not in self._sinks:
            raise ValueError("El sink no está en la lista")
        self._sinks.remove(sink)
        if not self._sinks:
            raise ValueError("No se puede remover el último sink")
