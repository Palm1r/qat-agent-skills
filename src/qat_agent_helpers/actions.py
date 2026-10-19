"""Input: clicks, keys and text, sent so that modal dialogs cannot block the script.

Clicks and keys are posted without waiting for their handlers and followed by a barrier,
a request the app answers only once it has handled them, even from inside a dialog's
exec() (ADR 0001). Text is typed blocking, because Qat has no other way to type it.
Every command is sent once, without the Qat client's retries, which would repeat it.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from qat_agent_helpers import targets
from qat_agent_helpers.adapter import AppConnection
from qat_agent_helpers.errors import (
    NonAsciiTextError,
    NotAcceptedError,
    NotToggledError,
    ObjectGoneError,
)


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
    button or switch is clicked on its indicator, and an error is raised if its checked
    state does not change.
    """
    if (x is None) != (y is None):
        raise ValueError("Pass both x and y, or neither.")
    found = targets.ready(target)
    connection, properties = found.app.connection, found.properties
    toggles = properties.get("checkable") is True and button == "left" and not double
    if toggles and x is None:
        x, y = _indicator(connection, found.uid, properties) or (None, None)
    connection.click(found.uid, button=button, double=double, modifiers=tuple(modifiers), x=x, y=y)
    connection.barrier()
    if toggles:
        _check_toggled(found, connection.properties(found.uid).get("checked"))


def press_keys(target: Any, keys: str) -> None:
    """Press a key or a shortcut such as "Return" or "Ctrl+S" on an object, once it is ready.

    The keys are in QKeySequence's notation and sent like qat.shortcut(..., blocking=False).
    """
    if not keys.strip():
        raise ValueError("Pass the key or shortcut to press, such as Return or Ctrl+S.")
    found = targets.ready(target)
    found.app.connection.press_keys(found.uid, keys)
    found.app.connection.barrier()


def type_text(target: Any, text: str) -> None:
    """Type ASCII text into an object, such as a text field, once it is ready.

    Qat focuses the object first and waits until the app has handled the keys.
    """
    if not text:
        raise ValueError("Pass the text to type.")
    if not text.isascii():
        other = next(character for character in text if not character.isascii())
        shown = json.dumps(text, ensure_ascii=False)
        raise NonAsciiTextError(
            "type_text() types ASCII text only: Qat cannot type other characters (Qat issue "
            f'#45), and {shown} contains "{other}". Set the text property instead, for '
            f"example qat.wait_for_object(definition).text = {shown}."
        )
    found = targets.ready(target)
    if not found.app.connection.type_text(found.uid, text):
        raise NotAcceptedError(
            f"No widget accepted the keys typed into "
            f"{targets.line_of(found.app, found.uid, found.properties)}: it may not take text. "
            "Target a text field instead."
        )


def _indicator(
    connection: AppConnection, uid: str, properties: dict[str, Any]
) -> tuple[int, int] | None:
    """Where a check box, radio button or switch has its indicator, relative to itself.

    A centre click misses the box of a QCheckBox that its layout stretched, and
    QCheckBox reacts only to clicks on its indicator and its text.
    """
    indicator = properties.get("indicator")
    if isinstance(indicator, dict) and "uid" in indicator:
        # A Qt Quick control: its indicator item, positioned in the control's coordinates.
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
            # The indicator sits at the leading edge, about as wide as the widget is high.
            offset = max(1, min(width, height) // 2)
            right_to_left = properties.get("layoutDirection") == "RightToLeft"
            return (width - 1 - offset if right_to_left else offset), height // 2
    return None


def _check_toggled(found: targets.Ready, checked_after: Any) -> None:
    before = found.properties.get("checked")
    # Clicking an exclusive button that is checked already leaves it checked, as it should.
    if checked_after != before or (before is True and found.properties.get("autoExclusive")):
        return
    raise NotToggledError(
        f"The click on {targets.line_of(found.app, found.uid, found.properties)} did not toggle "
        f"it: checked stayed {before}. Click its indicator, or press Space on it with "
        "press_keys()."
    )
