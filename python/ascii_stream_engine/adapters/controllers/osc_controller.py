"""Controlador OSC usando python-osc."""

import logging
import threading
from typing import Any, Dict, Optional

from .base import BaseController

logger = logging.getLogger(__name__)

# Intentar importar python-osc
try:
    from pythonosc import osc_server, udp_client
    from pythonosc.dispatcher import Dispatcher
    from pythonosc.osc_message_builder import OscMessageBuilder

    OSC_AVAILABLE = True
except ImportError:
    OSC_AVAILABLE = False
    osc_server = None
    udp_client = None
    Dispatcher = None
    OscMessageBuilder = None


class OscController(BaseController):
    """Controlador OSC usando python-osc."""

    name = "osc_controller"

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5005,
        enabled: bool = True,
    ) -> None:
        """
        Inicializa el controlador OSC.

        Args:
            host: Dirección IP para recibir mensajes OSC
            port: Puerto para recibir mensajes OSC
            enabled: Si el controlador está habilitado
        """
        super().__init__(enabled)

        if not OSC_AVAILABLE:
            raise ImportError(
                "Se requiere 'python-osc' para usar OscController. "
                "Instala con: pip install python-osc"
            )

        self.host = host
        self.port = port
        self._server = None
        self._server_thread: Optional[threading.Thread] = None
        self._dispatcher = None
        self._stop_event = threading.Event()

    def _do_connect(self) -> None:
        """Inicia el servidor OSC."""
        self._dispatcher = Dispatcher()
        self._dispatcher.set_default_handler(self._osc_callback)

        self._server = osc_server.ThreadingOSCUDPServer((self.host, self.port), self._dispatcher)
        self._stop_event.clear()

        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()

        logger.info(f"Servidor OSC iniciado en {self.host}:{self.port}")

    def _osc_callback(self, address: str, *args) -> None:
        """
        Callback para mensajes OSC recibidos.

        Args:
            address: Dirección OSC del mensaje
            *args: Argumentos del mensaje
        """
        params: Dict[str, Any] = {
            "address": address,
            "args": list(args),
            "type": "osc",
        }

        # Extraer información común
        if args:
            params["value"] = args[0] if len(args) == 1 else args

        self._notify_callbacks(params)

        # Publicar evento con el comando basado en la dirección
        command = address.split("/")[-1] if "/" in address else address
        self._publish_event(command, params, params.get("value"))

    def _do_disconnect(self) -> None:
        """Detiene el servidor OSC."""
        if self._server:
            self._stop_event.set()
            self._server.shutdown()
            if self._server_thread:
                self._server_thread.join(timeout=2.0)
            self._server = None
            self._server_thread = None

    def send_message(
        self,
        address: str,
        *args,
        target_host: Optional[str] = None,
        target_port: Optional[int] = None,
    ) -> None:
        """
        Envía un mensaje OSC (opcional, para bidireccionalidad).

        Args:
            address: Dirección OSC
            *args: Argumentos del mensaje
            target_host: Host destino (None para usar self.host)
            target_port: Puerto destino (None para usar self.port)
        """
        if not OSC_AVAILABLE:
            logger.warning("python-osc no está disponible, no se puede enviar mensaje")
            return

        try:
            client = udp_client.SimpleUDPClient(
                target_host or self.host,
                target_port or self.port,
            )
            client.send_message(address, args)
        except Exception as e:
            logger.error(f"Error enviando mensaje OSC: {e}", exc_info=True)
