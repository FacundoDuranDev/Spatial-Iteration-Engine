"""WebSocket endpoint. See .claude/scratch/ws_protocol.md (v=1).

Phase B: toggle_filter and set_param are wired to the registry-backed
EngineBridge. Filter mutations are sync microsecond ops and run inline on
the event loop; only start/stop go through an executor.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from . import registry
from .bridge import EngineBridge
from .protocol import (
    PROTOCOL_VERSION,
    clamp_float,
    clamp_int,
    coerce_bool,
    is_allowed_op,
)

logger = logging.getLogger("web_dashboard.ws")

PING_INTERVAL_S = 15.0
PONG_TIMEOUT_S = 30.0
STATE_TICK_S = 1.0


def _coerce_value(param: dict, raw: Any) -> Any:
    """Clamp/coerce a raw client value against the registry param spec.

    Out-of-range values are silently clamped (per ws_protocol §2.4). Bad
    types fall back to the registry default. Selects validate against
    ``options`` else default.
    """
    kind = param["kind"]
    default = param["default"]
    if kind == "select":
        opts = param.get("options", [])
        if isinstance(raw, str) and raw in opts:
            return raw
        return default
    if kind == "switch":
        return coerce_bool(raw)
    if kind == "angle":
        return clamp_float(raw, 0.0, 360.0, default=float(default))
    lo = param.get("min")
    hi = param.get("max")
    step = param.get("step", 1)
    # Stepper is always int; slider becomes int iff its step is integral.
    is_int = kind == "stepper" or (
        isinstance(step, int) and isinstance(default, int)
    )
    if is_int:
        return clamp_int(
            raw,
            int(lo),
            int(hi),
            step=int(step) if step else 1,
            default=int(default),
        )
    return clamp_float(raw, float(lo), float(hi), default=float(default))


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

            if op == "toggle_filter":
                fid = payload.get("filter")
                if not isinstance(fid, str):
                    await socket.send_json(
                        {"type": "error", "code": "bad_payload", "msg": "filter required"}
                    )
                    continue
                spec = registry.find_filter(fid)
                if spec is None:
                    await socket.send_json(
                        {"type": "error", "code": "unknown_filter", "msg": fid}
                    )
                    continue
                if spec.get("wip"):
                    await socket.send_json(
                        {"type": "error", "code": "wip_filter", "msg": fid}
                    )
                    continue
                if "on" not in payload:
                    await socket.send_json(
                        {"type": "error", "code": "bad_payload", "msg": "on required"}
                    )
                    continue
                on = coerce_bool(payload.get("on"))
                try:
                    bridge.toggle_filter(fid, on)
                except Exception:
                    logger.exception("toggle_filter dispatch failed")
                    await socket.send_json(
                        {"type": "error", "code": "internal", "msg": "toggle_filter"}
                    )
                    continue
                await socket.send_json(bridge.snapshot())
                continue

            if op == "set_param":
                fid = payload.get("filter")
                pid = payload.get("param")
                if not isinstance(fid, str) or not isinstance(pid, str):
                    await socket.send_json(
                        {"type": "error", "code": "bad_payload", "msg": "filter+param required"}
                    )
                    continue
                spec = registry.find_filter(fid)
                if spec is None:
                    await socket.send_json(
                        {"type": "error", "code": "unknown_filter", "msg": fid}
                    )
                    continue
                if spec.get("wip"):
                    await socket.send_json(
                        {"type": "error", "code": "wip_filter", "msg": fid}
                    )
                    continue
                param = registry.find_param(fid, pid)
                if param is None:
                    await socket.send_json(
                        {"type": "error", "code": "unknown_param", "msg": f"{fid}.{pid}"}
                    )
                    continue
                clamped = _coerce_value(param, payload.get("value"))
                try:
                    bridge.set_param(fid, pid, clamped)
                except Exception:
                    logger.exception("set_param dispatch failed")
                    await socket.send_json(
                        {"type": "error", "code": "internal", "msg": "set_param"}
                    )
                    continue
                await socket.send_json(bridge.snapshot())
                continue

            # Should be unreachable given is_allowed_op gate above.
            await socket.send_json(
                {"type": "error", "code": "internal", "msg": f"{op} unhandled"}
            )

    except WebSocketDisconnect:
        logger.info("ws %s: disconnected", client_id)
    except Exception:
        logger.exception("ws %s: handler crashed", client_id)
    finally:
        hb.cancel()
        tick.cancel()
