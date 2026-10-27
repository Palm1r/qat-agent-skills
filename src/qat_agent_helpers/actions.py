from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from qat_agent_helpers import targets
from qat_agent_helpers.adapter import AppConnection
from qat_agent_helpers.definitions import line_of
from qat_agent_helpers.errors import NotAcceptedError, NotToggledError, ObjectGoneError


def click(
    target: Any,
    button: str = "left",
    double: bool = False,
    modifiers: Iterable[str] = (),
    x: int | None = None,
    y: int | None = None,
) -> None:
    """Click an object, given as a Qat definition or a Qat object, once it is ready.

    `button` is "left", "right" or "middle", `modifiers` holds "ctrl", "shift" or "alt",
    and `x` and `y` are relative to the object (its centre by default). A check box, radio
    button or switch is clicked on its indicator. An error is raised when the click on a
    button with an indicator, or on any checkable widget button, left `checked` as it was;
    other checkable objects, such as a QGroupBox, toggle only on their own parts.
    """
    if (x is None) != (y is None):
        raise ValueError("Pass both x and y, or neither.")
    found = targets.ready(target)
    connection, properties = found.app.connection, found.properties
    toggles = properties.get("checkable") is True and button == "left" and not double
    indicator = _indicator(connection, found.uid, properties) if toggles and x is None else None
    if indicator is not None:
        x, y = indicator
    connection.click(found.uid, button=button, double=double, modifiers=tuple(modifiers), x=x, y=y)
    if toggles and (indicator is not None or connection.is_a(found.uid, "QAbstractButton")):
        _check_toggled(found, connection.properties(found.uid))


def press_keys(target: Any, keys: str) -> None:
    """Press a key or a shortcut such as "Return" or "Ctrl+S" on an object, once it is ready.

    The keys are in QKeySequence's notation and sent like qat.shortcut(..., blocking=False).
    """
    if not keys.strip():
        raise ValueError("Pass the key or shortcut to press, such as Return or Ctrl+S.")
    found = targets.ready(target)
    found.app.connection.press_keys(found.uid, keys)


def type_text(target: Any, text: str) -> None:
    """Type text into an object, such as a text field, once it is ready.

    Qat focuses the object first and waits until the app has handled the keys.
    """
    if not text:
        raise ValueError("Pass the text to type.")
    found = targets.ready(target)
    if not found.app.connection.type_text(found.uid, text):
        raise NotAcceptedError(
            f"No widget accepted the keys typed into "
            f"{line_of(found.app.connection, found.uid, found.properties)}: it may not take text. "
            "Target a text field instead."
        )


def _indicator(
    connection: AppConnection, uid: str, properties: dict[str, Any]
) -> tuple[int, int] | None:
    indicator = properties.get("indicator")
    if isinstance(indicator, dict) and "uid" in indicator:
        try:
            item = connection.properties(indicator["uid"])
        except ObjectGoneError:
            return None
        geometry = [item.get(name) for name in ("x", "y", "width", "height")]
        numbers = [float(value) for value in geometry if isinstance(value, int | float)]
        if len(numbers) != 4:
            return None
        left, top, width, height = numbers
        return int(left + width / 2), int(top + height / 2)
    if connection.is_a(uid, "QCheckBox") or connection.is_a(uid, "QRadioButton"):
        width, height = properties.get("width"), properties.get("height")
        if isinstance(width, int) and isinstance(height, int):
            offset = max(1, min(width, height) // 2)
            right_to_left = properties.get("layoutDirection") == "RightToLeft"
            return (width - 1 - offset if right_to_left else offset), height // 2
    return None


def _check_toggled(found: targets.Ready, after: dict[str, Any]) -> None:
    before = found.properties
    # Qt Quick's check box shows its check state, and checked stays false from unchecked to
    # partly checked. Qt Widgets show no check state, and checked stays true from partly
    # checked to checked, so a checked tristate widget check box may rightly stay checked, as
    # a checked radio button does.
    name = "checkState" if "checkState" in before else "checked"
    if before.get("checked") is True and (
        before.get("autoExclusive") or (before.get("tristate") is True and name == "checked")
    ):
        return
    if after.get(name) != before.get(name):
        return
    raise NotToggledError(
        f"The click on {line_of(found.app.connection, found.uid, found.properties)} did not toggle "
        f"it: {name} stayed {before.get(name)}. Click its indicator, or press Space on it with "
        "press_keys()."
    )
