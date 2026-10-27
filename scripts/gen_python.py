"""Generate python/src/bitpin_sdk/_generated/spec.py from spec/bitpin.yaml.

Run without arguments to write the file, or with --check to fail (exit 1) when the
committed file differs from what the spec produces.
"""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pformat
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec" / "bitpin.yaml"
OUT = ROOT / "python" / "src" / "bitpin_sdk" / "_generated" / "spec.py"

HEADER = '''\
# Generated from spec/bitpin.yaml by scripts/gen_python.py. Do not edit.
"""Bitpin API description: endpoints, rate limits, constants and capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Auth = Literal["public", "private", "credentials"]
Method = Literal["GET", "POST", "DELETE"]
Period = Literal["sec", "min", "hour", "day"]


@dataclass(frozen=True)
class Endpoint:
    id: str
    method: Method
    path: str
    auth: Auth
    buckets: tuple[str, ...]
    idempotent: bool


@dataclass(frozen=True)
class ErrorRule:
    status: int
    error: str
    paths: tuple[str, ...] = ()
    detail: tuple[str, ...] = ()

'''


def _table(name: str, annotation: str, value: Any) -> str:
    return f"{name}: {annotation} = {pformat(value, width=96, sort_dicts=True)}\n\n"


def render(spec: dict[str, Any]) -> str:
    parts = [HEADER]
    parts.append(_table("URLS", "dict[str, str]", spec["urls"]))
    parts.append(_table("CONSTANTS", "dict[str, int]", spec["constants"]))
    rate_limits = {k: (v["limit"], v["period"]) for k, v in spec["rate_limits"].items()}
    parts.append(_table("RATE_LIMITS", "dict[str, tuple[int, Period]]", rate_limits))

    lines = ["ENDPOINTS: dict[str, Endpoint] = {"]
    for endpoint_id in sorted(spec["endpoints"]):
        e = spec["endpoints"][endpoint_id]
        lines.append(
            f"    {endpoint_id!r}: Endpoint(\n"
            f"        id={endpoint_id!r},\n"
            f"        method={e['method']!r},\n"
            f"        path={e['path']!r},\n"
            f"        auth={e['auth']!r},\n"
            f"        buckets={tuple(e['buckets'])!r},\n"
            f"        idempotent={e['idempotent']!r},\n"
            "    ),"
        )
    lines.append("}\n\n")
    parts.append("\n".join(lines))

    lines = ["ERROR_RULES: tuple[ErrorRule, ...] = ("]
    for rule in spec["errors"]:
        lines.append(
            f"    ErrorRule(status={rule['status']!r}, error={rule['error']!r}, "
            f"paths={tuple(rule.get('paths', ()))!r}, detail={tuple(rule.get('detail', ()))!r}),"
        )
    lines.append(")\n\n")
    parts.append("\n".join(lines))

    parts.append(_table("HAS", "dict[str, bool]", spec["has"]))
    not_supported = {k: (v["en"], v["fa"]) for k, v in spec["not_supported"].items()}
    parts.append(_table("NOT_SUPPORTED", "dict[str, tuple[str, str]]", not_supported))
    parts.append(_table("WS_CHANNELS", "dict[str, str]", spec["ws"]["channels"]))
    parts.append(_table("WS_EVENTS", "dict[str, str]", spec["ws"]["events"]).rstrip() + "\n")
    return "".join(parts)


def main(argv: list[str]) -> int:
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    content = render(spec)
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != content:
            print(f"{OUT.relative_to(ROOT)} is stale. Run: python scripts/gen_python.py")
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
