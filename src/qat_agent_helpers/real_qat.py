"""The Qat adapter backed by the qat package (1.8.1).

It is written against the Qat 1.8.1 source rather than its documentation, and it uses
Qat internals where the public API falls short (ADR 0002). It leaves Qat's settings to
the script and to its testSettings.json.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any, TypeVar, cast

import qat
from qat.internal import app_launcher, debug_operations, qat_environment
from qat.internal import find_object as qat_find
from qat.internal.application_context import ApplicationContext
from qat.test_settings import Settings, load_test_settings

from qat_agent_helpers.adapter import Child
from qat_agent_helpers.errors import AppGoneError, CommandError, LaunchError, ObjectGoneError

T = TypeVar("T")

# What Qat says when a cache_uid no longer names a live object.
EXPIRED_OBJECT = "May have expired in cache"

# How long an input command or a barrier may take, and how long a killed app may take
# to go away.
REQUEST_TIMEOUT_MS = 10_000
KILL_TIMEOUT = 5.0

TARGET_REQUIREMENTS = (
    "a Release or RelWithDebInfo build with dynamically linked Qt 5.15 or 6.2-6.11"
    + (", built with MSVC," if sys.platform == "win32" else "")
    + " that shows a visible top-level window"
)


class RealQat:
    def launch(
        self, path: Path, args: list[str], env: dict[str, str], *, lock_ui: bool
    ) -> RealAppConnection:
        # Qat's start_application() reads the environment only from os.environ, does not
        # quote the executable path on Windows, needs a registry entry and launches twice
        # on failure, so the library starts the process itself and reuses Qat's injection and
        # connection steps.
        _load_test_settings()
        context = ApplicationContext(path.stem, str(path))
        process_env = {**os.environ, **env}
        process_env.setdefault("TEMP", str(qat_environment.get_temp_folder()))
        if sys.platform.startswith("linux"):
            process_env["LD_PRELOAD"] = str(app_launcher.get_injector(path.parent))
        elif sys.platform == "darwin":
            process_env["DYLD_INSERT_LIBRARIES"] = str(app_launcher.get_injector(path.parent))

        try:
            process = subprocess.Popen(
                [str(path), *args], cwd=path.parent, env=process_env, stdin=subprocess.DEVNULL
            )
        except OSError as error:
            context.detach()
            raise LaunchError(f"Could not start {path}: {error.strerror or error}.") from error
        # What ApplicationContext.launch() would have set.
        context._internal.process = process  # pyright: ignore[reportAttributeAccessIssue]
        context._internal.has_ownership = True
        context.pid = process.pid

        try:
            if sys.platform == "win32":
                app_launcher.inject_dll(context)
            app_launcher.connect_to(context)
            if lock_ui:
                debug_operations.lock_application(context)
        except Exception as error:
            exit_code = process.poll()
            context.kill()
            if exit_code is not None:
                message = f"{path.name} exited with code {exit_code} before Qat could connect."
            else:
                message = f"Qat could not connect to {path.name} ({error}), so it was stopped."
            raise LaunchError(f"{message} The app must be {TARGET_REQUIREMENTS}.") from error

        # Qat's own exit hook kills the apps in its global state if the script dies abruptly.
        qat.get_state().app_context_list.append(context)
        return RealAppConnection(context, process)

    def attach(self, pid: int) -> RealAppConnection:
        # Qat's attach_to_application() also takes names, matched as substrings of command
        # lines; the library attaches by pid only, with the same injection and connection steps.
        _load_test_settings()
        if not app_launcher.can_attach(pid):
            raise LaunchError(
                f"Qat can attach to pid {pid} only if Qat launched it: on Linux and macOS, "
                "start the app with qat_agent_helpers.launch() instead."
            )
        context = ApplicationContext(f"pid {pid}", str(Path.cwd()))
        context.pid = pid
        try:
            if sys.platform == "win32":
                app_launcher.inject_dll(context)
            app_launcher.connect_to(context)
        except Exception as error:
            context.detach()
            raise LaunchError(
                f"Could not attach to pid {pid} ({error}). The app must be {TARGET_REQUIREMENTS}."
            ) from error
        qat.get_state().app_context_list.append(context)
        return RealAppConnection(context, None)


class RealAppConnection:
    def __init__(
        self, context: ApplicationContext, process: subprocess.Popen[bytes] | None
    ) -> None:
        self._context = context
        self._process = process  # None for an attached app

    @property
    def pid(self) -> int:
        return self._context.pid

    @property
    def context(self) -> ApplicationContext:
        return self._context

    def make_current(self) -> None:
        qat.set_current_application_context(self._context)

    def top_windows(self) -> list[str]:
        windows = self._call(lambda: qat_find.list_top_windows(self._context))
        return [_uid_of(window) for window in windows]

    def children(self, uid: str) -> list[Child]:
        # QtObject.__getattr__ answers a `children` request with a list of QtObjects.
        children = cast(list[qat.QtObject], self._call(lambda: self._object(uid).children))
        return [
            Child(uid=_uid_of(child), has_children=bool(child.get_definition().get("children")))
            for child in children
        ]

    def properties(self, uid: str) -> dict[str, Any]:
        properties = self._call(lambda: self._object(uid).list_properties())
        return {name: _plain(value) for name, value in properties}

    def find(self, definition: dict[str, Any]) -> list[str]:
        matches = self._call(lambda: qat_find.find_all_objects(self._context, definition))
        return [_uid_of(match) for match in matches]

    def parent(self, uid: str) -> str | None:
        # Qat answers `parent` for widgets, Qt Quick items and windows, as an object.
        try:
            parent = self._call(lambda: self._object(uid).parent)
        except AttributeError:
            return None
        if not isinstance(parent, qat.QtObject) or parent.is_null():
            return None
        return _uid_of(parent)

    def is_a(self, uid: str, type_name: str) -> bool:
        return bool(self._call(lambda: self._object(uid).is_a(type_name)))

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
        # What qat.mouse_press() and qat.mouse_release() send, minus their pre-flight wait,
        # which skips the visible and enabled check for objects addressed by uid. A single
        # non-blocking "click" does not reach Qt Quick buttons on macOS (ADR 0001), so a
        # click is sent as a press and a release. Qat reads the modifiers as a list.
        args: dict[str, Any] = {
            "button": button,
            "modifier": list(modifiers) or "none",
            "blocking": False,
        }
        if x is not None and y is not None:
            args["x"], args["y"] = x, y
        for mode in ("double-click",) if double else ("press", "release"):
            self._send(
                {"command": "mouse", "object": {"cache_uid": uid}, "attribute": mode, "args": args}
            )

    def type_text(self, uid: str, text: str) -> bool:
        # What qat.type_in() sends. Qat focuses the object first and warns when no widget
        # accepted the keys.
        result = self._send(
            {"command": "keyboard", "object": {"cache_uid": uid}, "attribute": "type", "args": text}
        )
        return "warning" not in result

    def press_keys(self, uid: str, keys: str) -> None:
        # What qat.shortcut() sends; unlike the mouse, it takes `blocking` at the top level.
        self._send(
            {
                "command": "keyboard",
                "object": {"cache_uid": uid},
                "attribute": "shortcut",
                "args": keys,
                "blocking": False,
            }
        )

    def barrier(self) -> None:
        # No object lookup, and the same queued path to the GUI thread as posted input.
        self._send({"command": "list", "attribute": "versionInfo"})

    def quit(self) -> None:
        # Qat itself only kills apps. The call is sent once, as every state-changing command
        # is: the client's retries would re-send it while the app shuts down (ADR 0001).
        quit_call = {
            "command": "call",
            "object": qat.QApp,
            "attribute": "quit",
            "args": [],
            "blocking": False,
        }
        # An app that is already gone is left to wait_for_exit() and kill().
        with suppress(ConnectionError, RuntimeError):
            self._context.send_command(quit_call, 3000, nb_trials=1)

    def wait_for_exit(self, timeout: float) -> int | None:
        if self._process is None:
            return None  # an attached app's exit code is not ours to see
        try:
            return self._process.wait(timeout)
        except subprocess.TimeoutExpired:
            return None

    def kill(self) -> None:
        # Also stops Qat's callback server and removes the app's port file.
        self._context.kill()
        if self._process is not None:
            with suppress(subprocess.TimeoutExpired):
                self._process.wait(KILL_TIMEOUT)
        self._forget()

    def detach(self) -> None:
        self._context.detach()
        self._forget()

    def _forget(self) -> None:
        """Remove the app from Qat's global state, which would otherwise kill it at exit."""
        state = qat.get_state()
        if self._context in state.app_context_list:
            state.app_context_list.remove(self._context)
        if state.current_app_context is self._context:
            state.current_app_context = None

    def _object(self, uid: str) -> qat.QtObject:
        return qat.QtObject(self._context, {"cache_uid": uid})

    def _send(self, command: dict[str, Any]) -> dict[str, Any]:
        """Send a command once: the client's retries would run a click or a key twice."""
        try:
            return self._call(
                lambda: self._context.send_command(command, REQUEST_TIMEOUT_MS, nb_trials=1)
            )
        except (RuntimeError, LookupError) as error:
            raise CommandError(str(error)) from error

    def _call(self, request: Callable[[], T]) -> T:
        """Send a request, translating Qat's errors for dead objects and dead apps."""
        # QtObject silently switches to Qat's "current" app when its own app is gone.
        if not self._context.is_running():
            raise AppGoneError(f"The app with pid {self.pid} is no longer running.")
        try:
            return request()
        except Exception as error:
            if not self._context.is_running():
                raise AppGoneError(f"The app with pid {self.pid} is no longer running.") from error
            if EXPIRED_OBJECT in str(error):
                raise ObjectGoneError(str(error)) from error
            raise


def _uid_of(qt_object: qat.QtObject) -> str:
    return str(qt_object.get_definition()["cache_uid"])


def _plain(value: Any) -> Any:
    """A property value as plain data: object references become their uid."""
    if isinstance(value, qat.QtObject):
        return {"uid": _uid_of(value)}
    if isinstance(value, qat.QtCustomObject):
        return value.get_attribute_dict()
    return value


def _load_test_settings() -> None:
    """Read testSettings.json as Qat itself does, without Qat's notice when there is none."""
    if not Settings.loaded and Path("testSettings.json").is_file():
        load_test_settings()
