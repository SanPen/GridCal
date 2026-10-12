# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import re
import struct
from pathlib import Path
from typing import Tuple

from VeraGridEngine.enumerations import IeeeCigreDllPlatform


def _read_binary(path: Path, maximum_size: int) -> bytes:
    """Read one bounded regular native library.

    :param path: Manufacturer binary path.
    :param maximum_size: Maximum accepted byte size.
    :return: Exact file bytes.
    """
    if not path.is_file() or path.is_symlink():
        raise ValueError("Manufacturer native source must be a regular file")
    else:
        pass
    byte_size: int = path.stat().st_size
    if byte_size < 1 or byte_size > maximum_size:
        raise ValueError("Manufacturer native source size is outside the inspection limit")
    else:
        data: bytes = path.read_bytes()
    if len(data) != byte_size:
        raise ValueError("Manufacturer native source changed while being read")
    else:
        return data


def _read_ascii_name(data: bytes, offset: int, name: str) -> str:
    """Read one bounded NUL-terminated ASCII dependency basename.

    :param data: Complete binary bytes.
    :param offset: File offset of the string.
    :param name: Diagnostic field name.
    :return: Lowercase dependency basename.
    """
    if offset < 0 or offset >= len(data):
        raise ValueError(f"{name} string offset is outside the binary")
    else:
        pass
    end: int = data.find(b"\x00", offset, min(len(data), offset + 512))
    if end < 0:
        raise ValueError(f"{name} is not a bounded NUL-terminated string")
    else:
        pass
    try:
        value: str = data[offset:end].decode("ascii", errors="strict").lower()
    except UnicodeDecodeError as ex:
        raise ValueError(f"{name} must be ASCII") from ex
    if len(value) == 0 or "/" in value or "\\" in value or value in (".", ".."):
        raise ValueError(f"{name} must be a dependency basename")
    else:
        return value


def _validate_windows_dependency(name: str) -> None:
    """Apply the approved Windows OS-runtime dependency allowlist.

    :param name: Lowercase imported DLL basename.
    :return: None.
    """
    fixed_names: Tuple[str, ...] = (
        "kernel32.dll", "ntdll.dll", "bcrypt.dll", "ucrtbase.dll", "vcruntime140.dll",
        "vcruntime140_1.dll", "msvcp140.dll", "msvcp140_1.dll",
        "msvcp140_2.dll", "concrt140.dll",
    )
    contract_match: bool = (
        re.fullmatch(r"api-ms-win-core-[a-z0-9-]{1,96}\.dll", name) is not None
        or re.fullmatch(r"api-ms-win-crt-[a-z0-9-]{1,96}\.dll", name) is not None
        or re.fullmatch(r"ext-ms-[a-z0-9-]{1,96}\.dll", name) is not None
    )
    if name in fixed_names or contract_match:
        pass
    else:
        raise ValueError(f"Windows dependency is outside veragrid-native-os-runtime-v1: {name}")


def _pe_rva_to_offset(data: bytes,
                      sections: Tuple[Tuple[int, int, int, int], ...],
                      rva: int) -> int:
    """Translate one PE RVA through validated section ranges.

    :param data: Complete PE bytes.
    :param sections: Virtual address, virtual size, raw pointer and raw size tuples.
    :param rva: Relative virtual address.
    :return: File offset.
    """
    virtual_address: int
    virtual_size: int
    raw_pointer: int
    raw_size: int
    for virtual_address, virtual_size, raw_pointer, raw_size in sections:
        span: int = max(virtual_size, raw_size)
        if rva >= virtual_address and rva < virtual_address + span:
            delta: int = rva - virtual_address
            if delta >= raw_size or raw_pointer + delta >= len(data):
                raise ValueError("PE RVA resolves outside section raw data")
            else:
                return raw_pointer + delta
        else:
            pass
    raise ValueError("PE RVA does not resolve to a section")


def inspect_windows_pe_machine(data: bytes) -> int:
    """Return the COFF machine after validating the bounded PE envelope.

    :param data: Complete primary library bytes.
    :return: COFF machine identifier.
    """
    if len(data) < 512 or data[:2] != b"MZ":
        raise ValueError("Windows manufacturer library is not a PE image")
    else:
        pe_offset: int = struct.unpack_from("<I", data, 0x3c)[0]
    if pe_offset + 24 > len(data) or data[pe_offset:pe_offset + 4] != b"PE\x00\x00":
        raise ValueError("Windows manufacturer library has an invalid PE signature")
    else:
        pass
    machine: int
    section_count: int
    optional_size: int
    machine, section_count, _, _, _, optional_size, _ = struct.unpack_from("<HHIIIHH", data, pe_offset + 4)
    if section_count < 1 or section_count > 96:
        raise ValueError("Windows manufacturer library has an invalid section count")
    else:
        return machine


