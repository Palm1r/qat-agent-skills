# qat-agent-helpers design

qat-agent-helpers is a Python helper library for AI agents that drive running Qt apps with [Qat](https://gitlab.com/testing-tool/qat) scripts. It ships together with one agent skill, `qat`. This document records the design agreed on 2026-10-18 and reworked on 2026-10-28; the names were chosen on 2026-10-19. The vocabulary is in [GLOSSARY.md](../GLOSSARY.md).

## Scope

- **First goal:** an agent writes and runs Python scripts on Qat and qat-agent-helpers to drive a live app, launching or attaching, looking, acting and checking, whether to explore the app, to check a change in it or to reproduce a bug.
- **Second goal:** turning what the agent learned while driving into tests, in a pytest suite or in the project's Qat suite.
- **What the library covers:** it helps only where Qat is weak. For everything else, including waits, property access and screenshots, agents use Qat's own API, which the skill documents in full.
- **Out of scope for the library**, though the skill shows Qat's own calls for them:
  - running Qat suites, which keep their own runner;
  - touch and gestures;
  - signal subscriptions.
- **Out of scope altogether:**
  - automation backends other than Qat;
  - an MCP server ([ADR 0004](adr/0004-agents-drive-apps-with-scripts-not-mcp.md));
  - setting up tests in CI, for now;
  - languages other than English in tests.

## Package

- **Name:** `qat-agent-helpers` as the package and `qat_agent_helpers` as the import, under the MIT licence. It is not on PyPI yet: until it is, scripts and test suites install it from this repository's release tag, `qat-agent-helpers @ git+https://github.com/Palm1r/qat-agent-skills@vX.Y.Z`. It was called qatkit until 2026-10-19.
- **Unofficial:** the README starts with, and the package description includes, "Unofficial, community-made. Not affiliated with or endorsed by the Qat project."
- **Python:** `requires-python >= 3.10`.
- **Qat:** pinned exactly, `qat==1.9.0`, and bumped deliberately. A release waits until its Qat is on PyPI, since installs from a git tag take Qat from PyPI whatever index development uses.
- **Repository:** `Palm1r/qat-agent-skills` on GitHub.

## How the calls work

The calls and their parameters are listed once, in the skill's [SKILL.md](../skills/qat/SKILL.md#qat-agent-helpers); this section records how they work and why.

A target is a Qat definition or a Qat object proxy. There are no refs. A definition is looked up in the current app: `launch()` and `attach()` make the new app Qat's current app, as `qat.start_application()` does, so that Qat's own `wait_for_*` functions work on it at once. The library reads the current app from Qat and keeps none of its own, so a switch made with `qat.set_current_application_context()` applies to its calls too, and when the current app is closed or detached, the newest open app takes its place, or no app is current when none is left ([ADR 0003](adr/0003-the-current-app-is-qats.md)).

- **`launch()`** starts the app with Qat's parts ([ADR 0002](adr/0002-apps-are-launched-with-qats-parts.md)) and waits until it is connected. No `applications.json` is written, there is a single launch attempt, `env` applies to this app only, and the app's Qat server leaves its port in the app's `TEMP`, which is the script's unless `env` sets another. On macOS, an app whose architecture Qat's server for its Qt version is not built for is refused before it is launched, and on Linux, an app on a Qt version Qat has no server for.
- **`attach(pid)`** attaches to any suitable process on Windows, and on Linux and macOS only to one that Qat launched.
- **`App.close()`** calls `quit()` through Qat for a launched app, kills the process if it is still running after `timeout`, and returns its exit code, so that a test can check for 0, a clean quit. Launched apps are also closed when the context manager exits or the script ends. **`App.detach()`** releases an attached app, which is never closed, also once the app has exited.
- **`click()`** sends a non-blocking press and release, followed by a barrier ([ADR 0001](adr/0001-input-is-non-blocking-with-a-barrier.md)). For check boxes, radio buttons and switches, it aims at the indicator. It raises if the click did not change the check state of a control with an indicator or of a widget button: `checkState` on a Qt Quick check box, `checked` elsewhere. A checked radio button may stay checked, and so may a checked tristate widget check box, whose `checked` stays true from partly checked to checked, while Qt Widgets show no check state. A checkable `QGroupBox` toggles only on its title, so there a centre click is no error.
- **`press_keys()`** sends a key or a shortcut with `shortcut(..., blocking=False)`, followed by a barrier.
- **`type_text()`** calls `type_in`, which is blocking because Qat has no other mode. Since Qat 1.9.0 it types any text, except characters beyond the Basic Multilingual Plane into a Qt 5 app on Linux and macOS.
- **`definition_for()`** returns a portable definition that matches only this object, for tests. When none is unique, it returns the best candidate with an `AmbiguousDefinitionWarning`.
- **Virtual widgets:** Qat reaches a row or cell of an item view through a wrapper it makes for each request, which has no cached uid, so the library's calls cannot address it. Until they can, a definition with `row` or `column` at any level raises a `ValueError` that names Qat's own call to use.

What `snapshot` prints:
- the tree is de-duplicated by uid;
- by default only visible objects are included, and non-visual QObjects are left out;
- internal objects are left out with their subtrees, hidden or not, unless `include_internal=True`. For now they are the containers Qt puts a scroll area's scroll bars in (`qt_scrollarea_hcontainer`, `qt_scrollarea_vcontainer`): every scroll area, such as a list or a text editor, has two, and they never hold the app's own objects. The other objects Qt names `qt_...` stay, because they hold what agents need: a scroll area's viewport and contents (`qt_scrollarea_viewport`), a tab widget's pages (`qt_tabwidget_stackedwidget`), a message box's text and buttons (`qt_msgbox_label`, `qt_msgbox_buttonbox`) and a spin box's field (`qt_spinbox_lineedit`);
- virtual widgets are not listed yet: an item view shows up without its rows;
- each line carries the type, `#objectName`, `id=`, the text or `placeholderText`, flags, and `def={...}` when a unique definition exists;
- output is cut at about 8k tokens with a note; the tree is walked lazily, so the walk stops there too instead of asking the app about objects that would not be shown.

Three more pieces:
- **Waiting:** before `click`, `press_keys` and `type_text`, the library waits until the target is visible and enabled, as long as `qat.wait_for_object()` would (`Settings.wait_for_object_timeout`), because Qat skips that check for objects addressed by uid. As in that function, a definition's containers must be visible and enabled too, and a container that is not there yet is waited for like the target.
- **Ambiguous lookups:** an error lists the candidates with their definitions, also when a definition's container matches several objects, which Qat itself refuses.
- **pytest plugin:** the fixture factory `launch_app`, which launches an app and closes it in teardown.

Definitions are picked in this order, with each candidate checked for uniqueness with `find_all_objects`:
1. `objectName` + `type`;
2. QML `id` + `type`;
3. `type` + `text`;
4. the same inside the nearest ancestor that has a unique definition (`container`). That definition may have a container of its own, since Qat resolves containers at any depth, and `snapshot` and `definition_for` pick the same one;
5. otherwise, the best candidate, flagged as ambiguous, with a hint to set an `objectName` in the app.

## The skill

One skill, `skills/qat/`, follows the Agent Skills standard ([ADR 0005](adr/0005-one-skill-named-qat.md)). Its SKILL.md holds what every task needs:
- a table of what to read for which task, which points into `references/`;
- how to run scripts: a PEP 723 header (`# /// script`, with `dependencies = ["qat-agent-helpers @ git+https://github.com/Palm1r/qat-agent-skills@vX.Y.Z"]`) and `uv run script.py` need no setup in the user's project, and the progress lines of Qat that read like errors;
- the loop: launch, look with a snapshot and a screenshot, act, and check each effect with a Qat wait, until one script runs the whole scenario;
- when the work is done, for exploring an app, checking a change and reproducing a bug;
- which build to drive, and the `objectName` an agent may add to the app's code;
- the library's calls, in the one table of them, and Qat's essentials: definitions, waits and object proxies;
- the pitfalls: modal dialogs, typing, Return in a text field, check boxes, ambiguous definitions, emoji in Qt 5 apps, and input that a user could not give.

`references/` holds what only some tasks reach:
- `tests.md`: tests in a pytest suite, with the setup, the rules, the `launch_app` fixture and how to run them;
- `qat-suites.md`: tests in a Qat suite, BDD or scripts, with how the suite starts apps, where the library's calls fit in steps, and how to run behave;
- `qat-api.md`: Qat's API beyond the essentials, from the mouse and keyboard to item views, menus, native dialogs, method calls, signals and screenshots, with what blocks;
- `platforms.md`: what an app needs on each platform, a build for Qat, launch failures, and agent sandboxes.

The skill's unit tests check its frontmatter, that SKILL.md links every reference, that every library and Qat name it mentions exists, that SKILL.md's table lists every exported call, and that every pinned library version is the current one.

How it is distributed: the README documents `npx skills add Palm1r/qat-agent-skills`, `gh skill install Palm1r/qat-agent-skills`, and copying `skills/qat` by hand into `.claude/skills/` (Claude Code), `.agents/skills/` (Codex) or either of them (Cursor). There are no plugin manifests. A Claude Code plugin marketplace is the first one to add if needed.

## Development and releases

- **Toolchain:** mise provides Python 3.13 and uv, and uv manages the virtual environment and the lockfile.
- **Tests:** development is test-first, in vertical slices. Unit tests drive a fake Qat adapter, so they need no Qt. Changes that depend on how real Qat behaves, and any Qat version bump, need a run against real Qt apps: the integration tests in qat-demo-bench drive its two demo apps through real Qat.
- **Releases:**
  - the version lives in `pyproject.toml`, starts at 0.1.0 and is bumped by hand;
  - each release gets a `vX.Y.Z` tag, which is what the skill installs from. Publishing to PyPI through Trusted Publishing on that tag is planned but not set up;
  - CHANGELOG.md follows Keep a Changelog.
- **Known Qat issues:** listed in the README.
