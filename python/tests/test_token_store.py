from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest

from bitpin_sdk._core.auth import Tokens
from bitpin_sdk.token_store import FileTokenStore, MemoryTokenStore, key_id

TOKENS = Tokens("access", "refresh", 100.0, 200.0)


def test_key_id_is_a_hash_not_the_key() -> None:
    kid = key_id("MY-API-KEY")
    assert len(kid) == 16
    assert "MY-API-KEY" not in kid
    assert kid == key_id("MY-API-KEY")
    assert kid != key_id("OTHER")


def test_memory_store_round_trip() -> None:
    store = MemoryTokenStore()
    assert store.load("k") is None
    store.save("k", TOKENS)
    assert store.load("k") == TOKENS
    store.clear("k")
    assert store.load("k") is None


def test_file_store_round_trip(tmp_path: Path) -> None:
    store = FileTokenStore(tmp_path / "cache")
    store.save("abc", TOKENS)
    assert FileTokenStore(tmp_path / "cache").load("abc") == TOKENS
    store.clear("abc")
    assert store.load("abc") is None
    store.clear("abc")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_file_store_is_private(tmp_path: Path) -> None:
    store = FileTokenStore(tmp_path / "cache")
    store.save("abc", TOKENS)
    path = tmp_path / "cache" / "abc.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "cache").stat().st_mode) == 0o700


def test_file_store_ignores_corrupt_file(tmp_path: Path) -> None:
    store = FileTokenStore(tmp_path)
    (tmp_path / "abc.json").write_text("{not json", encoding="utf-8")
    assert store.load("abc") is None


def test_file_store_default_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert FileTokenStore().directory == tmp_path / "bitpin-sdk"


def test_file_store_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="key id"):
        FileTokenStore(tmp_path).save("../x", TOKENS)


def test_file_store_survives_a_leftover_temp_path(tmp_path: Path) -> None:
    """Another process mid-save (or a crash) can leave <id>.tmp behind; saving still works."""
    (tmp_path / "abc.tmp").mkdir()
    store = FileTokenStore(tmp_path)
    store.save("abc", TOKENS)
    assert store.load("abc") == TOKENS


def test_file_store_rejects_wrongly_typed_file(tmp_path: Path) -> None:
    (tmp_path / "abc.json").write_text(
        '{"access": "a", "refresh": "r", "access_exp": "soon", "refresh_exp": 1}', encoding="utf-8"
    )
    assert FileTokenStore(tmp_path).load("abc") is None


def test_key_id_uses_a_slow_key_derivation() -> None:
    import hashlib

    expected = hashlib.pbkdf2_hmac(
        "sha256", b"MY-API-KEY", b"bitpin-sdk/token-store", 100_000
    ).hex()[:16]
    assert key_id("MY-API-KEY") == expected
