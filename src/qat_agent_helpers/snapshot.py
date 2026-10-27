from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from qat_agent_helpers import apps, definitions, targets
from qat_agent_helpers.adapter import AppConnection
from qat_agent_helpers.describe import describe, is_visual
from qat_agent_helpers.errors import ObjectGoneError

# About 8k tokens: Codex cuts text results over 10k tokens, Claude Code warns at 10k.
BUDGET_CHARS = 24_000
CUT_NOTE = "...cut here, at about 8k tokens; narrow with a target or depth to see more objects."

INTERNAL_NAMES = frozenset({"qt_scrollarea_hcontainer", "qt_scrollarea_vcontainer"})


@dataclass(frozen=True)
class Visited:
    level: int
    uid: str
    properties: dict[str, Any]


def snapshot(
    target: Any = None,
    depth: int | None = None,
    include_hidden: bool = False,
    include_internal: bool = False,
) -> str:
    """The object tree below `target` as text, or every top-level window of the current app.

    `target` is a Qat definition or a Qat object; it is shown whatever it is. `depth` is
    the number of levels shown below it, and `include_hidden` keeps hidden objects too.
    `include_internal` keeps the containers of Qt's scroll bars, which are left out.
    """
    if target is None:
        app = apps.current_app()
        roots, explicit = app.connection.top_windows(), False
    else:
        app, uid = targets.uid_of(target)
        roots, explicit = [uid], True
    objects = walk(
        app.connection,
        roots,
        depth=depth,
        include_hidden=include_hidden,
        include_internal=include_internal,
        explicit=explicit,
    )
    return render(app.connection, objects)


def walk(
    connection: AppConnection,
    roots: list[str],
    *,
    depth: int | None = None,
    include_hidden: bool = False,
    include_internal: bool = False,
    explicit: bool = False,
) -> Iterator[Visited]:
    seen: set[str] = set()

    def visit(uid: str, level: int, has_children: bool) -> Iterator[Visited]:
        if uid in seen:
            return
        seen.add(uid)
        is_root = level == 0
        try:
            properties = connection.properties(uid)
        except ObjectGoneError:
            if is_root and explicit:
                raise
            return
        if not (is_root and explicit):
            if not is_visual(properties):
                return
            if properties.get("visible") is not True and not include_hidden:
                return
            if properties.get("objectName") in INTERNAL_NAMES and not include_internal:
                return
        yield Visited(level, uid, properties)
        if has_children and (depth is None or level < depth):
            for child in connection.children(uid):
                yield from visit(child.uid, level + 1, child.has_children)

    for uid in roots:
        yield from visit(uid, level=0, has_children=True)


def render(connection: AppConnection, objects: Iterator[Visited]) -> str:
    lines: list[str] = []
    size = 0
    tree = definitions.TreeDefinitions(connection)
    for found in objects:
        unique = tree.at(found.level, found.uid, found.properties)
        line = "  " * found.level + "- " + describe(found.properties, unique)
        size += len(line) + 1
        if size > BUDGET_CHARS - len(CUT_NOTE) - 1:
            lines.append(CUT_NOTE)
            break
        lines.append(line)
    return "\n".join(lines)
