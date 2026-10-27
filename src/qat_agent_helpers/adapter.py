from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Child:
    uid: str
    has_children: bool


@dataclass(frozen=True)
class Proxy:
    context: Any
    definition: dict[str, Any]


class AppConnection(Protocol):
    """A connected app. Objects are addressed by Qat's cache_uid, here called uid.

    Object calls raise ObjectGoneError for a destroyed object and AppGoneError once the
    app has exited. Clicks and keys are posted and return once the app has handled them,
    so that a modal dialog cannot block them; typed text can only be sent blocking (ADR 0001).
    kill() and detach() leave Qat's current app as it is (ADR 0003).
    """

    @property
    def pid(self) -> int: ...

    @property
    def context(self) -> Any: ...

    def top_windows(self) -> list[str]: ...

    def children(self, uid: str) -> list[Child]: ...

    def properties(self, uid: str) -> dict[str, Any]: ...

    def find(self, definition: dict[str, Any]) -> list[str]: ...

    def parent(self, uid: str) -> str | None: ...

    def is_a(self, uid: str, type_name: str) -> bool: ...

    def click(
        self,
        uid: str,
        *,
        button: str = "left",
        double: bool = False,
        modifiers: tuple[str, ...] = (),
        x: int | None = None,
        y: int | None = None,
    ) -> None: ...

    def type_text(self, uid: str, text: str) -> bool: ...

    def press_keys(self, uid: str, keys: str) -> None: ...

    def quit(self) -> None: ...

    def wait_for_exit(self, timeout: float) -> int | None: ...

    def kill(self) -> None: ...

    def detach(self) -> None: ...


class QatAdapter(Protocol):
    def launch(
        self, path: Path, args: list[str], env: dict[str, str], *, lock_ui: bool
    ) -> AppConnection: ...

    def attach(self, pid: int) -> AppConnection: ...

    def adopt(self, context: Any) -> AppConnection: ...

    def current_context(self) -> Any | None: ...

    def make_current(self, context: Any | None) -> None: ...

    def proxy_of(self, target: Any) -> Proxy | None: ...

    def wait_timeout(self) -> float: ...
