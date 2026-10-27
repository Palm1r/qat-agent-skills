from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qat_agent_helpers.adapter import AppConnection
from qat_agent_helpers.describe import describe
from qat_agent_helpers.errors import ObjectGoneError

MAX_CONTAINER_LEVELS = 10


@dataclass(frozen=True)
class FoundDefinition:
    definition: dict[str, Any]
    matches: int


def find_definition(
    connection: AppConnection, uid: str, properties: dict[str, Any]
) -> FoundDefinition:
    own = candidates(properties)
    unique = _own_unique(connection, uid, own)
    if unique is None:
        container = _container_above(connection, uid)
        if container is not None:
            unique = _scoped_unique(connection, uid, properties, own, container)
    if unique is not None:
        return FoundDefinition(unique, 1)
    best = own[0] if own else {"type": properties.get("type")}
    return FoundDefinition(best, len(connection.find(best)))


class TreeDefinitions:
    def __init__(self, connection: AppConnection) -> None:
        self._connection = connection
        self._levels: list[dict[str, Any] | None] = []

    def at(self, level: int, uid: str, properties: dict[str, Any]) -> dict[str, Any] | None:
        del self._levels[level:]
        own = candidates(properties)
        unique = _own_unique(self._connection, uid, own)
        if unique is None:
            container = next((found for found in reversed(self._levels) if found), None)
            if container is None and level == 0:
                # A walk may start below the container that makes its first object unique.
                container = _container_above(self._connection, uid)
            if container is not None:
                unique = _scoped_unique(self._connection, uid, properties, own, container)
        self._levels.append(unique)
        return unique


def line_of(connection: AppConnection, uid: str, properties: dict[str, Any]) -> str:
    try:
        found = find_definition(connection, uid, properties)
    except ObjectGoneError:
        return describe(properties, None)
    return describe(properties, found.definition if found.matches == 1 else None)


def candidates(properties: dict[str, Any]) -> list[dict[str, Any]]:
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


def _container_above(connection: AppConnection, uid: str) -> dict[str, Any] | None:
    between: list[tuple[str, dict[str, Any], list[dict[str, Any]]]] = []
    ancestor = connection.parent(uid)
    for _ in range(MAX_CONTAINER_LEVELS):
        if ancestor is None:
            return None
        properties = connection.properties(ancestor)
        own = candidates(properties)
        container = _own_unique(connection, ancestor, own)
        if container is not None:
            for below, below_properties, below_own in reversed(between):
                scoped = _scoped_unique(connection, below, below_properties, below_own, container)
                if scoped is not None:
                    container = scoped
            return container
        between.append((ancestor, properties, own))
        ancestor = connection.parent(ancestor)
    return None


def _own_unique(
    connection: AppConnection, uid: str, own: list[dict[str, Any]]
) -> dict[str, Any] | None:
    return next((candidate for candidate in own if connection.find(candidate) == [uid]), None)


def _scoped_unique(
    connection: AppConnection,
    uid: str,
    properties: dict[str, Any],
    own: list[dict[str, Any]],
    container: dict[str, Any],
) -> dict[str, Any] | None:
    for candidate in [*own, {"type": properties.get("type")}]:
        scoped = {**candidate, "container": container}
        if connection.find(scoped) == [uid]:
            return scoped
    return None
