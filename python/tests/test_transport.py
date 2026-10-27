"""Transport behaviour shared by every call: auth, headers, retries, rate limiting, errors."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx
import pytest
import respx

from bitpin_sdk import AsyncBitpin, __version__, errors
from bitpin_sdk._generated.spec import ENDPOINTS
from bitpin_sdk.token_store import MemoryTokenStore, key_id
from tests.conftest import NOW, FakeTime, call, make_jwt, route


async def test_every_endpoint_has_an_implicit_method(client: Any) -> None:
    for endpoint_id in ENDPOINTS:
        assert callable(getattr(client, endpoint_id)), endpoint_id


async def test_unknown_attribute_raises(client: Any) -> None:
    with pytest.raises(AttributeError):
        _ = client.public_get_nothing


async def test_public_call_sends_no_token(client: Any, mock: respx.MockRouter) -> None:
    tickers = route(mock, "public_get_mkt_tickers")
    await call(client.public_get_mkt_tickers())
    request = tickers.calls.last.request
    assert "authorization" not in request.headers
    assert request.headers["user-agent"] == f"bitpin-sdk-python/{__version__}"
    assert request.headers["accept"] == "application/json"


async def test_private_call_authenticates_once_and_sends_bearer(
    client: Any, mock: respx.MockRouter
) -> None:
    auth = mock.routes[0]
    wallets = route(mock, "private_get_wlt_wallets")
    await call(client.private_get_wlt_wallets())
    await call(client.private_get_wlt_wallets())
    assert auth.call_count == 1
    assert json.loads(auth.calls.last.request.content) == {
        "api_key": "test-key",
        "secret_key": "test-secret",
    }
    token = route_body("credentials_post_usr_authenticate")["access"]
    assert wallets.calls.last.request.headers["authorization"] == f"Bearer {token}"


def route_body(endpoint_id: str) -> Any:
    from tests.fixtures import body

    return body(endpoint_id)


async def test_implicit_method_splits_path_params(client: Any, mock: respx.MockRouter) -> None:
    book = route(mock, "public_get_mth_orderbook_symbol", symbol="BTC_IRT")
    await call(client.public_get_mth_orderbook_symbol({"symbol": "BTC_IRT", "limit": 20}))
    request = book.calls.last.request
    assert request.url.path == "/api/v1/mth/orderbook/BTC_IRT/"
    assert request.url.params["limit"] == "20"


async def test_private_call_without_credentials_raises(
    client_factory: Any, mock: respx.MockRouter
) -> None:
    client = client_factory(api_key=None, secret_key=None)
    with pytest.raises(errors.AuthenticationError, match="api_key and secret_key"):
        await call(client.private_get_wlt_wallets())


async def test_access_token_is_refreshed_before_expiry(
    client: Any, mock: respx.MockRouter, fake_time: FakeTime
) -> None:
    route(
        mock,
        "credentials_post_usr_authenticate",
        json_body={"access": make_jwt(NOW + 900), "refresh": make_jwt(NOW + 86400)},
    )
    refresh = route(
        mock, "credentials_post_usr_refresh_token", json_body={"access": make_jwt(NOW + 1800)}
    )
    wallets = route(mock, "private_get_wlt_wallets")
    await call(client.private_get_wlt_wallets())
    fake_time.advance(900 - 60)
    await call(client.private_get_wlt_wallets())
    assert refresh.call_count == 1
    assert json.loads(refresh.calls.last.request.content) == {"refresh": make_jwt(NOW + 86400)}
    assert wallets.calls.last.request.headers["authorization"] == f"Bearer {make_jwt(NOW + 1800)}"


async def test_failed_refresh_falls_back_to_authenticate(
    client: Any, mock: respx.MockRouter, fake_time: FakeTime
) -> None:
    auth = route(
        mock,
        "credentials_post_usr_authenticate",
        json_body={"access": make_jwt(NOW + 900), "refresh": make_jwt(NOW + 86400)},
    )
    route(
        mock,
        "credentials_post_usr_refresh_token",
        status=401,
        json_body={"detail": "Token is invalid or expired"},
    )
    route(mock, "private_get_wlt_wallets")
    await call(client.private_get_wlt_wallets())
    fake_time.advance(900)
    await call(client.private_get_wlt_wallets())
    assert auth.call_count == 2


async def test_401_triggers_one_reauth_and_one_retry(client: Any, mock: respx.MockRouter) -> None:
    auth = mock.routes[0]
    wallets = mock.route(method="GET", path="/api/v1/wlt/wallets/").mock(
        side_effect=[httpx.Response(401, json={"detail": "revoked"}), httpx.Response(200, json=[])]
    )
    route(mock, "credentials_post_usr_refresh_token")
    assert await call(client.private_get_wlt_wallets()) == []
    assert wallets.call_count == 2
    assert auth.call_count == 1


async def test_repeated_401_raises(client: Any, mock: respx.MockRouter) -> None:
    route(mock, "credentials_post_usr_refresh_token")
    route(mock, "private_get_wlt_wallets", status=401, json_body={"detail": "revoked"})
    with pytest.raises(errors.AuthenticationError):
        await call(client.private_get_wlt_wallets())


async def test_tokens_come_from_and_go_to_the_store(
    client_factory: Any, mock: respx.MockRouter
) -> None:
    store = MemoryTokenStore()
    auth = route(mock, "credentials_post_usr_authenticate")
    route(mock, "private_get_wlt_wallets")
    first = client_factory(token_store=store)
    await call(first.private_get_wlt_wallets())
    assert store.load(key_id("test-key")) is not None
    second = client_factory(token_store=store)
    await call(second.private_get_wlt_wallets())
    assert auth.call_count == 1


@pytest.mark.parametrize("failure", [httpx.ConnectError("boom"), httpx.Response(503)])
async def test_idempotent_get_is_retried(
    client: Any, mock: respx.MockRouter, fake_time: FakeTime, failure: Any
) -> None:
    tickers = mock.route(method="GET", path="/api/v1/mkt/tickers/").mock(
        side_effect=[failure, httpx.Response(200, json=[])]
    )
    assert await call(client.public_get_mkt_tickers()) == []
    assert tickers.call_count == 2
    assert fake_time.sleeps == [0.5]


async def test_retries_stop_after_max_retries(
    client_factory: Any, mock: respx.MockRouter, fake_time: FakeTime
) -> None:
    client = client_factory(max_retries=2)
    tickers = route(mock, "public_get_mkt_tickers", status=503, json_body=None)
    with pytest.raises(errors.ExchangeNotAvailable):
        await call(client.public_get_mkt_tickers())
    assert tickers.call_count == 3
    assert fake_time.sleeps == [0.5, 1.0]


@pytest.mark.parametrize(
    "failure",
    [
        httpx.Response(429, json={"detail": "Expected available in 1 seconds."}),
        httpx.ReadTimeout("slow"),
        httpx.Response(503),
    ],
)
async def test_create_order_is_never_retried(
    client: Any, mock: respx.MockRouter, failure: Any
) -> None:
    orders = mock.route(method="POST", path="/api/v1/odr/orders/").mock(
        side_effect=[failure, httpx.Response(201, json={})]
    )
    with pytest.raises(errors.NetworkError):
        await call(client.private_post_odr_orders({"symbol": "BTC_IRT"}))
    assert orders.call_count == 1


async def test_timeout_maps_to_request_timeout(client_factory: Any, mock: respx.MockRouter) -> None:
    client = client_factory(max_retries=0)
    mock.route(method="GET", path="/api/v1/mkt/tickers/").mock(
        side_effect=httpx.ReadTimeout("slow")
    )
    with pytest.raises(errors.RequestTimeout):
        await call(client.public_get_mkt_tickers())


async def test_transport_error_maps_to_network_error(
    client_factory: Any, mock: respx.MockRouter
) -> None:
    client = client_factory(max_retries=0)
    mock.route(method="GET", path="/api/v1/mkt/tickers/").mock(
        side_effect=httpx.ConnectError("down")
    )
    with pytest.raises(errors.NetworkError) as info:
        await call(client.public_get_mkt_tickers())
    assert type(info.value) is errors.NetworkError


async def test_short_429_is_waited_out_on_idempotent_call(
    client: Any, mock: respx.MockRouter, fake_time: FakeTime
) -> None:
    tickers = mock.route(method="GET", path="/api/v1/mkt/tickers/").mock(
        side_effect=[
            httpx.Response(429, json={"detail": "Expected available in 2 seconds."}),
            httpx.Response(200, json=[]),
        ]
    )
    await call(client.public_get_mkt_tickers())
    assert tickers.call_count == 2
    assert fake_time.sleeps == [2.0]


async def test_long_429_is_raised_with_retry_after(client: Any, mock: respx.MockRouter) -> None:
    route(
        mock,
        "public_get_mkt_tickers",
        status=429,
        json_body={"detail": "Expected available in 86398 seconds."},
    )
    with pytest.raises(errors.RateLimitExceeded) as info:
        await call(client.public_get_mkt_tickers())
    assert info.value.retry_after == 86398.0


async def test_client_side_limiter_waits(
    client_factory: Any, mock: respx.MockRouter, fake_time: FakeTime
) -> None:
    client = client_factory(rate_limits={"tickers": "2/min"})
    route(mock, "public_get_mkt_tickers")
    for _ in range(3):
        await call(client.public_get_mkt_tickers())
    assert fake_time.sleeps == [60.0]


async def test_limiter_can_be_disabled(
    client_factory: Any, mock: respx.MockRouter, fake_time: FakeTime
) -> None:
    client = client_factory(rate_limits={"tickers": "1/min"}, enable_rate_limit=False)
    route(mock, "public_get_mkt_tickers")
    for _ in range(3):
        await call(client.public_get_mkt_tickers())
    assert fake_time.sleeps == []


async def test_204_returns_none(client: Any, mock: respx.MockRouter) -> None:
    route(mock, "private_delete_odr_orders_id", id="1")
    assert await call(client.private_delete_odr_orders_id({"id": 1})) is None


async def test_non_json_error_body_is_kept_as_text(
    client_factory: Any, mock: respx.MockRouter
) -> None:
    client = client_factory(max_retries=0)
    mock.route(method="GET", path="/api/v1/mkt/tickers/").mock(
        return_value=httpx.Response(502, text="<html>bad gateway</html>")
    )
    with pytest.raises(errors.ExchangeNotAvailable) as info:
        await call(client.public_get_mkt_tickers())
    assert info.value.body == "<html>bad gateway</html>"


async def test_invalid_json_success_body_raises_exchange_error(
    client: Any, mock: respx.MockRouter
) -> None:
    mock.route(method="GET", path="/api/v1/mkt/tickers/").mock(
        return_value=httpx.Response(200, text="not json")
    )
    with pytest.raises(errors.ExchangeError, match="invalid JSON"):
        await call(client.public_get_mkt_tickers())


async def test_secrets_never_reach_logs_or_errors(
    client: Any, mock: respx.MockRouter, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="bitpin_sdk")
    route(
        mock,
        "credentials_post_usr_authenticate",
        status=406,
        json_body={"detail": "api_credential_wrong"},
    )
    with pytest.raises(errors.AuthenticationError) as info:
        await call(client.private_get_wlt_wallets())
    text = caplog.text + str(info.value) + repr(info.value.body) + repr(client)
    assert "test-secret" not in text
    assert "test-key" not in text
    assert "POST https://api.bitpin.org/api/v1/usr/authenticate/ -> 406" in caplog.text


async def test_context_manager_closes_owned_client(fake_time: FakeTime) -> None:
    async with AsyncBitpin(clock=fake_time, sleep=fake_time.async_sleep) as client:
        assert not client._http.is_closed
    assert client._http.is_closed


async def test_external_http_client_is_not_closed(fake_time: FakeTime) -> None:
    http = httpx.AsyncClient()
    client = AsyncBitpin(http_client=http, clock=fake_time, sleep=fake_time.async_sleep)
    await client.close()
    assert not http.is_closed
    await http.aclose()


async def test_concurrent_calls_authenticate_once(
    fake_time: FakeTime, mock: respx.MockRouter
) -> None:
    auth = route(mock, "credentials_post_usr_authenticate")
    route(mock, "private_get_wlt_wallets")
    client = AsyncBitpin(
        {"api_key": "k", "secret_key": "s"}, clock=fake_time, sleep=fake_time.async_sleep
    )
    await asyncio.gather(*(client.private_get_wlt_wallets() for _ in range(10)))
    assert auth.call_count == 1
    await client.close()


async def test_ccxt_style_constructor(fake_time: FakeTime) -> None:
    client = AsyncBitpin(
        {"apiKey": "k", "secret": "s", "timeout": 2500},
        clock=fake_time,
        sleep=fake_time.async_sleep,
    )
    assert client.config.api_key == "k"
    assert client.config.timeout == 2.5
    assert client.id == "bitpin"
    await client.close()


def test_sync_context_manager_closes_owned_client(fake_time: FakeTime) -> None:
    from bitpin_sdk import Bitpin

    with Bitpin(clock=fake_time, sleep=fake_time.sync_sleep) as client:
        assert not client._http.is_closed
    assert client._http.is_closed
    external = httpx.Client()
    Bitpin(http_client=external).close()
    assert not external.is_closed
    external.close()


async def test_concurrent_burst_is_spread_not_fired_together(
    fake_time: FakeTime, mock: respx.MockRouter
) -> None:
    route(mock, "public_get_mth_orderbook_symbol")
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:  # yields without moving the clock
        sleeps.append(seconds)
        await asyncio.sleep(0)

    client = AsyncBitpin({"rate_limits": {"orderbook": "2/sec"}}, clock=fake_time, sleep=sleep)
    await asyncio.gather(*(client.fetch_order_book("BTC/IRT") for _ in range(8)))
    assert sorted(sleeps) == [1.0, 1.0, 2.0, 2.0, 3.0, 3.0]
    await client.close()


async def test_late_401_for_an_old_token_does_not_refresh_again(
    client: Any, mock: respx.MockRouter
) -> None:
    first = route_body("credentials_post_usr_authenticate")["access"]
    route(mock, "credentials_post_usr_refresh_token", json_body={"access": make_jwt(NOW + 5000)})
    refresh = mock.routes[-1]
    route(mock, "private_get_wlt_wallets")
    await call(client.private_get_wlt_wallets())  # authenticate: tokens hold `first`
    client._tokens.set_access({"access": make_jwt(NOW + 4000)})  # another request refreshed
    client._tokens.expire_access(first)  # the late 401 of a request that used `first`
    await call(client.private_get_wlt_wallets())
    assert refresh.call_count == 0


async def test_credentials_are_not_reachable_through_exception_chaining(
    client_factory: Any, mock: respx.MockRouter
) -> None:
    client = client_factory(max_retries=0)
    mock.route(method="POST", path="/api/v1/usr/authenticate/").mock(
        side_effect=httpx.ConnectError("down")
    )
    with pytest.raises(errors.NetworkError) as info:
        await call(client.private_get_wlt_wallets())
    assert info.value.__cause__ is None
    assert info.value.__suppress_context__ is True


async def test_key_id_is_derived_once_per_client(
    client: Any, mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    import bitpin_sdk._async.client as async_client
    import bitpin_sdk._sync.client as sync_client

    calls: list[str] = []
    for module in (async_client, sync_client):
        monkeypatch.setattr(module, "key_id", lambda key: calls.append(key) or "kid")
    route(mock, "private_get_wlt_wallets")
    for _ in range(3):
        await call(client.private_get_wlt_wallets())
    assert len(calls) == 1


async def test_close_still_closes_http_when_the_websocket_close_fails(fake_time: FakeTime) -> None:
    class BrokenSocket:
        async def close(self) -> None:
            raise RuntimeError("ws close failed")

    client = AsyncBitpin(clock=fake_time, sleep=fake_time.async_sleep)
    client._ws = BrokenSocket()
    with pytest.raises(RuntimeError):
        await client.close()
    assert client._http.is_closed
    assert client._ws is None
