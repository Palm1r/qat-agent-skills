from __future__ import annotations

import plistlib
from pathlib import Path

import pytest
import qat

from qat_agent_helpers import macos
from tests.unit.mach_o import ARM64, LIBCXX, POWERPC, QT5_CORE, QT6_CORE, X86_64, thin, universal


def make_bundle(tmp_path: Path, info: bytes | None) -> Path:
    bundle = tmp_path / "Demo App.app"
    (bundle / "Contents" / "MacOS").mkdir(parents=True)
    if info is not None:
        (bundle / "Contents" / "Info.plist").write_bytes(info)
    return bundle


@pytest.mark.parametrize("plist_format", [plistlib.FMT_XML, plistlib.FMT_BINARY])
def test_a_bundles_executable_is_the_one_its_info_plist_names(tmp_path, plist_format):
    info = plistlib.dumps({"CFBundleExecutable": "demo"}, fmt=plist_format)
    bundle = make_bundle(tmp_path, info)

    assert macos.bundle_executable(bundle) == bundle / "Contents" / "MacOS" / "demo"


@pytest.mark.parametrize(
    "info",
    [None, plistlib.dumps({"CFBundleName": "Demo"}), b"not a property list", b"<plist><dict>"],
    ids=["no Info.plist", "no CFBundleExecutable", "not a plist", "broken XML"],
)
def test_otherwise_the_executable_is_named_after_the_bundle(tmp_path, info):
    bundle = make_bundle(tmp_path, info)

    assert macos.bundle_executable(bundle) == bundle / "Contents" / "MacOS" / "Demo App"


