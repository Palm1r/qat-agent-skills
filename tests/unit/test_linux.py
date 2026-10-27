from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from qat_agent_helpers import linux

QAT_1_8_1_SERVERS = ["5.15", *(f"6.{minor}" for minor in range(2, 12))]


def fake_ldd(monkeypatch: pytest.MonkeyPatch, output: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"args": args, **kwargs})
        return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    return calls


def ldd_output(qt_core: str) -> str:
    return (
        "\tlinux-vdso.so.1 (0x00007ffd5f3e2000)\n"
        "\tlibQt6Widgets.so.6 => /opt/Qt/lib/libQt6Widgets.so.6 (0x00007fad00c00000)\n"
        f"\tlibQt6Core.so.6 => {qt_core} (0x00007facff800000)\n"
        "\tlibc.so.6 => /usr/lib/libc.so.6 (0x00007facff400000)\n"
    )


def servers(tmp_path: Path, versions: list[str]) -> Path:
    server_dir = tmp_path / "qat-bin"
    server_dir.mkdir()
    for version in versions:
        (server_dir / f"libQatServer.{version}.so").write_bytes(b"")
    return server_dir


def qt_core_file(tmp_path: Path, name: str) -> Path:
    lib = tmp_path / "Qt lib"  # a space, as in a user's home folder
    lib.mkdir(exist_ok=True)
    (lib / name).write_bytes(b"")
    return lib / name


def test_the_loaded_qt_core_is_where_ldd_resolves_it_with_the_apps_environment(
    tmp_path, monkeypatch
):
    app = tmp_path / "demo"
    calls = fake_ldd(monkeypatch, ldd_output("/home/me/Qt/6.11.1/gcc_64/lib/libQt6Core.so.6"))

    found = linux.loaded_qt_core(app, {"LD_LIBRARY_PATH": "/opt/qt"})

    assert found == Path("/home/me/Qt/6.11.1/gcc_64/lib/libQt6Core.so.6")
    assert calls[0]["args"] == ["ldd", str(app)]
    assert calls[0]["env"] == {"LD_LIBRARY_PATH": "/opt/qt"}
    assert calls[0]["cwd"] == tmp_path


def test_a_path_with_spaces_is_read_whole(tmp_path, monkeypatch):
    fake_ldd(monkeypatch, ldd_output("/home/me/My Qt/lib/libQt5Core.so.5"))

    assert linux.loaded_qt_core(tmp_path / "demo", {}) == Path("/home/me/My Qt/lib/libQt5Core.so.5")


@pytest.mark.parametrize(
    "output",
    [
        "\tlibQt6Core.so.6 => not found\n",
        "\tlibc.so.6 => /usr/lib/libc.so.6 (0x00007facff400000)\n",
        "",
    ],
    ids=["not found", "no QtCore", "not a dynamic executable"],
)
def test_there_is_none_when_ldd_names_no_qt_core(tmp_path, monkeypatch, output):
    fake_ldd(monkeypatch, output)

    assert linux.loaded_qt_core(tmp_path / "demo", {}) is None


@pytest.mark.parametrize(
    "error",
    [FileNotFoundError("ldd"), subprocess.TimeoutExpired("ldd", 10)],
    ids=["no ldd", "ldd hangs"],
)
def test_there_is_none_when_ldd_cannot_run(tmp_path, monkeypatch, error):
    def run(*args: Any, **kwargs: Any) -> None:
        raise error

    monkeypatch.setattr(subprocess, "run", run)

    assert linux.loaded_qt_core(tmp_path / "demo", {}) is None


@pytest.mark.parametrize(
    ("name", "version"),
    [("libQt6Core.so.6.12.0", (6, 12)), ("libQt5Core.so.5.15.19", (5, 15))],
)
def test_the_qt_version_is_in_the_name_of_the_library_file(tmp_path, name, version):
    assert linux.qt_version(qt_core_file(tmp_path, name)) == version


@pytest.mark.skipif(sys.platform == "win32", reason="symbolic links need privileges on Windows")
def test_the_links_to_the_library_are_followed(tmp_path):
    real = qt_core_file(tmp_path, "libQt6Core.so.6.11.1")
    link = real.parent / "libQt6Core.so.6"
    link.symlink_to(real.name)

    assert linux.qt_version(link) == (6, 11)


def test_a_library_named_without_its_full_version_has_none(tmp_path):
    assert linux.qt_version(qt_core_file(tmp_path, "libQt6Core.so.6")) is None


def test_an_app_on_a_qt_qat_has_no_server_for_is_refused_with_what_to_do(tmp_path, monkeypatch):
    server_dir = servers(tmp_path, QAT_1_8_1_SERVERS)
    qt_core = qt_core_file(tmp_path, "libQt6Core.so.6.12.0")
    fake_ldd(monkeypatch, ldd_output(str(qt_core)))

    message = linux.missing_server(tmp_path / "demo", server_dir, {})

    assert message == (
        f"demo loads Qt 6.12 from {qt_core}, and Qat has no server for that version, only "
        "for Qt 5.15 and 6.2-6.11, so Qat cannot be injected into the app. Build the app with "
        "one of those Qt versions: with CMake, set CMAKE_PREFIX_PATH to that Qt, such as "
        "~/Qt/6.11.1/gcc_64 from the Qt online installer."
    )


def test_an_app_on_a_qt_qat_has_a_server_for_goes_ahead(tmp_path, monkeypatch):
    server_dir = servers(tmp_path, QAT_1_8_1_SERVERS)
    fake_ldd(monkeypatch, ldd_output(str(qt_core_file(tmp_path, "libQt6Core.so.6.11.1"))))

    assert linux.missing_server(tmp_path / "demo", server_dir, {}) is None


def test_an_app_whose_qt_version_cannot_be_told_goes_ahead(tmp_path, monkeypatch):
    server_dir = servers(tmp_path, QAT_1_8_1_SERVERS)
    fake_ldd(monkeypatch, ldd_output(str(qt_core_file(tmp_path, "libQt6Core.so.6"))))

    assert linux.missing_server(tmp_path / "demo", server_dir, {}) is None


def test_an_app_goes_ahead_when_no_server_of_qats_is_found(tmp_path, monkeypatch):
    server_dir = servers(tmp_path, [])
    fake_ldd(monkeypatch, ldd_output(str(qt_core_file(tmp_path, "libQt6Core.so.6.12.0"))))

    assert linux.missing_server(tmp_path / "demo", server_dir, {}) is None


@pytest.mark.parametrize(
    ("versions", "named"),
    [
        (["6.5"], "only for Qt 6.5,"),
        (["5.15", "6.2", "6.3", "6.5"], "only for Qt 5.15, 6.2-6.3 and 6.5,"),
    ],
)
def test_the_versions_qat_has_servers_for_are_named_in_runs(tmp_path, monkeypatch, versions, named):
    server_dir = servers(tmp_path, versions)
    fake_ldd(monkeypatch, ldd_output(str(qt_core_file(tmp_path, "libQt6Core.so.6.12.0"))))

    assert named in (linux.missing_server(tmp_path / "demo", server_dir, {}) or "")
