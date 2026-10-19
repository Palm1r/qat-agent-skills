---
name: qat-explore
description: Drive a running Qt app (Qt Widgets or Qt Quick/QML) from Python scripts with Qat and qat-agent-helpers. Launch or attach to the app, print its object tree with ready-made definitions, click, type and press keys, and check each effect with Qat's waits. Use when you need to look inside a Qt app, try or reproduce a scenario in it, or find the definitions a test will need. To turn a working scenario into pytest tests, use qat-tests.
license: MIT
---

# Exploring Qt apps with Qat and qat-agent-helpers

[Qat](https://gitlab.com/testing-tool/qat) injects a small server into a Qt app and lets Python drive it. qat-agent-helpers is a helper library on top of Qat. It launches apps, prints the object tree with ready-made definitions, and sends clicks and keys so that modal dialogs cannot hang the script. Everything else, including waits, properties, method calls and screenshots, is Qat's own API. This skill and qat-agent-helpers are community-made and not part of the Qat project.

## Workflow

1. **Check that the app can be driven.** Qat connects only to a Release or RelWithDebInfo build with dynamically linked Qt 5.15 or 6.2–6.11, built with MSVC on Windows, that shows a visible top-level window. A Debug build never connects.
2. **Look at the app.** Write `explore.py` with the header from [Running scripts](#running-scripts), and run it with `uv run explore.py`:

   ```python
   import qat_agent_helpers

   with qat_agent_helpers.launch(r"path/to/app.exe"):
       print(qat_agent_helpers.snapshot())
   ```

   A snapshot line looks like this:

   ```
   - QPushButton #incrementButton "Increment" def={"objectName": "incrementButton", "type": "QPushButton"}
   ```

   It shows the object's type, `#objectName`, QML `id=`, its text (or `placeholder=` for an empty field), state flags (`hidden`, `disabled`, `focused`, `checked`) and, last, its definition. Copy definitions from `def=` rather than composing them; an object without `def=` has no unique one. Narrow a big tree with `qat_agent_helpers.snapshot(definition, depth=2)`.
3. **Act and check.** Act with `qat_agent_helpers.click()`, `qat_agent_helpers.type_text()` and `qat_agent_helpers.press_keys()`, and check each effect with Qat's waits:

   ```python
   import qat
   import qat_agent_helpers

   with qat_agent_helpers.launch(r"path/to/app.exe"):
       qat_agent_helpers.click({"objectName": "incrementButton", "type": "QPushButton"})
       counter = {"objectName": "counterLabel", "type": "QLabel"}
       qat.wait_for_property_value(counter, "text", "1", check=True)
   ```

   Keep the whole scenario in one script and rerun it from the start after each change: qat-agent-helpers closes the app when the script ends.

The exploration is done when the script runs the whole scenario from a fresh launch without errors, checks every effect with a Qat wait, and names every object it touches by a definition taken from a snapshot. To keep the scenario as tests, continue with the qat-tests skill.

## qat-agent-helpers

A target is a Qat definition or a Qat object, such as the one `qat.wait_for_object()` returns.

| Call | What it does |
|---|---|
| `qat_agent_helpers.launch(path, args=(), env=None, lock_ui=False)` | Starts the app with Qat and waits until it is connected. Returns an `App`, also a context manager. |
| `qat_agent_helpers.attach(pid)` | Takes over a running Qt process. On Linux and macOS, only one that Qat launched. |
| `app.close(timeout=5)` | Asks a launched app to quit, kills it if it still runs after `timeout` seconds, and returns its exit code; 0 means it quit cleanly. |
| `app.detach()` | Releases an attached app and leaves it running. |
| `app.context`, `app.pid` | Qat's `ApplicationContext` and the process id. |
| `qat_agent_helpers.snapshot(target=None, depth=None, include_hidden=False, include_internal=False)` | The object tree as text; without a target, every top-level window. It leaves out the containers of Qt's scroll bars (`qt_scrollarea_hcontainer`, `qt_scrollarea_vcontainer`), which never hold the app's own objects, unless `include_internal=True`. Other objects named `qt_...`, such as a tab widget's pages or a message box's buttons, are shown. |
| `qat_agent_helpers.click(target, button="left", double=False, modifiers=(), x=None, y=None)` | Clicks without blocking on what the click opens. |
| `qat_agent_helpers.press_keys(target, "Ctrl+S")` | A key or a shortcut in Qt's notation, such as `Return`, `Escape` or `Ctrl+Shift+Z`. The Enter key is `Return`; `Enter` is the keypad's. |
| `qat_agent_helpers.type_text(target, "text")` | Types ASCII text into a text field. |
| `qat_agent_helpers.definition_for(obj)` | A definition that matches only this object, for example one that `qat.wait_for_object()` returned. |

Actions first wait, as long as `qat.wait_for_object()` would, until their target is visible and enabled, then raise `NotReadyError` or `NotFoundError`. A definition that matches several objects raises `AmbiguousDefinitionError`, which lists every match with its own definition. The newest app is Qat's current app; switch with `qat.set_current_application_context(app.context)`.

## Qat cheat sheet

- **Definitions** are dicts of property values that must match exactly one object.
  - `type` matches the class or any base class: `{"type": "QAbstractButton"}` finds check boxes too. QML types drop their `QQuick` prefix (`Button`, `TextField`).
  - `container` limits the search to the descendants of the object it matches: `{"type": "QPushButton", "text": "OK", "container": {"objectName": "confirmDialog"}}`.
- **Waits** take timeouts in milliseconds; the default is `qat.Settings.wait_for_object_timeout`, 3000.
  - `qat.wait_for_object(definition)` waits until the object exists, is visible and is enabled, and returns it.
  - `qat.wait_for_object_exists(definition)` waits only until it exists, even hidden or disabled.
  - `qat.wait_for_object_missing(definition)` waits until the object is deleted. A hidden object still exists, so the wait raises `TimeoutError`; to wait until it is hidden, use `qat.wait_for_property_value(definition, "visible", False, check=True)`.
  - `qat.wait_for_property_value(definition, "text", "3", check=True)` waits for a value. Without `check=True` it returns False instead of raising.
- **Objects:** `obj = qat.wait_for_object(definition)`.
  - Read and write properties as attributes: `obj.text`, `obj.text = "new"`.
  - Call slots and `Q_INVOKABLE` methods: `obj.close()`.
  - Walk the tree with `obj.children` and `obj.parent`, list everything with `obj.list_properties()`, and find every match with `qat.find_all_objects(definition)`.
- **Screenshots:** `qat.grab_screenshot(definition).save("window.png")`.

## Pitfalls

- **Modal dialogs.** A click whose handler opens a dialog with `exec()` makes Qat's `qat.mouse_click()` wait until the dialog closes, so the script hangs. `qat_agent_helpers.click()` and `qat_agent_helpers.press_keys()` return at once. In a plain Qat call, pass `blocking=False`, then wait for the dialog with `qat.wait_for_object()`.
- **Return in a text field.** A blocking `qat.shortcut(field, "Return")` raises "No widget accepted this event", because a `QLineEdit` lets Return through after it emits `returnPressed`. Use `qat_agent_helpers.press_keys()`, or pass `blocking=False`.
- **Check boxes.** Qt toggles a `QCheckBox` only on clicks on its indicator or its text, and layouts often stretch the widget, so a click at its centre misses. `qat_agent_helpers.click()` aims at the indicator and raises `NotToggledError` if `checked` did not change. In a plain Qat call, click at `x=10, y=height // 2`, or press Space on it.
- **Ambiguous definitions.** Two objects with the same `objectName` make a definition match both, and Qat fails. Take the `def=` of the one you mean from the snapshot or from the error, or give the object a unique `objectName` in the app's code.
- **Non-ASCII text.** Qat types ASCII only (Qat issue #45), and `qat_agent_helpers.type_text()` refuses other text. Set the property instead: `qat.wait_for_object(definition).text = "café"`.

## Running scripts

- **A script** needs no setup in the user's project with this header and `uv run script.py`. The library is not on PyPI yet, so the header installs it from its GitHub release tag:

  ```python
  # /// script
  # requires-python = ">=3.10"
  # dependencies = ["qat-agent-helpers @ git+https://github.com/Palm1r/qat-agent-skills@v0.1.0"]
  # ///
  ```

- Qat prints progress lines to stdout, which are not errors: "Starting Python TCP server" when an app starts, and "Could not close communication with application" and "Stopping Python TCP server" when it closes. qat-agent-helpers writes no `applications.json` and needs no registered apps, unlike `qat.start_application()`.

## Sandboxes

Scripts reach the app's Qat server over TCP on localhost, which agent sandboxes may block. This is untested:
- **Codex:** allow network access in the sandbox (`network_access = true` under `[sandbox_workspace_write]` in `~/.codex/config.toml`), or approve each run.
- **Cursor:** run the scripts outside its sandbox.
