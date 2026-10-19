"""Definitions that match exactly one object, for scripts and for Qat tests.

The candidates, in order (library.md): objectName and type, QML id and type, type and
text, then the same inside the nearest ancestor that has a unique definition, as a
`container`. Each one is checked with one find request. Visibility and enabledness are
left out: in a test, Qat's wait_for_object() adds them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from qat_agent_helpers.adapter import AppConnection

# How far up the tree the search for a container goes.
MAX_CONTAINER_LEVELS = 10


@dataclass(frozen=True)
class FoundDefinition:
    definition: dict[str, Any]
    matches: int  # how many objects it matches; 1 when it is unique


def unique_definition(
    connection: AppConnection,
    uid: str,
    properties: dict[str, Any],
    container: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """A definition that matches only this object, using `container` if it needs one."""
    own = candidates(properties)
    for candidate in own:
        if connection.find(candidate) == [uid]:
            return candidate
    if container is not None:
        for candidate in [*own, {"type": properties.get("type")}]:
            scoped = {**candidate, "container": container}
            if connection.find(scoped) == [uid]:
                return scoped
    return None


def find_definition(
    connection: AppConnection, uid: str, properties: dict[str, Any]
) -> FoundDefinition:
    """The object's unique definition, or else its best candidate and how many it matches."""
    container = _nearest_unique_ancestor(connection, uid)
    unique = unique_definition(connection, uid, properties, container)
    if unique is not None:
        return FoundDefinition(unique, 1)
    own = candidates(properties)
    best = own[0] if own else {"type": properties.get("type")}
    return FoundDefinition(best, len(connection.find(best)))


def candidates(properties: dict[str, Any]) -> list[dict[str, Any]]:
    """The object's own candidate definitions, without a container."""
    type_name = properties.get("type")
    found = []
    if properties.get("objectName"):
        found.append({"objectName": properties["objectName"], "type": type_name})
    if properties.get("id"):
        found.append({"id": properties["id"], "type": type_name})
    text = properties.get("text")
    if isinstance(text, str) and text:
        found.append({"type": type_name, "text": text})
    return found


def python_literal(value: Any) -> str:
    """A definition or a value as Python source, ready to paste into a script."""
    if isinstance(value, dict):
        items = (f"{python_literal(key)}: {python_literal(item)}" for key, item in value.items())
        return "{" + ", ".join(items) + "}"
    if isinstance(value, list | tuple):
        return "[" + ", ".join(python_literal(item) for item in value) + "]"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)  # JSON's string escapes are Python's too
    return repr(value)


def _nearest_unique_ancestor(connection: AppConnection, uid: str) -> dict[str, Any] | None:
    ancestor = connection.parent(uid)
    for _ in range(MAX_CONTAINER_LEVELS):
        if ancestor is None:
            return None
        for candidate in candidates(connection.properties(ancestor)):
            if connection.find(candidate) == [ancestor]:
                return candidate
        ancestor = connection.parent(ancestor)
    return None
