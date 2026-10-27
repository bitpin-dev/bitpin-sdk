"""Validate spec/bitpin.yaml against spec/schema.json. Exit 1 on any problem."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    spec = yaml.safe_load((ROOT / "spec" / "bitpin.yaml").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "spec" / "schema.json").read_text(encoding="utf-8"))
    try:
        jsonschema.validate(spec, schema)
    except jsonschema.ValidationError as exc:
        print(f"spec/bitpin.yaml is invalid: {exc.message} at {list(exc.absolute_path)}")
        return 1
    if spec["default_domain"] not in spec["domains"]:
        print(f"default_domain {spec['default_domain']!r} is not one of the domains")
        return 1
    print(
        f"spec ok: {len(spec['endpoints'])} endpoints, {len(spec['rate_limits'])} rate-limit buckets"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