def _inspect_pe(data: bytes, platform: IeeeCigreDllPlatform) -> Tuple[str, ...]:
    """Validate one selected Windows PE image and return ordinary imports.

    :param data: Complete primary library bytes.
    :param platform: Exact Windows architecture selected by the caller.
    :return: Ordered lowercase dependency basenames.
    """
    machine: int = inspect_windows_pe_machine(data)
    pe_offset: int = struct.unpack_from("<I", data, 0x3c)[0]
    section_count: int
    optional_size: int
    _, section_count, _, _, _, optional_size, _ = struct.unpack_from("<HHIIIHH", data, pe_offset + 4)
    if platform == IeeeCigreDllPlatform.WINDOWS_X86:
        expected_machine: int = 0x014c
        expected_magic: int = 0x10b
        directory_count_offset: int = 92
        directory_offset: int = 96
    else:
        if platform == IeeeCigreDllPlatform.WINDOWS_X64:
            expected_machine = 0x8664
            expected_magic = 0x20b
            directory_count_offset = 108
            directory_offset = 112
        else:
            raise ValueError("PE inspection requires a Windows manufacturer platform")
    if machine != expected_machine:
        raise ValueError("Windows manufacturer library machine does not match the selected platform")
    else:
        optional_offset: int = pe_offset + 24
    if optional_offset + optional_size > len(data) or optional_size < 120:
        raise ValueError("Windows manufacturer library optional header is truncated")
    else:
        pass
    if struct.unpack_from("<H", data, optional_offset)[0] != expected_magic:
        raise ValueError("Windows manufacturer library optional format does not match its machine")
    else:
        pass
    directory_count: int = struct.unpack_from("<I", data, optional_offset + directory_count_offset)[0]
    if directory_count <= 13:
        raise ValueError("Windows manufacturer library lacks required data directories")
    else:
        pass
    import_rva: int
    import_size: int
    import_rva, import_size = struct.unpack_from("<II", data, optional_offset + directory_offset + 8)
    delay_rva: int
    delay_size: int
    delay_rva, delay_size = struct.unpack_from("<II", data, optional_offset + directory_offset + 13 * 8)
    if delay_rva != 0 or delay_size != 0:
        raise ValueError("Windows manufacturer library delay imports are not accepted")
    else:
        pass
    section_offset: int = optional_offset + optional_size
    if section_offset + section_count * 40 > len(data):
        raise ValueError("Windows manufacturer library section table is truncated")
    else:
        pass
    section_list: list[Tuple[int, int, int, int]] = list()
    section_index: int
    for section_index in range(section_count):
        base: int = section_offset + section_index * 40
        virtual_size: int = struct.unpack_from("<I", data, base + 8)[0]
        virtual_address: int = struct.unpack_from("<I", data, base + 12)[0]
        raw_size: int = struct.unpack_from("<I", data, base + 16)[0]
        raw_pointer: int = struct.unpack_from("<I", data, base + 20)[0]
        if raw_pointer + raw_size > len(data):
            raise ValueError("Windows manufacturer library section exceeds file bounds")
        else:
            section_list.append((virtual_address, virtual_size, raw_pointer, raw_size))
    sections: Tuple[Tuple[int, int, int, int], ...] = tuple(section_list)
    if import_rva == 0 and import_size == 0:
        return tuple()
    else:
        descriptor_offset: int = _pe_rva_to_offset(data, sections, import_rva)
    dependencies: list[str] = list()
    descriptor_count: int = 0
    reading: bool = True
    while reading:
        if descriptor_offset + 20 > len(data) or descriptor_count >= 256:
            raise ValueError("Windows import descriptor table is unbounded or truncated")
        else:
            descriptor: Tuple[int, int, int, int, int] = struct.unpack_from("<IIIII", data, descriptor_offset)
        if descriptor == (0, 0, 0, 0, 0):
            reading = False
        else:
            name_offset: int = _pe_rva_to_offset(data, sections, descriptor[3])
            dependency: str = _read_ascii_name(data, name_offset, "PE import")
            _validate_windows_dependency(dependency)
            dependencies.append(dependency)
            descriptor_offset += 20
            descriptor_count += 1
    return tuple(dependencies)


def _validate_linux_dependency(name: str) -> None:
    """Apply the approved Linux OS-runtime dependency allowlist.

    :param name: Lowercase DT_NEEDED basename.
    :return: None.
    """
    allowed: Tuple[str, ...] = (
        "libc.so.6", "libm.so.6", "libpthread.so.0", "librt.so.1",
        "libdl.so.2", "libgcc_s.so.1", "libstdc++.so.6", "ld-linux-x86-64.so.2",
    )
    if name in allowed:
        pass
    else:
        raise ValueError(f"Linux dependency is outside veragrid-native-os-runtime-v1: {name}")


