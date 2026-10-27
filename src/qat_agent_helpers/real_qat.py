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

from qat_agent_helpers import linux, macos
from qat_agent_helpers.adapter import Child, Proxy
from qat_agent_helpers.errors import AppGoneError, CommandError, LaunchError, ObjectGoneError

T = TypeVar("T")

EXPIRED_OBJECT = "May have expired in cache"
CONTAINER_NOT_ONE = (
    "No object found that matches this definition",
    "Multiple objects found that match this definition",
)

REQUEST_TIMEOUT_MS = 10_000
KILL_TIMEOUT = 5.0

# On macOS a Debug build connects too, as long as it loads Qt's release frameworks.
TARGET_REQUIREMENTS = (
    ("a build" if sys.platform == "darwin" else "a Release or RelWithDebInfo build")
    + " with dynamically linked Qt 5.15 or 6.2-6.12"
    + (", built with MSVC," if sys.platform == "win32" else "")
    + (", without the hardened runtime," if sys.platform == "darwin" else "")
    + " that shows a visible top-level window"
)


class RealQat:
    def launch(
        self, path: Path, args: list[str], env: dict[str, str], *, lock_ui: bool
    ) -> RealAppConnection:
        _load_test_settings()
        process_env = {**os.environ, **env}
        process_env.setdefault("TEMP", str(qat_environment.get_temp_folder()))
        if sys.platform == "darwin":
            server_dir = app_launcher.get_injector(path.parent).parent
            mismatch = macos.server_mismatch(path, server_dir)
            if mismatch is not None:
                raise LaunchError(mismatch)
        elif sys.platform.startswith("linux"):
            server_dir = app_launcher.get_injector(path.parent).parent
            missing = linux.missing_server(path, server_dir, process_env)
            if missing is not None:
                raise LaunchError(missing)
        context = ApplicationContext(path.stem, str(path))
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
        # The app's Qat server leaves its port in the app's TEMP, which env may set; a relative
        # one is relative to the app's working folder.
        port_file = qat_environment.create_qat_config_file_path(process.pid).name
        context.config_file = path.parent / process_env["TEMP"] / port_file

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

    def adopt(self, context: ApplicationContext) -> RealAppConnection:
        return RealAppConnection(context, None)

    def current_context(self) -> ApplicationContext | None:
        return qat.current_application_context()

    def make_current(self, context: ApplicationContext | None) -> None:
        qat.set_current_application_context(context)  # pyright: ignore[reportArgumentType]

    def proxy_of(self, target: Any) -> Proxy | None:
        if not isinstance(target, qat.QtObject):
            return None
        # QtObject resolves attributes remotely, so its context is read from __dict__.
        return Proxy(target.__dict__["_app_context"], dict(target.get_definition()))

    def wait_timeout(self) -> float:
        return Settings.wait_for_object_timeout / 1000


class RealAppConnection:
    def __init__(
        self, context: ApplicationContext, process: subprocess.Popen[bytes] | None
    ) -> None:
        self._context = context
        self._process = process

    @property
    def pid(self) -> int:
        return self._context.pid

    @property
    def context(self) -> ApplicationContext:
        return self._context

    def top_windows(self) -> list[str]:
        windows = self._call(lambda: qat_find.list_top_windows(self._context))
        return [_uid_of(window) for window in windows]

    def children(self, uid: str) -> list[Child]:
        children = cast(list[qat.QtObject], self._call(lambda: self._object(uid).children))
        return [
            Child(uid=_uid_of(child), has_children=bool(child.get_definition().get("children")))
            for child in children
        ]

    def properties(self, uid: str) -> dict[str, Any]:
        properties = self._call(lambda: self._object(uid).list_properties())
        return {name: _plain(value) for name, value in properties}

    def find(self, definition: dict[str, Any]) -> list[str]:
        try:
            matches = self._call(lambda: qat_find.find_all_objects(self._context, definition))
        except LookupError as error:
            container_refused = any(text in str(error) for text in CONTAINER_NOT_ONE)
            if isinstance(error, ObjectGoneError) or not container_refused:
                raise
            return []
        return [_uid_of(match) for match in matches]

    def parent(self, uid: str) -> str | None:
        try:
            parent = self._call(lambda: self._object(uid).parent)
        except AttributeError:
            return None
        if isinstance(parent, qat.QtObject) and not parent.is_null():
            return _uid_of(parent)
        # Qat gives a Qt Quick window's content item no parent, yet lists it among the
        # window's children, which is where a snapshot's walk meets it.
        for window in self.top_windows():
            if any(child.uid == uid for child in self.children(window)):
                return window
        return None

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
        # A press and a release rather than Qat's "click" (ADR 0001).
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
        self._barrier()

    def type_text(self, uid: str, text: str) -> bool:
        result = self._send(
            {"command": "keyboard", "object": {"cache_uid": uid}, "attribute": "type", "args": text}
        )
        return "warning" not in result

    def press_keys(self, uid: str, keys: str) -> None:
        self._send(
            {
                "command": "keyboard",
                "object": {"cache_uid": uid},
                "attribute": "shortcut",
                "args": keys,
                "blocking": False,
            }
        )
        self._barrier()

    def _barrier(self) -> None:
        """Return once the app has handled the input posted before: the request takes the same
        queued path to the GUI thread, even from a dialog's exec() (ADR 0001)."""
        self._send({"command": "list", "attribute": "versionInfo"})

    def quit(self) -> None:
        quit_call = {
            "command": "call",
            "object": qat.QApp,
            "attribute": "quit",
            "args": [],
            "blocking": False,
        }
        with suppress(ConnectionError, RuntimeError):
            self._context.send_command(quit_call, 3000, nb_trials=1)

    def wait_for_exit(self, timeout: float) -> int | None:
        if self._process is None:
            return None
        try:
            return self._process.wait(timeout)
        except subprocess.TimeoutExpired:
            return None

    def kill(self) -> None:
        self._context.kill()
        if self._process is not None:
            with suppress(subprocess.TimeoutExpired):
                self._process.wait(KILL_TIMEOUT)
        self._forget()

    def detach(self) -> None:
        try:
            self._context.detach()
        except ConnectionError:
            # Qat's detach() says goodbye to the app first, and when the app has exited it
            # raises before it stops its own server. It drops its client on the way, so a
            # second call gets past the goodbye.
            self._context.detach()
        finally:
            self._forget()

    def _forget(self) -> None:
        """Remove the app from Qat's list of apps, whose exit hook would otherwise kill it."""
        state = qat.get_state()
        if self._context in state.app_context_list:
            state.app_context_list.remove(self._context)

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
    if isinstance(value, qat.QtObject):
        return {"uid": _uid_of(value)}
    if isinstance(value, qat.QtCustomObject):
        return value.get_attribute_dict()
    return value


def _load_test_settings() -> None:
    if not Settings.loaded and Path("testSettings.json").is_file():
        load_test_settings()
