"""Load the shared fixtures in /fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def fixture(endpoint_id: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{endpoint_id}.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def body(endpoint_id: str) -> Any:
    return fixture(endpoint_id)["body"]
