"""Protocolos para procesadores de frames (filters y analyzers)."""

from typing import Optional, Protocol, Union, runtime_checkable

import numpy as np

from ..domain.config import EngineConfig


class FrameProcessor(Protocol):
    """Protocolo base para procesadores de frames (filters y analyzers).

    Este protocolo define la interfaz común que deben implementar todos los
    procesadores de frames, ya sean filters (que modifican el frame) o analyzers
    (que extraen información del frame).
    """

    name: str
    """Nombre único del procesador."""

    enabled: bool
    """Indica si el procesador está habilitado."""

    def process(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        context: Optional[dict] = None,
    ) -> Union[np.ndarray, dict]:
        """
        Procesa un frame.

        Args:
            frame: Frame de video a procesar
            config: Configuración del engine
            context: Contexto adicional (puede incluir análisis previos, etc.)

        Returns:
            Para filters: Frame procesado (np.ndarray)
            Para analyzers: Diccionario con resultados del análisis (dict)
        """
        ...


class Filter(Protocol):
    """Protocolo específico para filters que modifican frames.

    Los filters toman un frame y lo transforman, retornando un nuevo frame
    procesado.
    """

    name: str
    enabled: bool

    def apply(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        analysis: Optional[dict] = None,
    ) -> np.ndarray:
        """
        Aplica el filtro al frame.

        Args:
            frame: Frame de video a filtrar
            config: Configuración del engine
            analysis: Resultados de análisis previos (opcional)

        Returns:
            Frame procesado
        """
        ...


class Analyzer(Protocol):
    """Protocolo específico para analyzers que extraen información de frames.

    Los analyzers analizan un frame y extraen información/metadata, retornando
    un diccionario con los resultados.
    """

    name: str
    enabled: bool

    def analyze(
        self,
        frame: np.ndarray,
        config: EngineConfig,
    ) -> dict:
        """
        Analiza el frame y extrae información.

        Args:
            frame: Frame de video a analizar
            config: Configuración del engine

        Returns:
            Diccionario con resultados del análisis
        """
        ...


@runtime_checkable
class ProcessorPipeline(Protocol):
    """Protocolo para pipelines de procesadores.

    Un pipeline agrupa múltiples procesadores y los ejecuta en secuencia.
    """

    def add(self, processor: FrameProcessor) -> None:
        """Agrega un procesador al pipeline."""
        ...

    def remove(self, processor: FrameProcessor) -> None:
        """Remueve un procesador del pipeline."""
        ...

    def process(
        self,
        frame: np.ndarray,
        config: EngineConfig,
        context: Optional[dict] = None,
    ) -> Union[np.ndarray, dict]:
        """
        Procesa un frame a través de todos los procesadores del pipeline.

        Args:
            frame: Frame de video a procesar
            config: Configuración del engine
            context: Contexto adicional

        Returns:
            Resultado del procesamiento (frame procesado o resultados de análisis)
        """
        ...

    def has_any(self) -> bool:
        """
        Verifica si hay procesadores en el pipeline.

        Returns:
            True si hay al menos un procesador, False en caso contrario
        """
        ...
