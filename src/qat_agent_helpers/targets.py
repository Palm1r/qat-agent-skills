"""Targets: the objects this library's functions work on, given as a Qat definition or proxy.

A definition is looked up in the current app, the newest one open. A proxy, such as one
that qat.wait_for_object() returns, carries its own app.
"""

from __future__ import annotations

import time
import warnings
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from qat_agent_helpers import apps, definitions
from qat_agent_helpers.apps import App
from qat_agent_helpers.describe import describe, is_visual
from qat_agent_helpers.errors import (
    AmbiguousDefinitionError,
    AmbiguousDefinitionWarning,
    NotFoundError,
    NotReadyError,
    ObjectGoneError,
    QatAgentHelpersError,
)

# How many matches of an ambiguous definition an error lists.
MAX_CANDIDATES = 20
# How often ready() looks again.
POLL_INTERVAL = 0.05
READY_ADVICE = {
    "hidden": "Make it visible first, or wait for it with qat.wait_for_object().",
    "disabled": "Wait until it is enabled, for example with qat.wait_for_object().",
}


@dataclass(frozen=True)
class Ready:
    """An object that can take input now, with its properties at that moment."""

    app: App
    uid: str
    properties: dict[str, Any]


def ready(target: Any) -> Ready:
    """The target once it is visible and enabled.

    Waits as long as qat.wait_for_object() would, Qat's Settings.wait_for_object_timeout:
    Qat's own wait before a click skips this check for objects addressed by uid. A
    definition is matched among visible and enabled objects only, as in that function.
    """
    from qat.test_settings import Settings

    timeout = Settings.wait_for_object_timeout / 1000
    app, uid, definition = _unresolved(target)
    deadline = time.monotonic() + timeout
    while True:
        found = _ready_by_uid(app, uid) if uid else _ready_by_definition(app, definition)
        if found is not None:
            return found
        if time.monotonic() >= deadline:
            raise _not_ready(app, uid, definition, timeout)
        time.sleep(POLL_INTERVAL)


def app_of(target: Any) -> App:
    """The app a target belongs to."""
    if _is_proxy(target):
        return _app_of_context(target.__dict__["_app_context"])
    return apps.current_app()


def uid_of(target: Any) -> tuple[App, str]:
    """The app and uid of the one object a target names."""
    if _is_proxy(target):
        app = app_of(target)
        definition = target.get_definition()
        if "cache_uid" in definition:
            return app, str(definition["cache_uid"])
        return app, find_one(app, definition)
    if isinstance(target, dict):
        app = apps.current_app()
        return app, find_one(app, target)
    raise TypeError(
        f"A target is a Qat definition such as {{'objectName': 'okButton'}} or a Qat object, "
        f"not {type(target).__name__}."
    )


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
                f"{definitions.python_literal(found.definition)}, matches {found.matches} "
                "objects. Give the object an objectName in the app's code to make it unique."
            ),
            stacklevel=2,
        )
    return found.definition


def find_one(app: App, definition: dict[str, Any]) -> str:
    """The uid of the one object that matches `definition`."""
    uids = app.connection.find(definition)
    if not uids:
        raise NotFoundError(
            f"No object matches the definition {definitions.python_literal(definition)}. "
            "Take a snapshot to see what is there."
        )
    if len(uids) > 1:
        raise ambiguity(app, definition, uids)
    return uids[0]


def ambiguity(app: App, definition: dict[str, Any], uids: list[str]) -> AmbiguousDefinitionError:
    """The error for a definition that matches several objects: Qat itself just fails."""
    lines = [
        f"The definition {definitions.python_literal(definition)} matches {len(uids)} objects:"
    ]
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


def _unresolved(target: Any) -> tuple[App, str | None, dict[str, Any]]:
    """The target's app, and its uid if it names one, or else its definition."""
    if _is_proxy(target):
        definition = dict(target.get_definition())
        uid = definition.get("cache_uid")
        return app_of(target), str(uid) if uid is not None else None, definition
    if isinstance(target, dict):
        return apps.current_app(), None, target
    raise TypeError(
        f"A target is a Qat definition such as {{'objectName': 'okButton'}} or a Qat object, "
        f"not {type(target).__name__}."
    )


def _ready_by_uid(app: App, uid: str) -> Ready | None:
    return _if_ready(Ready(app, uid, app.connection.properties(uid)))


def _ready_by_definition(app: App, definition: dict[str, Any]) -> Ready | None:
    uids = app.connection.find({**definition, "visible": True, "enabled": True})
    if len(uids) > 1:
        raise ambiguity(app, definition, uids)
    if not uids:
        return None
    try:
        properties = app.connection.properties(uids[0])
    except ObjectGoneError:
        return None  # destroyed since; look again
    return _if_ready(Ready(app, uids[0], properties))


def _if_ready(found: Ready) -> Ready | None:
    """The object if it can take input now, or None to wait. Fails for non-visual objects."""
    if not is_visual(found.properties):
        raise QatAgentHelpersError(
            f"{line_of(found.app, found.uid, found.properties)} is not a widget, Qt Quick item "
            "or window, so it cannot take input."
        )
    return found if _readiness(found.properties) is None else None


def _not_ready(
    app: App, uid: str | None, definition: dict[str, Any], timeout: float
) -> QatAgentHelpersError:
    """Why the target was not ready in time."""
    if uid is None:
        shown = definitions.python_literal(definition)
        uids = app.connection.find(definition)
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
        f"{line_of(app, uid, properties)} is still {problem} after {timeout:g} s. "
        + READY_ADVICE.get(problem, "")
    )


def _readiness(properties: dict[str, Any]) -> str | None:
    """Why the object cannot take input now, or None when it can."""
    if properties.get("visible") is not True:
        return "hidden"
    if properties.get("enabled") is False:
        return "disabled"
    return None


def line_of(app: App, uid: str, properties: dict[str, Any]) -> str:
    """The object's snapshot line, with its unique definition if it has one."""
    found = definitions.find_definition(app.connection, uid, properties)
    return describe(properties, found.definition if found.matches == 1 else None)


def _is_proxy(target: Any) -> bool:
    import qat

    return isinstance(target, qat.QtObject)


def _app_of_context(context: Any) -> App:
    for app in apps.open_apps():
        if app.context is context:
            return app
    # An app that Qat started or attached to by itself: the library only talks to it.
    from qat_agent_helpers.real_qat import RealAppConnection

    return App(RealAppConnection(context, None), launched=False, path=None)
