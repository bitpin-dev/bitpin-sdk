"""Write llms-full.txt: llms.txt followed by every English docs page, for AI agents.

Run without arguments to write it, or with --check to fail when it is stale.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORDER = [
    "index", "quickstart", "authentication", "configuration", "rate-limits", "market-data",
    "trading", "wallet", "websocket", "errors", "not-supported", "migrating-from-ccxt", "faq",
]


def render() -> str:
    pages = [(ROOT / "docs" / "en" / f"{name}.md").read_text(encoding="utf-8") for name in ORDER]
    extra = sorted(p.stem for p in (ROOT / "docs" / "en").glob("*.md") if p.stem not in ORDER)
    if extra:
        raise SystemExit(f"add these pages to ORDER in {Path(__file__).name}: {extra}")
    head = (ROOT / "llms.txt").read_text(encoding="utf-8")
    return head + "\n\n" + "\n\n---\n\n".join(p.strip() for p in pages) + "\n"


def main(argv: list[str]) -> int:
    content = render()
    out = ROOT / "llms-full.txt"
    if "--check" in argv:
        if not out.exists() or out.read_text(encoding="utf-8") != content:
            print("llms-full.txt is stale. Run: python scripts/gen_llms_full.py")
            return 1
        return 0
    out.write_text(content, encoding="utf-8")
    print("wrote llms-full.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
