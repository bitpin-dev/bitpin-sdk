"""The generated endpoint table must match spec/bitpin.yaml exactly."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from bitpin_sdk._generated import spec as generated

ROOT = Path(__file__).resolve().parents[2]


def test_generated_is_fresh() -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts" / "gen_python.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_endpoints_match_yaml() -> None:
    raw = yaml.safe_load((ROOT / "spec" / "bitpin.yaml").read_text(encoding="utf-8"))
    assert set(generated.ENDPOINTS) == set(raw["endpoints"])
    for endpoint_id, entry in raw["endpoints"].items():
        endpoint = generated.ENDPOINTS[endpoint_id]
        assert endpoint.id == endpoint_id
        assert endpoint.method == entry["method"]
        assert endpoint.path == entry["path"]
        assert endpoint.auth == entry["auth"]
        assert endpoint.buckets == tuple(entry["buckets"])
        assert endpoint.idempotent is entry["idempotent"]


def test_tables_match_yaml() -> None:
    raw = yaml.safe_load((ROOT / "spec" / "bitpin.yaml").read_text(encoding="utf-8"))
    assert generated.URLS == raw["urls"]
    assert generated.CONSTANTS == raw["constants"]
    assert generated.RATE_LIMITS == {k: (v["limit"], v["period"]) for k, v in raw["rate_limits"].items()}
    assert generated.HAS == raw["has"]
    assert generated.NOT_SUPPORTED == {k: (v["en"], v["fa"]) for k, v in raw["not_supported"].items()}
    assert generated.WS_CHANNELS == raw["ws"]["channels"]
    assert generated.WS_EVENTS == raw["ws"]["events"]
    assert len(generated.ERROR_RULES) == len(raw["errors"])
    first = generated.ERROR_RULES[0]
    assert (first.status, first.error) == (raw["errors"][0]["status"], raw["errors"][0]["error"])
