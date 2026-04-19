"""FastAPI app factory for the v3 web dashboard.

Mounts static files, registers /, /health, /ws routes. Returns a tuple
(app, auth_token) so the caller can print/QR the token.
"""
from __future__ import annotations

import logging
import secrets
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse

from .bridge import EngineBridge
from .ws import websocket_endpoint

logger = logging.getLogger("web_dashboard.app")

STATIC_DIR = Path(__file__).parent / "static"


def create_app(engine, auth_token: Optional[str] = None) -> tuple[FastAPI, str, EngineBridge]:
    """Create the FastAPI app wired to the given engine.

    Returns (app, auth_token, bridge). The bridge is exposed so the entry
    script can hold a reference (and so engine -> ws push can be wired
    in Phase B without going through app.state).
    """
    if auth_token is None:
        auth_token = secrets.token_hex(8)

    bridge = EngineBridge(engine)

    app = FastAPI(title="SIE web dashboard v3", version="3.0.0")
    app.state.bridge = bridge
    app.state.auth_token = auth_token

    # Mount static AFTER endpoint registration so /static catches everything else.
    from fastapi.staticfiles import StaticFiles

    @app.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "running": bridge.running,
            "version": "3.0.0",
            "protocol": "1",
        }

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await websocket_endpoint(socket, bridge, auth_token)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app, auth_token, bridge
