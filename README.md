# qat-agent-skills

Unofficial, community-made. Not affiliated with or endorsed by the Qat project.

An agent skill and a Python helper library for AI agents that drive running Qt apps with [Qat](https://gitlab.com/testing-tool/qat) scripts and write tests for them. Agents write scripts on Qat's own API, which the skill documents. The library, qat-agent-helpers, covers Qat's weak spots: launching without a registry, an object tree with ready-made definitions, and clicks and keys that modal dialogs and check boxes cannot trip up.

> **Status:** early development, verified on Windows, on macOS (Apple silicon) and on Linux (X11 and Wayland), not published on PyPI yet. The design is in [docs/library.md](docs/library.md), the vocabulary in [GLOSSARY.md](GLOSSARY.md), and the decisions in [docs/adr](docs/adr/).

## What an app needs

Qat injects a small server into the app, which works with:

- dynamically linked Qt 5.15 or 6.2–6.12, and a visible top-level window;
- on Windows, a Release or RelWithDebInfo build made with MSVC;
- on macOS, an app without the hardened runtime, because Qat injects itself through `DYLD_INSERT_LIBRARIES`; on Apple silicon, a Qt 5.15 app built for x86_64 and run under Rosetta, because Qat builds its Qt 5.15 server for x86_64 only;
- on Linux, a Qt that Qat has a server for: a distribution may ship a newer one, so build with another Qt, for example from the Qt online installer.

The details, with what to do when a launch fails, are in [the skill's platform notes](skills/qat/references/platforms.md).

## Installing

qat-agent-helpers is not on PyPI yet, so it installs from this repository's release tag:

- a one-off script needs only a [PEP 723](https://peps.python.org/pep-0723/) header and `uv run script.py`:

  ```python
  # /// script
  # requires-python = ">=3.10"
  # dependencies = ["qat-agent-helpers @ git+https://github.com/Palm1r/qat-agent-skills@v0.1.1"]
  # ///
  ```

- a test suite adds it and pytest, which it does not bring itself, as dev dependencies: `uv add --dev pytest "qat-agent-helpers @ git+https://github.com/Palm1r/qat-agent-skills@v0.1.1"`.

## Using it

```python
import qat
import qat_agent_helpers

# Windows; Linux and macOS "path/to/app"; or a macOS "path/to/App.app"
with qat_agent_helpers.launch(r"path\to\app.exe"):
    print(qat_agent_helpers.snapshot())
    qat_agent_helpers.click({"objectName": "incrementButton", "type": "QPushButton"})
    qat.wait_for_property_value({"objectName": "counterLabel"}, "text", "1", check=True)
```

`snapshot()` prints one line per object, ending with a definition to copy:

```
- MainWindow #mainWindow "Demo Widgets" def={"objectName": "mainWindow", "type": "MainWindow"}
  - QWidget #centralWidget def={"objectName": "centralWidget", "type": "QWidget"}
    - QPushButton #incrementButton "Increment" def={"objectName": "incrementButton", "type": "QPushButton"}
    - QLineEdit #nameField placeholder="Your name" def={"objectName": "nameField", "type": "QLineEdit"}
    - QPushButton #twinButton "Twin A" def={"type": "QPushButton", "text": "Twin A"}
```

Every call, with its parameters, is in [the skill's table](skills/qat/SKILL.md#qat-agent-helpers), and the `launch_app` pytest fixture is in [its notes on tests](skills/qat/references/tests.md).

## The agent skill

[qat](skills/qat/SKILL.md) teaches an agent to drive a running app from scripts, to check a change in it, to reproduce a bug, and to write, fix and run its tests. Its SKILL.md holds the loop of launching, looking, acting and checking, the library's calls, Qat's essentials and the pitfalls; its `references/` folder holds tests in pytest, tests in a Qat suite, Qat's API beyond the essentials, and what an app needs on each platform.

Install it with one of:

```bash
npx skills add Palm1r/qat-agent-skills
```

```bash
gh skill install Palm1r/qat-agent-skills
```

or copy `skills/qat` by hand into `.claude/skills/` for Claude Code, into `.agents/skills/` for Codex, or into either one for Cursor.

Versions up to 0.1.1 shipped two skills, qat-explore and qat-tests, which `qat` replaces: remove them when you install it.

## Known issues

- Qat's server inside the app listens on `0.0.0.0` without authentication. Use it on trusted networks only.
- Apps take about 2 s to exit after they are asked to quit.
- Qat 1.9.0 supports Qt up to 6.12. On Linux, `launch()` refuses an app on a newer Qt and says so; on Windows and macOS such an app fails only when Qat gives up waiting for it, after about 10 s.
- On Apple silicon, Qat 1.9.0 drives Qt 5.15 apps only when they are built for x86_64 and run under Rosetta: its Qt 5.15 server is built for x86_64 only. `launch()` refuses an arm64 app on Qt 5.15 and says so.
- qat-agent-helpers cannot act on rows and cells of item views yet, because Qat reaches each through a short-lived wrapper; Qat wraps the items of Qt Widgets menus the same way. Use Qat's own calls on them, as the skill shows.
- Agent sandboxes may stop scripts from reaching the app's Qat server on localhost, or the app from opening its window: inside Codex's sandbox on macOS, an app aborts at once. The skill's platform notes say what Claude Code, Codex and Cursor need; all three have been tried on macOS.

## Development

The toolchain comes from [mise](https://mise.jdx.dev): Python 3.13 and uv.

```bash
mise trust
mise install
```

Tasks:

- `mise run test` runs the unit tests, which drive a fake Qat and need no Qt;
- `mise run lint` and `mise run typecheck` run ruff and pyright;
- `mise run build` builds the wheel and the source distribution into `dist/`.

Changes that depend on how real Qat behaves need a run of the integration tests in qat-demo-bench, which drive two demo apps through real Qat.

## Licence

MIT © Petr Mironychev
