# Configuration

Every setting has a default from Bitpin's server, and you can override any of it.

```python
from bitpin_sdk import Bitpin, Config, RateLimit

config = Config(
    api_key="...",
    secret_key="...",
    timeout=10,               # seconds per request
    max_retries=3,            # for idempotent requests only
    enable_rate_limit=True,   # client-side limiter
    rate_limits={"orderbook": "10800/min", "order_create": RateLimit(180_000, "hour")},
    rest_url="https://api.bitpin.org",
    ws_url="wss://centrifugo.bitpin.org/connection/websocket",
    user_agent=None,          # default: bitpin-sdk-python/<version>
    token_store=None,         # default: in memory; see Authentication
)
client = Bitpin(config)
```

## Four ways to build a config

```python
Config(api_key="...", secret_key="...")                     # in code
Config.from_env(timeout=5)                                  # BITPIN_API_KEY, BITPIN_SECRET_KEY
Config.from_file("bitpin.toml")                             # TOML, see below
Bitpin({"apiKey": "...", "secret": "...", "timeout": 5000}) # ccxt-style dict (timeout in ms)
```

`bitpin.toml`:

```toml
[bitpin]
api_key = "..."
secret_key = "..."
timeout = 10

[bitpin.rate_limits]
orderbook = "10800/min"
fills = "600/min"
```

Unknown keys and unknown rate-limit bucket names raise `ValueError`, so a typo can't silently do nothing.

`client.describe()` shows the effective URLs, capabilities, timeframes and rate limits.
