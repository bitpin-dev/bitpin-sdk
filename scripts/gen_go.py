"""Generate go/spec_gen.go from spec/bitpin.yaml.

Run without arguments to write the file, or with --check to fail (exit 1) when the
committed file differs from what the spec produces.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec" / "bitpin.yaml"
OUT = ROOT / "go" / "spec_gen.go"


def go_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def go_strings(values: list[str]) -> str:
    return "[]string{" + ", ".join(go_str(v) for v in values) + "}"


def render(spec: dict[str, Any]) -> str:
    out = [
        "// Code generated from spec/bitpin.yaml by scripts/gen_go.py. DO NOT EDIT.",
        "",
        "package bitpin",
        "",
        "// Domains Bitpin serves the API on; REST and WebSocket switch together.",
        "var specDomains = map[Domain]domainURLs{",
    ]
    for name in sorted(spec["domains"]):
        d = spec["domains"][name]
        out.append(f"\t{go_str(name)}: {{rest: {go_str(d['rest'])}, ws: {go_str(d['ws'])}}},")
    out += ["}", "", f"const defaultDomain Domain = {go_str(spec['default_domain'])}", ""]
    out.append(f"const docsURL = {go_str(spec['urls']['docs'])}")
    out += ["", "var specConstants = map[string]int{"]
    for k in sorted(spec["constants"]):
        out.append(f"\t{go_str(k)}: {spec['constants'][k]},")
    out += ["}", "", "var specRateLimits = map[string]RateLimit{"]
    for k in sorted(spec["rate_limits"]):
        v = spec["rate_limits"][k]
        out.append(f"\t{go_str(k)}: {{Limit: {v['limit']}, Period: {go_str(v['period'])}}},")
    out += ["}", "", "var specEndpoints = map[string]endpoint{"]
    for k in sorted(spec["endpoints"]):
        e = spec["endpoints"][k]
        out.append(
            f"\t{go_str(k)}: {{id: {go_str(k)}, method: {go_str(e['method'])}, path: {go_str(e['path'])}, "
            f"auth: {go_str(e['auth'])}, buckets: {go_strings(e['buckets'])}, idempotent: {str(e['idempotent']).lower()}}},"
        )
    out += ["}", "", "var specErrorRules = []errorRule{"]
    for r in spec["errors"]:
        out.append(
            f"\t{{status: {r['status']}, kind: {go_str(r['error'])}, paths: {go_strings(r.get('paths', []))}, "
            f"detail: {go_strings(r.get('detail', []))}}},"
        )
    out += ["}", "", "// Has is the ccxt-style capability map: false means Bitpin doesn't offer it yet.",
            "var Has = map[string]bool{"]
    for k in sorted(spec["has"]):
        out.append(f"\t{go_str(k)}: {str(spec['has'][k]).lower()},")
    out += ["}", "", "var specNotSupported = map[string][2]string{"]
    for k in sorted(spec["not_supported"]):
        v = spec["not_supported"][k]
        out.append(f"\t{go_str(k)}: {{{go_str(v['en'])}, {go_str(v['fa'])}}},")
    out += ["}", "", "var specWSChannels = map[string]string{"]
    for k in sorted(spec["ws"]["channels"]):
        out.append(f"\t{go_str(k)}: {go_str(spec['ws']['channels'][k])},")
    out += ["}", ""]
    source = "\n".join(out)
    # gofmt aligns map literals; formatting here keeps --check stable.
    return subprocess.run(["gofmt"], input=source, capture_output=True, text=True, check=True).stdout


def main(argv: list[str]) -> int:
    content = render(yaml.safe_load(SPEC.read_text(encoding="utf-8")))
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != content:
            print(f"{OUT.relative_to(ROOT)} is stale. Run: python scripts/gen_go.py")
            return 1
        return 0
    OUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
