"""Build HTTP requests from the endpoint table. Pure: no I/O."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import quote

from bitpin_sdk._core.numbers import fmt_decimal
from bitpin_sdk._generated.spec import ENDPOINTS, Auth, Method
from bitpin_sdk.config import Config


@dataclass(frozen=True)
class Request:
    endpoint_id: str
    method: Method
    url: str
    params: dict[str, str] | None
    json: Any
    auth: Auth
    buckets: tuple[str, ...]
    idempotent: bool


def _query_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (Decimal, float)):
        return fmt_decimal(value)
    if isinstance(value, (list, tuple, set)):
        return ",".join(_query_value(v) for v in value)
    return str(value)


def _body_value(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (Decimal, float, int)):
        return fmt_decimal(value)
    if isinstance(value, Mapping):
        return {k: _body_value(v) for k, v in value.items() if v is not None}
    if isinstance(value, (list, tuple)):
        return [_body_value(v) for v in value]
    return value


def build_request(
    config: Config,
    endpoint_id: str,
    path_params: Mapping[str, Any] | None = None,
    params: Mapping[str, Any] | None = None,
    body: Any = None,
) -> Request:
    endpoint = ENDPOINTS[endpoint_id]
    path = endpoint.path
    for key, value in (path_params or {}).items():
        path = path.replace("{" + key + "}", quote(str(value), safe=""))
    if "{" in path:
        missing = path[path.index("{") + 1 : path.index("}")]
        raise ValueError(f"missing path parameter {missing!r} for {endpoint_id}")

    query = {k: _query_value(v) for k, v in (params or {}).items() if v is not None}
    return Request(
        endpoint_id=endpoint_id,
        method=endpoint.method,
        url=config.rest_url.rstrip("/") + path,
        params=query or None,
        json=_body_value(body) if body is not None else None,
        auth=endpoint.auth,
        buckets=endpoint.buckets,
        idempotent=endpoint.idempotent,
    )
