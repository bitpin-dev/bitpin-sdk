"""Generate java/src/main/java/io/github/bitpindev/bitpin/Spec.java from spec/bitpin.yaml.

Run without arguments to write the file, or with --check to fail (exit 1) when the
committed file differs from what the spec produces.
"""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec" / "bitpin.yaml"
OUT = (
    ROOT / "java" / "src" / "main" / "java" / "io" / "github" / "bitpindev" / "bitpin" / "Spec.java"
)


def java_str(value: str) -> str:
    # Persian text keeps its letters, but invisible format characters (e.g. the zero-width
    # non-joiner U+200C) are written as \u escapes so they're visible in the source.
    text = json.dumps(value, ensure_ascii=False)
    return "".join(f"\\u{ord(ch):04x}" if unicodedata.category(ch) == "Cf" else ch for ch in text)


def java_list(values: list[str]) -> str:
    return "List.of(" + ", ".join(java_str(v) for v in values) + ")"


def render(spec: dict[str, Any]) -> str:
    out = [
        "// Code generated from spec/bitpin.yaml by scripts/gen_java.py. DO NOT EDIT.",
        "",
        "package io.github.bitpindev.bitpin;",
        "",
        "import java.util.List;",
        "import java.util.Map;",
        "",
        "/** The values of spec/bitpin.yaml. */",
        "final class Spec {",
        "  private Spec() {}",
        "",
        "  /** Domains Bitpin serves the API on; REST and WebSocket switch together. */",
        "  static final Map<String, List<String>> DOMAINS =",
        "      Map.ofEntries(",
    ]
    names = sorted(spec["domains"])
    for i, name in enumerate(names):
        d = spec["domains"][name]
        sep = "," if i < len(names) - 1 else ");"
        out.append(
            f"          Map.entry({java_str(name)}, List.of({java_str(d['rest'])}, {java_str(d['ws'])})){sep}"
        )
    out += [
        "",
        f"  static final String DEFAULT_DOMAIN = {java_str(spec['default_domain'])};",
        "",
        f"  static final String DOCS_URL = {java_str(spec['urls']['docs'])};",
        "",
        "  static final Map<String, Integer> CONSTANTS =",
        "      Map.ofEntries(",
    ]
    keys = sorted(spec["constants"])
    for i, k in enumerate(keys):
        sep = "," if i < len(keys) - 1 else ");"
        out.append(f"          Map.entry({java_str(k)}, {spec['constants'][k]}){sep}")
    out += ["", "  static final Map<String, RateLimit> RATE_LIMITS =", "      Map.ofEntries("]
    keys = sorted(spec["rate_limits"])
    for i, k in enumerate(keys):
        v = spec["rate_limits"][k]
        sep = "," if i < len(keys) - 1 else ");"
        out.append(
            f"          Map.entry({java_str(k)}, new RateLimit({v['limit']}, {java_str(v['period'])})){sep}"
        )
    out += ["", "  static final Map<String, Endpoint> ENDPOINTS =", "      Map.ofEntries("]
    keys = sorted(spec["endpoints"])
    for i, k in enumerate(keys):
        e = spec["endpoints"][k]
        sep = "," if i < len(keys) - 1 else ");"
        out += [
            "          Map.entry(",
            f"              {java_str(k)},",
            "              new Endpoint(",
            f"                  {java_str(k)},",
            f"                  {java_str(e['method'])},",
            f"                  {java_str(e['path'])},",
            f"                  {java_str(e['auth'])},",
            f"                  {java_list(e['buckets'])},",
            f"                  {str(e['idempotent']).lower()})){sep}",
        ]
    out += ["", "  static final List<ErrorRule> ERROR_RULES =", "      List.of("]
    rules = spec["errors"]
    for i, r in enumerate(rules):
        sep = "," if i < len(rules) - 1 else ");"
        out.append(
            f"          new ErrorRule({r['status']}, {java_str(r['error'])}, "
            f"{java_list(r.get('paths', []))}, {java_list(r.get('detail', []))}){sep}"
        )
    out += [
        "",
        "  /** The ccxt-style capability map: false means Bitpin doesn't offer it yet. */",
        "  static final Map<String, Boolean> HAS =",
        "      Map.ofEntries(",
    ]
    keys = sorted(spec["has"])
    for i, k in enumerate(keys):
        sep = "," if i < len(keys) - 1 else ");"
        out.append(f"          Map.entry({java_str(k)}, {str(spec['has'][k]).lower()}){sep}")
    out += ["", "  /** English and Persian messages for each missing capability. */"]
    out += ["  static final Map<String, List<String>> NOT_SUPPORTED =", "      Map.ofEntries("]
    keys = sorted(spec["not_supported"])
    for i, k in enumerate(keys):
        v = spec["not_supported"][k]
        sep = "," if i < len(keys) - 1 else ");"
        out += [
            "          Map.entry(",
            f"              {java_str(k)},",
            "              List.of(",
            f"                  {java_str(v['en'])},",
            f"                  {java_str(v['fa'])})){sep}",
        ]
    out += ["", "  static final Map<String, String> WS_CHANNELS =", "      Map.ofEntries("]
    keys = sorted(spec["ws"]["channels"])
    for i, k in enumerate(keys):
        sep = "," if i < len(keys) - 1 else ");"
        out.append(
            f"          Map.entry({java_str(k)}, {java_str(spec['ws']['channels'][k])}){sep}"
        )
    out += ["}", ""]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    content = render(yaml.safe_load(SPEC.read_text(encoding="utf-8")))
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != content:
            print(f"{OUT.relative_to(ROOT)} is stale. Run: python scripts/gen_java.py")
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
