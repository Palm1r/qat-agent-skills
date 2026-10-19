"""Apps: launching Qt processes or attaching to them, and closing or detaching them.

The newest app is Qat's current app, so that Qat's own functions, such as
qat.wait_for_object(), act on it right away. Launched apps still open when the script
ends are closed then.
"""

from __future__ import annotations

import atexit
import time
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import TracebackType
from typing import Any

from qat_agent_helpers.adapter import AppConnection, QatAdapter
from qat_agent_helpers.errors import QatAgentHelpersError

# How long close() gives an app to quit before it kills it.
QUIT_TIMEOUT = 5.0

_adapter: QatAdapter | None = None
_apps: list[App] = []


class App:
    """A running Qt app that the script controls through Qat, launched or attached."""

    def __init__(self, connection: AppConnection, *, launched: bool, path: Path | None) -> None:
        self._connection = connection
        self._launched = launched
        self._path = path
        self._exit_code: int | None = None
        self._done = False

    @property
    def context(self) -> Any:
        """Qat's ApplicationContext for this app, for direct Qat calls."""
        return self._connection.context

    @property
    def pid(self) -> int:
        return self._connection.pid

    @property
    def launched(self) -> bool:
        """True for an app that launch() started, False for one that attach() took over."""
        return self._launched

    @property
    def connection(self) -> AppConnection:
        return self._connection

    def close(self, timeout: float = QUIT_TIMEOUT) -> int | None:
        """Ask a launched app to quit, and kill it if it still runs after `timeout` seconds.

        Returns its exit code. Closing a closed app does nothing.
        """
        if not self._launched:
            raise QatAgentHelpersError(
                f"{self} was attached, so qat-agent-helpers never closes it; call detach() instead."
            )
        if not self._done:
            _close_apps([self], timeout)
        return self._exit_code

    def detach(self) -> None:
        """Release an attached app and leave it running."""
        if self._launched:
            raise QatAgentHelpersError(
                f"{self} was launched by qat-agent-helpers; call close() instead."
            )
        if not self._done:
            self._connection.detach()
            _forget(self)

    def __enter__(self) -> App:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._launched:
            self.close()
        else:
            self.detach()

    def __repr__(self) -> str:
        how = "launched" if self._launched else "attached"
        where = f" {self._path}" if self._path else ""
        return f"<qat_agent_helpers.App pid {self.pid}, {how}{where}>"


def launch(
    path: str | Path,
    args: Iterable[str] = (),
    env: Mapping[str, str] | None = None,
    lock_ui: bool = False,
) -> App:
    """Start an app with Qat injected and wait until it is connected (ADR 0002).

    `env` adds variables for this app only. `lock_ui` lets Qat block user input to it.
    No applications.json is written, and the app is launched once, without retries.
    """
    executable = Path(path).expanduser().resolve()
    if not executable.is_file():
        raise FileNotFoundError(
            f"No executable at {executable}. Pass the full path to the app's executable."
        )
    connection = _qat().launch(executable, list(args), dict(env or {}), lock_ui=lock_ui)
    return _remember(App(connection, launched=True, path=executable))


def attach(pid: int) -> App:
    """Take over a running Qt process.

    On Windows any suitable process works; on Linux and macOS, only one that Qat launched.
    """
    return _remember(App(_qat().attach(pid), launched=False, path=None))


def current_app() -> App:
    """The newest app that is still open."""
    if not _apps:
        raise QatAgentHelpersError(
            "No app is open: launch one with qat_agent_helpers.launch() or attach with "
            "qat_agent_helpers.attach()."
        )
    return _apps[-1]


def open_apps() -> list[App]:
    """The apps launched or attached to and not yet closed or detached, oldest first."""
    return list(_apps)


def close_all() -> None:
    """Close every launched app that is still open, and detach every attached one."""
    open_apps = list(reversed(_apps))
    _close_apps([app for app in open_apps if app.launched], QUIT_TIMEOUT)
    for app in open_apps:
        if not app.launched:
            app.detach()


def _remember(app: App) -> App:
    _apps.append(app)
    app.connection.make_current()
    return app


def _forget(app: App) -> None:
    app._done = True
    if app in _apps:
        _apps.remove(app)
        if _apps:
            _apps[-1].connection.make_current()


def _close_apps(closing: list[App], timeout: float) -> None:
    """Ask every app to quit at once, then kill those still running after `timeout` seconds."""
    for app in closing:
        app.connection.quit()
    deadline = time.monotonic() + timeout
    for app in closing:
        exit_code = app.connection.wait_for_exit(max(0.0, deadline - time.monotonic()))
        app.connection.kill()  # also frees Qat's side of the connection
        app._exit_code = exit_code if exit_code is not None else app.connection.wait_for_exit(0)
        _forget(app)


def _qat() -> QatAdapter:
    # Created on first use. The exit hook is registered after qat's own, so that it runs
    # first and lets the apps quit before Qat's hook kills them.
    global _adapter
    if _adapter is None:
        from qat_agent_helpers.real_qat import RealQat

        _adapter = RealQat()
        atexit.register(close_all)
    return _adapter
