---
name: qat
description: Drive running Qt apps (Qt Widgets or Qt Quick/QML) with Qat from Python scripts, and write GUI tests for them. Launch or attach to an app, read its object tree with ready-made definitions, look at screenshots, click, type and press keys, and check each effect with Qat's waits. Use when you need to look inside a Qt app, check that a change works in the running app, reproduce a bug in it, or write, fix or run its GUI tests, in pytest or in an existing Qat suite (behave feature files or Qat scripts).
license: MIT
---

# Driving Qt apps with Qat

[Qat](https://gitlab.com/testing-tool/qat) injects a small server into a Qt app and lets Python drive it. qat-agent-helpers is a library on top of Qat for what Qat does poorly on its own: it launches apps without a registry, prints the object tree with ready-made definitions, and sends clicks and keys that modal dialogs cannot hang. Everything else is Qat's own API. This skill and qat-agent-helpers are community-made and not part of the Qat project.

## What to read for the task

Every task follows the steps below. Some need a file from this skill's `references/` folder too; read it before you start that part of the work:

| Task | Read |
|---|---|
| Writing, fixing or running tests in pytest, or adding the first tests to a project | [references/tests.md](references/tests.md) |
| A project with a Qat suite: a `features/` folder whose `environment.py` calls `qat.bdd_hooks`, or scripts that report through `qat.report` | [references/qat-suites.md](references/qat-suites.md) |
| Input other than clicks, keys and typed text (drags, the mouse wheel, hovering, touch), rows of item views and Qt Quick lists, menus, the system's own file dialogs (a `QMessageBox` or a `QDialog` is an ordinary object), method calls, signals, pixels of a screenshot | [references/qat-api.md](references/qat-api.md) |
| An app that will not launch or connect, a build for Qat, an agent sandbox | [references/platforms.md](references/platforms.md) |

Before you write or change a test, look for a Qat suite in the project: when there is one, the tests go there, in its style, unless the user asks for pytest. A project without one gets a pytest suite.

## Running scripts

A script needs no setup in the user's project with this header and `uv run script.py`. The library is not on PyPI yet, so the header installs it from its GitHub release tag:

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["qat-agent-helpers @ git+https://github.com/Palm1r/qat-agent-skills@v0.1.1"]
# ///
```

In an agent's sandbox, run the scripts and tests outside it from the start: Codex's sandbox, for one, refuses the script's own port and keeps the app from opening its window. references/platforms.md says what each agent needs.

Qat, its injector and its plugins print progress lines, such as "Detected Qt version 6.11.1", "Locking application" or "Client removed". The app is connected once "New connection from 127.0.0.1" appears. Some lines read like errors and are normal too:
- "Failed to load plugin: ...libQmlPlugin..." in a Qt Widgets app, or "...libQWidgetPlugin..." in a Qt Quick one, on Linux followed by a loader error such as "version `Qt_6.12' not found": Qat drives the app through its other plugin.
- "Closing server..." and "Stopping Qat server", and on Linux and macOS also "OnUnload" and "Deleting startup thread": the injector is done, and the app and its Qat server keep running. They come as the app starts, but may show up later, even after the script's own lines, since the app's output and the script's reach a pipe in buffered chunks.
- When an app closes, "Connection was closed by the client", "Could not close communication with application" and "Stopping Python TCP server", sometimes twice.
- On Windows, PowerShell's "Get-Process : Cannot find a process with the process identifier 12345", with a few lines of detail, when `qat.start_application()` starts an app, as a Qat suite does: Qat is deleting the port files left in the temp folder by apps that were killed rather than closed, and prints this once for each.
- The app's own warnings, such as Qt Quick's "fontInfo: item has no JS engine" while a snapshot reads properties, or macOS's "TSMSendMessageToUIServer: CFMessagePortSendRequest FAILED(-1)" while text is typed.

## The loop

1. **Launch the app.**

   ```python
   import qat_agent_helpers

   # Windows; Linux and macOS "path/to/app"; or a macOS "path/to/App.app"
   with qat_agent_helpers.launch(r"path\to\app.exe"):
       print(qat_agent_helpers.snapshot())
   ```

   `launch()` waits until Qat is connected. An app that Qat cannot be injected into is refused with a `LaunchError` that says why; when a launch fails, read references/platforms.md.

2. **Look at it.** A snapshot prints one line per object:

   ```
   - QPushButton #incrementButton "Increment" def={"objectName": "incrementButton", "type": "QPushButton"}
   ```

   The line shows the object's type, `#objectName`, QML `id=`, its text (or `placeholder=` for an empty field), state flags (`hidden`, `disabled`, `focused`, `checked`) and, last, its definition. Copy definitions from `def=` rather than composing them; an object without `def=` has no unique one. Narrow a big tree with `qat_agent_helpers.snapshot(definition, depth=2)`. Objects that appear only after an action are found the same way: `snapshot(include_hidden=True)` shows what is hidden until then, and a snapshot taken while a dialog is open shows the dialog.

   A snapshot tells what the objects are; a screenshot shows how the app looks. Take one after every change that shows on screen, and whenever the snapshot cannot tell: custom-painted widgets, Canvas and Shape items, charts, images, colours and layout. Save it outside the user's project and open the file:

   ```python
   import tempfile
   from pathlib import Path

   import qat

   shot = Path(tempfile.gettempdir()) / "main-window.png"
   qat.grab_screenshot({"objectName": "mainWindow", "type": "MainWindow"}).save(str(shot))
   print(shot)
   ```

   A Qt Quick window that is not on screen, such as a minimized one, cannot be grabbed: `grab_screenshot()` raises `RuntimeError: Failed to grab image`. On Wayland an app cannot restore its own minimized window, so ask the user to restore it. A Qt Widgets window is grabbed either way.

   Rows and cells of Qt Widgets item views, such as a `QListWidget` or a `QTableView`, are virtual widgets, which a snapshot does not list: it shows the view alone. Reach them as references/qat-api.md says.

3. **Act** with `qat_agent_helpers.click()`, `qat_agent_helpers.type_text()` and `qat_agent_helpers.press_keys()`. For any other input, call Qat with `blocking=False`, as references/qat-api.md shows.

4. **Check each effect** with a Qat wait rather than after `time.sleep()`:

   ```python
   import qat
   import qat_agent_helpers

   # Windows; Linux and macOS "path/to/app"; or a macOS "path/to/App.app"
   with qat_agent_helpers.launch(r"path\to\app.exe"):
       qat_agent_helpers.click({"objectName": "incrementButton", "type": "QPushButton"})
       counter = {"objectName": "counterLabel", "type": "QLabel"}
       qat.wait_for_property_value(counter, "text", "1", check=True)
   ```

Keep the whole scenario in one script and rerun it from a fresh launch after each change: the library closes the app when the script ends.

## When the work is done

That depends on why you drive the app:
- **Exploring it**, for example to find what a test needs: the script runs the whole scenario from a fresh launch without errors, checks every effect with a Qat wait, and names every object it touches by a definition taken from a snapshot.
- **Checking a change**: you launched a build that contains the change and saw the new behaviour through a Qat wait, and through a screenshot you looked at when the change shows on screen. Report what you saw and what you could not check.
- **Reproducing a bug**: the script reproduces it from a fresh launch twice in a row, and your report shows the evidence, such as property values and a screenshot. Then offer a regression test that fails while the bug is there.

## The app and its build

- Drive the build the user already has, rebuilt with their change. Build another one only when that one cannot connect, such as a Debug build on Windows: put it in a separate build directory and leave the user's build as it is. references/platforms.md shows how.
- When an object you need has no unique definition, give it an `objectName` in the app's code, such as `setObjectName("saveButton")` in C++ or `objectName: "saveButton"` in QML, rebuild, and list every such change in your report. Change nothing that affects how the app behaves.

## qat-agent-helpers

| Call | What it does |
|---|---|
| `qat_agent_helpers.launch(path, args=(), env=None, lock_ui=False)` | Starts the app with Qat and waits until it is connected. `path` is the app's executable, such as `app.exe` on Windows or `app` on Linux and macOS, or, on macOS, its `.app` bundle. `env` adds environment variables for this app only, and `lock_ui=True` makes the app ignore the user's own mouse and keys. Returns an `App`, also a context manager. |
| `qat_agent_helpers.attach(pid)` | Takes over a running Qt process. On Linux and macOS, only one that Qat launched. |
| `app.close(timeout=5)` | Asks a launched app to quit, kills it if it still runs after `timeout` seconds, and returns its exit code; 0 means it quit cleanly. |
| `app.detach()` | Releases an attached app and leaves it running. |
| `app.context`, `app.pid` | Qat's `ApplicationContext` and the process id. |
| `qat_agent_helpers.snapshot(target=None, depth=None, include_hidden=False, include_internal=False)` | The object tree as text, cut at about 8k tokens; without a target, every top-level window. It leaves out the containers of Qt's scroll bars (`qt_scrollarea_hcontainer`, `qt_scrollarea_vcontainer`), which never hold the app's own objects, unless `include_internal=True`. Other objects named `qt_...`, such as a tab widget's pages or a message box's buttons, are shown. |
| `qat_agent_helpers.click(target, button="left", double=False, modifiers=(), x=None, y=None)` | Clicks without blocking on what the click opens. `button` is `"left"`, `"right"` or `"middle"`, and `modifiers` holds `"ctrl"`, `"shift"` or `"alt"`. On a check box, radio button or switch it aims at the indicator and raises `NotToggledError` if the click did not change its check state. |
| `qat_agent_helpers.press_keys(target, "Ctrl+S")` | A key or a shortcut in Qt's notation, such as `Return`, `Escape` or `Ctrl+Shift+Z`. The Enter key is `Return`; `Enter` is the keypad's. |
| `qat_agent_helpers.type_text(target, "text")` | Types text into a text field and returns once the app has handled it. |
| `qat_agent_helpers.definition_for(obj)` | A definition that matches only this object, for example one that `qat.wait_for_object()` returned, while the object is still shown. |

A target is a Qat definition or a Qat object, such as one that `qat.wait_for_object()` returns. Actions first wait, as long as `qat.wait_for_object()` would, until their target and its containers are visible and enabled, then raise `NotReadyError` or `NotFoundError`. A definition that matches several objects raises `AmbiguousDefinitionError`, which lists every match with its own definition, and so does a definition whose container matches several. A row or cell of an item view raises `ValueError`: the library cannot act on virtual widgets yet.

The calls work on Qat's current app, the one launched or attached last, and so do Qat's own functions. Switch to another app with `qat.set_current_application_context(app.context)`; when the current app closes, the newest app still open takes its place.

## Qat essentials

- **Definitions** are dicts of property values that must match exactly one object.
  - `type` matches the class or any base class: `{"type": "QAbstractButton"}` finds check boxes too. QML types drop their `QQuick` prefix (`Button`, `TextField`), and `id` matches a QML id.
  - `text` keeps the `&` of a mnemonic: the Yes button of a `QMessageBox` is `{"type": "QPushButton", "text": "&Yes"}`, and `"Yes"` matches nothing. Only menu items take it either way.
  - `container` limits the search to the descendants of the one object it matches, and may have a container of its own: `{"type": "QPushButton", "text": "OK", "container": {"objectName": "confirmDialog"}}`.
- **Waits** take timeouts in milliseconds; the default is `qat.Settings.wait_for_object_timeout`, 3000.
  - `qat.wait_for_object(definition)` waits until the object exists, is visible and is enabled, and returns it.
  - `qat.wait_for_object_exists(definition)` waits only until it exists, even hidden or disabled.
  - `qat.wait_for_object_missing(definition)` waits until the object is deleted. A hidden object still exists, so the wait raises `TimeoutError`; to wait until it is hidden, use `qat.wait_for_property_value(definition, "visible", False, check=True)`, which in turn raises `LookupError` once the object is deleted.
  - `qat.wait_for_property_value(definition, "text", "3", check=True)` waits for a value, and `qat.wait_for_property_change(definition, "text", "3", check=True)` for any value but the one given. Without `check=True` both return False instead of raising, and Qat prints a line such as `Warning: Property "text" is "2" (ref is 3)`, which is no error of its own.
  - `qat.wait_for(lambda: ..., timeout=3000)` waits for any condition and returns whether it came true.
- **Objects:** `obj = qat.wait_for_object(definition)`.
  - Read and write properties as attributes: `obj.text`, `obj.text = "new"`.
  - Call slots and `Q_INVOKABLE` methods: `obj.close()`.
  - Walk the tree with `obj.children` and `obj.parent`, list what an object offers with `obj.list_properties()` and `obj.list_methods()`, and find every match with `qat.find_all_objects(definition)`.
  - An object from `qat.wait_for_object()` keeps the definition it was found by, with `"visible": True` and `"enabled": True` added, and Qat looks it up by that definition on every use. Once it is hidden or deleted, such as a dialog that has closed, using it raises `AttributeError: Unable to find object`, and `qat_agent_helpers.definition_for()` raises `NotFoundError` for it. Reach a hidden object through `qat.wait_for_object_exists(definition)` instead.

## Pitfalls

- **Modal dialogs.** A blocking Qat call whose handler opens a dialog with `exec()` waits until the dialog closes, so the script hangs, and Qat's input calls block by default. `qat_agent_helpers.click()` and `qat_agent_helpers.press_keys()` never block; in a plain Qat call, pass `blocking=False`, as in `qat.mouse_click(target, blocking=False)`, then wait for the dialog with `qat.wait_for_object()`. A dialog run with `exec()` is usually deleted when it closes, so wait for that by passing its definition to `qat.wait_for_object_missing()`: the `def=` of its snapshot line, or what `qat_agent_helpers.definition_for()` returned while the dialog was open.
- **Typing waits for the app.** `qat_agent_helpers.type_text()` returns once the app has handled the keys, because Qat has no other way to type. A field whose `textChanged` handler opens a dialog with `exec()` hangs it; set the `text` property instead, or type before the dialog can open.
- **Return in a text field.** A blocking `qat.shortcut(field, "Return")` raises "No widget accepted this event", because a `QLineEdit` lets Return through after it emits `returnPressed`. Use `qat_agent_helpers.press_keys()`, or pass `blocking=False`.
- **Check boxes.** Qt toggles a `QCheckBox` only on clicks on its indicator or its text, and layouts often stretch the widget, so a click at its centre misses. `qat_agent_helpers.click()` aims at the indicator and raises `NotToggledError` if the click did not change its check state. In a plain Qat call, click at `x=10, y=height // 2`, or press Space on it.
- **Ambiguous definitions.** Two objects with the same `objectName` make a definition match both, and Qat fails. Take the `def=` of the one you mean from the snapshot or from the error, or give the object a unique `objectName` in the app's code.
- **Message boxes under KDE Plasma.** On Linux, an app built with the distribution's Qt loads Plasma's platform theme, which shows a `QMessageBox` through a copy of its own. A snapshot then lists two message boxes with the same text: the app's own, which has a `def=` but ignores clicks, and the copy on screen, which has no parent and no `def=`. Launch the app with `env={"QT_QPA_PLATFORMTHEME": "generic"}`, which makes Qt show its own message box alone.
- **Emoji in Qt 5 apps.** On Linux and macOS, Qat cannot type characters beyond the Basic Multilingual Plane, such as emoji, into a Qt 5 app. Set the property instead: `qat.wait_for_object(definition).text = "👋"`.
- **Input that a user could not give.** Qat sends its events to the object even when a dialog covers it, it is scrolled out of view or its window is in the background, so a click that works does not prove that a user can make it. Look at a screenshot when that matters.
