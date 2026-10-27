from __future__ import annotations

import platform
import plistlib
import re
import struct
from pathlib import Path
from typing import BinaryIO
from xml.parsers.expat import ExpatError

FAT_MAGIC = 0xCAFEBABE
FAT_MAGIC_64 = 0xCAFEBABF
MH_MAGIC_64 = 0xFEEDFACF
CPU_TYPES = {0x01000007: "x86_64", 0x0100000C: "arm64"}
LC_LOAD_DYLIB = 0xC
LC_LOAD_WEAK_DYLIB = 0x80000018
LC_REEXPORT_DYLIB = 0x8000001F
LC_LOAD_UPWARD_DYLIB = 0x80000023
LOAD_DYLIB_COMMANDS = {LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB, LC_LOAD_UPWARD_DYLIB}
# A Java class file starts with the same magic number, followed by a version larger
# than this.
MAX_SLICES = 20

QT_CORE = re.compile(
    r"(?:^|/)(?:QtCore\.framework/(?:Versions/[^/]+/)?QtCore|libQt\d*Core(?:\.\d+)*\.dylib)$"
)
SERVER = re.compile(r"libQatServer\.(\d+)\.(\d+)\.dylib")


def bundle_executable(bundle: Path) -> Path:
    name = bundle.stem
    try:
        with (bundle / "Contents" / "Info.plist").open("rb") as file:
            info = plistlib.load(file)
    except (OSError, ValueError, ExpatError):
        info = None
    if isinstance(info, dict) and isinstance(info.get("CFBundleExecutable"), str):
        name = info["CFBundleExecutable"] or name
    return bundle / "Contents" / "MacOS" / name


def architectures(path: Path) -> list[str]:
    with path.open("rb") as file:
        return list(dict.fromkeys(architecture for architecture, _ in _slices(file)))


def linked_qt_version(path: Path, architecture: str) -> tuple[int, int] | None:
    with path.open("rb") as file:
        for slice_architecture, offset in _slices(file):
            if slice_architecture == architecture:
                return _qt_version(file, offset)
    return None


def server_mismatch(executable: Path, server_dir: Path, machine: str | None = None) -> str | None:
    try:
        architecture = _architecture_to_run(architectures(executable), machine)
        if architecture is None:
            return None
        version = linked_qt_version(executable, architecture)
        if version is None:
            return None
        server = server_dir / _server_name(version)
        if not server.is_file():
            return None
        server_architectures = architectures(server)
        if not server_architectures or architecture in server_architectures:
            return None
        others = _versions_with(server_dir, architecture)
    except (OSError, struct.error):
        return None

    built_for = " and ".join(server_architectures)
    message = (
        f"{executable.name} runs as {architecture}, but Qat's server for Qt "
        f"{version[0]}.{version[1]}, {server.name}, is built for {built_for} only, so Qat "
        "cannot be injected into the app."
    )
    if architecture == "arm64" and "x86_64" in server_architectures:
        message += (
            " Build the app for x86_64 (with CMake, -DCMAKE_OSX_ARCHITECTURES=x86_64) and "
            "launch it on a Mac that has Rosetta"
        )
    else:
        message += f" Build the app for {built_for}"
    if others:
        message += f", or build it with a Qt that Qat has an {architecture} server for: {others}"
    return message + "."


def _architecture_to_run(built_for: list[str], machine: str | None) -> str | None:
    machine = machine or platform.machine()
    if machine in built_for:
        return machine
    return built_for[0] if len(built_for) == 1 else None


def _server_name(version: tuple[int, int]) -> str:
    return f"libQatServer.{version[0]}.{version[1]}.dylib"


def _versions_with(server_dir: Path, architecture: str) -> str:
    versions = sorted(
        (int(match.group(1)), int(match.group(2)))
        for path in server_dir.glob("libQatServer.*.dylib")
        if (match := SERVER.fullmatch(path.name))
    )
    fitting = [
        version
        for version in versions
        if architecture in architectures(server_dir / _server_name(version))
    ]
    if not fitting:
        return ""
    names = [f"{major}.{minor}" for major, minor in fitting]
    first = versions.index(fitting[0])
    if len(fitting) > 1 and versions[first : first + len(fitting)] == fitting:
        return f"Qt {names[0]}-{names[-1]}"
    return "Qt " + ", ".join(names)


def _slices(file: BinaryIO) -> list[tuple[str, int]]:
    file.seek(0)
    head = file.read(8)
    if len(head) < 8:
        return []
    (magic,) = struct.unpack(">I", head[:4])
    if magic in (FAT_MAGIC, FAT_MAGIC_64):
        (count,) = struct.unpack(">I", head[4:])
        if count > MAX_SLICES:
            return []
        entry = struct.Struct(">iiQQII" if magic == FAT_MAGIC_64 else ">iiIII")
        table = file.read(entry.size * count)
        if len(table) < entry.size * count:
            return []
        slices = []
        for index in range(count):
            cpu_type, _, offset, *_ = entry.unpack_from(table, index * entry.size)
            if cpu_type in CPU_TYPES:
                slices.append((CPU_TYPES[cpu_type], offset))
        return slices
    magic, cpu_type = struct.unpack("<Ii", head)
    if magic == MH_MAGIC_64 and cpu_type in CPU_TYPES:
        return [(CPU_TYPES[cpu_type], 0)]
    return []


def _qt_version(file: BinaryIO, offset: int) -> tuple[int, int] | None:
    file.seek(offset)
    header = file.read(32)
    if len(header) < 32:
        return None
    magic, _, _, _, count, size, _, _ = struct.unpack("<IiiIIIII", header)
    if magic != MH_MAGIC_64:
        return None
    commands = file.read(size)
    position = 0
    for _ in range(count):
        if position + 8 > len(commands):
            return None
        command, command_size = struct.unpack_from("<II", commands, position)
        if command_size < 8 or position + command_size > len(commands):
            return None
        if command in LOAD_DYLIB_COMMANDS and command_size >= 24:
            name_offset, _, version, _ = struct.unpack_from("<IIII", commands, position + 8)
            name = commands[position + name_offset : position + command_size].split(b"\0")[0]
            if QT_CORE.search(name.decode("utf-8", "replace")):
                return version >> 16, (version >> 8) & 0xFF
        position += command_size
    return None
