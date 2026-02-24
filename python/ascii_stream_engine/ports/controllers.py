"""Protocolo para controladores externos (MIDI, OSC, etc.)."""

from typing import Any, Callable, Dict, Optional, Protocol


class Controller(Protocol):
    """Protocolo para controladores externos."""

    def connect(self) -> None:
        """Conecta el controlador."""
        ...

    def disconnect(self) -> None:
        """Desconecta el controlador."""
        ...

    def is_connected(self) -> bool:
        """
        Verifica si el controlador está conectado.

        Returns:
            True si está conectado
        """
        ...

    def on_message(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Registra un callback para recibir mensajes.

        Args:
            callback: Función que será llamada con cada mensaje
        """
        ...
