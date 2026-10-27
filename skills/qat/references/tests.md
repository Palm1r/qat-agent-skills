# Tests in a pytest suite

These tests launch a Qt app, drive it through Qat with qat-agent-helpers for the input, and check its state with Qat's waits. Start from a scenario that already works and from definitions copied from snapshots, which driving the app as SKILL.md describes gives you. A project that has a Qat suite gets its tests there instead, unless the user asks for pytest: read qat-suites.md.

## Setup

Add the library and pytest as dev dependencies of the project that holds the tests; the library does not bring pytest itself. It is not on PyPI yet, so install it from its GitHub release tag, for example with `uv add --dev pytest "qat-agent-helpers @ git+https://github.com/Palm1r/qat-agent-skills@v0.1.1"`. In a folder that has no project yet, run `uv init --bare` first. The library's pytest plugin provides the `launch_app` fixture, so the tests need no conftest.

## Writing a test

```python
import qat
import qat_agent_helpers

APP = r"path\to\app.exe"  # Windows; Linux and macOS "path/to/app"; or a macOS "path/to/App.app"
INCREMENT = {"objectName": "incrementButton", "type": "QPushButton"}
COUNTER = {"objectName": "counterLabel", "type": "QLabel"}


def test_increment_adds_one(launch_app):
    app = launch_app(APP)

    qat_agent_helpers.click(INCREMENT)

    assert qat.wait_for_property_value(COUNTER, "text", "1", check=True)
    assert app.close() == 0  # it quit by itself and was not killed
```

- **One behaviour per test.** Each test launches its own app with `launch_app`, which closes it after the test, so no test depends on another one's state. Steps that depend on each other, such as opening a dialog, pressing OK and checking the result, stay together in one test; independent steps of a scenario get a test each, unless the user asks for one test of the whole scenario. A launch takes a second or two.
- **Definitions in constants.** Copy them from the `def=` of a snapshot line, or get them from an object with `qat_agent_helpers.definition_for(obj)`. Prefer definitions by `objectName`; when an object has none, give it one in the app's code rather than relying on its text.
- **A wait for every effect.** A GUI changes some time after the input that causes it, so check state with `qat.wait_for_property_value(..., check=True)` or `qat.wait_for_object()`, not after `time.sleep()`.
- **The app's path in one place,** such as `APP` above: the executable (`app.exe` on Windows, `app` on Linux) or, on macOS, the `.app` bundle. Read it from an environment variable when the suite has to run on other machines.
- **A clean exit.** `app.close()` returns 0 when the app quit by itself; any other code means that it failed or was killed after `timeout`. `assert app.close() == 0` makes a clean exit part of the test.
- **A test for a bug** fails while the bug is there and passes once it is fixed.

## The fixture

| Call | What it does |
|---|---|
| `launch_app(path, args=(), env=None, lock_ui=False)` | Launches the app as `qat_agent_helpers.launch()` does, returns the `App`, and closes the app after the test. `lock_ui=True` keeps the user's own mouse and keys away from the app while the tests run. |

The other calls a test makes are in SKILL.md's table and in Qat's essentials there.

## Running tests

Run them like any pytest tests, for example `uv run pytest tests/gui`. The app needs a desktop session, as any GUI test does, and an agent sandbox may keep the tests from reaching the app's Qat server: see platforms.md. When a test fails for a reason the error does not show, run its scenario as a script and look at a snapshot and a screenshot at the step that fails.

A test is done when it passes with `pytest` on its own, launches the app itself, asserts every effect the scenario relies on, and waits with Qat's `wait_for_*` functions instead of `time.sleep()`.
