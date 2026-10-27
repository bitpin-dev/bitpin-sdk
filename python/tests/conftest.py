"""Shared test harness.

Every client test is written once, as an ``async def``, and runs against both clients:
``await call(client.fetch_ticker(...))`` awaits the async client's coroutine and passes the
sync client's plain value through. HTTP is mocked with respx; time is a fake clock.
"""

from __future__ import annotations

import base64
import inspect
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
import respx

from bitpin_sdk import AsyncBitpin
from bitpin_sdk._generated.spec import ENDPOINTS
from tests.fixtures import fixture

try:  # the sync client is generated from the async one (Task 9)
    from bitpin_sdk import Bitpin
except ImportError:  # pragma: no cover
    Bitpin = None  # type: ignore[assignment,misc]

BASE = "https://api.bitpin.org"
NOW = 4_000_000_000.0  # before the fixture tokens expire (4102444800)

CLIENT_KINDS = ["async"] + (["sync"] if Bitpin is not None else [])


def make_jwt(exp: float) -> str:
    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    return f"{b64(b'{}')}.{b64(json.dumps({'exp': exp}).encode())}.c2ln"


async def call(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


class FakeTime:
    def __init__(self) -> None:
        self.now = NOW
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def sync_sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    async def async_sleep(self, seconds: float) -> None:
        self.sync_sleep(seconds)


@pytest.fixture
def fake_time() -> FakeTime:
    return FakeTime()


@pytest.fixture
def mock() -> respx.MockRouter:
    with respx.mock(base_url=BASE, assert_all_called=False) as router:
        yield router


def route(
    router: respx.MockRouter,
    endpoint_id: str,
    *,
    status: int | None = None,
    json_body: Any = ...,
    **path: str,
) -> respx.Route:
    """Mock one endpoint with its shared fixture (or the given status/body)."""
    endpoint = ENDPOINTS[endpoint_id]
    data = fixture(endpoint_id)
    status = data["status"] if status is None else status
    body = data["body"] if json_body is ... else json_body
    url_path = endpoint.path.format(**path) if path else endpoint.path
    if "{" in url_path:
        prefix = url_path[: url_path.index("{")]
        matcher = router.route(method=endpoint.method, path__startswith=prefix)
    else:
        matcher = router.route(method=endpoint.method, path=url_path)
    response = httpx.Response(status) if body is None else httpx.Response(status, json=body)
    return matcher.mock(return_value=response)


def make_client(kind: str, fake_time: FakeTime, **config: Any) -> Any:
    options: dict[str, Any] = {"api_key": "test-key", "secret_key": "test-secret", **config}
    if kind == "async":
        return AsyncBitpin(options, clock=fake_time, sleep=fake_time.async_sleep)
    return Bitpin(options, clock=fake_time, sleep=fake_time.sync_sleep)


@pytest.fixture(params=CLIENT_KINDS)
async def client(
    request: pytest.FixtureRequest, fake_time: FakeTime, mock: respx.MockRouter
) -> AsyncIterator[Any]:
    instance = make_client(request.param, fake_time)
    route(mock, "credentials_post_usr_authenticate")
    yield instance
    await call(instance.close())


@pytest.fixture(params=CLIENT_KINDS)
def client_factory(request: pytest.FixtureRequest, fake_time: FakeTime) -> Callable[..., Any]:
    return lambda **config: make_client(request.param, fake_time, **config)
