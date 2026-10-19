"""One line per object: its type, #objectName, QML id=, text, flags and definition.

QPushButton #incrementButton "Increment" def={"objectName": "incrementButton", ...}
"""

from __future__ import annotations

import json
from typing import Any

from qat_agent_helpers.definitions import python_literal

MAX_TEXT_LENGTH = 80


def describe(properties: dict[str, Any], definition: dict[str, Any] | None) -> str:
    """The object's line, with `definition` as def={...} when it has a unique one."""
    parts = [str(properties.get("type", "QObject"))]
    object_name = properties.get("objectName")
    if object_name:
        parts.append(f"#{object_name}")
    qml_id = properties.get("id")
    if qml_id:
        parts.append(f"id={qml_id}")
    text = _text(properties)
    if text is not None:
        parts.append(text)
    parts.extend(_flags(properties))
    if definition is not None:
        parts.append(f"def={python_literal(definition)}")
    return " ".join(parts)


def is_visual(properties: dict[str, Any]) -> bool:
    """Widgets, Qt Quick items and windows have a visibility and a size; other QObjects don't."""
    has_size = "geometry" in properties or ("width" in properties and "height" in properties)
    return "visible" in properties and has_size


def _text(properties: dict[str, Any]) -> str | None:
    """The quoted text or title, or the placeholder of an empty field."""
    text = None
    for name in ("text", "title"):
        value = properties.get(name)
        if isinstance(value, str):
            text = value
            break
    else:
        window_title = properties.get("windowTitle")
        if isinstance(window_title, str) and window_title:
            text = window_title
    placeholder = properties.get("placeholderText")
    if not text and isinstance(placeholder, str) and placeholder:
        return f"placeholder={_quote(placeholder)}"
    return None if text is None else _quote(text)


def _flags(properties: dict[str, Any]) -> list[str]:
    flags = []
    if properties.get("visible") is False:
        flags.append("hidden")
    if properties.get("enabled") is False:
        flags.append("disabled")
    # A Qt Quick item's `focus` only marks it within its focus scope.
    focus_property = "activeFocus" if "activeFocus" in properties else "focus"
    if properties.get(focus_property) is True:
        flags.append("focused")
    if properties.get("checked") is True:
        flags.append("checked")
    return flags


def _quote(text: str) -> str:
    if len(text) > MAX_TEXT_LENGTH:
        text = text[: MAX_TEXT_LENGTH - 3] + "..."
    return json.dumps(text, ensure_ascii=False)
