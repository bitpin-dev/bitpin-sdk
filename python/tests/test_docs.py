from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_docs_are_complete_in_both_languages() -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts" / "check_docs.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_llms_full_is_fresh() -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts" / "gen_llms_full.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
