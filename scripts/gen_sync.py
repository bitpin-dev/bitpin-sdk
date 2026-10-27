"""Generate the sync client (python/src/bitpin_sdk/_sync/) from the async one with unasync.

Run without arguments to write the files, or with --check to fail (exit 1) when the
committed files differ from what the async source produces. ``_sync/_compat.py`` is
hand-written and not generated.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import unasync

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "python" / "src" / "bitpin_sdk"
FILES = ("__init__.py", "client.py")
HEADER = "# Generated from _async/{name} by scripts/gen_sync.py. Do not edit.\n"
REPLACEMENTS = {
    "_async": "_sync",
    "AsyncBitpin": "Bitpin",
    "AsyncClient": "Client",
    "aclose": "close",
}
# unasync rewrites code tokens; these fix the same words inside docstrings and comments.
TEXT_REPLACEMENTS = {
    "AsyncBitpin": "Bitpin",
    "``_sync/client.py`` is generated from this file by ``scripts/gen_sync.py``. Edit this file\n"
    "only, then regenerate.": "Generated from ``_async/client.py``; edit that file instead.",
    "The async client. The hand-written source of truth; ``_sync`` is generated from it.": (
        "The sync client, generated from ``_async``."
    ),
    "await client.": "client.",
}


def render() -> dict[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "_async"
        src.mkdir()
        for name in FILES:
            (src / name).write_text(
                (PKG / "_async" / name).read_text(encoding="utf-8"), encoding="utf-8"
            )
        rule = unasync.Rule(
            str(src) + "/", str(Path(tmp) / "_sync") + "/", additional_replacements=REPLACEMENTS
        )
        unasync.unasync_files([str(src / n) for n in FILES], [rule])
        out: dict[str, str] = {}
        for name in FILES:
            text = (Path(tmp) / "_sync" / name).read_text(encoding="utf-8")
            for old, new in TEXT_REPLACEMENTS.items():
                text = text.replace(old, new)
            out[name] = HEADER.format(name=name) + text
        return out


def main(argv: list[str]) -> int:
    rendered = render()
    target = PKG / "_sync"
    if "--check" in argv:
        stale = [
            n
            for n, text in rendered.items()
            if not (target / n).exists() or (target / n).read_text(encoding="utf-8") != text
        ]
        if stale:
            print(f"_sync is stale ({', '.join(stale)}). Run: python scripts/gen_sync.py")
            return 1
        return 0
    target.mkdir(exist_ok=True)
    for name, text in rendered.items():
        (target / name).write_text(text, encoding="utf-8")
        print(f"wrote {(target / name).relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
