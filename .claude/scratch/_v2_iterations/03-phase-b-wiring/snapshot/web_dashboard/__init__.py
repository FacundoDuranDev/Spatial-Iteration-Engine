"""Web dashboard output adapter (v3).

Mobile-first FastAPI + WebSocket control surface for the engine.
Replaces the v1/v2 Gradio dashboards. See .claude/scratch/ws_protocol.md
for the wire contract.
"""
from .app import create_app

__all__ = ["create_app"]
