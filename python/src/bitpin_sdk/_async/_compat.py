"""Async primitives. ``_sync/_compat.py`` is the hand-written sync counterpart."""

from __future__ import annotations

import asyncio
from typing import Any

Lock = asyncio.Lock
default_sleep = asyncio.sleep


def websocket(client: Any, transport_factory: Any) -> Any:
    """The WebSocket client behind ``AsyncBitpin.watch_*``."""
    from bitpin_sdk.ws.client import BitpinWS

    return BitpinWS(client, transport_factory=transport_factory)
