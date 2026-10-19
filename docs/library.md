# qat-agent-helpers design

qat-agent-helpers is a Python helper library for AI agents that drive running Qt apps with [Qat](https://gitlab.com/testing-tool/qat) scripts. It ships together with two agent skills, qat-explore and qat-tests. This document records the design agreed on 2026-10-18; the names were chosen on 2026-10-19. The vocabulary is in [GLOSSARY.md](../GLOSSARY.md).

## Scope

- **First goal:** an agent writes and runs Python scripts on Qat and qat-agent-helpers to drive a live app: launch or attach, look, act, check.
- **Second goal:** turning what the agent learned while driving into Qat pytest tests.
- **What the library covers:** it helps only where Qat is weak. For everything else, including waits, property access and screenshots, agents use Qat's own API.
- **Out of scope:**
  - running existing Qat suites;
  - automation backends other than Qat;
  - touch and gestures;
  - signal subscriptions;
  - languages other than English in tests.

## Package

- **Name:** `qat-agent-helpers` as the package and `qat_agent_helpers` as the import, under the MIT licence. It is not on PyPI yet: until it is, scripts and test suites install it from this repository's release tag, `qat-agent-helpers @ git+https://github.com/Palm1r/qat-agent-skills@vX.Y.Z`. It was called qatkit until 2026-10-19.
- **Unofficial:** the README starts with, and the package description includes, "Unofficial, community-made. Not affiliated with or endorsed by the Qat project."
- **Python:** `requires-python >= 3.10`.
- **Qat:** pinned exactly, `qat==1.8.1`, and bumped deliberately.
- **Repository:** `Palm1r/qat-agent-skills` on GitHub.

## API, v1

A target is a Qat definition or a Qat object proxy. There are no refs. A definition is looked up in the current app: `launch()` and `attach()` make the new app Qat's current app, as `qat.start_application()` does, so that Qat's own `wait_for_*` functions work on it at once.

| Call | What it does |
|---|---|
| `launch(path, args=(), env=None, lock_ui=False) -> App` | Starts the app with Qat's parts ([ADR 0002](adr/0002-apps-are-launched-with-qats-parts.md)) and waits until it is connected. No `applications.json` is written, there is a single launch attempt, `env` applies to this app only, and state lives in a per-process temp directory. Also works as a context manager. |
| `attach(pid) -> App` | Attaches to a running Qt process. On Windows that can be any suitable process; on Linux and macOS, only one that Qat launched. |
| `App.close(timeout=5)` | For a launched app: calls `quit()` through Qat, kills the process if it is still running after `timeout`, and returns its exit code, so that a test can check for 0, a clean quit. Launched apps are also closed when the context manager exits or the script ends. |
| `App.detach()` | For an attached app; attached apps are never closed. |
| `App.context`, `App.pid` | The Qat `ApplicationContext`, for direct Qat calls, and the process id. |
| `snapshot(target=None, depth=None, include_hidden=False, include_internal=False) -> str` | A compact object tree, described below the table. Without a target, it shows every top-level window of the current app. |
| `click(target, button="left", double=False, modifiers=(), x=None, y=None)` | A non-blocking press and release, followed by a barrier ([ADR 0001](adr/0001-input-is-non-blocking-with-a-barrier.md)). For check boxes, radio buttons and switches, it aims at the indicator and raises if `checked` did not change. |
| `press_keys(target, keys)` | A key or shortcut such as `Return` or `Ctrl+S`, sent with `shortcut(..., blocking=False)` and followed by a barrier. |
| `type_text(target, text)` | Calls `type_in`, which is blocking because Qat has no other mode. Refuses non-ASCII text with a hint to set the `text` property instead. |
| `definition_for(obj) -> dict` | A portable definition that matches only this object, for tests. When none is unique, it returns the best candidate with an `AmbiguousDefinitionWarning`. |

What `snapshot` prints:
- the tree is de-duplicated by uid;
- by default only visible objects are included, and non-visual QObjects are left out;
- internal objects are left out with their subtrees, hidden or not, unless `include_internal=True`. For now they are the containers Qt puts a scroll area's scroll bars in (`qt_scrollarea_hcontainer`, `qt_scrollarea_vcontainer`): every scroll area, such as a list or a text editor, has two, and they never hold the app's own objects. The other objects Qt names `qt_...` stay, because they hold what agents need: a scroll area's viewport and contents (`qt_scrollarea_viewport`), a tab widget's pages (`qt_tabwidget_stackedwidget`), a message box's text and buttons (`qt_msgbox_label`, `qt_msgbox_buttonbox`) and a spin box's field (`qt_spinbox_lineedit`);
- each line carries the type, `#objectName`, `id=`, the text or `placeholderText`, flags, and `def={...}` when a unique definition exists;
- output is cut at about 8k tokens with a note on how many objects were left out.

Three more pieces:
- **Waiting:** before `click`, `press_keys` and `type_text`, the library waits until the target is visible and enabled, as long as `qat.wait_for_object()` would (`Settings.wait_for_object_timeout`), because Qat skips that check for objects addressed by uid.
- **Ambiguous lookups:** an error lists the candidates with their definitions.
- **pytest plugin:** the fixture factory `launch_app`, which launches an app and closes it in teardown.

Definitions are picked in this order, with each candidate checked for uniqueness with `find_all_objects`:
1. `objectName` + `type`;
2. QML `id` + `type`;
3. `type` + `text`;
4. the same inside the nearest ancestor that has a unique definition (`container`);
5. otherwise, the best candidate, flagged as ambiguous, with a hint to set an `objectName` in the app.

## Skills

Two skills live in `skills/` and follow the Agent Skills standard. Each `name` matches its folder, and each description says what the skill is for and points at the other one, so that an agent picks the right one.

`skills/qat-explore/SKILL.md` is for working with a live app. It covers:
- the workflow: launch with qat-agent-helpers, take a snapshot, act, check with Qat's `wait_for_*`, until one script runs the whole scenario;
- the library's calls and a Qat cheat-sheet: definitions, waits, proxies and screenshots;
- the pitfalls:
  - only Release builds work, and on Windows only MSVC;
  - modal dialogs;
  - Return in a text field;
  - check boxes;
  - ambiguous definitions;
  - non-ASCII text;
- how to run scripts. A PEP 723 header (`# /// script`, with `dependencies = ["qat-agent-helpers @ git+https://github.com/Palm1r/qat-agent-skills@vX.Y.Z"]`) and `uv run script.py` need no setup in the user's project;
- sandboxes, which are untested. Codex needs network access in its sandbox (`network_access = true`) or an approval per run, and Cursor needs commands run outside its sandbox. Without that, scripts probably cannot reach the app's Qat server on localhost.

`skills/qat-tests/SKILL.md` is for turning what was learned into pytest tests. It covers:
- the setup: `qat-agent-helpers` as a dev dependency, whose plugin provides `launch_app`;
- writing tests: one behaviour per test, definitions in constants, a wait for every effect, and `assert app.close() == 0` for a clean exit;
- the pitfalls that matter in tests, repeated from qat-explore: non-blocking clicks, check boxes, what `wait_for_object_missing` waits for, and the exit code from `close()`;
- running the tests. For exploring an app, it points to qat-explore.

How they are distributed: the README documents `npx skills add Palm1r/qat-agent-skills`, `gh skill install Palm1r/qat-agent-skills`, and copying both folders by hand into `.claude/skills/` (Claude Code), `.agents/skills/` (Codex) or either of them (Cursor). There are no plugin manifests in v1. A Claude Code plugin marketplace is the first one to add if needed.

## Development and releases

- **Toolchain:** mise provides Python 3.13 and uv, and uv manages the virtual environment and the lockfile.
- **Tests:** development is test-first, in vertical slices. Unit tests drive a fake Qat adapter, so they need no Qt. Changes that depend on how real Qat behaves, and any Qat version bump, need a run against a real Qt app.
- **Releases:**
  - the version lives in `pyproject.toml`, starts at 0.1.0 and is bumped by hand;
  - each release gets a `vX.Y.Z` tag, which is what the skills install from. Publishing to PyPI through Trusted Publishing on that tag is planned but not set up;
  - CHANGELOG.md follows Keep a Changelog.
- **Known Qat issues:** listed in the README.
