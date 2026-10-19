---
name: qat-tests
description: Write, fix and run pytest GUI tests for Qt apps (Qt Widgets or Qt Quick/QML) that drive the app through Qat with the launch_app fixture of qat-agent-helpers. Use when you need to add automated GUI tests for a Qt application, turn a scenario that already works into tests, or repair and run such tests. To look inside a running app or find object definitions first, use qat-explore.
license: MIT
---

# Writing Qat tests with qat-agent-helpers

These tests launch a Qt app, drive it through [Qat](https://gitlab.com/testing-tool/qat) with qat-agent-helpers for the input, and check its state with Qat's waits. Start from a scenario that already works and from definitions copied from snapshots; the qat-explore skill finds both. This skill and qat-agent-helpers are community-made and not part of the Qat project.

## Setup

Add the library as a dev dependency of the project that holds the tests. It is not on PyPI yet, so install it from its GitHub release tag, for example with `uv add --dev "qat-agent-helpers @ git+https://github.com/Palm1r/qat-agent-skills@v0.1.1"`. Its pytest plugin provides the `launch_app` fixture, so the tests need no conftest.

## Writing a test

```python
import qat
import qat_agent_helpers

APP = r"path/to/app.exe"
INCREMENT = {"objectName": "incrementButton", "type": "QPushButton"}
COUNTER = {"objectName": "counterLabel", "type": "QLabel"}


def test_increment_adds_one(launch_app):
    app = launch_app(APP)

    qat_agent_helpers.click(INCREMENT)

    assert qat.wait_for_property_value(COUNTER, "text", "1", check=True)
    assert app.close() == 0  # it quit by itself and was not killed
```

- **One behaviour per test.** Each test launches its own app with `launch_app`, which closes it after the test, so no test depends on another one's state. A launch takes about 2 s.
- **Definitions in constants.** Copy them from the `def=` of a snapshot line, or get them from an object with `qat_agent_helpers.definition_for(obj)`. Prefer definitions by `objectName`; when an object has none, give it one in the app's code rather than relying on its text.
- **A wait for every effect.** A GUI changes some time after the input that causes it, so check state with `qat.wait_for_property_value(..., check=True)` or `qat.wait_for_object()`, not after `time.sleep()`.
- **The app's path in one place,** such as `APP` above. Read it from an environment variable when the suite has to run on other machines.

A test is done when it passes with `pytest` on its own, launches the app itself, asserts every effect the scenario relies on, and waits with Qat's `wait_for_*` functions instead of `time.sleep()`.

## Calls tests use

| Call | What it does |
|---|---|
| `launch_app(path, args=(), env=None, lock_ui=False)` | The pytest fixture: launches the app as `qat_agent_helpers.launch()` does, returns the `App`, and closes the app after the test. |
| `app.close(timeout=5)` | Asks the app to quit, kills it if it still runs after `timeout` seconds, and returns its exit code. |
| `qat_agent_helpers.click(target)`, `qat_agent_helpers.press_keys(target, keys)`, `qat_agent_helpers.type_text(target, text)` | Input that first waits for its target to be visible and enabled, and never blocks on a modal dialog. |
| `qat_agent_helpers.definition_for(obj)` | A definition that matches only this object. |
| `qat_agent_helpers.snapshot(target)` | The object tree below the target as text, to look at while writing a test or to print when one fails. |

A target is a Qat definition or a Qat object, such as the one `qat.wait_for_object()` returns.

## Pitfalls in tests

- **Modal dialogs.** Qat's `qat.mouse_click()` on a button whose handler opens a dialog with `exec()` waits until the dialog closes, so the test hangs. `qat_agent_helpers.click()` returns at once; then wait for the dialog with `qat.wait_for_object()`.
- **Check boxes.** A click at the centre of a check box that a layout stretched misses its indicator. `qat_agent_helpers.click()` aims at the indicator and raises `NotToggledError` if `checked` did not change.
- **Waiting for an object to go.** `qat.wait_for_object_missing(definition)` waits until the object is deleted. A hidden object still exists, so the wait raises `TimeoutError`; to wait until it is hidden, use `qat.wait_for_property_value(definition, "visible", False, check=True)`.
- **The exit code.** `app.close()` returns 0 when the app quit by itself; any other code means that it failed or was killed after `timeout`. `assert app.close() == 0` makes a clean exit part of the test.

For Return in text fields, non-ASCII text, ambiguous definitions and a Qat cheat sheet, see the qat-explore skill.

## Running tests

Run them like any pytest tests, for example `uv run pytest tests/gui`. The app needs a desktop session, as any GUI test does, and agent sandboxes may stop the tests from reaching the app's Qat server: see qat-explore. Qat prints progress lines such as "Starting Python TCP server", "Could not close communication with application" and "Stopping Python TCP server"; they are not errors.
