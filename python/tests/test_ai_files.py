"""The agent instructions point at files that exist, and enforced permissions match the policy."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / ".ai" / "project"


def test_root_files_exist() -> None:
    for name in (
        "AGENTS.md",
        "CLAUDE.md",
        "REVIEW.md",
        "SECURITY.md",
        ".github/copilot-instructions.md",
    ):
        assert (ROOT / name).is_file(), name


def test_claude_md_imports_agents_files() -> None:
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "@AGENTS.md" in text
    assert "@.ai/project/AGENTS.md" in text


def test_every_path_named_in_project_agents_exists() -> None:
    text = (PROJECT / "AGENTS.md").read_text(encoding="utf-8")
    paths = re.findall(r"`(\.ai/project/[^`]+)`", text)
    assert len(paths) >= 9
    for path in paths:
        assert (ROOT / path).exists(), path


def test_every_rule_and_skill_is_listed() -> None:
    text = (PROJECT / "AGENTS.md").read_text(encoding="utf-8")
    for rule in (PROJECT / "rules").glob("*.md"):
        assert f".ai/project/rules/{rule.name}" in text, rule.name
    for skill in (PROJECT / "skills").iterdir():
        assert f".ai/project/skills/{skill.name}/SKILL.md" in text, skill.name


@pytest.mark.parametrize(
    "skill", sorted(p.name for p in (PROJECT / "skills").iterdir()) if PROJECT.exists() else []
)
def test_skill_frontmatter(skill: str) -> None:
    text = (PROJECT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"^---\nname: (.+)\ndescription: (.+)\n---\n", text)
    assert match, skill
    assert match.group(1) == skill
    assert len(match.group(2)) <= 1024


def test_claude_settings_deny_dangerous_actions() -> None:
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    deny = settings["permissions"]["deny"]
    for rule in (
        "Read(./.env)",
        "Read(./.env.*)",
        "Bash(git push --force:*)",
        "Bash(twine upload:*)",
    ):
        assert rule in deny, rule


def test_no_internal_backend_references() -> None:
    """The repo is public: nothing may point into Bitpin's private backend code."""
    pattern = re.compile(
        r"bitpin/[a-z_]+/[a-z_]+\.py|gitlab\."
    )
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix in {
            ".md",
            ".py",
            ".yaml",
            ".yml",
            ".json",
            ".txt",
            ".toml",
        }:
            if any(
                part in {".venv", ".git", ".superpowers", "node_modules", "site"}
                for part in path.parts
            ):
                continue
            if path.name == "test_ai_files.py":
                continue
            assert not pattern.search(path.read_text(encoding="utf-8", errors="ignore")), path


def test_dependabot_prefixes_pass_the_pr_title_check() -> None:
    import yaml

    dependabot = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    workflow_path = ROOT / ".github" / "workflows" / "pr-title.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    types = workflow["jobs"]["conventional"]["steps"][0]["with"]["types"].split()
    for update in dependabot["updates"]:
        assert update["commit-message"]["prefix"] in types, update["package-ecosystem"]
