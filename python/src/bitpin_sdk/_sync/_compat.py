"""Sync primitives. Hand-written counterpart of ``_async/_compat.py``."""

from __future__ import annotations

import threading
import time
from typing import Any


Lock = threading.Lock
default_sleep = time.sleep


def websocket(client: Any, transport_factory: Any) -> Any:
    """The WebSocket client behind ``Bitpin.watch_*``: the async one, on a background thread."""
    from bitpin_sdk.ws.sync import SyncWS

    return SyncWS(client, transport_factory)
