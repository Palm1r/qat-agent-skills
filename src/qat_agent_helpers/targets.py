from __future__ import annotations

import time
import warnings
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from qat_agent_helpers import apps, definitions
from qat_agent_helpers.apps import App
from qat_agent_helpers.definitions import line_of
from qat_agent_helpers.describe import describe, is_visual, python_literal
from qat_agent_helpers.errors import (
    AmbiguousDefinitionError,
    AmbiguousDefinitionWarning,
    NotFoundError,
    NotReadyError,
    ObjectGoneError,
    QatAgentHelpersError,
)

MAX_CANDIDATES = 20
POLL_INTERVAL = 0.05
READY_ADVICE = {
    "hidden": "Make it visible first, or wait for it with qat.wait_for_object().",
    "disabled": "Wait until it is enabled, for example with qat.wait_for_object().",
}


@dataclass(frozen=True)
class Resolved:
    app: App
    uid: str | None
    definition: dict[str, Any]


@dataclass(frozen=True)
class Ready:
    app: App
    uid: str
    properties: dict[str, Any]


def resolve(target: Any) -> Resolved:
    proxy = apps.adapter().proxy_of(target)
    if proxy is not None:
        uid = proxy.definition.get("cache_uid")
        app = apps.app_of_context(proxy.context)
        resolved = Resolved(app, str(uid) if uid is not None else None, proxy.definition)
    elif isinstance(target, dict):
        resolved = Resolved(apps.current_app(), None, target)
    else:
        raise TypeError(
            f"A target is a Qat definition such as {{'objectName': 'okButton'}} or a Qat object, "
            f"not {type(target).__name__}."
        )
    if _names_a_row(resolved.definition):
        raise ValueError(
            f"{python_literal(resolved.definition)} is a row or cell of an item view, which "
            "qat-agent-helpers cannot act on yet. Use Qat's own calls on it, such as "
            "qat.mouse_click(definition, blocking=False), and check the effect with a Qat wait."
        )
    return resolved


def _names_a_row(definition: Any) -> bool:
    """Whether a definition, or one of its containers, picks a row or cell of an item view: Qat
    reaches those through a wrapper it makes for each request, which has no cached uid."""
    while isinstance(definition, dict):
        if "row" in definition or "column" in definition:
            return True
        definition = definition.get("container")
    return False


def ready(target: Any) -> Ready:
    timeout = apps.adapter().wait_timeout()
    resolved = resolve(target)
    app, uid, definition = resolved.app, resolved.uid, resolved.definition
    deadline = time.monotonic() + timeout
    while True:
        found = _ready_by_uid(app, uid) if uid else _ready_by_definition(app, definition)
        if found is not None:
            return found
        if time.monotonic() >= deadline:
            raise _not_ready(app, uid, definition, timeout)
        time.sleep(POLL_INTERVAL)


def uid_of(target: Any) -> tuple[App, str]:
    resolved = resolve(target)
    if resolved.uid is not None:
        return resolved.app, resolved.uid
    return resolved.app, find_one(resolved.app, resolved.definition)


def definition_for(obj: Any) -> dict[str, Any]:
    """A portable definition that matches only this object, for scripts and Qat tests.

    `obj` is a Qat object or a definition. The candidates are tried in the order
    library.md lists. When none is unique, the best one comes back with an
    AmbiguousDefinitionWarning.
    """
    app, uid = uid_of(obj)
    properties = app.connection.properties(uid)
    found = definitions.find_definition(app.connection, uid, properties)
    if found.matches != 1:
        warnings.warn(
            AmbiguousDefinitionWarning(
                f"No definition matches only {describe(properties, None)}: the best one, "
                f"{python_literal(found.definition)}, matches {found.matches} "
                "objects. Give the object an objectName in the app's code to make it unique."
            ),
            stacklevel=2,
        )
    return found.definition


def find_one(app: App, definition: dict[str, Any]) -> str:
    uids = _find(app, definition, definition)
    if not uids:
        raise NotFoundError(
            f"No object matches the definition {python_literal(definition)}. "
            "Take a snapshot to see what is there."
        )
    if len(uids) > 1:
        raise ambiguity(app, definition, uids)
    return uids[0]


def ambiguity(
    app: App, definition: dict[str, Any], uids: list[str], what: str = "definition"
) -> AmbiguousDefinitionError:
    lines = [f"The {what} {python_literal(definition)} matches {len(uids)} objects:"]
    found: list[dict[str, Any] | None] = []
    for uid in uids[:MAX_CANDIDATES]:
        with suppress(ObjectGoneError):
            properties = app.connection.properties(uid)
            candidate = definitions.find_definition(app.connection, uid, properties)
            unique = candidate.definition if candidate.matches == 1 else None
            found.append(unique)
            lines.append("- " + describe(properties, unique))
    if len(uids) > MAX_CANDIDATES:
        lines.append(f"...and {len(uids) - MAX_CANDIDATES} more; narrow the definition.")
    return AmbiguousDefinitionError("\n".join(lines), found)


def _ready_by_uid(app: App, uid: str) -> Ready | None:
    return _if_ready(Ready(app, uid, app.connection.properties(uid)))


def _ready_by_definition(app: App, definition: dict[str, Any]) -> Ready | None:
    uids = _find(app, definition, _accessible(definition))
    if len(uids) > 1:
        raise ambiguity(app, definition, uids)
    if not uids:
        return None
    try:
        properties = app.connection.properties(uids[0])
    except ObjectGoneError:
        return None
    return _if_ready(Ready(app, uids[0], properties))


def _if_ready(found: Ready) -> Ready | None:
    if not is_visual(found.properties):
        raise QatAgentHelpersError(
            f"{line_of(found.app.connection, found.uid, found.properties)} is not a widget, "
            "Qt Quick item or window, so it cannot take input."
        )
    return found if _readiness(found.properties) is None else None


def _not_ready(
    app: App, uid: str | None, definition: dict[str, Any], timeout: float
) -> QatAgentHelpersError:
    if uid is None:
        shown = python_literal(definition)
        uids = _find(app, definition, _accessible(definition, itself=False))
        if not uids:
            return NotFoundError(
                f"No object matches the definition {shown} after {timeout:g} s. "
                "Take a snapshot to see what is there."
            )
        if len(uids) > 1:
            return NotReadyError(
                f"The definition {shown} matches {len(uids)} objects, but none of them is "
                f"visible and enabled after {timeout:g} s."
            )
        uid = uids[0]
    properties = app.connection.properties(uid)
    problem = _readiness(properties) or "not ready"
    return NotReadyError(
        f"{line_of(app.connection, uid, properties)} is still {problem} after {timeout:g} s. "
        + READY_ADVICE.get(problem, "")
    )


def _find(app: App, definition: dict[str, Any], searched: dict[str, Any]) -> list[str]:
    uids = app.connection.find(searched)
    container, searched_container = definition.get("container"), searched.get("container")
    if not uids and isinstance(container, dict) and isinstance(searched_container, dict):
        containers = _find(app, container, searched_container)
        if len(containers) > 1:
            raise ambiguity(app, container, containers, what="container")
    return uids


def _accessible(definition: dict[str, Any], *, itself: bool = True) -> dict[str, Any]:
    accessible = {
        name: _accessible(value) if isinstance(value, dict) else value
        for name, value in definition.items()
    }
    if itself:
        accessible.setdefault("visible", True)
        accessible.setdefault("enabled", True)
    return accessible


def _readiness(properties: dict[str, Any]) -> str | None:
    if properties.get("visible") is not True:
        return "hidden"
    if properties.get("enabled") is False:
        return "disabled"
    return None
