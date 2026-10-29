# Qat's API beyond the essentials

Plain Qat 1.9.0 calls for what qat-agent-helpers does not cover. They act on Qat's current app, take a definition or a Qat object, and first wait for their target to be visible and enabled, as `qat.wait_for_object()` does.

- [Blocking calls](#blocking-calls)
- [Mouse](#mouse)
- [Keyboard](#keyboard)
- [Touch and gestures](#touch-and-gestures)
- [Item views](#item-views)
- [Lists in Qt Quick](#lists-in-qt-quick)
- [Menus and actions](#menus-and-actions)
- [Native dialogs](#native-dialogs)
- [Methods and properties](#methods-and-properties)
- [Signals](#signals)
- [Screenshots](#screenshots)
- [Several apps, the registry and settings](#several-apps-the-registry-and-settings)
- [What Qat cannot do](#what-qat-cannot-do)

## Blocking calls

Qat's input calls block by default: they return once the app has handled the event, so a handler that opens a dialog with `exec()` keeps them waiting until the dialog closes, and the script hangs. Pass `blocking=False` to any call whose input may open such a dialog; the call then returns at once, so check its effect with a Qat wait. `check=True` raises when no widget accepted the event, and works in blocking mode only.

`type_in()`, `press_key()`, `release_key()`, `mouse_drag_and_drop()` and the touch and gesture calls have no `blocking` parameter. Use them only where their input cannot open a modal dialog; a method call with `async_call` is the way around ([Methods and properties](#methods-and-properties)).

## Mouse

`x` and `y` are relative to the target, its centre by default. `button` is one of `qat.Button.LEFT`, `RIGHT` and `MIDDLE`, and `modifier` one of `qat.Modifier.NONE`, `ALT`, `CTL` and `SHIFT`.

| Call | What it does |
|---|---|
| `qat.mouse_press(target, x=None, y=None, modifier=..., button=..., check=False, blocking=True)`, `qat.mouse_release(...)` with the same parameters | Presses or releases a button. A press and a release sent one after the other make a click. |
| `qat.mouse_click(target, ...)`, `qat.double_click(target, ...)` with the same parameters | A click or a double click. Two clicks in a row are not a double click. |
| `qat.mouse_move(target, x=None, y=None, modifier=..., button=..., blocking=True)` | Moves the pointer onto the target, as hovering does, for example to show a tooltip. Wait for the tooltip like for any other object. |
| `qat.mouse_drag(target, x=None, y=None, dx=None, dy=None, modifier=..., button=..., check=False, blocking=True)` | Presses at `x, y`, moves by `dx, dy` and releases: a slider's handle, a splitter, a selection. |
| `qat.mouse_wheel(target, x=None, y=None, x_degrees=0, y_degrees=0, modifier=..., check=False, blocking=True)` | Turns the wheel. 15 degrees is one notch, and a positive `y_degrees` turns it away from the user, which scrolls up. |
| `qat.mouse_drag_and_drop(source, target, sx=None, sy=None, tx=None, ty=None, modifier=..., check=False)` | Drags from one object and drops on another, `sx, sy` and `tx, ty` relative to each. |

## Keyboard

| Call | What it does |
|---|---|
| `qat.type_in(target, text)` | Types text, as `qat_agent_helpers.type_text()` does. Special keys go in angle brackets: `<Backspace>`, `<Delete>`, `<Enter>`, `<Escape>`, `<Return>`, `<Tab>`, `<Control>`, `<Shift>`, `<Alt>`. |
| `qat.shortcut(target, "Ctrl+Z", blocking=True)` | A key combination in Qt's notation. On macOS, `Ctrl` is the Command key, as in Qt. |
| `qat.press_key(target, key)`, `qat.release_key(target, key)` | Hold a key down and let it go, for example `<Shift>` around clicks. |

## Touch and gestures

- `qat.touch_tap(target, x=None, y=None, modifier=...)`, `qat.touch_double_tap(...)`, `qat.touch_press(...)`, `qat.touch_move(...)` and `qat.touch_release(...)` touch the target with one finger, or with several when `x` and `y` are lists of the same length. `qat.touch_drag(target, x=None, y=None, dx=0, dy=0, modifier=...)` drags.
- `qat.flick(target, dx=0, dy=0)` moves a Qt Quick `Flickable`, such as a `ListView`, by `dx, dy` pixels.
- `qat.pinch(target, rotation=0.0, translation=None, scale=1.0)` pinches with two fingers: `rotation` in degrees clockwise, `translation` of the point between the fingers, and `scale` of the distance between them.
- `qat.native_pinch(target, angle=None, scale=None, check=False)` sends the operating system's own pinch gesture, in Qt Quick only.
- Events sent inside `with qat.event_sequence():` get timestamps close enough to count as one gesture, such as two taps as a double tap. The feature is experimental.

## Item views

Rows and cells of a `QListView`, `QTableView` or `QTreeView`, and of the `QListWidget`, `QTableWidget` and `QTreeWidget` built on them, are virtual widgets. Qat finds one by a definition whose `container` is the view and whose `row`, and for tables and trees `column`, are indexes from 0. A snapshot does not list them, and qat-agent-helpers raises `ValueError` for them, so use Qat's own calls:

```python
LIST = {"objectName": "fruitList", "type": "QListWidget"}
row = {"container": LIST, "row": 1}

print(qat.wait_for_object(row).text)  # "Banana"
qat.mouse_click(row, blocking=False)
qat.wait_for_property_value(LIST, "currentRow", 1, check=True)
view = qat.wait_for_object(LIST)
assert view.selectionModel.isSelected(view.model.index(1, 0))
```

- The object `qat.wait_for_object()` returns for a row has `row`, `column`, `text` (the text on screen) and `color`; `data(role)` and `setData(value, role)` for any `Qt::ItemDataRole`; and `ScrollTo()`, which scrolls the view until the row shows.
- The rows of a tree under another row take that row's definition as their `container`: `{"container": {"container": TREE, "row": 2}, "row": 0}`.
- The view's model is reachable too: `model = qat.wait_for_object(view).model`, then `index = model.index(row, column)`, or `model.index(row, column, parent_index)` in a tree, `model.data(index, role)` and `model.setData(index, value, role)`.
- The view's `selectionModel` holds the selection, which `currentRow` does not tell. Ask it about one index at a time with `isSelected(index)`, as above: a list of indexes, such as `selectedIndexes`, comes back through Qat as `None`.

## Lists in Qt Quick

A Qt Quick `ListView`, `GridView` or `TableView` creates delegates only for the part on screen and a little around it, so an item further down does not exist until the view gets there. A delegate is an ordinary object once it exists, with its definition in a snapshot. Scroll the view with `qat.flick(view, dy=...)` or `qat.mouse_wheel(view, y_degrees=..., blocking=False)`, or set its `contentY` property, until `qat.wait_for_object()` finds the delegate.

These views keep no selection of their own: what a click on a delegate does is up to the app, which often sets the view's `currentIndex` or a delegate's `highlighted`. Check the property the app changes. When none changes after a click that reached the delegate, as its `clicked()` signal shows ([Signals](#signals)), the app does not select on a click, and a test cannot make it.

## Menus and actions

In Qt Widgets, the items of a `QMenuBar` or a `QMenu` are virtual widgets. A definition with the menu bar or the menu as its `container` and the item's `text` finds one; the `&` of a mnemonic is optional. qat-agent-helpers cannot act on them yet, so use Qat's own calls with `blocking=False`, since an item may open a dialog:

```python
qat.mouse_click({"container": {"type": "QMenuBar"}, "text": "File"}, blocking=False)
qat.mouse_click({"container": {"objectName": "fileMenu"}, "text": "Open"}, blocking=False)
```

The object returned for an item has `text`, `visible`, `enabled`, `checked` and its `action`.

In Qt Quick, menus are ordinary objects. Give `type` in the definition of a `MenuBarItem` or a `MenuItem`, because an `IconLabel` inside each item carries the same `text`: `{"container": {"type": "MenuBar"}, "type": "MenuBarItem", "text": "File"}`. A submenu opens from the `MenuItem` that Qt adds to the parent menu with the submenu's `title` as its text.

An action can be triggered without its menu: `qat.wait_for_object_exists({"container": menu, "type": "QAction", "text": "Open"}).trigger.async_call()`, with `"type": "Action"` in Qt Quick. `async_call` keeps the call from blocking on a dialog the action opens.

## Native dialogs

On Windows and macOS, Qt apps show the system's own file dialogs unless they ask for Qt's (`QFileDialog::DontUseNativeDialog`). Qt's own dialogs are ordinary objects and far easier to drive; whether the app uses them in tests is the user's call. Qat reaches native windows and controls through wrappers too, by `type` and `text`, since they have no `objectName`:
- On Windows, a file dialog is `{"type": "Dialog", "text": "Open"}`, its file name field `{"container": {"container": dialog, "type": "ComboBox", "text": ""}, "type": "Edit"}`, and its button `{"container": dialog, "type": "Button", "text": "Open"}`. Two dialogs with the same type and text, such as an error over a file dialog, differ in their `handle` property.
- On macOS, a Cocoa window is a `QNSWindow`, with views such as `NSTextField`, but the controls of a file panel are out of reach. Send keys to the system with `qat.Platform` instead, with a short sleep between steps: `qat.shortcut(qat.Platform, "Ctrl+Shift+G")` opens the path field, then `qat.type_in(qat.Platform, "/path/to/file")` and `qat.type_in(qat.Platform, "<Enter>")`. macOS asks for the Accessibility permission for this.
- Events on native controls are handled later, not when the call returns, so check their effect with a Qat wait.

## Methods and properties

- A method's arguments and a property's new value are Python values, Qat objects, or Qt values from `qat.qt_types`, such as `QColor("#ff0000")`, `QPoint(10, 20)`, `QSize(640, 480)` and `QFont("Arial", pointSize=12)`.
- A method that opens a modal dialog, or that runs long, blocks like any blocking call. Call it with `async_call`, as in `obj.exec.async_call()` or `action.trigger.async_call()`; the call then returns nothing.
- Setting a property is not user input: `field.text = "Ada"` changes the text without the signals that only the user causes, such as `QLineEdit`'s `textEdited`. Type when the app reacts to typing.

## Signals

`qat.connect(target, name, callback)` calls `callback` with a signal's arguments, or with a property's new value, each time it changes, and returns an id for `qat.disconnect()`. It catches what is gone before a wait could see it, such as a message that shows for a moment:

```python
texts = []
connection = qat.connect({"objectName": "nameField"}, "text", texts.append)
qat_agent_helpers.type_text({"objectName": "nameField"}, "Ada")
qat.wait_for(lambda: texts[-1:] == ["Ada"], timeout=3000)  # texts is ["A", "Ad", "Ada"]
qat.disconnect(connection)
```

- A signal is given by its signature, such as `"clicked()"`, and the callback takes at most its arguments.
- A property needs a notification signal: a `QLabel`'s `text` has none, and connecting to it raises `RuntimeError`.
- `qat.bind(target, "property", python_object, "attribute")` keeps a Python attribute equal to a property.

## Screenshots

- `qat.grab_screenshot(target, delay=0, timeout=None)` returns an image of the object, taken after `delay` milliseconds. `image.save(path)` writes it, in the format the extension names, and `image.width`, `image.height`, `image.getPixel(x, y)` and `image.getPixelRGBA(x, y)` read it.
- The image has the screen's pixels, not Qt's: on a scaled display it is larger than the object's `width` and `height`, such as 714×816 for a 420×480 window at 170 %. Scale a point of the object by `image.width / obj.width` before reading its pixel.
- `qat.take_screenshot(path=None)` saves every top-level window, into a `screenshots/` folder in the current folder when no path is given. Prefer `grab_screenshot()` with a path outside the user's project.

## Several apps, the registry and settings

- Each launch or attach makes a new current app. `qat.set_current_application_context(app.context)` switches between them, and a Qat object keeps talking to the app it came from.
- `qat.start_application(name)` starts an app registered in an `applications.json`, by `qat.register_application(name, path)` or Qat's `qat-gui`, as Qat suites do. `qat_agent_helpers.launch()` needs no registry and launches the app once.
- `qat.Settings` holds Qat's timeouts in milliseconds: `wait_for_object_timeout`, `wait_for_app_start_timeout`, `wait_for_app_stop_timeout`, `wait_for_app_attach_timeout` and `long_operation_timeout`. Qat reads them from a `testSettings.json` in the current folder when it starts the first app.

## What Qat cannot do

- Items of a `QGraphicsScene` are out of its reach.
- It compares no images: read pixels with `getPixel()`, or look at the screenshot.
- Some keys do not reach an app whose window is in the background (Qat issue #44).
