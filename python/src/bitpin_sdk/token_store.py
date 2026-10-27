"""Where tokens are cached between client instances and process restarts.

Authenticate allows 3 requests per minute per IP. A bot that restarts often, or several
bots on one host, should share tokens through ``FileTokenStore`` (or your own store, e.g.
Redis) so they don't hit that limit.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Protocol

from bitpin_sdk._core.auth import Tokens

_KEY_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def key_id(api_key: str) -> str:
    """A stable, non-secret id for an API key, used as the cache key."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


class TokenStore(Protocol):
    def load(self, key_id: str) -> Tokens | None: ...
    def save(self, key_id: str, tokens: Tokens) -> None: ...
    def clear(self, key_id: str) -> None: ...


class MemoryTokenStore:
    """The default: tokens live as long as the client object."""

    def __init__(self) -> None:
        self._tokens: dict[str, Tokens] = {}

    def load(self, key_id: str) -> Tokens | None:
        return self._tokens.get(key_id)

    def save(self, key_id: str, tokens: Tokens) -> None:
        self._tokens[key_id] = tokens

    def clear(self, key_id: str) -> None:
        self._tokens.pop(key_id, None)


class FileTokenStore:
    """Tokens in ``$XDG_CACHE_HOME/bitpin-sdk/<key id>.json`` (default ``~/.cache``), mode 0600."""

    def __init__(self, directory: str | Path | None = None) -> None:
        if directory is None:
            base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
            directory = Path(base) / "bitpin-sdk"
        self.directory = Path(directory)

    def _path(self, key_id: str) -> Path:
        if not _KEY_ID.match(key_id):
            raise ValueError(f"invalid key id {key_id!r}")
        return self.directory / f"{key_id}.json"

    def load(self, key_id: str) -> Tokens | None:
        try:
            data = json.loads(self._path(key_id).read_text(encoding="utf-8"))
            return Tokens(**data)
        except (OSError, ValueError, TypeError):
            return None

    def save(self, key_id: str, tokens: Tokens) -> None:
        path = self._path(key_id)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            os.chmod(self.directory, 0o700)
        tmp = path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(dataclasses.asdict(tokens), fh)
        os.replace(tmp, path)

    def clear(self, key_id: str) -> None:
        with contextlib.suppress(FileNotFoundError):
            self._path(key_id).unlink()
