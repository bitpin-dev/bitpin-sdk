"""Unified wallet methods: balance, deposit address, deposits, withdrawals and OTP."""

from __future__ import annotations

import json
from decimal import Decimal as D
from typing import Any

import httpx
import pytest
import respx

from bitpin_sdk import errors
from tests.conftest import call, route
from tests.fixtures import body


def sent(r: respx.Route) -> Any:
    return json.loads(r.calls.last.request.content)


async def test_fetch_balance(client: Any, mock: respx.MockRouter) -> None:
    wallets = route(mock, "private_get_wlt_wallets")
    balance = await call(client.fetch_balance())
    params = wallets.calls.last.request.url.params
    assert params["service"] == "main"
    assert params["limit"] == "1000"
    assert balance["BTC"]["total"] == D("0.0135")
    assert balance["free"]["IRT"] == D("150000000")


async def test_fetch_balance_reads_every_page(client: Any, mock: respx.MockRouter) -> None:
    rows = body("private_get_wlt_wallets")
    page1 = [{**rows[0], "id": 1000 + i, "asset": f"C{i}"} for i in range(1000)]
    wallets = mock.route(method="GET", path="/api/v1/wlt/wallets/").mock(
        side_effect=[httpx.Response(200, json=page1), httpx.Response(200, json=rows)]
    )
    balance = await call(client.fetch_balance({"service": "stake"}))
    assert wallets.call_count == 2
    assert wallets.calls[0].request.url.params["service"] == "stake"
    assert wallets.calls[1].request.url.params["offset"] == "1000"
    assert "C999" in balance
    assert "BTC" in balance


async def test_fetch_bank_accounts(client: Any, mock: respx.MockRouter) -> None:
    route(mock, "private_get_wlt_account_numbers")
    accounts = await call(client.fetch_bank_accounts())
    assert accounts[0]["id"] == "123"
    assert accounts[0]["status"] == "verified"


async def test_fetch_deposit_address(client: Any, mock: respx.MockRouter) -> None:
    address = route(mock, "private_post_wlt_address")
    result = await call(client.fetch_deposit_address("usdt", "trx"))
    assert sent(address) == {"currency": "USDT", "network": "TRX"}
    assert result["network"] == "TRX"
    assert result["address"] == "TTestAddressDoNotUse000000000000000"


async def test_fetch_deposit_address_network_from_params(
    client: Any, mock: respx.MockRouter
) -> None:
    address = route(mock, "private_post_wlt_address")
    await call(client.fetch_deposit_address("USDT", params={"network": "TRX"}))
    assert sent(address)["network"] == "TRX"


async def test_fetch_deposit_address_requires_network(client: Any) -> None:
    with pytest.raises(errors.BadRequest, match="network"):
        await call(client.fetch_deposit_address("USDT"))


async def test_fetch_currency_networks(client: Any, mock: respx.MockRouter) -> None:
    networks = route(mock, "private_get_wlt_networks")
    result = await call(client.fetch_currency_networks("usdt"))
    assert networks.calls.last.request.url.params["currency_code"] == "USDT"
    assert {n["network"]: n["withdraw"] for n in result} == {"TRX": False, "ETH": True}


async def test_fetch_deposits(client: Any, mock: respx.MockRouter) -> None:
    deposits = route(mock, "private_get_wlt_deposits")
    result = await call(client.fetch_deposits("usdt", since=1793083530123, limit=10))
    params = deposits.calls.last.request.url.params
    assert params["currency"] == "USDT"
    assert params["start"] == "2026-10-27T06:45:30.123000+00:00"
    assert params["limit"] == "10"
    assert result[0]["status"] == "ok"


async def test_fetch_withdrawals(client: Any, mock: respx.MockRouter) -> None:
    withdraws = route(mock, "private_get_wlt_withdraws")
    result = await call(client.fetch_withdrawals("USDT", since=1793083530123))
    params = withdraws.calls.last.request.url.params
    assert params["currency"] == "USDT"
    assert params["start"] == "2026-10-27"
    assert [w["id"] for w in result] == ["7001", "7002"]


