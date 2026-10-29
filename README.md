# qat-agent-skills

Unofficial, community-made. Not affiliated with or endorsed by the Qat project.

Help AI agents explore running Qt apps, check changes, reproduce bugs and write GUI tests with [Qat](https://gitlab.com/testing-tool/qat). Supports both Qt Widgets and Qt Quick/QML.

This repository provides two things:

- **The [`qat` agent skill](skills/qat/SKILL.md)** teaches an agent how to launch an app, inspect its UI, interact with it and check the results. It covers tests in pytest and in existing Qat suites.
- **The `qat-agent-helpers` Python library** launches apps by path, shows their object tree with selectors to copy, and handles common input pitfalls such as modal dialogs and check boxes. Scripts use Qat's own API for waits, properties, screenshots and other actions.

> [!NOTE]
> **Many thanks to the [Qat developers](https://gitlab.com/testing-tool/qat) for creating such an excellent tool!**
> This project builds on their work.

> **Status:** early development. Verified on Windows, macOS (Apple silicon) and Linux (X11 and Wayland). The helper library is not on PyPI yet.

## Start with an agent

Install the skill:

```bash
npx skills add Palm1r/qat-agent-skills
```

Alternatively, use GitHub CLI:

```bash
gh skill install Palm1r/qat-agent-skills
```

For manual installation, copy `skills/qat` into `.claude/skills/` for Claude Code, `.agents/skills/` for Codex, or either directory for Cursor.

Then give the agent the app's path and a task, for example:

> Use the qat skill to launch /absolute/path/to/my-app, inspect its UI and write a GUI test for its main workflow.

Scripts need Python 3.10+ and [uv](https://docs.astral.sh/uv/). The skill shows the agent how to install the helper library as it runs a script; Qat is installed automatically as a dependency.

**Upgrading from 0.1.1 or earlier?** Remove the old `qat-explore` and `qat-tests` skills; `qat` replaces both.

## App requirements

Qat injects a small server into the app. The app needs dynamically linked **Qt 5.15 or 6.2–6.12**, a desktop session and a visible top-level window.

| Platform | Requirements |
|---|---|
| Windows | An MSVC Release or RelWithDebInfo build, with its Qt DLLs available. |
| macOS | A build without the hardened runtime. Qt 5.15 apps on Apple silicon must use x86_64 under Rosetta. |
| Linux | A Qt version supported by Qat; a distribution may ship a newer one. Both X11 and Wayland work. |

See the [platform notes](skills/qat/references/platforms.md) for build setup, launch failures and agent sandbox settings.

## Use the Python helpers directly

Save this as `example.py`. Replace `APP` with your executable's path, or a `.app` bundle on macOS:

For a first look at an unfamiliar app, keep only the `print()` inside the `with` block. Add actions after copying definitions from its snapshot.

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["qat-agent-helpers @ git+https://github.com/Palm1r/qat-agent-skills@v0.2.0"]
# ///

import qat
import qat_agent_helpers

APP = "/absolute/path/to/app"

with qat_agent_helpers.launch(APP):
    print(qat_agent_helpers.snapshot())

    # Example: replace these definitions with ones from your app's snapshot.
    qat_agent_helpers.click({"objectName": "incrementButton", "type": "QPushButton"})
    counter = {"objectName": "counterLabel", "type": "QLabel"}
    qat.wait_for_property_value(counter, "text", "1", check=True)
```

Run it with:

```bash
uv run example.py
```

`snapshot()` returns the visible object tree as text, with a `def=` selector wherever it can identify an object uniquely:

```
- MainWindow #mainWindow "Demo Widgets" def={"objectName": "mainWindow", "type": "MainWindow"}
  - QWidget #centralWidget def={"objectName": "centralWidget", "type": "QWidget"}
    - QPushButton #incrementButton "Increment" def={"objectName": "incrementButton", "type": "QPushButton"}
    - QLabel #counterLabel "0" def={"objectName": "counterLabel", "type": "QLabel"}
```

Copy definitions from `def=` into your actions and checks. `launch()` waits for the app to connect, and the `with` block closes it when finished. Qat's waits check the effect of each action without fixed delays.

The [API reference](skills/qat/SKILL.md#qat-agent-helpers) lists every helper and its parameters.

### Add GUI tests

In an existing Python project, install the library and pytest as dev dependencies:

```bash
uv add --dev pytest "qat-agent-helpers @ git+https://github.com/Palm1r/qat-agent-skills@v0.2.0"
```

In an empty directory, run `uv init --bare` first. The library provides a `launch_app` pytest fixture that starts the app and closes it after each test.

See the [pytest guide](skills/qat/references/tests.md) for a complete test, or the [Qat suite guide](skills/qat/references/qat-suites.md) if the project already uses Qat tests.

## Known limitations

- Qat's server inside the app listens on `0.0.0.0` without authentication. Use it on trusted networks only.
- Agent sandboxes may block localhost connections or prevent the app's window from opening. See the [sandbox notes](skills/qat/references/platforms.md#agent-sandboxes).
- The helpers cannot act on rows and cells in Qt Widgets item views, or on Qt Widgets menu items yet. Use [Qat's own calls](skills/qat/references/qat-api.md) for those.
- Apps take about 2 seconds to exit after they are asked to quit.

## Development

The development toolchain uses [mise](https://mise.jdx.dev) to install Python 3.13 and uv:

```bash
mise trust
mise install
```

- `mise run test` — unit tests with a fake Qat; no Qt installation needed.
- `mise run lint` — formatting and lint checks with ruff.
- `mise run typecheck` — type checks with pyright.
- `mise run build` — wheel and source distribution in `dist/`.

Changes that depend on real Qat behaviour also need the integration tests in `qat-demo-bench`, which drive two demo apps through Qat.

Further reading: [library design](docs/library.md), [glossary](GLOSSARY.md), [architecture decisions](docs/adr/) and [changelog](CHANGELOG.md).

## Licence

MIT © Petr Mironychev
