"""WebSocket endpoint. See .claude/scratch/ws_protocol.md (v=1).

Phase A: handles handshake (auth + version), heartbeat, start/stop ops.
toggle_filter / set_param respond with `internal: not_implemented` until
Phase B wires the registry.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from .bridge import EngineBridge
from .protocol import PROTOCOL_VERSION, is_allowed_op

logger = logging.getLogger("web_dashboard.ws")

PING_INTERVAL_S = 15.0
PONG_TIMEOUT_S = 30.0
STATE_TICK_S = 1.0


async def websocket_endpoint(socket: WebSocket, bridge: EngineBridge, auth_token: str) -> None:
    """Handle one WS connection lifetime."""
    qs = dict(socket.query_params)
    if qs.get("t") != auth_token:
        await socket.close(code=4401, reason="auth_failed")
        return
    if qs.get("v") != PROTOCOL_VERSION:
        await socket.close(code=1008, reason="version_mismatch")
        return

    await socket.accept()
    client_id = f"{socket.client.host}:{socket.client.port}" if socket.client else "?"
    logger.info("ws connected: %s", client_id)

    try:
        await socket.send_json(bridge.snapshot())
    except Exception:
        return

    loop = asyncio.get_running_loop()
    last_pong_at = loop.time()

    async def heartbeat() -> None:
        nonlocal last_pong_at
        while True:
            await asyncio.sleep(PING_INTERVAL_S)
            try:
                await socket.send_json({"type": "ping"})
            except Exception:
                return
            if loop.time() - last_pong_at > PONG_TIMEOUT_S:
                logger.info("ws %s: pong timeout, closing", client_id)
                try:
                    await socket.close(code=1011, reason="pong_timeout")
                except Exception:
                    pass
                return

    async def state_tick() -> None:
        while True:
            await asyncio.sleep(STATE_TICK_S)
            try:
                await socket.send_json(bridge.snapshot())
            except Exception:
                return

    hb = asyncio.create_task(heartbeat())
    tick = asyncio.create_task(state_tick())

    try:
        while True:
            raw = await socket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await socket.send_json(
                    {"type": "error", "code": "bad_payload", "msg": "json parse"}
                )
                await socket.close(code=1003, reason="bad_payload")
                return

            op = payload.get("op")
            if not is_allowed_op(op):
                await socket.send_json(
                    {"type": "error", "code": "unknown_op", "msg": f"got {op!r}"}
                )
                await socket.close(code=1003, reason="unknown_op")
                return

            if op == "pong":
                last_pong_at = loop.time()
                continue

            if op == "start":
                await loop.run_in_executor(None, bridge.start)
                await socket.send_json(bridge.snapshot())
                continue

            if op == "stop":
                await loop.run_in_executor(None, bridge.stop)
                await socket.send_json(bridge.snapshot())
                continue

            # toggle_filter / set_param land here in Phase A (not wired yet).
            await socket.send_json(
                {"type": "error", "code": "internal", "msg": f"{op} not implemented yet"}
            )

    except WebSocketDisconnect:
        logger.info("ws %s: disconnected", client_id)
    except Exception:
        logger.exception("ws %s: handler crashed", client_id)
    finally:
        hb.cancel()
        tick.cancel()
