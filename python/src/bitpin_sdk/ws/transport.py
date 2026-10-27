"""The Centrifugo connection. Tests replace it with a fake that has the same three methods."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

GetToken = Callable[[], Awaitable[str]]


class Transport(Protocol):
    async def connect(self) -> None: ...
    async def subscribe(self, channel: str, on_data: Callable[[Any], None]) -> None: ...
    async def close(self) -> None: ...


TransportFactory = Callable[[str, GetToken | None], Transport]


class CentrifugeTransport:
    """Wraps ``centrifuge-python``. It reconnects on its own and calls ``get_token`` again
    when the connection token expires."""

    def __init__(self, url: str, get_token: GetToken | None) -> None:
        try:
            import centrifuge
        except ImportError as exc:  # pragma: no cover - depends on the installed extras
            raise ImportError('WebSocket support needs: pip install "bitpin-sdk[ws]"') from exc
        self._centrifuge = centrifuge
        self._client = centrifuge.Client(url, get_token=get_token, name="bitpin-sdk-python")

    async def connect(self) -> None:  # pragma: no cover - needs a live server
        await self._client.connect()

    async def subscribe(
        self, channel: str, on_data: Callable[[Any], None]
    ) -> None:  # pragma: no cover - needs a live server
        centrifuge = self._centrifuge

        class Handler(centrifuge.SubscriptionEventHandler):  # type: ignore[misc,name-defined]
            async def on_publication(self, ctx: Any) -> None:
                on_data(ctx.pub.data)

        subscription = self._client.new_subscription(channel, events=Handler())
        await subscription.subscribe()

    async def close(self) -> None:  # pragma: no cover - needs a live server
        await self._client.disconnect()
