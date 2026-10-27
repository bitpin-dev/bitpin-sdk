"""Unified trading methods: orders, bulk, cancels, fills and order history."""

from __future__ import annotations

import json
from decimal import Decimal as D
from typing import Any

import httpx
import pytest
import respx

from bitpin_sdk import errors
from tests.conftest import NOW, call, route
from tests.fixtures import body


def sent(r: respx.Route) -> Any:
    return json.loads(r.calls.last.request.content)


async def test_create_limit_order(client: Any, mock: respx.MockRouter) -> None:
    orders = route(mock, "private_post_odr_orders")
    order = await call(
        client.create_order(
            "BTC/IRT", "limit", "buy", D("0.001"), 3100000000, {"clientOrderId": "mm-bid-1"}
        )
    )
    assert sent(orders) == {
        "symbol": "BTC_IRT",
        "type": "limit",
        "side": "buy",
        "base_amount": "0.001",
        "price": "3100000000",
        "identifier": "mm-bid-1",
    }
    assert order["id"] == "535179385"
    assert order["status"] == "open"


async def test_create_market_order_by_quote_amount(client: Any, mock: respx.MockRouter) -> None:
    orders = route(mock, "private_post_odr_orders")
    await call(client.create_order("USDT/IRT", "market", "buy", params={"quoteAmount": "1000000"}))
    assert sent(orders) == {
        "symbol": "USDT_IRT",
        "type": "market",
        "side": "buy",
        "quote_amount": "1000000",
    }


async def test_create_stop_limit_and_oco(client: Any, mock: respx.MockRouter) -> None:
    orders = route(mock, "private_post_odr_orders")
    await call(
        client.create_order("BTC/USDT", "stop_limit", "sell", 1, 57990, {"stopPrice": 58000})
    )
    assert sent(orders)["stop_price"] == "58000"
    await call(
        client.create_order(
            "BTC/USDT", "oco", "sell", 1, 57990, {"triggerPrice": 58000, "takeProfitPrice": 70000}
        )
    )
    assert sent(orders) == {
        "symbol": "BTC_USDT",
        "type": "oco",
        "side": "sell",
        "base_amount": "1",
        "price": "57990",
        "stop_price": "58000",
        "oco_target_price": "70000",
    }


async def test_unknown_params_pass_through(client: Any, mock: respx.MockRouter) -> None:
    orders = route(mock, "private_post_odr_orders")
    await call(client.create_order("BTC/IRT", "limit", "buy", 1, 1, {"new_field": "x"}))
    assert sent(orders)["new_field"] == "x"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("BTC/IRT", "limit", "buy", None, 1), "amount"),
        (("BTC/IRT", "limit", "buy", 1, None), "price"),
        (("BTC/IRT", "market", "buy", None, None), "amount or params"),
        (("BTC/IRT", "stop_limit", "buy", 1, 1), "stopPrice"),
        (("BTC/IRT", "oco", "buy", 1, 1, {"stopPrice": 1}), "takeProfitPrice"),
        (("BTC/IRT", "trailing", "buy", 1, 1), "type"),
        (("BTC/IRT", "limit", "long", 1, 1), "side"),
        (("BTC/IRT", "limit", "buy", 0, 1), "amount"),
        (("BTC/IRT", "limit", "buy", 1, -5), "price"),
    ],
)
async def test_create_order_validates_before_sending(
    client: Any, mock: respx.MockRouter, args: tuple[Any, ...], message: str
) -> None:
    orders = route(mock, "private_post_odr_orders")
    with pytest.raises(errors.InvalidOrder, match=message):
        await call(client.create_order(*args))
    assert orders.call_count == 0


async def test_market_order_with_both_amounts_is_rejected(client: Any) -> None:
    with pytest.raises(errors.InvalidOrder, match="only one"):
        await call(client.create_order("BTC/IRT", "market", "buy", 1, params={"quoteAmount": 10}))


async def test_insufficient_funds(client: Any, mock: respx.MockRouter) -> None:
    route(mock, "private_post_odr_orders", status=406, json_body={"detail": "insufficent_balance"})
    with pytest.raises(errors.InsufficientFunds):
        await call(client.create_order("BTC/IRT", "limit", "buy", 1, 1))


async def test_create_orders_bulk(client: Any, mock: respx.MockRouter) -> None:
    bulk = route(mock, "private_post_odr_orders_bulk")
    result = await call(
        client.create_orders(
            [
                {
                    "symbol": "BTC/IRT",
                    "type": "limit",
                    "side": "buy",
                    "amount": "0.001",
                    "price": "3100000000",
                    "params": {"clientOrderId": "mm-bid-1"},
                },
                {
                    "symbol": "BTC/IRT",
                    "type": "limit",
                    "side": "buy",
                    "amount": "0.001",
                    "price": "3090000000",
                },
            ]
        )
    )
    assert sent(bulk) == [
        {
            "symbol": "BTC_IRT",
            "type": "limit",
            "side": "buy",
            "base_amount": "0.001",
            "price": "3100000000",
            "identifier": "mm-bid-1",
        },
        {
            "symbol": "BTC_IRT",
            "type": "limit",
            "side": "buy",
            "base_amount": "0.001",
            "price": "3090000000",
        },
    ]
    assert [o["id"] for o in result] == ["535179385", "535179386"]


