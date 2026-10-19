"""Snapshots: a compact text view of part of an app's object tree, one line per object.

    - MainWindow #mainWindow "Demo Widgets" def={"objectName": "mainWindow", "type": "MainWindow"}
      - QPushButton #incrementButton "Increment" def={"objectName": "incrementButton", ...}

Non-visual QObjects are left out, and so are hidden objects and the containers of Qt's
scroll bars unless asked for. Each line ends with the object's definition when a unique
one exists, ready to paste into a script.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from qat_agent_helpers import definitions, targets
from qat_agent_helpers.adapter import AppConnection
from qat_agent_helpers.describe import describe, is_visual
from qat_agent_helpers.errors import ObjectGoneError

# About 8k tokens at roughly three characters per token: Codex cuts the middle out of
# text results over 10k tokens, and Claude Code warns at 10k.
BUDGET_CHARS = 24_000
NOTE_ROOM = 100

# The containers Qt puts a scroll area's scroll bars in. They never hold the app's own
# objects, unlike the other objects Qt names qt_..., such as a scroll area's viewport, a
# tab widget's page stack or a message box's text and buttons, which agents need.
INTERNAL_NAMES = frozenset({"qt_scrollarea_hcontainer", "qt_scrollarea_vcontainer"})


@dataclass
class Node:
    uid: str
    properties: dict[str, Any]
    children: list[Node] = field(default_factory=list)


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
        app = targets.app_of(None)
        roots, explicit = app.connection.top_windows(), False
    else:
        app, uid = targets.uid_of(target)
        roots, explicit = [uid], True
    nodes = collect(
        app.connection,
        roots,
        depth=depth,
        include_hidden=include_hidden,
        include_internal=include_internal,
        explicit=explicit,
    )
    return render(app.connection, nodes)


def collect(
    connection: AppConnection,
    roots: list[str],
    *,
    depth: int | None = None,
    include_hidden: bool = False,
    include_internal: bool = False,
    explicit: bool = False,
) -> list[Node]:
    """Walk the object tree below `roots`, keeping visual objects that are visible.

    Scroll-bar containers are left out with their scroll bars unless `include_internal`.
    With `explicit` the roots are kept whatever they are. Qat lists an object's children as
    the union of QObject children, QML child items and widgets managed by a layout, so one
    object can turn up under two parents; it is kept once, where the walk meets it first.
    """
    seen: set[str] = set()

    def visit(uid: str, level: int, has_children: bool) -> Node | None:
        if uid in seen:
            return None
        seen.add(uid)
        is_root = level == 0
        try:
            properties = connection.properties(uid)
        except ObjectGoneError:
            if is_root and explicit:
                raise
            return None  # destroyed while the walk was under way
        if not (is_root and explicit):
            if not is_visual(properties):
                return None
            if properties.get("visible") is not True and not include_hidden:
                return None
            if properties.get("objectName") in INTERNAL_NAMES and not include_internal:
                return None
        node = Node(uid, properties)
        if has_children and (depth is None or level < depth):
            for child in connection.children(uid):
                child_node = visit(child.uid, level + 1, child.has_children)
                if child_node is not None:
                    node.children.append(child_node)
        return node

    nodes = [visit(uid, level=0, has_children=True) for uid in roots]
    return [node for node in nodes if node is not None]


def render(connection: AppConnection, nodes: list[Node]) -> str:
    """The snapshot text, cut to the size budget with a note on what was left out.

    Definitions are found line by line, only for the lines that fit.
    """
    total = sum(1 for _ in _walk(nodes, 0))
    kept: list[str] = []
    size = 0
    for line in _lines(connection, nodes, indent=0, container=None):
        size += len(line) + 1
        if size > BUDGET_CHARS - NOTE_ROOM:
            kept.append(
                f"{total - len(kept)} more objects not shown; narrow with a target or depth."
            )
            break
        kept.append(line)
    return "\n".join(kept)


def _lines(
    connection: AppConnection,
    nodes: list[Node],
    indent: int,
    container: dict[str, Any] | None,
) -> Iterator[str]:
    """The lines in tree order; `container` is the nearest ancestor's unique definition."""
    for node in nodes:
        unique = definitions.unique_definition(connection, node.uid, node.properties, container)
        yield "  " * indent + "- " + describe(node.properties, unique)
        yield from _lines(connection, node.children, indent + 1, unique or container)


def _walk(nodes: list[Node], indent: int) -> Iterator[Node]:
    for node in nodes:
        yield node
        yield from _walk(node.children, indent + 1)
