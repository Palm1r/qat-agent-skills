from __future__ import annotations

import struct

ARM64 = 0x0100000C
X86_64 = 0x01000007
POWERPC = 0x12

QT5_CORE = "@rpath/QtCore.framework/Versions/5/QtCore"
QT6_CORE = "@rpath/QtCore.framework/Versions/A/QtCore"
LIBCXX = "/usr/lib/libc++.1.dylib"

MH_MAGIC_64 = 0xFEEDFACF
MH_EXECUTE = 0x2
LC_LOAD_DYLIB = 0xC
LC_RPATH = 0x8000001C
# The CPU subtypes Apple's toolchain writes, CPU_SUBTYPE_X86_64_ALL and CPU_SUBTYPE_ARM64_ALL,
# so that lipo and otool name the slices as they name real ones.
SUBTYPES = {X86_64: 3}


def thin(cpu_type: int, *dylibs: tuple[str, str]) -> bytes:
    commands = [
        _rpath("/Users/me/Qt/lib"),
        *(_load_dylib(name, version) for name, version in dylibs),
    ]
    body = b"".join(commands)
    subtype = SUBTYPES.get(cpu_type, 0)
    header = struct.pack(
        "<IiiIIIII", MH_MAGIC_64, cpu_type, subtype, MH_EXECUTE, len(commands), len(body), 0, 0
    )
    return header + body


def universal(*slices: tuple[int, bytes], fat64: bool = False) -> bytes:
    entry = struct.Struct(">iiQQII" if fat64 else ">iiIII")
    offset = _aligned(8 + entry.size * len(slices))
    table, data = b"", b""
    for cpu_type, image in slices:
        subtype = SUBTYPES.get(cpu_type, 0)
        fields = (cpu_type, subtype, offset + len(data), len(image), 4, *((0,) if fat64 else ()))
        table += entry.pack(*fields)
        data += image.ljust(_aligned(len(image)), b"\0")
    head = struct.pack(">II", 0xCAFEBABF if fat64 else 0xCAFEBABE, len(slices)) + table
    return head.ljust(offset, b"\0") + data


def _load_dylib(name: str, version: str) -> bytes:
    major, minor, patch = (int(part) for part in version.split("."))
    encoded = name.encode() + b"\0"
    size = _aligned(24 + len(encoded), 8)
    current = (major << 16) | (minor << 8) | patch
    fields = struct.pack("<IIIIII", LC_LOAD_DYLIB, size, 24, 2, current, 1 << 16)
    return fields + encoded.ljust(size - 24, b"\0")


def _rpath(path: str) -> bytes:
    encoded = path.encode() + b"\0"
    size = _aligned(12 + len(encoded), 8)
    return struct.pack("<III", LC_RPATH, size, 12) + encoded.ljust(size - 12, b"\0")


def _aligned(size: int, alignment: int = 16) -> int:
    return -(-size // alignment) * alignment
