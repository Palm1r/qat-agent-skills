"""The seam between this library and Qat: what it needs from Qat, in its own terms.

RealQat implements it with the qat package, and the unit tests use a fake.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Child:
    uid: str
    has_children: bool


class AppConnection(Protocol):
    """A connected app. Objects are addressed by Qat's cache_uid, here called uid.

    Object calls raise ObjectGoneError for a destroyed object and AppGoneError once the
    app has exited.
    """

    @property
    def pid(self) -> int: ...

    @property
    def context(self) -> Any:
        """Qat's ApplicationContext for the app, for direct Qat calls."""
        ...

    def make_current(self) -> None:
        """Make the app Qat's current app, which Qat's own functions act on."""
        ...

    def top_windows(self) -> list[str]:
        """The uids of the app's top-level windows."""
        ...

    def children(self, uid: str) -> list[Child]: ...

    def properties(self, uid: str) -> dict[str, Any]:
        """Every property with its value, plus Qat's synthetic `type` and `id` (the QML id)."""
        ...

    def find(self, definition: dict[str, Any]) -> list[str]:
        """The uids of every object that matches a Qat definition."""
        ...

    def parent(self, uid: str) -> str | None:
        """The uid of the object's parent, or None for a top-level object."""
        ...

    def is_a(self, uid: str, type_name: str) -> bool:
        """Whether the object is of the given class or inherits from it."""
        ...

    def click(
        self,
        uid: str,
        *,
        button: str = "left",
        double: bool = False,
        modifiers: tuple[str, ...] = (),
        x: int | None = None,
        y: int | None = None,
    ) -> None:
        """Post a click to the object, without waiting for the app to handle it (ADR 0001).

        `x` and `y` are relative to the object; without them the click hits its centre.
        """
        ...

    def type_text(self, uid: str, text: str) -> bool:
        """Type ASCII text into the object and wait until the app has handled it.

        Returns False when no widget accepted the keys. Qat has no non-blocking way to
        type text (ADR 0001).
        """
        ...

    def press_keys(self, uid: str, keys: str) -> None:
        """Post a key or a shortcut such as Return or Ctrl+S to the object, without waiting.

        `keys` is in QKeySequence's format.
        """
        ...

    def barrier(self) -> None:
        """Return once the app has handled the input posted before this call."""
        ...

    def quit(self) -> None:
        """Ask the app to quit, without waiting. Does nothing if it has already exited."""
        ...

    def wait_for_exit(self, timeout: float) -> int | None:
        """The exit code, or None if the app is still running after `timeout` seconds."""
        ...

    def kill(self) -> None:
        """Kill the app if it is still running and drop the connection to it."""
        ...

    def detach(self) -> None:
        """Drop the connection to the app and leave it running."""
        ...


class QatAdapter(Protocol):
    def launch(
        self, path: Path, args: list[str], env: dict[str, str], *, lock_ui: bool
    ) -> AppConnection:
        """Start the executable with Qat injected and wait until it connects."""
        ...

    def attach(self, pid: int) -> AppConnection:
        """Take over a running Qt process and wait until it connects."""
        ...
