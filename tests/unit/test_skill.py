"""The agent skills follow the Agent Skills format and name only APIs that exist."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import qat

import qat_agent_helpers

ROOT = Path(__file__).resolve().parents[2]
SKILLS = sorted((ROOT / "skills").glob("*/SKILL.md"))


def frontmatter_and_body(skill: Path) -> tuple[dict[str, str], str]:
    text = skill.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    assert match, f"{skill} must start with YAML frontmatter between --- lines"
    fields = dict(line.split(": ", 1) for line in match.group(1).splitlines())
    return fields, match.group(2)


@pytest.fixture(params=SKILLS, ids=lambda skill: skill.parent.name)
def skill(request: pytest.FixtureRequest) -> Path:
    return request.param


def test_there_is_one_skill_to_explore_apps_and_one_to_write_tests():
    assert [skill.parent.name for skill in SKILLS] == ["qat-explore", "qat-tests"]


def test_the_name_follows_the_rules_and_matches_the_folder(skill: Path):
    fields, _ = frontmatter_and_body(skill)

    assert fields["name"] == skill.parent.name
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fields["name"])


def test_the_description_says_what_and_when_within_1024_characters(skill: Path):
    fields, _ = frontmatter_and_body(skill)

    assert 0 < len(fields["description"]) <= 1024
    assert "Use when" in fields["description"]


def test_each_description_points_at_the_other_skill():
    explore, tests = (frontmatter_and_body(skill)[0]["description"] for skill in SKILLS)

    assert "qat-tests" in explore
    assert "qat-explore" in tests


def test_the_body_stays_under_500_lines(skill: Path):
    _, body = frontmatter_and_body(skill)

    assert len(body.splitlines()) < 500


def test_every_pinned_library_version_is_the_current_one(skill: Path):
    _, body = frontmatter_and_body(skill)
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)

    assert version
    # Until the library is on PyPI, the skills install it from this repository's release tag.
    pins = re.findall(
        r"qat-agent-helpers @ git\+https://github\.com/Palm1r/qat-agent-skills@v(\d+(?:\.\d+)*)",
        body,
    )
    assert pins and set(pins) == {version.group(1)}
    assert "qat-agent-helpers==" not in body


def test_every_helper_and_qat_function_it_names_exists(skill: Path):
    _, body = frontmatter_and_body(skill)

    helper_names = set(re.findall(r"\bqat_agent_helpers\.(\w+)\(", body))
    qat_names = set(re.findall(r"\bqat\.(\w+)", body))

    assert helper_names and qat_names
    exported = set(qat_agent_helpers.__all__)
    assert helper_names <= exported, helper_names - exported
    assert {name for name in qat_names if not hasattr(qat, name)} == set()
