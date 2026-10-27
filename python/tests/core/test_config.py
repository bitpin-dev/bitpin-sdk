"""Config: defaults from the spec, user overrides from code, a ccxt dict, a TOML file or env."""

from __future__ import annotations

from pathlib import Path

import pytest

from bitpin_sdk.config import Config, RateLimit


def test_defaults_come_from_spec() -> None:
    config = Config()
    assert config.rest_url == "https://api.bitpin.org"
    assert config.ws_url == "wss://centrifugo.bitpin.org/connection/websocket"
    assert config.rate_limit("auth") == RateLimit(3, "min")
    assert config.rate_limit("order_create") == RateLimit(18000, "hour")
    assert config.rate_limit("order_history") == RateLimit(5, "sec")
    assert config.enable_rate_limit is True
    assert config.timeout == 10.0
    assert config.max_retries == 3


def test_override_one_bucket_keeps_the_others() -> None:
    config = Config(rate_limits={"orderbook": RateLimit(10_800, "min")})
    assert config.rate_limit("orderbook") == RateLimit(10_800, "min")
    assert config.rate_limit("matches") == RateLimit(60, "min")


def test_override_accepts_string_form() -> None:
    config = Config(rate_limits={"orderbook": "10800/min"})
    assert config.rate_limit("orderbook") == RateLimit(10_800, "min")


@pytest.mark.parametrize("bad", ["10/minute", "x/min", "0/min", "10"])
def test_bad_rate_limit_string_raises(bad: str) -> None:
    with pytest.raises(ValueError, match="rate limit"):
        RateLimit.parse(bad)


def test_unknown_bucket_raises() -> None:
    with pytest.raises(ValueError, match="unknown rate-limit bucket 'orderbok'"):
        Config(rate_limits={"orderbok": RateLimit(1, "min")})


def test_rate_limit_period_seconds() -> None:
    assert RateLimit(1, "sec").period_seconds == 1
    assert RateLimit(1, "min").period_seconds == 60
    assert RateLimit(1, "hour").period_seconds == 3600
    assert RateLimit(1, "day").period_seconds == 86400


def test_from_ccxt_dict() -> None:
    config = Config.from_ccxt(
        {
            "apiKey": "k",
            "secret": "s",
            "timeout": 5000,
            "enableRateLimit": False,
            "options": {"rateLimits": {"fills": "600/min"}},
        }
    )
    assert config.api_key == "k"
    assert config.secret_key == "s"
    assert config.timeout == 5.0
    assert config.enable_rate_limit is False
    assert config.rate_limit("fills") == RateLimit(600, "min")


def test_from_file(tmp_path: Path) -> None:
    path = tmp_path / "bitpin.toml"
    path.write_text(
        '[bitpin]\napi_key = "k"\nsecret_key = "s"\ntimeout = 3\nmax_retries = 1\n'
        '[bitpin.rate_limits]\norderbook = "10800/min"\n',
        encoding="utf-8",
    )
    config = Config.from_file(path)
    assert (config.api_key, config.secret_key, config.timeout, config.max_retries) == (
        "k",
        "s",
        3.0,
        1,
    )
    assert config.rate_limit("orderbook") == RateLimit(10_800, "min")


def test_from_file_unknown_key_raises(tmp_path: Path) -> None:
    path = tmp_path / "bitpin.toml"
    path.write_text('[bitpin]\napikey = "k"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="unknown config key 'apikey'"):
        Config.from_file(path)


def test_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BITPIN_API_KEY", "k")
    monkeypatch.setenv("BITPIN_SECRET_KEY", "s")
    config = Config.from_env(timeout=2)
    assert (config.api_key, config.secret_key, config.timeout) == ("k", "s", 2)


def test_coerce_accepts_config_mapping_or_none() -> None:
    config = Config(api_key="k")
    assert Config.coerce(config) is config
    assert Config.coerce(None) == Config()
    assert Config.coerce({"apiKey": "k", "secret": "s"}).secret_key == "s"
    assert Config.coerce({"api_key": "k", "secret_key": "s"}).secret_key == "s"


def test_has_credentials() -> None:
    assert Config(api_key="k", secret_key="s").has_credentials
    assert not Config(api_key="k").has_credentials


def test_repr_redacts_secrets() -> None:
    text = repr(Config(api_key="AKEY-123", secret_key="SECRET-456"))
    assert "AKEY-123" not in text
    assert "SECRET-456" not in text
    assert "api_key='***'" in text
    assert "secret_key='***'" in text


def test_token_store_is_carried_and_not_compared(tmp_path: Path) -> None:
    from bitpin_sdk.token_store import FileTokenStore

    store = FileTokenStore(tmp_path)
    config = Config(token_store=store)
    assert config.token_store is store
    assert config == Config()
    assert "token_store" not in repr(config)


@pytest.mark.parametrize(
    ("domain", "rest", "ws"),
    [
        ("org", "https://api.bitpin.org", "wss://centrifugo.bitpin.org/connection/websocket"),
        ("ir", "https://api.bitpin.ir", "wss://centrifugo.bitpin.ir/connection/websocket"),
        (
            "market",
            "https://api.bitpin.market",
            "wss://centrifugo.bitpin.market/connection/websocket",
        ),
    ],
)
def test_domain_selects_rest_and_ws_urls(domain: str, rest: str, ws: str) -> None:
    config = Config(domain=domain)  # type: ignore[arg-type]
    assert (config.domain, config.rest_url, config.ws_url) == (domain, rest, ws)


def test_default_domain_is_org() -> None:
    assert Config().domain == "org"


def test_explicit_urls_win_over_the_domain() -> None:
    config = Config(domain="ir", rest_url="https://proxy.example/bitpin")
    assert config.rest_url == "https://proxy.example/bitpin"
    assert config.ws_url == "wss://centrifugo.bitpin.ir/connection/websocket"


def test_unknown_domain_raises() -> None:
    with pytest.raises(ValueError, match="unknown domain 'com'; use one of: ir, market, org"):
        Config(domain="com")  # type: ignore[arg-type]


def test_domain_from_ccxt_file_and_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert (
        Config.from_ccxt({"options": {"domain": "market"}}).rest_url == "https://api.bitpin.market"
    )
    path = tmp_path / "bitpin.toml"
    path.write_text('[bitpin]\ndomain = "ir"\n', encoding="utf-8")
    assert Config.from_file(path).rest_url == "https://api.bitpin.ir"
    monkeypatch.setenv("BITPIN_DOMAIN", "market")
    assert Config.from_env().domain == "market"
