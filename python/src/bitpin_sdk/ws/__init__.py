"""Real-time data over Bitpin's Centrifugo WebSocket.

    ticker = await client.watch_ticker("BTC/IRT")   # AsyncBitpin: waits for the next update
    ticker = client.watch_ticker("BTC/IRT")         # Bitpin: blocks on a background thread

Install the extra: ``pip install "bitpin-sdk[ws]"``.
"""

from bitpin_sdk.ws.client import BitpinWS

__all__ = ["BitpinWS"]
