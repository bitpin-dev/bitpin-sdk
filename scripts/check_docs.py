"""Check that the English and Persian docs stay complete and in sync with the code and spec.

- every page in docs/en has a twin in docs/fa (and the other way round)
- every public client method is documented in both languages and in llms.txt
- the rate-limit pages list every bucket with its default, the not-supported pages list
  every missing capability
- both READMEs exist and link to each other
"""

from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "src"))

from bitpin_sdk import AsyncBitpin  # noqa: E402
from bitpin_sdk._generated.spec import HAS, RATE_LIMITS  # noqa: E402

SPECIAL = {"sandbox": "set_sandbox_mode", "fetchOHLCV": "fetch_ohlcv", "watchOHLCV": "watch_ohlcv"}


def snake(name: str) -> str:
    return SPECIAL.get(name) or re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def public_methods() -> list[str]:
    return sorted(
        name
        for name, _ in inspect.getmembers(AsyncBitpin, inspect.isfunction)
        if not name.startswith("_")
    )


def read_dir(path: Path) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(path.glob("*.md")))


def check() -> list[str]:
    problems: list[str] = []
    en_dir, fa_dir = ROOT / "docs" / "en", ROOT / "docs" / "fa"
    en_pages = {p.name for p in en_dir.glob("*.md")}
    fa_pages = {p.name for p in fa_dir.glob("*.md")}
    for page in sorted(en_pages - fa_pages):
        problems.append(f"docs/fa/{page} is missing (exists in English)")
    for page in sorted(fa_pages - en_pages):
        problems.append(f"docs/en/{page} is missing (exists in Persian)")

    texts = {"docs/en": read_dir(en_dir), "docs/fa": read_dir(fa_dir)}
    llms = ROOT / "llms.txt"
    texts["llms.txt"] = llms.read_text(encoding="utf-8") if llms.exists() else ""
    for method in public_methods():
        for where, text in texts.items():
            if not re.search(rf"\b{method}\b", text):
                problems.append(f"{where}: method {method} is not documented")

    for lang in ("en", "fa"):
        page = ROOT / "docs" / lang / "rate-limits.md"
        text = page.read_text(encoding="utf-8") if page.exists() else ""
        for bucket, (limit, period) in RATE_LIMITS.items():
            if not re.search(rf"`{bucket}`.*\|\s*{limit:,}\s*/\s*{period}\b".replace(",", r"[,٬]?"), text):
                problems.append(f"docs/{lang}/rate-limits.md: bucket {bucket} ({limit}/{period}) missing")
        page = ROOT / "docs" / lang / "not-supported.md"
        text = page.read_text(encoding="utf-8") if page.exists() else ""
        for feature, ok in HAS.items():
            if not ok and f"`{snake(feature)}" not in text:
                problems.append(f"docs/{lang}/not-supported.md: {snake(feature)} missing")

    for name, other in (("README.md", "README.fa.md"), ("README.fa.md", "README.md")):
        path = ROOT / name
        if not path.exists():
            problems.append(f"{name} is missing")
        elif other not in path.read_text(encoding="utf-8"):
            problems.append(f"{name} doesn't link to {other}")
    return problems


def main() -> int:
    problems = check()
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} docs problem(s)")
        return 1
    print("docs ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
