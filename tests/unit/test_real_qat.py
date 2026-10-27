from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import qat
from qat.internal import app_launcher, tcp_server
from qat.internal.application_context import ApplicationContext

from qat_agent_helpers import real_qat
from qat_agent_helpers.errors import LaunchError
from qat_agent_helpers.real_qat import RealAppConnection, RealQat
from tests.unit.mach_o import ARM64, QT5_CORE, X86_64, thin


def test_on_macos_an_app_qats_server_cannot_load_into_is_refused_before_it_is_launched(
    tmp_path, monkeypatch
):
    server_dir = tmp_path / "qat-bin"
    server_dir.mkdir()
    (server_dir / "libQatServer.5.15.dylib").write_bytes(thin(X86_64))
    app = tmp_path / "demo"
    app.write_bytes(thin(ARM64, (QT5_CORE, "5.15.19")))

    def must_not_be_called(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("the app must not be launched")

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    monkeypatch.setattr(app_launcher, "get_injector", lambda _: server_dir / "libinjector.dylib")
    monkeypatch.setattr(real_qat, "ApplicationContext", must_not_be_called)
    monkeypatch.setattr(subprocess, "Popen", must_not_be_called)

    with pytest.raises(LaunchError, match=r"^demo runs as arm64, .* x86_64 only"):
        RealQat().launch(app, [], {}, lock_ui=False)


def test_on_linux_an_app_on_a_qt_qat_has_no_server_for_is_refused_before_it_is_launched(
    tmp_path, monkeypatch
):
    server_dir = tmp_path / "qat-bin"
    server_dir.mkdir()
    (server_dir / "libQatServer.6.11.so").write_bytes(b"")
    qt_core = tmp_path / "libQt6Core.so.6.12.0"
    qt_core.write_bytes(b"")
    app = tmp_path / "demo"
    ldd_envs: list[dict[str, str]] = []

    def ldd(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        ldd_envs.append(kwargs["env"])
        output = f"\tlibQt6Core.so.6 => {qt_core} (0x00007f8194600000)\n"
        return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")

    def must_not_be_called(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("the app must not be launched")

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(app_launcher, "get_injector", lambda _: server_dir / "libinjector.so")
    monkeypatch.setattr(subprocess, "run", ldd)
    monkeypatch.setattr(real_qat, "ApplicationContext", must_not_be_called)
    monkeypatch.setattr(subprocess, "Popen", must_not_be_called)

    with pytest.raises(LaunchError, match=r"^demo loads Qt 6\.12 from .* only for Qt 6\.11,"):
        RealQat().launch(app, [], {"LD_LIBRARY_PATH": "/opt/qt"}, lock_ui=False)
    assert ldd_envs[0]["LD_LIBRARY_PATH"] == "/opt/qt"
    assert "libinjector" not in ldd_envs[0].get("LD_PRELOAD", "")


class SocketlessServer:
    """Qat's server for an app's callbacks, without its socket."""

    def __init__(self, context: Any) -> None:
        self.stopped = False

    def start(self) -> None:
        pass

    def stop(self) -> None:
        self.stopped = True


@pytest.fixture
def qat_state(monkeypatch) -> SimpleNamespace:
    """Qat's global list of apps, empty, with app contexts that open no socket."""
    state = SimpleNamespace(app_context_list=[])
    monkeypatch.setattr(qat, "get_state", lambda: state)
    monkeypatch.setattr(tcp_server, "TcpServer", SocketlessServer)
    return state


@pytest.mark.parametrize("app_temp", [None, "app-temp"])
def test_the_app_is_reached_through_the_temp_folder_it_runs_with(
    app_temp, tmp_path, monkeypatch, qat_state
):
    app = tmp_path / "demo.exe"
    app.write_bytes(b"")
    app_envs: list[dict[str, str]] = []
    port_files: list[Path] = []

    def popen(args: list[str], **options: Any) -> SimpleNamespace:
        app_envs.append(options["env"])
        return SimpleNamespace(pid=4321, poll=lambda: None)

    monkeypatch.setenv("TEMP", str(tmp_path / "script-temp"))
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(app_launcher, "inject_dll", lambda context: None)
    monkeypatch.setattr(
        app_launcher, "connect_to", lambda context: port_files.append(Path(context.config_file))
    )
    env = {} if app_temp is None else {"TEMP": str(tmp_path / app_temp)}

    RealQat().launch(app, [], env, lock_ui=False)

    temp = tmp_path / (app_temp or "script-temp")
    assert app_envs[0]["TEMP"] == str(temp)
    assert port_files == [temp / "qat-4321.txt"]


class FakeContext:
    pid = 4321

    def __init__(self) -> None:
        self.sent: list[tuple[dict[str, Any], int]] = []
        self.refusal: str | None = None
        self.answers: dict[tuple[str, str, str | None], dict[str, Any]] = {}

    def is_running(self) -> bool:
        return True

    def send_command(
        self, command: dict[str, Any], timeout: int | None = None, nb_trials: int = 3
    ) -> dict:
        self.sent.append((command, nb_trials))
        if self.refusal is not None and command["command"] in ("find", "list"):
            raise LookupError(self.refusal)
        target = command.get("object")
        uid = target.get("cache_uid") if isinstance(target, dict) else None
        return self.answers.get((command["command"], command["attribute"], uid), {})


def connect() -> tuple[RealAppConnection, FakeContext]:
    context = FakeContext()
    return RealAppConnection(context, None), context  # pyright: ignore[reportArgumentType]


def mouse_commands(context: FakeContext) -> list[tuple[str, dict[str, Any]]]:
    return [
        (command["attribute"], command["args"])
        for command, _ in context.sent
        if command["command"] == "mouse"
    ]


def wire(context: FakeContext) -> list[tuple[str, str, int]]:
    return [(command["command"], command["attribute"], trials) for command, trials in context.sent]


def test_a_click_is_a_press_then_a_release_neither_of_them_blocking():
    connection, context = connect()

    connection.click("7")

    assert mouse_commands(context) == [
        ("press", {"button": "left", "modifier": "none", "blocking": False}),
        ("release", {"button": "left", "modifier": "none", "blocking": False}),
    ]
    mouse = [command for command, _ in context.sent if command["command"] == "mouse"]
    assert all(command["object"] == {"cache_uid": "7"} for command in mouse)


def test_the_press_and_the_release_carry_the_button_modifiers_and_position():
    connection, context = connect()

    connection.click("7", button="right", modifiers=("ctrl", "shift"), x=3, y=4)

    args = {"button": "right", "modifier": ["ctrl", "shift"], "blocking": False, "x": 3, "y": 4}
    assert mouse_commands(context) == [("press", args), ("release", args)]


def test_a_click_returns_after_a_barrier_and_sends_each_command_once():
    connection, context = connect()

    connection.click("7")

    assert wire(context) == [
        ("mouse", "press", 1),
        ("mouse", "release", 1),
        ("list", "versionInfo", 1),
    ]


def test_a_double_click_is_followed_by_a_barrier_too():
    connection, context = connect()

    connection.click("7", double=True)

    assert wire(context) == [("mouse", "double-click", 1), ("list", "versionInfo", 1)]


def test_keys_are_posted_without_blocking_and_followed_by_a_barrier():
    connection, context = connect()

    connection.press_keys("7", "Ctrl+S")

    assert wire(context) == [("keyboard", "shortcut", 1), ("list", "versionInfo", 1)]
    shortcut = context.sent[0][0]
    assert (shortcut["args"], shortcut["blocking"]) == ("Ctrl+S", False)


def test_a_double_click_stays_one_double_click_command():
    connection, context = connect()

    connection.click("7", double=True)

    assert mouse_commands(context) == [
        ("double-click", {"button": "left", "modifier": "none", "blocking": False}),
    ]


@pytest.mark.parametrize(
    "refusal",
    [
        "Unable to find object: {...}\nNo object found that matches this definition",
        "Unable to find object: {...}\nMultiple objects found that match this definition",
    ],
)
def test_a_lookup_whose_container_is_not_exactly_one_object_finds_nothing(refusal):
    connection, context = connect()
    context.refusal = refusal

    found = connection.find({"type": "QPushButton", "container": {"objectName": "openDialog"}})

    assert found == []


def test_other_refused_lookups_still_raise():
    connection, context = connect()
    context.refusal = "Invalid definition"

    with pytest.raises(LookupError, match="Invalid definition"):
        connection.find({"type": "QPushButton"})


def window_with_content_item(context: FakeContext) -> None:
    context.answers = {
        ("get", "parent", "10"): {"object": {"cache_uid": 0}},  # a null object
        ("get", "parent", "11"): {"object": {"cache_uid": 0}},
        ("list", "topWindows", None): {"object": [{"cache_uid": "10"}]},
        ("get", "children", "10"): {"children": [{"cache_uid": "11"}]},
    }


def test_a_qt_quick_windows_content_item_has_the_window_as_its_parent():
    connection, context = connect()
    window_with_content_item(context)

    assert connection.parent("11") == "10"


def test_a_top_level_window_has_no_parent():
    connection, context = connect()
    window_with_content_item(context)

    assert connection.parent("10") is None


def test_a_parent_qat_reports_is_taken_without_looking_at_the_windows():
    connection, context = connect()
    context.answers = {("get", "parent", "12"): {"object": {"cache_uid": "11"}}}

    assert connection.parent("12") == "11"
    assert [command["attribute"] for command, _ in context.sent] == ["parent"]


class ClientOfAnExitedApp:
    def is_connected(self) -> bool:
        return False

    def close(self) -> None:
        pass


def test_detaching_from_an_app_that_has_exited_stops_qats_server_and_forgets_the_app(qat_state):
    context = ApplicationContext("demo", "/apps/demo")
    context.pid = 4321
    context._internal.client = ClientOfAnExitedApp()  # pyright: ignore[reportAttributeAccessIssue]
    server = context._internal.server
    qat_state.app_context_list.append(context)

    RealAppConnection(context, None).detach()

    assert isinstance(server, SocketlessServer)
    assert server.stopped
    assert qat_state.app_context_list == []
