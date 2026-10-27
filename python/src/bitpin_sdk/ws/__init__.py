"""Real-time data over Bitpin's Centrifugo WebSocket (async only).

    ticker = await client.watch_ticker("BTC/IRT")   # waits for the next update

Install the extra: ``pip install "bitpin-sdk[ws]"``.
"""

from bitpin_sdk.ws.client import BitpinWS

__all__ = ["BitpinWS"]