def write(tmp_path: Path, name: str, content: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def test_a_thin_binary_has_its_one_architecture(tmp_path):
    assert macos.architectures(write(tmp_path, "arm", thin(ARM64))) == ["arm64"]
    assert macos.architectures(write(tmp_path, "intel", thin(X86_64))) == ["x86_64"]


@pytest.mark.parametrize("fat64", [False, True], ids=["fat", "fat64"])
def test_a_universal_binary_has_the_architectures_of_its_slices(tmp_path, fat64):
    binary = universal((X86_64, thin(X86_64)), (ARM64, thin(ARM64)), fat64=fat64)

    assert macos.architectures(write(tmp_path, "app", binary)) == ["x86_64", "arm64"]


def test_slices_of_one_architecture_count_once(tmp_path):
    binary = universal((X86_64, thin(X86_64)), (ARM64, thin(ARM64)), (ARM64, thin(ARM64)))

    assert macos.architectures(write(tmp_path, "app", binary)) == ["x86_64", "arm64"]


def test_architectures_the_library_does_not_know_are_left_out(tmp_path):
    binary = universal((POWERPC, b"\0" * 32), (ARM64, thin(ARM64)))

    assert macos.architectures(write(tmp_path, "app", binary)) == ["arm64"]


@pytest.mark.parametrize(
    "content",
    [b"", b"#!/bin/sh\necho hi\n", b"MZ\x90\x00" + b"\0" * 60, bytes.fromhex("cafebabe00000034")],
    ids=["empty", "script", "Windows executable", "Java class file"],
)
def test_other_files_have_no_architectures(tmp_path, content):
    assert macos.architectures(write(tmp_path, "app", content)) == []


def test_the_qt_version_comes_from_the_qtcore_the_binary_links(tmp_path):
    app = write(tmp_path, "app", thin(ARM64, (LIBCXX, "1700.255.5"), (QT5_CORE, "5.15.19")))

    assert macos.linked_qt_version(app, "arm64") == (5, 15)


def test_each_slice_of_a_universal_binary_has_its_own_qt_version(tmp_path):
    binary = universal(
        (X86_64, thin(X86_64, (QT6_CORE, "6.8.3"))), (ARM64, thin(ARM64, (QT6_CORE, "6.11.1")))
    )
    app = write(tmp_path, "app", binary)

    assert macos.linked_qt_version(app, "x86_64") == (6, 8)
    assert macos.linked_qt_version(app, "arm64") == (6, 11)


def test_qtcore_as_a_plain_dylib_counts_too(tmp_path):
    app = write(tmp_path, "app", thin(ARM64, ("@rpath/libQt6Core.6.dylib", "6.5.2")))

    assert macos.linked_qt_version(app, "arm64") == (6, 5)


def test_a_binary_without_qtcore_has_no_qt_version(tmp_path):
    compat = "@rpath/QtCore5Compat.framework/Versions/A/QtCore5Compat"
    app = write(tmp_path, "app", thin(ARM64, (LIBCXX, "1700.255.5"), (compat, "6.11.1")))

    assert macos.linked_qt_version(app, "arm64") is None
    assert macos.linked_qt_version(app, "x86_64") is None


def test_a_truncated_binary_has_no_qt_version(tmp_path):
    app = write(tmp_path, "app", thin(ARM64, (QT5_CORE, "5.15.19"))[:60])

    assert macos.linked_qt_version(app, "arm64") is None


@pytest.fixture
def servers(tmp_path: Path) -> Path:
    server_dir = tmp_path / "qat-bin"
    server_dir.mkdir()
    write(server_dir, "libQatServer.5.15.dylib", thin(X86_64))
    for version in ("6.8", "6.11"):
        server = universal((X86_64, thin(X86_64)), (ARM64, thin(ARM64)))
        write(server_dir, f"libQatServer.{version}.dylib", server)
    return server_dir


def test_an_arm64_app_on_qt_5_15_gets_told_why_and_what_to_do(tmp_path, servers):
    app = write(tmp_path, "demo", thin(ARM64, (QT5_CORE, "5.15.19")))

    message = macos.server_mismatch(app, servers, machine="arm64")

    assert message == (
        "demo runs as arm64, but Qat's server for Qt 5.15, libQatServer.5.15.dylib, is built "
        "for x86_64 only, so Qat cannot be injected into the app. Build the app for x86_64 "
        "(with CMake, -DCMAKE_OSX_ARCHITECTURES=x86_64) and launch it on a Mac that has "
        "Rosetta, or build it with a Qt that Qat has an arm64 server for: Qt 6.8-6.11."
    )


def test_a_universal_app_runs_as_this_process_does(tmp_path, servers):
    binary = universal(
        (X86_64, thin(X86_64, (QT5_CORE, "5.15.19"))),
        (ARM64, thin(ARM64, (QT5_CORE, "5.15.19"))),
    )
    app = write(tmp_path, "demo", binary)

    assert macos.server_mismatch(app, servers, machine="arm64") is not None
    assert macos.server_mismatch(app, servers, machine="x86_64") is None


@pytest.mark.parametrize(
    "image",
    [
        pytest.param(thin(ARM64, (QT6_CORE, "6.11.1")), id="the server fits"),
        pytest.param(thin(X86_64, (QT5_CORE, "5.15.19")), id="x86_64 runs under Rosetta"),
        pytest.param(thin(ARM64, (QT6_CORE, "6.12.0")), id="no server for the Qt version"),
        pytest.param(thin(ARM64, (LIBCXX, "1700.255.5")), id="no QtCore"),
        pytest.param(b"#!/bin/sh\n", id="not a Mach-O file"),
    ],
)
def test_an_app_is_let_through_whenever_a_mismatch_is_not_certain(tmp_path, servers, image):
    app = write(tmp_path, "demo", image)

    assert macos.server_mismatch(app, servers, machine="arm64") is None


def test_a_missing_app_is_left_to_the_launch(tmp_path, servers):
    assert macos.server_mismatch(tmp_path / "missing", servers, machine="arm64") is None


def test_qat_1_9_0_builds_its_qt_5_15_server_for_x86_64_only():
    # The library pins qat==1.9.0, whose single wheel carries the servers for every platform.
    server_dir = Path(qat.__file__).parent / "bin"

    assert macos.architectures(server_dir / "libQatServer.5.15.dylib") == ["x86_64"]
    for minor in range(2, 13):
        assert "arm64" in macos.architectures(server_dir / f"libQatServer.6.{minor}.dylib")


def test_the_message_for_qat_1_9_0_names_the_qt_versions_it_has_arm64_servers_for(tmp_path):
    server_dir = Path(qat.__file__).parent / "bin"
    app = write(tmp_path, "demo", thin(ARM64, (QT5_CORE, "5.15.19")))

    message = macos.server_mismatch(app, server_dir, machine="arm64")

    assert message is not None
    assert message.endswith("an arm64 server for: Qt 6.2-6.12.")
