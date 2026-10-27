"""Sync primitives. Hand-written counterpart of ``_async/_compat.py``."""

from __future__ import annotations

import threading
import time
from typing import Any

from bitpin_sdk import errors

Lock = threading.Lock
default_sleep = time.sleep


def websocket(client: Any, transport_factory: Any) -> Any:
    """WebSocket streams are async only."""
    raise errors.NotSupported(
        "WebSocket streams need AsyncBitpin (watch_* methods are async). "
        "استریم وب‌سوکت فقط با AsyncBitpin کار می‌کند.",
        feature="websocket",
    )
