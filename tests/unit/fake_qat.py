"""A fake Qat adapter: apps are in-memory object trees, so the unit tests need no Qt.

Objects report the properties real Qat reports for them: widgets have `geometry`,
Qt Quick items have `width` and `height`, and non-visual QObjects have neither.
"""

from __future__ import annotations

import itertools
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qat_agent_helpers.adapter import Child
from qat_agent_helpers.errors import AppGoneError, CommandError, LaunchError, ObjectGoneError

_uids = itertools.count(1000)
_pids = itertools.count(4000)


@dataclass(eq=False)
class FakeObject:
    properties: dict[str, Any]
    children: list[FakeObject] = field(default_factory=list)
    uid: str = field(default_factory=lambda: str(next(_uids)))
    # What the app does when the object is clicked (given the click's options) or gets keys.
    on_click: Callable[[dict[str, Any]], None] | None = None
    on_keys: Callable[[str], None] | None = None
    # Whether typed text lands in its `text` property, as in a QLineEdit.
    takes_text: bool = False
    # The classes it inherits from, besides its own `type`.
    bases: tuple[str, ...] = ()

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


def widget(
    type: str,
    object_name: str = "",
    *children: FakeObject,
    text: str | None = None,
    placeholder: str | None = None,
    window_title: str = "",
    visible: bool = True,
    enabled: bool = True,
    focus: bool = False,
    checked: bool | None = None,
    size: tuple[int, int] = (100, 30),
) -> FakeObject:
    """A QWidget, which has a geometry, a size and an empty QML id."""
    width, height = size
    properties: dict[str, Any] = {
        "type": type,
        "objectName": object_name,
        "id": "",
        "windowTitle": window_title,
        "visible": visible,
        "enabled": enabled,
        "focus": focus,
        "geometry": {"x": 0, "y": 0, "width": width, "height": height},
        "width": width,
        "height": height,
        "layoutDirection": "LeftToRight",
    }
    if text is not None:
        properties["text"] = text
    if placeholder is not None:
        properties["placeholderText"] = placeholder
    if checked is not None:
        properties["checkable"] = True
        properties["checked"] = checked
    return FakeObject(properties, list(children))


def item(
    type: str,
    object_name: str = "",
    *children: FakeObject,
    qml_id: str = "",
    text: str | None = None,
    title: str | None = None,
    visible: bool = True,
    enabled: bool = True,
    focus: bool = False,
    active_focus: bool = False,
) -> FakeObject:
    """A Qt Quick item, which has a size and maybe a QML id."""
    properties: dict[str, Any] = {
        "type": type,
        "objectName": object_name,
        "id": qml_id,
        "visible": visible,
        "enabled": enabled,
        "focus": focus,
        "activeFocus": active_focus,
        "x": 0,
        "y": 0,
        "width": 100,
        "height": 30,
    }
    if text is not None:
        properties["text"] = text
    if title is not None:
        properties["title"] = title
    return FakeObject(properties, list(children))


def check_box(
    object_name: str, text: str, *, checked: bool = False, size: tuple[int, int] = (400, 21)
) -> FakeObject:
    """A QCheckBox stretched by its layout. As in Qt, it toggles only when a click hits its
    indicator or its text, here the first 80 pixels, so a click at its centre misses."""
    box = widget("QCheckBox", object_name, text=text, checked=checked, size=size)
    box.bases = ("QAbstractButton", "QWidget")

    def toggle(options: dict[str, Any]) -> None:
        x = options["x"] if options["x"] is not None else box.properties["width"] // 2
        if options["button"] == "left" and x < 80:
            box.properties["checked"] = not box.properties["checked"]

    box.on_click = toggle
    return box


def qml_check_box(object_name: str, text: str, *, checked: bool = False) -> FakeObject:
    """A Qt Quick CheckBox, whose `indicator` property points at its indicator item."""
    indicator = item("CheckIndicator", "", qml_id="indicator")
    indicator.properties.update(x=6, y=4, width=28, height=28)
    box = item("CheckBox", object_name, indicator, text=text)
    box.properties.update(checkable=True, checked=checked, indicator={"uid": indicator.uid})
    box.properties.update(width=120, height=36)

    def toggle(options: dict[str, Any]) -> None:
        box.properties["checked"] = not box.properties["checked"]

    box.on_click = toggle
    return box


