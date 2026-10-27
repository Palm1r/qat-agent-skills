from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
import qat

import qat_agent_helpers

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "qat"
SKILL = SKILL_DIR / "SKILL.md"
REFERENCES = sorted((SKILL_DIR / "references").glob("*.md"))


def frontmatter_and_body(skill: Path) -> tuple[dict[str, str], str]:
    text = skill.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    assert match, f"{skill} must start with YAML frontmatter between --- lines"
    fields = dict(line.split(": ", 1) for line in match.group(1).splitlines())
    return fields, match.group(2)


def body() -> str:
    return frontmatter_and_body(SKILL)[1]


@pytest.fixture(params=[SKILL, *REFERENCES], ids=lambda page: page.name)
def page(request: pytest.FixtureRequest) -> str:
    path: Path = request.param
    return body() if path == SKILL else path.read_text(encoding="utf-8")


def table_rows(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if line.startswith("| `"))


def test_there_is_one_skill_named_qat():
    assert [path.parent.name for path in sorted((ROOT / "skills").glob("*/SKILL.md"))] == ["qat"]


def test_the_name_follows_the_rules_and_matches_the_folder():
    fields, _ = frontmatter_and_body(SKILL)

    assert fields["name"] == SKILL_DIR.name
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fields["name"])


def test_the_description_says_what_and_when_within_1024_characters():
    fields, _ = frontmatter_and_body(SKILL)

    assert 0 < len(fields["description"]) <= 1024
    assert "Use when" in fields["description"]


def test_the_body_stays_under_500_lines():
    assert len(body().splitlines()) < 500


def test_skill_md_links_every_reference_and_only_existing_ones():
    linked = set(re.findall(r"\]\((references/[\w.-]+\.md)\)", body()))

    assert {f"references/{path.name}" for path in REFERENCES} == linked


def test_a_long_reference_opens_with_its_contents():
    for path in REFERENCES:
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > 100:
            assert any(line.startswith("- [") for line in lines[:10]), path.name


def test_every_pinned_library_version_is_the_current_one(page: str):
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)

    assert version
    # Until the library is on PyPI, the skill installs it from this repository's release tag.
    pins = re.findall(
        r"qat-agent-helpers @ git\+https://github\.com/Palm1r/qat-agent-skills@v(\d+(?:\.\d+)*)",
        page,
    )
    assert set(pins) <= {version.group(1)}
    assert "qat-agent-helpers==" not in page


def test_every_helper_and_qat_name_it_mentions_exists(page: str):
    helper_names = set(re.findall(r"\bqat_agent_helpers\.(\w+)\(", page))
    qat_names = set(re.findall(r"\bqat\.(\w+)", page))

    exported = set(qat_agent_helpers.__all__)
    assert helper_names <= exported, helper_names - exported
    missing = {
        name
        for name in qat_names
        if not hasattr(qat, name) and importlib.util.find_spec(f"qat.{name}") is None
    }
    assert missing == set()


def test_skill_md_lists_every_exported_function_and_app_member_in_its_table():
    # README.md and docs/library.md point here instead of repeating the table, so a call
    # missing here is a call agents never learn about.
    rows = table_rows(body())

    exported_functions = {
        name
        for name in qat_agent_helpers.__all__
        if callable(getattr(qat_agent_helpers, name)) and not name[0].isupper()
    }
    listed = set(re.findall(r"qat_agent_helpers\.(\w+)\(", rows))
    assert exported_functions <= listed, exported_functions - listed
    for member in ("app.close(", "app.detach(", "app.context", "app.pid"):
        assert member in rows, member


def test_the_tests_reference_shows_the_fixture_and_a_clean_exit():
    tests = (SKILL_DIR / "references" / "tests.md").read_text(encoding="utf-8")

    assert "launch_app(" in table_rows(tests)
    assert "assert app.close() == 0" in tests


def test_skill_md_pins_the_library_in_its_script_header():
    pin = r"qat-agent-helpers @ git\+https://github\.com/Palm1r/qat-agent-skills@v"

    assert re.search(pin, body())
