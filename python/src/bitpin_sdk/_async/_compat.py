"""Async primitives. ``_sync/_compat.py`` is the hand-written sync counterpart."""

from __future__ import annotations

import asyncio

Lock = asyncio.Lock
default_sleep = asyncio.sleep
