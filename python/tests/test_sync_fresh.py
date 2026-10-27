"""The sync client is generated from the async one and must not drift."""

from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path

from bitpin_sdk import AsyncBitpin, Bitpin

ROOT = Path(__file__).resolve().parents[2]


def test_sync_is_fresh() -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts" / "gen_sync.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_sync_client_mirrors_async_public_methods() -> None:
    def public(cls: type) -> set[str]:
        return {n for n, _ in inspect.getmembers(cls, inspect.isfunction) if not n.startswith("_")}

    assert public(Bitpin) == public(AsyncBitpin)
    assert not any(inspect.iscoroutinefunction(getattr(Bitpin, n)) for n in public(Bitpin))


def test_sync_client_has_no_async_leftovers() -> None:
    source = (ROOT / "python" / "src" / "bitpin_sdk" / "_sync" / "client.py").read_text(
        encoding="utf-8"
    )
    for word in ("await ", "async ", "AsyncBitpin", "AsyncClient", "asyncio", "aclose"):
        assert word not in source, word