async def test_withdraw_crypto(client: Any, mock: respx.MockRouter) -> None:
    create = route(mock, "private_post_wlt_withdraws")
    result = await call(
        client.withdraw(
            "USDT", D("50"), "TTestAddressDoNotUse000000000000000", params={"network": "trx"}
        )
    )
    assert sent(create) == {
        "currency": "USDT",
        "amount": "50",
        "address": "TTestAddressDoNotUse000000000000000",
        "network": "TRX",
    }
    assert result["id"] == "7003"
    assert result["status"] == "pending"
    assert result["info"]["is_single_otp"] is False


async def test_withdraw_with_memo(client: Any, mock: respx.MockRouter) -> None:
    create = route(mock, "private_post_wlt_withdraws")
    await call(client.withdraw("XRP", 10, "rTest", "12345", {"network": "XRP"}))
    assert sent(create)["memo"] == "12345"


async def test_withdraw_irt_to_bank_account(client: Any, mock: respx.MockRouter) -> None:
    create = route(mock, "private_post_wlt_withdraws")
    await call(client.withdraw("IRT", 5000000, params={"accountNumber": 123}))
    assert sent(create) == {"currency": "IRT", "amount": "5000000", "account_number": "123"}


async def test_withdraw_internal_transfer(client: Any, mock: respx.MockRouter) -> None:
    create = route(mock, "private_post_wlt_withdraws")
    await call(client.withdraw("USDT", 1, params={"alternativeAddress": "user@example.com"}))
    assert sent(create) == {
        "currency": "USDT",
        "amount": "1",
        "alternative_address": "user@example.com",
    }


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("USDT", 1, "addr"), "network"),
        (("USDT", 1), "address"),
        (("USDT", 0, "a", None, {"network": "TRX"}), "amount"),
    ],
)
async def test_withdraw_validates(
    client: Any, mock: respx.MockRouter, args: tuple[Any, ...], message: str
) -> None:
    create = route(mock, "private_post_wlt_withdraws")
    with pytest.raises(errors.BadRequest, match=message):
        await call(client.withdraw(*args))
    assert create.call_count == 0


async def test_withdraw_is_never_retried(client: Any, mock: respx.MockRouter) -> None:
    create = mock.route(method="POST", path="/api/v2/wlt/withdraws/").mock(
        side_effect=httpx.ConnectError("down")
    )
    with pytest.raises(errors.NetworkError):
        await call(client.withdraw("USDT", 1, "a", params={"network": "TRX"}))
    assert create.call_count == 1


async def test_verify_withdraw_otp(client: Any, mock: respx.MockRouter) -> None:
    verify = route(mock, "private_post_wlt_withdraws_verify_otp_id", id="7003")
    assert await call(client.verify_withdraw_otp(7003, "123456")) == {"detail": "success"}
    assert sent(verify) == {"otp": "123456", "is_second_otp": False}
    await call(client.verify_withdraw_otp(7003, "654321", second=True))
    assert sent(verify)["is_second_otp"] is True
    assert verify.calls.last.request.url.path == "/api/v1/wlt/withdraws/verify/otp/7003/"


async def test_verify_withdraw_otp_wrong_code(client: Any, mock: respx.MockRouter) -> None:
    route(
        mock,
        "private_post_wlt_withdraws_verify_otp_id",
        status=400,
        json_body={"code": "extra_try"},
        id="1",
    )
    with pytest.raises(errors.InvalidOTP) as info:
        await call(client.verify_withdraw_otp(1, "000000"))
    assert info.value.code == "extra_try"


async def test_resend_withdraw_otp(client: Any, mock: respx.MockRouter) -> None:
    retry = route(mock, "private_post_wlt_withdraws_retry_id", id="7003")
    await call(client.resend_withdraw_otp(7003))
    assert sent(retry) == {"first": True, "use_voice_call": False}
    await call(client.resend_withdraw_otp(7003, first=False, voice_call=True))
    assert sent(retry) == {"first": False, "use_voice_call": True}


async def test_paginate_without_limit_uses_the_max_page_size(
    client: Any, mock: respx.MockRouter
) -> None:
    deposits = route(mock, "private_get_wlt_deposits")
    await call(client.fetch_deposits(params={"paginate": True}))
    assert deposits.calls.last.request.url.params["limit"] == "1000"
    assert deposits.call_count == 1  # the fixture page is shorter than the limit
