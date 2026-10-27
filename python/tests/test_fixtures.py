from __future__ import annotations

import re

from bitpin_sdk._generated.spec import ENDPOINTS
from tests.fixtures import FIXTURES, fixture


def test_every_endpoint_has_a_fixture() -> None:
    names = {p.stem for p in FIXTURES.glob("*.json")} - {"expected"}
    assert names == set(ENDPOINTS)


def test_fixture_status_is_success() -> None:
    for endpoint_id in ENDPOINTS:
        assert fixture(endpoint_id)["status"] in (200, 201, 204), endpoint_id


def test_fixtures_contain_no_real_looking_secrets() -> None:
    for path in FIXTURES.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"IR\d{2}(?!0{22})\d{22}", text), path.name  # only all-zero IBANs
        assert not re.search(r"09\d{9}", text), path.name  # no Iranian mobile numbers


def test_expected_outputs_are_fresh() -> None:
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(root / "scripts" / "gen_expected.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
