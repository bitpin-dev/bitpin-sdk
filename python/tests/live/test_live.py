"""Live, read-only checks against the real Bitpin API. Never run in CI.

    BITPIN_LIVE=1 [BITPIN_API_KEY=... BITPIN_SECRET_KEY=...] uv run pytest -m live

Every response is parsed by the SDK and compared with the shape of its fixture, so a server
change (renamed field, new type) shows up here before users hit it.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest

from bitpin_sdk import Bitpin, Config
from tests.fixtures import body

LIVE = os.environ.get("BITPIN_LIVE") == "1"
PRIVATE = LIVE and bool(os.environ.get("BITPIN_API_KEY") and os.environ.get("BITPIN_SECRET_KEY"))
ALLOWED_WRITES = {"/api/v1/usr/authenticate/", "/api/v1/usr/refresh_token/", "/api/v1/usr/ws-info/"}

pytestmark = [pytest.mark.live, pytest.mark.skipif(not LIVE, reason="set BITPIN_LIVE=1")]


def _read_only(request: httpx.Request) -> None:
    if request.method != "GET" and request.url.path not in ALLOWED_WRITES:
        raise RuntimeError(f"live tests are read-only: refused {request.method} {request.url.path}")


@pytest.fixture(scope="module")
def client() -> Iterator[Bitpin]:
    http = httpx.Client(timeout=15, event_hooks={"request": [_read_only]})
    with Bitpin(Config.from_env(max_retries=1), http_client=http) as instance:
        yield instance
    http.close()


def _first(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    if isinstance(value, dict) and "results" in value:
        return _first(value["results"])
    return value


def _type(value: Any) -> str:
    return (
        "number"
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else type(value).__name__
    )


def assert_shape(endpoint_id: str, live: Any) -> None:
    """Every key of the fixture's first row exists live with the same type (None matches all)."""
    want, got = _first(body(endpoint_id)), _first(live)
    if not isinstance(want, dict) or got is None:
        return
    for key, value in want.items():
        assert key in got, f"{endpoint_id}: missing field {key}"
        if value is not None and got[key] is not None:
            assert _type(got[key]) == _type(value), f"{endpoint_id}.{key}"


PUBLIC: list[tuple[str, Callable[[Bitpin], Any]]] = [
    ("public_get_mkt_currencies", lambda c: c.public_get_mkt_currencies()),
    ("public_get_mkt_markets", lambda c: c.public_get_mkt_markets()),
    ("public_get_mkt_networks", lambda c: c.public_get_mkt_networks()),
    ("public_get_mkt_tickers", lambda c: c.public_get_mkt_tickers()),
    (
        "public_get_mth_orderbook_symbol",
        lambda c: c.public_get_mth_orderbook_symbol({"symbol": "USDT_IRT"}),
    ),
    (
        "public_get_mth_matches_symbol",
        lambda c: c.public_get_mth_matches_symbol({"symbol": "USDT_IRT"}),
    ),
]

PRIVATE_READS: list[tuple[str, Callable[[Bitpin], Any]]] = [
    ("private_get_mkt_commissions", lambda c: c.private_get_mkt_commissions()),
    ("private_get_odr_orders", lambda c: c.private_get_odr_orders({"limit": 5})),
    ("private_get_odr_fills", lambda c: c.private_get_odr_fills({"limit": 5})),
    ("private_get_odr_order_history", lambda c: c.private_get_odr_order_history({"limit": 5})),
    ("private_get_wlt_wallets", lambda c: c.private_get_wlt_wallets({"limit": 5})),
    ("private_get_wlt_account_numbers", lambda c: c.private_get_wlt_account_numbers()),
    ("private_get_wlt_networks", lambda c: c.private_get_wlt_networks({"currency_code": "USDT"})),
    ("private_get_wlt_deposits", lambda c: c.private_get_wlt_deposits({"limit": 5})),
    ("private_get_wlt_withdraws", lambda c: c.private_get_wlt_withdraws({"limit": 5})),
]


@pytest.mark.parametrize(("endpoint_id", "fetch"), PUBLIC, ids=[e for e, _ in PUBLIC])
def test_public_shapes(client: Bitpin, endpoint_id: str, fetch: Callable[[Bitpin], Any]) -> None:
    assert_shape(endpoint_id, fetch(client))


def test_unified_public_methods(client: Bitpin) -> None:
    assert client.load_markets()
    assert client.fetch_ticker("USDT/IRT")["last"] is not None
    assert client.fetch_order_book("USDT/IRT")["bids"]
    assert client.fetch_ohlcv("USDT/IRT", "1h", limit=5)
    assert isinstance(client.fetch_trades("USDT/IRT"), list)


@pytest.mark.skipif(not PRIVATE, reason="set BITPIN_API_KEY and BITPIN_SECRET_KEY")
@pytest.mark.parametrize(("endpoint_id", "fetch"), PRIVATE_READS, ids=[e for e, _ in PRIVATE_READS])
def test_private_shapes(client: Bitpin, endpoint_id: str, fetch: Callable[[Bitpin], Any]) -> None:
    assert_shape(endpoint_id, fetch(client))


@pytest.mark.skipif(not PRIVATE, reason="set BITPIN_API_KEY and BITPIN_SECRET_KEY")
def test_unified_private_reads(client: Bitpin) -> None:
    assert isinstance(client.fetch_balance(), dict)
    assert isinstance(client.fetch_open_orders(), list)
    assert isinstance(client.fetch_my_trades(), list)


def test_the_guard_refuses_writes(client: Bitpin) -> None:
    with pytest.raises(RuntimeError, match="read-only"):
        client.create_order("USDT/IRT", "limit", "buy", "1", "1")