def _inspect_elf(data: bytes) -> Tuple[str, ...]:
    """Validate an ELF64 little-endian x86-64 image and return DT_NEEDED names.

    :param data: Complete primary library bytes.
    :return: Ordered lowercase dependency basenames.
    """
    if len(data) < 64 or data[:4] != b"\x7fELF":
        raise ValueError("Linux manufacturer library is not an ELF image")
    else:
        pass
    if data[4] != 2 or data[5] != 1 or struct.unpack_from("<H", data, 18)[0] != 62:
        raise ValueError("Linux manufacturer library must be little-endian ELF64 x86-64")
    else:
        pass
    program_offset: int = struct.unpack_from("<Q", data, 32)[0]
    program_entry_size: int = struct.unpack_from("<H", data, 54)[0]
    program_count: int = struct.unpack_from("<H", data, 56)[0]
    if program_entry_size < 56 or program_count < 1 or program_count > 256:
        raise ValueError("Linux manufacturer library program header table is invalid")
    else:
        pass
    if program_offset + program_entry_size * program_count > len(data):
        raise ValueError("Linux manufacturer library program header table is truncated")
    else:
        pass
    load_segments: list[Tuple[int, int, int, int]] = list()
    dynamic_offset: int | None = None
    dynamic_size: int = 0
    program_index: int
    for program_index in range(program_count):
        base: int = program_offset + program_index * program_entry_size
        segment_type: int = struct.unpack_from("<I", data, base)[0]
        file_offset: int = struct.unpack_from("<Q", data, base + 8)[0]
        virtual_address: int = struct.unpack_from("<Q", data, base + 16)[0]
        file_size: int = struct.unpack_from("<Q", data, base + 32)[0]
        memory_size: int = struct.unpack_from("<Q", data, base + 40)[0]
        if file_offset + file_size > len(data):
            raise ValueError("Linux manufacturer library segment exceeds file bounds")
        else:
            pass
        if segment_type == 1:
            load_segments.append((virtual_address, memory_size, file_offset, file_size))
        else:
            if segment_type == 2:
                dynamic_offset = file_offset
                dynamic_size = file_size
            else:
                pass
    if dynamic_offset is None or dynamic_size < 16 or dynamic_size % 16 != 0:
        raise ValueError("Linux manufacturer library has no valid dynamic table")
    else:
        pass
    string_table_address: int | None = None
    string_table_size: int | None = None
    needed_offsets: list[int] = list()
    entry_offset: int
    for entry_offset in range(dynamic_offset, dynamic_offset + dynamic_size, 16):
        tag: int = struct.unpack_from("<q", data, entry_offset)[0]
        value: int = struct.unpack_from("<Q", data, entry_offset + 8)[0]
        if tag == 0:
            break
        elif tag == 1:
            needed_offsets.append(value)
        elif tag == 5:
            string_table_address = value
        elif tag == 10:
            string_table_size = value
        elif tag == 15 or tag == 29:
            raise ValueError("Linux manufacturer library RPATH/RUNPATH is not accepted")
        else:
            pass
    if string_table_address is None or string_table_size is None:
        raise ValueError("Linux manufacturer library dynamic string table is incomplete")
    else:
        pass
    string_table_offset: int | None = None
    virtual_address: int
    memory_size: int
    file_offset: int
    file_size: int
    for virtual_address, memory_size, file_offset, file_size in load_segments:
        if string_table_address >= virtual_address and string_table_address < virtual_address + memory_size:
            delta: int = string_table_address - virtual_address
            if delta + string_table_size > file_size:
                raise ValueError("Linux dynamic string table exceeds its load segment")
            else:
                string_table_offset = file_offset + delta
        else:
            pass
    if string_table_offset is None:
        raise ValueError("Linux dynamic string table cannot be mapped to file bytes")
    else:
        pass
    dependencies: list[str] = list()
    needed_offset: int
    for needed_offset in needed_offsets:
        if needed_offset >= string_table_size:
            raise ValueError("Linux DT_NEEDED offset exceeds the dynamic string table")
        else:
            dependency: str = _read_ascii_name(data, string_table_offset + needed_offset, "ELF DT_NEEDED")
        _validate_linux_dependency(dependency)
        dependencies.append(dependency)
    return tuple(dependencies)


def _inspect_native_binary(path: Path,
                           platform: IeeeCigreDllPlatform,
                           maximum_size: int) -> Tuple[int, Tuple[str, ...]]:
    """Validate format, architecture and declared dependencies without loading code.

    :param path: Manufacturer binary path.
    :param platform: Exact expected platform.
    :param maximum_size: Maximum accepted primary binary size.
    :return: Exact byte size and ordered dependency basenames.
    """
    data: bytes = _read_binary(path, maximum_size)
    if platform in (IeeeCigreDllPlatform.WINDOWS_X86, IeeeCigreDllPlatform.WINDOWS_X64):
        dependencies: Tuple[str, ...] = _inspect_pe(data, platform)
    else:
        if platform == IeeeCigreDllPlatform.LINUX_X64:
            dependencies = _inspect_elf(data)
        else:
            raise ValueError("Unsupported manufacturer native platform")
    return len(data), dependencies
