"""Sync primitives. Hand-written counterpart of ``_async/_compat.py``."""

from __future__ import annotations

import threading
import time

Lock = threading.Lock
default_sleep = time.sleep
