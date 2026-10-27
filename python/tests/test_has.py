"""The capability map: every true entry has a method, every false entry raises NotSupported."""

from __future__ import annotations

import re
from typing import Any

import pytest

from bitpin_sdk import errors
from bitpin_sdk._generated.spec import HAS
from tests.conftest import call

SPECIAL = {"sandbox": "set_sandbox_mode", "fetchOHLCV": "fetch_ohlcv", "watchOHLCV": "watch_ohlcv"}


def snake(name: str) -> str:
    return SPECIAL.get(name) or re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


@pytest.mark.parametrize("feature", sorted(HAS))
async def test_every_capability_has_a_method(client: Any, feature: str) -> None:
    assert callable(getattr(client, snake(feature))), feature


@pytest.mark.parametrize("feature", sorted(k for k, v in HAS.items() if not v))
async def test_missing_capabilities_raise_not_supported(client: Any, feature: str) -> None:
    with pytest.raises(errors.NotSupported) as info:
        await call(getattr(client, snake(feature))("x"))
    assert info.value.feature == feature
