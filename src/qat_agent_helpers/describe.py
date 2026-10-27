from __future__ import annotations

import json
from typing import Any

MAX_TEXT_LENGTH = 80


def describe(properties: dict[str, Any], definition: dict[str, Any] | None) -> str:
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
    has_size = "geometry" in properties or ("width" in properties and "height" in properties)
    return "visible" in properties and has_size


def python_literal(value: Any) -> str:
    if isinstance(value, dict):
        items = (f"{python_literal(key)}: {python_literal(item)}" for key, item in value.items())
        return "{" + ", ".join(items) + "}"
    if isinstance(value, list | tuple):
        return "[" + ", ".join(python_literal(item) for item in value) + "]"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return repr(value)


def _text(properties: dict[str, Any]) -> str | None:
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
