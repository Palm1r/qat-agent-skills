from __future__ import annotations

import atexit
import time
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import TracebackType
from typing import Any

from qat_agent_helpers import macos
from qat_agent_helpers.adapter import AppConnection, QatAdapter
from qat_agent_helpers.errors import QatAgentHelpersError

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
            self._mark_closed()
            _release([self])

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

    def _mark_closed(self, exit_code: int | None = None) -> None:
        self._done = True
        self._exit_code = exit_code

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

    `path` is the app's executable or, on macOS, its .app bundle. `env` adds variables for
    this app only. `lock_ui` lets Qat block user input to it. No applications.json is
    written, and the app is launched once, without retries.
    """
    executable = Path(path).expanduser().resolve()
    if executable.suffix == ".app" and executable.is_dir():
        bundle, executable = executable, macos.bundle_executable(executable)
        if not executable.is_file():
            raise FileNotFoundError(
                f"The app bundle {bundle} has no executable at {executable}. Pass the full "
                f"path to the app's executable instead, from {bundle.name}/Contents/MacOS/."
            )
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
    context = adapter().current_context()
    if context is not None:
        return app_of_context(context)
    if not _apps:
        raise QatAgentHelpersError(
            "No app is open: launch one with qat_agent_helpers.launch() or attach with "
            "qat_agent_helpers.attach()."
        )
    count = len(_apps)
    raise QatAgentHelpersError(
        f"No app is current, but {count} {'is' if count == 1 else 'are'} open: "
        + ", ".join(repr(app) for app in _apps)
        + ". Make one current with qat.set_current_application_context(app.context), or launch "
        "or attach another with qat_agent_helpers."
    )


def app_of_context(context: Any) -> App:
    for app in _apps:
        if app.context is context:
            return app
    return App(adapter().adopt(context), launched=False, path=None)


def open_apps() -> list[App]:
    return list(_apps)


def close_all() -> None:
    open_apps = list(reversed(_apps))
    _close_apps([app for app in open_apps if app.launched], QUIT_TIMEOUT)
    for app in open_apps:
        if not app.launched:
            app.detach()


def _remember(app: App) -> App:
    _apps.append(app)
    adapter().make_current(app.context)
    return app


def _release(released: list[App]) -> None:
    current = adapter().current_context()
    was_current = any(app.context is current for app in released)
    for app in released:
        if app in _apps:
            _apps.remove(app)
    if was_current:
        adapter().make_current(_apps[-1].context if _apps else None)


def _close_apps(closing: list[App], timeout: float) -> None:
    for app in closing:
        app.connection.quit()
    deadline = time.monotonic() + timeout
    for app in closing:
        exit_code = app.connection.wait_for_exit(max(0.0, deadline - time.monotonic()))
        app.connection.kill()
        app._mark_closed(exit_code if exit_code is not None else app.connection.wait_for_exit(0))
    _release(closing)


def adapter() -> QatAdapter:
    return _qat()


def _qat() -> QatAdapter:
    # The exit hook is registered after qat's own, so that it runs first and lets the apps
    # quit before Qat's hook kills them.
    global _adapter
    if _adapter is None:
        from qat_agent_helpers.real_qat import RealQat

        _adapter = RealQat()
        atexit.register(close_all)
    return _adapter