async def test_create_orders_rejects_more_than_ten(client: Any, mock: respx.MockRouter) -> None:
    bulk = route(mock, "private_post_odr_orders_bulk")
    order = {"symbol": "BTC/IRT", "type": "limit", "side": "buy", "amount": 1, "price": 1}
    with pytest.raises(errors.BadRequest, match="at most 10"):
        await call(client.create_orders([order] * 11))
    with pytest.raises(errors.BadRequest, match="at least one"):
        await call(client.create_orders([]))
    assert bulk.call_count == 0


async def test_bulk_create_uses_both_bulk_buckets(
    client_factory: Any, mock: respx.MockRouter, fake_time: Any
) -> None:
    client = client_factory(rate_limits={"order_bulk_cancel": "1/hour"})
    route(mock, "credentials_post_usr_authenticate")
    route(mock, "private_post_odr_orders_bulk")
    route(mock, "private_delete_odr_orders_bulk")
    order = {"symbol": "BTC/IRT", "type": "limit", "side": "buy", "amount": 1, "price": 1}
    await call(client.create_orders([order]))
    await call(client.cancel_orders(ids=[1]))
    assert fake_time.sleeps == [3600.0]


async def test_fetch_order(client: Any, mock: respx.MockRouter) -> None:
    one = route(mock, "private_get_odr_orders_id", id="535179385")
    order = await call(client.fetch_order(535179385))
    assert one.calls.last.request.url.path == "/api/v1/odr/orders/535179385/"
    assert order["clientOrderId"] == "mm-bid-1"


async def test_fetch_order_not_found(client: Any, mock: respx.MockRouter) -> None:
    route(mock, "private_get_odr_orders_id", status=404, json_body={"detail": "Not found."}, id="1")
    with pytest.raises(errors.OrderNotFound):
        await call(client.fetch_order("1"))


async def test_fetch_orders_filters_and_sorts(client: Any, mock: respx.MockRouter) -> None:
    orders = route(mock, "private_get_odr_orders")
    result = await call(
        client.fetch_orders("BTC/IRT", since=1793083530123, limit=2, params={"side": "buy"})
    )
    params = orders.calls.last.request.url.params
    assert params["symbol"] == "BTC_IRT"
    assert params["limit"] == "2"
    assert params["side"] == "buy"
    assert params["start"] == "2026-10-27T06:45:30.123000+00:00"
    assert [o["id"] for o in result] == ["535179300", "535179385"]


async def test_fetch_open_and_closed_orders(client: Any, mock: respx.MockRouter) -> None:
    orders = route(mock, "private_get_odr_orders")
    await call(client.fetch_open_orders())
    assert orders.calls.last.request.url.params["state"] == "initial,active"
    await call(client.fetch_closed_orders())
    assert orders.calls.last.request.url.params["state"] == "closed"


async def test_fetch_orders_paginates_by_id_cursor(client: Any, mock: respx.MockRouter) -> None:
    page1 = [{**body("private_post_odr_orders"), "id": i} for i in (30, 20)]
    page2 = [{**body("private_post_odr_orders"), "id": 10}]
    orders = mock.route(method="GET", path="/api/v1/odr/orders/").mock(
        side_effect=[httpx.Response(200, json=page1), httpx.Response(200, json=page2)]
    )
    result = await call(client.fetch_orders(limit=2, params={"paginate": True}))
    assert [o["id"] for o in result] == ["10", "20", "30"]
    assert "offset" not in orders.calls[0].request.url.params
    assert orders.calls[1].request.url.params["offset"] == "20"
    assert orders.call_count == 2


async def test_paginate_respects_max_pages(client: Any, mock: respx.MockRouter) -> None:
    full = [{**body("private_post_odr_orders"), "id": i} for i in (2, 1)]
    orders = mock.route(method="GET", path="/api/v1/odr/orders/").mock(
        return_value=httpx.Response(200, json=full)
    )
    await call(client.fetch_orders(limit=2, params={"paginate": True, "maxPages": 3}))
    assert orders.call_count == 3


async def test_cancel_order(client: Any, mock: respx.MockRouter) -> None:
    cancel = route(mock, "private_delete_odr_orders_id", id="7")
    assert await call(client.cancel_order(7)) == {"id": "7", "clientOrderId": None, "info": None}
    assert cancel.calls.last.request.url.path == "/api/v1/odr/orders/7/"