def list_widget(object_name: str) -> FakeObject:
    """A QListWidget as Qt builds it: a viewport for its items and a container for each
    scroll bar. Its items overflow only vertically, so the horizontal container is hidden."""
    return widget(
        "QListWidget",
        object_name,
        widget("QWidget", "qt_scrollarea_viewport"),
        widget(
            "QWidget",
            "qt_scrollarea_hcontainer",
            widget("QScrollBar", visible=False),
            visible=False,
        ),
        widget("QWidget", "qt_scrollarea_vcontainer", widget("QScrollBar")),
    )


def line_edit(object_name: str = "", text: str = "", **options: Any) -> FakeObject:
    """A QLineEdit: a widget that takes typed text."""
    field = widget("QLineEdit", object_name, text=text, **options)
    field.takes_text = True
    return field


def qobject(type: str, object_name: str = "", *children: FakeObject) -> FakeObject:
    """A non-visual QObject such as a layout or a model."""
    return FakeObject({"type": type, "objectName": object_name}, list(children))


class FakeApp:
    """A launched app: implements AppConnection over a tree of FakeObjects.

    Each request about its objects takes `seconds_per_request`, like a Qat round trip.
    """

    def __init__(
        self, *windows: FakeObject, quits: bool = True, seconds_per_request: float = 0.0
    ) -> None:
        self.pid = next(_pids)
        self.windows = list(windows)
        self.quits = quits
        self.seconds_per_request = seconds_per_request
        self.exit_code: int | None = None
        self.connected = True
        self.killed = False
        self.detached = False
        self.context = object()  # stands for Qat's ApplicationContext
        self.current = False  # whether it is Qat's current app
        # The input commands the app received, as (command, uid, options).
        self.inputs: list[tuple[str, str, dict[str, Any]]] = []
        self._destroyed: set[str] = set()
        self._later: list[tuple[float, FakeObject, dict[str, Any]]] = []
        self._answering = threading.Event()
        self._answering.set()

    # Test controls

    @contextmanager
    def stalled(self) -> Iterator[None]:
        """Requests made during the block wait until it ends, as when the app is busy."""
        self._answering.clear()
        try:
            yield
        finally:
            self._answering.set()

    def destroy(self, obj: FakeObject) -> None:
        for gone in obj.walk():
            self._destroyed.add(gone.uid)
        for parent in self._objects().values():
            if obj in parent.children:
                parent.children.remove(obj)

    def exit(self, code: int) -> None:
        self.exit_code = code

    def lose_connection(self) -> None:
        """The app keeps running but no longer answers Qat."""
        self.connected = False

    def later(self, seconds: float, obj: FakeObject, **properties: Any) -> None:
        """Change the object's properties once `seconds` have passed, as a timer would."""
        self._later.append((time.monotonic() + seconds, obj, properties))

    # AppConnection

    def make_current(self) -> None:
        self.current = True

    def detach(self) -> None:
        self.detached = True
        self.current = False

    def top_windows(self) -> list[str]:
        self._request()
        return [window.uid for window in self.windows]

    def children(self, uid: str) -> list[Child]:
        return [Child(child.uid, bool(child.children)) for child in self._find(uid).children]

    def properties(self, uid: str) -> dict[str, Any]:
        return dict(self._find(uid).properties)

    def find(self, definition: dict[str, Any]) -> list[str]:
        """Qat's matching: every property in the definition has exactly the given value.

        As in Qat, an object without a `visible` or `enabled` property counts as visible
        and enabled, and a `container` definition limits the search to the descendants
        of the objects it matches.
        """
        self._request()
        return [obj.uid for obj in self._matches(definition)]

    def parent(self, uid: str) -> str | None:
        """The nearest object that lists this one, preferring a widget over a layout."""
        self._find(uid)
        parents = [
            obj for obj in self._objects().values() if any(c.uid == uid for c in obj.children)
        ]
        candidates = [obj for obj in parents if "visible" in obj.properties] or parents
        return candidates[0].uid if candidates else None

    def click(
        self,
        uid: str,
        *,
        button: str = "left",
        double: bool = False,
        modifiers: tuple[str, ...] = (),
        x: int | None = None,
        y: int | None = None,
    ) -> None:
        obj = self._find(uid)
        width, height = obj.properties.get("width", 0), obj.properties.get("height", 0)
        if x is not None and y is not None and not (0 <= x < width and 0 <= y < height):
            raise CommandError("Given coordinates are outside widget's boundaries")
        options = {"button": button, "double": double, "modifiers": modifiers, "x": x, "y": y}
        self.inputs.append(("click", uid, options))
        if obj.on_click is not None:
            obj.on_click(options)

    def type_text(self, uid: str, text: str) -> bool:
        obj = self._find(uid)
        self.inputs.append(("type", uid, {"text": text}))
        if not obj.takes_text:
            return False
        obj.properties["text"] = obj.properties.get("text", "") + text
        return True

    def press_keys(self, uid: str, keys: str) -> None:
        obj = self._find(uid)
        self.inputs.append(("keys", uid, {"keys": keys}))
        if obj.on_keys is not None:
            obj.on_keys(keys)

    def barrier(self) -> None:
        self._request()

    def is_a(self, uid: str, type_name: str) -> bool:
        obj = self._find(uid)
        return type_name == obj.properties.get("type") or type_name in obj.bases

    def quit(self) -> None:
        if self.exit_code is None and self.quits:
            self.exit_code = 0

    def wait_for_exit(self, timeout: float) -> int | None:
        return self.exit_code

    def kill(self) -> None:
        self.current = False
        if self.exit_code is None:
            self.killed = True
            self.exit_code = 1

    def _objects(self) -> dict[str, FakeObject]:
        return {obj.uid: obj for window in self.windows for obj in window.walk()}

    def _matches(self, definition: dict[str, Any]) -> list[FakeObject]:
        defaults = {"visible": True, "enabled": True}
        properties = {name: value for name, value in definition.items() if name != "container"}
        if "container" in definition:
            scope: dict[str, FakeObject] = {}
            for container in self._matches(definition["container"]):
                scope.update({obj.uid: obj for obj in container.walk() if obj is not container})
        else:
            scope = self._objects()
        return [
            obj
            for obj in scope.values()
            if all(
                obj.properties.get(name, defaults.get(name)) == value
                for name, value in properties.items()
            )
        ]

    def _find(self, uid: str) -> FakeObject:
        self._request()
        if uid in self._destroyed:
            raise ObjectGoneError(uid)
        return self._objects()[uid]

    def _request(self) -> None:
        """A round trip to the app, which fails once the app is unreachable."""
        # A stalled request gives up after 10 s, so that a broken test fails instead of hanging.
        self._answering.wait(10)
        if self.seconds_per_request:
            time.sleep(self.seconds_per_request)
        if self.exit_code is not None or not self.connected:
            raise AppGoneError(f"pid {self.pid} is not reachable")
        now = time.monotonic()
        for change in [change for change in self._later if change[0] <= now]:
            self._later.remove(change)
            change[1].properties.update(change[2])


class FakeQat:
    """Hands out the given apps, in order, to launch() and attach()."""

    def __init__(self, *apps: FakeApp, launch_error: str | None = None) -> None:
        self._apps = list(apps)
        self.launch_error = launch_error
        self.launches: list[tuple[Path, list[str], dict[str, str], bool]] = []
        self.attaches: list[int] = []

    def launch(self, path: Path, args: list[str], env: dict[str, str], *, lock_ui: bool) -> FakeApp:
        if self.launch_error is not None:
            raise LaunchError(self.launch_error)
        self.launches.append((path, args, env, lock_ui))
        return self._apps.pop(0)

    def attach(self, pid: int) -> FakeApp:
        self.attaches.append(pid)
        app = self._apps.pop(0)
        app.pid = pid
        return app
