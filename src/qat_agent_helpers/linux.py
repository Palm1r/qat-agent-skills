from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from pathlib import Path

LDD_QT_CORE = re.compile(
    r"^\s*libQt\d+Core\.so[.\d]*\s+=>\s+(.+?)\s+\(0x[0-9a-fA-F]+\)\s*$", re.MULTILINE
)
QT_CORE_FILE = re.compile(r"libQt\d+Core\.so\.(\d+)\.(\d+)\.\d+")
SERVER = re.compile(r"libQatServer\.(\d+)\.(\d+)\.so")
LDD_TIMEOUT = 10.0


def loaded_qt_core(executable: Path, env: Mapping[str, str]) -> Path | None:
    try:
        result = subprocess.run(
            ["ldd", str(executable)],
            cwd=executable.parent,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=LDD_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = LDD_QT_CORE.search(result.stdout)
    return Path(match.group(1)) if match else None


def qt_version(qt_core: Path) -> tuple[int, int] | None:
    try:
        name = qt_core.resolve().name
    except OSError:
        return None
    match = QT_CORE_FILE.fullmatch(name)
    return (int(match.group(1)), int(match.group(2))) if match else None


def missing_server(executable: Path, server_dir: Path, env: Mapping[str, str]) -> str | None:
    qt_core = loaded_qt_core(executable, env)
    if qt_core is None:
        return None
    version = qt_version(qt_core)
    if version is None or (server_dir / _server_name(version)).is_file():
        return None
    available = _server_versions(server_dir)
    if not available:
        return None
    return (
        f"{executable.name} loads Qt {version[0]}.{version[1]} from {qt_core}, and Qat has no "
        f"server for that version, only for {_ranges(available)}, so Qat cannot be injected "
        "into the app. Build the app with one of those Qt versions: with CMake, set "
        "CMAKE_PREFIX_PATH to that Qt, such as ~/Qt/6.11.1/gcc_64 from the Qt online installer."
    )


def _server_name(version: tuple[int, int]) -> str:
    return f"libQatServer.{version[0]}.{version[1]}.so"


def _server_versions(server_dir: Path) -> list[tuple[int, int]]:
    try:
        names = [path.name for path in server_dir.glob("libQatServer.*.so")]
    except OSError:
        return []
    return sorted(
        (int(match.group(1)), int(match.group(2)))
        for name in names
        if (match := SERVER.fullmatch(name))
    )


def _ranges(versions: list[tuple[int, int]]) -> str:
    runs: list[list[tuple[int, int]]] = []
    for version in versions:
        if runs and runs[-1][-1] == (version[0], version[1] - 1):
            runs[-1].append(version)
        else:
            runs.append([version])
    names = [
        f"{run[0][0]}.{run[0][1]}" + (f"-{run[-1][0]}.{run[-1][1]}" if len(run) > 1 else "")
        for run in runs
    ]
    joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return "Qt " + joined