async def test_cancel_not_allowed(client: Any, mock: respx.MockRouter) -> None:
    route(
        mock,
        "private_delete_odr_orders_id",
        status=406,
        json_body={"detail": "Cancel order is not allowed.", "code": "cancel_order_not_allowed"},
        id="7",
    )
    with pytest.raises(errors.InvalidOrder):
        await call(client.cancel_order(7))


async def test_cancel_order_by_identifier(client: Any, mock: respx.MockRouter) -> None:
    cancel = route(mock, "private_delete_odr_orders_identifier_identifier", identifier="mm-bid-1")
    assert await call(client.cancel_order_by_identifier("mm-bid-1")) == {
        "id": None,
        "clientOrderId": "mm-bid-1",
        "info": None,
    }
    assert cancel.calls.last.request.url.path == "/api/v1/odr/orders/identifier/mm-bid-1/"


async def test_cancel_orders_by_ids(client: Any, mock: respx.MockRouter) -> None:
    bulk = route(mock, "private_delete_odr_orders_bulk")
    result = await call(client.cancel_orders(ids=[535179385, "535179386"]))
    assert sent(bulk) == {"ids": ["535179385", "535179386"]}
    assert result["canceled"] == ["535179385"]
    assert result["not_canceled"] == ["535179386"]


async def test_cancel_orders_by_identifiers(client: Any, mock: respx.MockRouter) -> None:
    bulk = route(
        mock,
        "private_delete_odr_orders_bulk",
        json_body={"canceled_orders": ["a"], "not_canceled_orders": []},
    )
    result = await call(client.cancel_orders(identifiers=["a"]))
    assert sent(bulk) == {"identifiers": ["a"]}
    assert result["canceled"] == ["a"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({}, "exactly one"),
        ({"ids": [1], "identifiers": ["a"]}, "exactly one"),
        ({"ids": list(range(11))}, "at most 10"),
    ],
)
async def test_cancel_orders_validates(client: Any, kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(errors.BadRequest, match=message):
        await call(client.cancel_orders(**kwargs))


async def test_fetch_my_trades(client: Any, mock: respx.MockRouter) -> None:
    fills = route(mock, "private_get_odr_fills")
    since = int(NOW * 1000) - 3_600_000
    trades = await call(client.fetch_my_trades("BTC/IRT", since=since, limit=100))
    params = fills.calls.last.request.url.params
    assert params["symbol"] == "BTC_IRT"
    assert params["start"] == str(since // 1000)
    assert params["limit"] == "100"
    assert trades[0]["fee"]["currency"] == "IRT"


async def test_fetch_my_trades_rejects_since_older_than_24h(client: Any) -> None:
    with pytest.raises(errors.BadRequest, match="24 hours"):
        await call(client.fetch_my_trades(since=int(NOW * 1000) - 86_401_000))


async def test_fetch_order_history_walks_cursor_and_resends_filters(
    client: Any, mock: respx.MockRouter
) -> None:
    row = body("private_get_odr_order_history")["results"][0]
    history = mock.route(method="GET", path="/api/v1/odr/order_history/").mock(
        side_effect=[
            httpx.Response(200, json={"results": [row], "next_cursor": "c1", "has_next": True}),
            httpx.Response(
                200, json={"results": [{**row, "id": 2}], "next_cursor": "", "has_next": False}
            ),
        ]
    )
    result = await call(
        client.fetch_order_history(
            "BTC/IRT",
            since=1,
            until=2,
            limit=1,
            params={"side": "buy", "type": "market", "paginate": True},
        )
    )
    first, second = (c.request.url.params for c in history.calls)
    assert dict(first) == {
        "symbol": "BTC_IRT",
        "start": "1",
        "end": "2",
        "limit": "1",
        "side": "buy",
        "type": "market",
    }
    assert dict(second) == {
        "symbol": "BTC_IRT",
        "limit": "1",
        "side": "buy",
        "type": "market",
        "cursor": "c1",
    }
    assert [o["id"] for o in result] == ["535100000", "2"]


async def test_fetch_order_history_single_page(client: Any, mock: respx.MockRouter) -> None:
    route(mock, "private_get_odr_order_history")
    result = await call(client.fetch_order_history())
    assert len(result) == 1


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"limit": 201}, "200"),
        ({"limit": 0}, "200"),
        ({"since": 0, "until": 91 * 86_400_000}, "90 days"),
        ({"since": 5, "until": 5}, "before"),
    ],
)
async def test_fetch_order_history_validates(
    client: Any, kwargs: dict[str, Any], message: str
) -> None:
    with pytest.raises(errors.BadRequest, match=message):
        await call(client.fetch_order_history(**kwargs))
