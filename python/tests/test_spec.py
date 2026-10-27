"""Checks on spec/bitpin.yaml, the single source of truth for every SDK language."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "spec" / "bitpin.yaml"
SCHEMA_PATH = ROOT / "spec" / "schema.json"


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_spec_validates_against_schema(spec: dict[str, Any]) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(spec, schema)


def test_every_endpoint_path_starts_with_api_and_ends_with_slash(spec: dict[str, Any]) -> None:
    for endpoint_id, endpoint in spec["endpoints"].items():
        assert endpoint["path"].startswith("/api/"), endpoint_id
        assert endpoint["path"].endswith("/"), endpoint_id


def test_every_endpoint_bucket_exists(spec: dict[str, Any]) -> None:
    for endpoint_id, endpoint in spec["endpoints"].items():
        for bucket in endpoint["buckets"]:
            assert bucket in spec["rate_limits"], f"{endpoint_id}: unknown bucket {bucket}"


def test_every_bucket_is_used(spec: dict[str, Any]) -> None:
    used = {b for e in spec["endpoints"].values() for b in e["buckets"]}
    assert set(spec["rate_limits"]) == used


def test_endpoint_id_matches_auth_method_and_path(spec: dict[str, Any]) -> None:
    for endpoint_id, endpoint in spec["endpoints"].items():
        prefix = f"{endpoint['auth']}_{endpoint['method'].lower()}_"
        assert endpoint_id.startswith(prefix), endpoint_id


def test_every_has_false_has_bilingual_message(spec: dict[str, Any]) -> None:
    missing = {name for name, ok in spec["has"].items() if not ok}
    assert missing == set(spec["not_supported"])
    for name, message in spec["not_supported"].items():
        assert message["en"].strip(), name
        assert message["fa"].strip(), name


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/wlt/address/",
        "/api/v1/wlt/networks/",
        "/api/v1/wlt/deposits/",
        "/api/v1/wlt/withdraws/",
        "/api/v1/wlt/withdraws/by-currency-code/",
    ],
)
def test_no_deprecated_v1_wallet_paths(spec: dict[str, Any], path: str) -> None:
    assert path not in {e["path"] for e in spec["endpoints"].values()}


def test_writes_are_never_idempotent(spec: dict[str, Any]) -> None:
    for endpoint_id, endpoint in spec["endpoints"].items():
        if endpoint["method"] in {"POST", "DELETE"} and endpoint_id != "private_post_wlt_address":
            assert endpoint["idempotent"] is False, endpoint_id
