"""
Servidor de signaling para WebRTC.

Este módulo implementa un servidor HTTP simple que maneja el intercambio
de ofertas y respuestas SDP entre el servidor y los clientes WebRTC.
"""

import asyncio
import json
import logging
from typing import Dict, Optional, Set
from urllib.parse import parse_qs

try:
    from aiohttp import web
except ImportError:
    web = None  # type: ignore

logger = logging.getLogger(__name__)


class WebRTCSignalingServer:
    """
    Servidor de signaling HTTP para WebRTC.

    Maneja el intercambio de ofertas y respuestas SDP entre el servidor
    y los clientes que se conectan vía WebRTC.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        """
        Inicializa el servidor de signaling.

        Args:
            host: Dirección IP donde escuchar (default: "0.0.0.0" para todas las interfaces)
            port: Puerto donde escuchar (default: 8080)
        """
        if web is None:
            raise ImportError("aiohttp no está instalado. Instala con: pip install aiohttp")

        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[asyncio.Thread] = None
        self._pending_offers: Dict[str, Dict] = {}
        self._pending_answers: Dict[str, Dict] = {}
        self._connected_peers: Set[str] = set()

        # Configurar rutas
        self.app.router.add_post("/offer", self.handle_offer)
        self.app.router.add_post("/answer", self.handle_answer)
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_get("/", self.handle_index)

    async def handle_offer(self, request: web.Request) -> web.Response:
        """
        Maneja una oferta SDP del cliente.

        Args:
            request: Request HTTP con la oferta SDP en el body

        Returns:
            Response HTTP con la respuesta del servidor
        """
        try:
            data = await request.json()
            offer = data.get("sdp")
            offer_type = data.get("type", "offer")
            peer_id = data.get("peer_id", "default")

            if not offer:
                return web.json_response({"error": "Missing 'sdp' field"}, status=400)

            logger.info(f"Received offer from peer {peer_id}")

            # Guardar la oferta para que el servidor WebRTC la procese
            self._pending_offers[peer_id] = {
                "sdp": offer,
                "type": offer_type,
                "peer_id": peer_id,
            }

            # Retornar que la oferta fue recibida
            # El servidor WebRTC generará la respuesta
            return web.json_response({"status": "offer_received", "peer_id": peer_id})

        except Exception as e:
            logger.error(f"Error handling offer: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def handle_answer(self, request: web.Request) -> web.Response:
        """
        Maneja una respuesta SDP del cliente (para peer-to-peer).

        Args:
            request: Request HTTP con la respuesta SDP en el body

        Returns:
            Response HTTP con la respuesta del servidor
        """
        try:
            data = await request.json()
            answer = data.get("sdp")
            peer_id = data.get("peer_id", "default")

            if not answer:
                return web.json_response({"error": "Missing 'sdp' field"}, status=400)

            logger.info(f"Received answer from peer {peer_id}")

            # Guardar la respuesta
            self._pending_answers[peer_id] = {"sdp": answer, "peer_id": peer_id}

            return web.json_response({"status": "answer_received", "peer_id": peer_id})

        except Exception as e:
            logger.error(f"Error handling answer: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def handle_health(self, request: web.Request) -> web.Response:
        """Endpoint de health check."""
        return web.json_response({"status": "ok", "peers": len(self._connected_peers)})

    async def handle_index(self, request: web.Request) -> web.Response:
        """Endpoint raíz que retorna información del servidor."""
        return web.json_response(
            {
                "service": "WebRTC Signaling Server",
                "version": "1.0",
                "endpoints": {
                    "offer": "/offer",
                    "answer": "/answer",
                    "health": "/health",
                },
            }
        )

    def get_pending_offer(self, peer_id: str = "default") -> Optional[Dict]:
        """
        Obtiene una oferta pendiente para un peer.

        Args:
            peer_id: ID del peer

        Returns:
            Diccionario con la oferta o None si no hay oferta pendiente
        """
        return self._pending_offers.pop(peer_id, None)

    def set_answer(self, peer_id: str, answer: Dict) -> None:
        """
        Establece una respuesta SDP para un peer.

        Args:
            peer_id: ID del peer
            answer: Diccionario con la respuesta SDP
        """
        self._pending_answers[peer_id] = answer

    def get_answer(self, peer_id: str = "default") -> Optional[Dict]:
        """
        Obtiene una respuesta pendiente para un peer.

        Args:
            peer_id: ID del peer

        Returns:
            Diccionario con la respuesta o None si no hay respuesta pendiente
        """
        return self._pending_answers.pop(peer_id, None)

    def mark_peer_connected(self, peer_id: str) -> None:
        """Marca un peer como conectado."""
        self._connected_peers.add(peer_id)

    def mark_peer_disconnected(self, peer_id: str) -> None:
        """Marca un peer como desconectado."""
        self._connected_peers.discard(peer_id)

    def start(self) -> None:
        """Inicia el servidor de signaling en un hilo separado."""
        if self.runner is not None:
            logger.warning("Signaling server already started")
            return

        def run_server():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._start_server())

        import threading

        self._thread = threading.Thread(target=run_server, daemon=True)
        self._thread.start()

        # Esperar un poco para que el servidor se inicie
        import time

        time.sleep(0.5)

    async def _start_server(self) -> None:
        """Inicia el servidor de signaling (async)."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        logger.info(f"WebRTC signaling server started on http://{self.host}:{self.port}")

    def stop(self) -> None:
        """Detiene el servidor de signaling."""
        if self.runner is None:
            return

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._stop_server(), self._loop)

        # Esperar a que el hilo termine
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    async def _stop_server(self) -> None:
        """Detiene el servidor de signaling (async)."""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        logger.info("WebRTC signaling server stopped")
