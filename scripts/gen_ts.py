"""Generate ts/src/generated/spec.ts from spec/bitpin.yaml.

Run without arguments to write the file, or with --check to fail (exit 1) when the
committed file differs from what the spec produces.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec" / "bitpin.yaml"
OUT = ROOT / "ts" / "src" / "generated" / "spec.ts"


def camel(endpoint_id: str) -> str:
    head, *rest = endpoint_id.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)


def literal(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def render(spec: dict[str, Any]) -> str:
    endpoints = {
        endpoint_id: {
            "id": endpoint_id,
            "method": e["method"],
            "path": e["path"],
            "auth": e["auth"],
            "buckets": e["buckets"],
            "idempotent": e["idempotent"],
            "implicit": camel(endpoint_id),
        }
        for endpoint_id, e in spec["endpoints"].items()
    }
    rules = [
        {
            "status": r["status"],
            "error": r["error"],
            "paths": r.get("paths", []),
            "detail": r.get("detail", []),
        }
        for r in spec["errors"]
    ]
    rate_limits = {k: [v["limit"], v["period"]] for k, v in spec["rate_limits"].items()}
    not_supported = {k: [v["en"], v["fa"]] for k, v in spec["not_supported"].items()}
    implicit = "\n".join(
        f"  {camel(eid)}(params?: Record<string, unknown>, body?: unknown): Promise<any>;"
        for eid in sorted(spec["endpoints"])
    )
    return f"""// Generated from spec/bitpin.yaml by scripts/gen_ts.py. Do not edit.

export type Auth = "public" | "private" | "credentials";
export type Method = "GET" | "POST" | "DELETE";
export type Period = "sec" | "min" | "hour" | "day";

export interface Endpoint {{
  readonly id: string;
  readonly method: Method;
  readonly path: string;
  readonly auth: Auth;
  readonly buckets: readonly string[];
  readonly idempotent: boolean;
  readonly implicit: string;
}}

export interface ErrorRule {{
  readonly status: number;
  readonly error: string;
  readonly paths: readonly string[];
  readonly detail: readonly string[];
}}

export const URLS = {literal(spec["urls"])} as const;

export const CONSTANTS = {literal(spec["constants"])} as const;

export const RATE_LIMITS: Readonly<Record<string, readonly [number, Period]>> = {literal(rate_limits)};

export const ENDPOINTS: Readonly<Record<string, Endpoint>> = {literal(endpoints)};

export const ERROR_RULES: readonly ErrorRule[] = {literal(rules)};

export const HAS: Readonly<Record<string, boolean>> = {literal(spec["has"])};

export const NOT_SUPPORTED: Readonly<Record<string, readonly [string, string]>> = {literal(not_supported)};

export const WS_CHANNELS = {literal(spec["ws"]["channels"])} as const;

export const WS_EVENTS: Readonly<Record<string, string>> = {literal(spec["ws"]["events"])};

/** One method per spec endpoint, named in camelCase like ccxt's implicit API. */
export interface ImplicitApi {{
{implicit}
}}
"""


def main(argv: list[str]) -> int:
    content = render(yaml.safe_load(SPEC.read_text(encoding="utf-8")))
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != content:
            print(f"{OUT.relative_to(ROOT)} is stale. Run: python scripts/gen_ts.py")
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
