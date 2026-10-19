# qat-agent-skills

Unofficial, community-made. Not affiliated with or endorsed by the Qat project.

Agent skills and a Python helper library for AI agents that drive running Qt apps with [Qat](https://gitlab.com/testing-tool/qat) scripts. Agents write scripts on Qat's own API. The library, qat-agent-helpers, covers Qat's weak spots: launching without a registry, an object tree with ready-made definitions, and clicks and keys that modal dialogs and check boxes cannot trip up.

> **Status:** early development, verified on Windows only, not published on PyPI yet. The design is in [docs/library.md](docs/library.md), the vocabulary in [GLOSSARY.md](GLOSSARY.md), and the decisions in [docs/adr](docs/adr/).

## What an app needs

Qat injects a small server into the app, which works with:

- a Release or RelWithDebInfo build with dynamically linked Qt 5.15 or 6.2–6.11;
- built with MSVC on Windows;
- a visible top-level window.

## Installing

qat-agent-helpers is not on PyPI yet, so it installs from this repository's release tag:

- a one-off script needs only a [PEP 723](https://peps.python.org/pep-0723/) header and `uv run script.py`:

  ```python
  # /// script
  # requires-python = ">=3.10"
  # dependencies = ["qat-agent-helpers @ git+https://github.com/Palm1r/qat-agent-skills@v0.1.0"]
  # ///
  ```

- a test suite adds it as a dev dependency: `uv add --dev "qat-agent-helpers @ git+https://github.com/Palm1r/qat-agent-skills@v0.1.0"`.

## Using it

```python
import qat
import qat_agent_helpers

with qat_agent_helpers.launch(r"path/to/app.exe"):
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

| Call | What it does |
|---|---|
| `launch(path, args=(), env=None, lock_ui=False)` | Starts the app with Qat and waits until it is connected. No `applications.json` is written, and the app is launched once. Returns an `App`, also a context manager. |
| `attach(pid)` | Takes over a running Qt process. On Linux and macOS, only one that Qat launched. |
| `App.close(timeout=5)`, `App.detach()` | Quits a launched app, kills it after `timeout` and returns its exit code (0 for a clean quit), or releases an attached one. Launched apps still open are closed when the script ends. |
| `App.context`, `App.pid` | Qat's `ApplicationContext` and the process id. The newest app is also Qat's current app. |
| `snapshot(target=None, depth=None, include_hidden=False, include_internal=False)` | The object tree as text, cut at about 8k tokens. The containers of Qt's scroll bars are left out unless `include_internal=True`. |
| `click(target, button="left", double=False, modifiers=(), x=None, y=None)` | A click that does not block on what it opens. On a check box, radio button or switch it aims at the indicator and raises if `checked` did not change. |
| `press_keys(target, keys)` | A key or a shortcut such as `Return` or `Ctrl+S`. |
| `type_text(target, text)` | Types ASCII text; other text is refused with a hint. |
| `definition_for(obj)` | A definition that matches only this object, for tests. |

A target is a Qat definition or a Qat object. Actions wait for their target to be visible and enabled, as long as `qat.wait_for_object()` would.

In tests, the `launch_app` fixture launches apps and closes them in teardown:

```python
def test_counter(launch_app):
    launch_app(r"path/to/app.exe")
    qat_agent_helpers.click({"objectName": "incrementButton", "type": "QPushButton"})
```

## The agent skills

- [qat-explore](skills/qat-explore/SKILL.md) teaches an agent to drive a running app from scripts: launching or attaching, snapshots, input, Qat's waits, a Qat cheat sheet and the pitfalls.
- [qat-tests](skills/qat-tests/SKILL.md) teaches it to turn a scenario that works into pytest tests with the `launch_app` fixture.

Install both with one of:

```bash
npx skills add Palm1r/qat-agent-skills
```

```bash
gh skill install Palm1r/qat-agent-skills
```

or copy `skills/qat-explore` and `skills/qat-tests` by hand into `.claude/skills/` for Claude Code, into `.agents/skills/` for Codex, or into either one for Cursor.

## Known issues

- Qat's server inside the app listens on `0.0.0.0` without authentication. Use it on trusted networks only.
- Apps take about 2 s to exit after they are asked to quit.
- Only Windows is verified so far. Paths to macOS `.app` bundles are not handled.
- Agent sandboxes may stop scripts from reaching the app's Qat server on localhost. Codex needs network access in its sandbox or an approval per run, and Cursor needs the scripts run outside its sandbox. This is untested.

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

## Licence

MIT © Petr Mironychev
