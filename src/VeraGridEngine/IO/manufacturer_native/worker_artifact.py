# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import time

from VeraGridEngine.enumerations import IeeeCigreDllPlatform
from VeraGridEngine.IO.manufacturer_native.binary_validation import (
    _inspect_native_binary,
    inspect_windows_pe_machine,
)
from VeraGridEngine.IO.native_compiler.compiler_interface import NativeCompilerSelection, NativeCompilerToolset
from VeraGridEngine.IO.native_compiler.selected_interface import (
    load_saved_local_llvm_selection,
    resolve_native_compiler_toolset,
)


class ManufacturerNativeWorkerArtifact:
    """Verified cached worker executable and its immutable identity."""

    __slots__ = (
        "executable_path", "content_sha256", "platform", "cache_key",
        "system_volume_serial", "system_file_id", "system_directory",
    )

    def __init__(self,
                 executable_path: Path,
                 content_sha256: str,
                 platform: IeeeCigreDllPlatform,
                 cache_key: str,
                 system_volume_serial: int = 0,
                 system_file_id: bytes = bytes(16),
                 system_directory: str = "") -> None:
        """Create one verified artifact description.

        :param executable_path: Absolute cached worker executable.
        :param content_sha256: Lowercase SHA-256 of the executable bytes.
        :param platform: Exact worker host platform.
        :param cache_key: Content-addressed build identity.
        :param system_volume_serial: Windows System32 volume identity.
        :param system_file_id: Windows System32 directory file identity.
        :param system_directory: Canonical Windows System32 directory.
        :return: None.
        """
        self.executable_path: Path = executable_path
        self.content_sha256: str = content_sha256
        self.platform: IeeeCigreDllPlatform = platform
        self.cache_key: str = cache_key
        self.system_volume_serial: int = system_volume_serial
        self.system_file_id: bytes = system_file_id
        self.system_directory: str = system_directory


class ManufacturerNativeWorkerPreparation:
    """Result of one explicit worker preparation request."""

    __slots__ = ("artifact", "compiled")

    def __init__(self,
                 artifact: ManufacturerNativeWorkerArtifact,
                 compiled: bool) -> None:
        """Create one preparation result.

        :param artifact: Verified artifact selected after preparation.
        :param compiled: Whether this request produced a new executable.
        :return: None.
        """
        self.artifact: ManufacturerNativeWorkerArtifact = artifact
        self.compiled: bool = compiled


def _host_platform() -> IeeeCigreDllPlatform:
    """Return the supported native worker platform for this process.

    :return: Windows x64 or Linux x64 platform.
    """
    if struct.calcsize("P") != 8:
        raise RuntimeError("Manufacturer native execution requires a 64-bit host")
    elif sys.platform == "win32":
        return IeeeCigreDllPlatform.WINDOWS_X64
    elif sys.platform.startswith("linux"):
        return IeeeCigreDllPlatform.LINUX_X64
    else:
        raise RuntimeError("Manufacturer native execution supports Windows x64 and Linux x64")


def _worker_sources() -> tuple[Path, ...]:
    """Return the reviewed source set in deterministic build order.

    :return: Absolute source and header paths.
    """
    source_root: Path = Path(__file__).resolve().parent / "native_worker" / "source"
    source_names: tuple[str, ...] = (
        "worker.c",
        "platform.h",
        "platform_hash.c",
        "protocol.h",
        "protocol.c",
        "adapter_ieee_cigre_v1_1.h",
        "adapter_common.h",
        "adapter_ieee_cigre_v1_0.h",
        "adapter_iec_ese.h",
        "adapter_ieee_cigre_v1_1.c",
        "adapter_ieee_cigre_v1_0.c",
        "adapter_iec_ese.c",
        "platform_windows.c",
        "platform_linux.c",
    )
    sources: list[Path] = list()
    source_name: str
    for source_name in source_names:
        source_path: Path = source_root / source_name
        if not source_path.is_file() or source_path.is_symlink():
            raise RuntimeError(f"Manufacturer native worker source is missing: {source_name}")
        else:
            sources.append(source_path)
    return tuple(sources)


def _source_digest(sources: tuple[Path, ...]) -> str:
    """Hash source names and bytes using deterministic framing.

    :param sources: Reviewed worker source set.
    :return: Lowercase SHA-256 build source identity.
    """
    digest = hashlib.sha256()
    source: Path
    for source in sources:
        name_bytes: bytes = source.name.encode("utf-8", errors="strict")
        content: bytes = source.read_bytes()
        digest.update(len(name_bytes).to_bytes(4, byteorder="big", signed=False))
        digest.update(name_bytes)
        digest.update(len(content).to_bytes(8, byteorder="big", signed=False))
        digest.update(content)
    return digest.hexdigest()


def _compiler_arguments(
    platform: IeeeCigreDllPlatform,
    sources: tuple[Path, ...],
    output_path: Path,
    toolset: NativeCompilerToolset,
) -> tuple[str, ...]:
    """Build the exact ordered selected-provider argument sequence.

    :param platform: Current supported host platform.
    :param sources: Reviewed worker source set.
    :param output_path: Private build output path.
    :param toolset: Authenticated selected-provider compiler contract.
    :return: Ordered compiler arguments excluding the executable.
    """
    source_arguments: list[str] = list()
    source: Path
    for source in sources:
        platform_mismatch: bool = (
            (source.name == "platform_windows.c" and platform != IeeeCigreDllPlatform.WINDOWS_X64)
            or (source.name == "platform_linux.c" and platform != IeeeCigreDllPlatform.LINUX_X64)
        )
        if source.suffix == ".c" and not platform_mismatch:
            source_arguments.append(str(source))
        else:
            pass
    arguments: list[str] = list(toolset.compiler_prefix_arguments)
    arguments.extend((
        "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
        "-Wno-unused-command-line-argument",
        "-DVERAGRID_MANUFACTURER_WORKER=1",
    ))
    arguments.extend(source_arguments)
    if platform == IeeeCigreDllPlatform.LINUX_X64:
        arguments.extend(["-ldl", "-lm"])
    else:
        pass
    arguments.extend(["-o", str(output_path)])
    return tuple(arguments)


def _cache_identity(
    platform: IeeeCigreDllPlatform,
    sources: tuple[Path, ...],
    toolset: NativeCompilerToolset,
) -> str:
    """Compute the content-addressed cache key before compilation.

    :param platform: Current supported host platform.
    :param sources: Reviewed worker source set.
    :param toolset: Authenticated selected-provider compiler contract.
    :return: Lowercase SHA-256 cache key.
    """
    identity_record: dict[str, object] = {
        "schema": 3,
        "source_sha256": _source_digest(sources),
        "compiler_framework": toolset.framework.value,
        "compiler_provider_version": toolset.provider_version,
        "compiler_tool_sha256": list(toolset.tool_hashes),
        "compiler_prefix_arguments": list(toolset.compiler_prefix_arguments),
        "platform": platform.value,
        "arguments": [
            "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-Wno-unused-command-line-argument",
            "-DVERAGRID_MANUFACTURER_WORKER=1",
            "native" if platform == IeeeCigreDllPlatform.WINDOWS_X64 else "-ldl,-lm",
        ],
    }
    identity_bytes: bytes = json.dumps(
        identity_record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(identity_bytes).hexdigest()


def _file_sha256(path: Path) -> str:
    """Hash one regular file.

    :param path: File to hash.
    :return: Lowercase SHA-256 digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk: bytes = stream.read(1024 * 1024)
            if len(chunk) == 0:
                break
            else:
                digest.update(chunk)
    return digest.hexdigest()


def _windows_system_identity(
        platform: IeeeCigreDllPlatform) -> tuple[int, bytes, str]:
    """Read the canonical Windows runtime directory identity.

    :param platform: Exact Windows worker architecture.
    :return: Volume serial, 16-byte file identifier and canonical directory path.
    """
    if os.name != "nt" or platform not in (
            IeeeCigreDllPlatform.WINDOWS_X86,
            IeeeCigreDllPlatform.WINDOWS_X64,
    ):
        raise RuntimeError("Windows runtime identity needs a Windows worker platform")
    else:
        pass

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    buffer = ctypes.create_unicode_buffer(32767)
    if platform == IeeeCigreDllPlatform.WINDOWS_X86:
        get_directory = kernel32.GetSystemWow64DirectoryW
    else:
        get_directory = kernel32.GetSystemDirectoryW
    get_directory.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    get_directory.restype = ctypes.c_uint32
    length: int = int(get_directory(ctypes.addressof(buffer), len(buffer)))
    if length < 1 or length >= len(buffer):
        raise OSError(ctypes.get_last_error(), "Cannot resolve Windows runtime directory")
    else:
        system_directory: str = str(Path(buffer.value).resolve(strict=True))

    kernel32.CreateFileW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    kernel32.CreateFileW.restype = ctypes.c_void_p
    kernel32.GetFileInformationByHandleEx.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    kernel32.GetFileInformationByHandleEx.restype = ctypes.c_int
    kernel32.GetFinalPathNameByHandleW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
    ]
    kernel32.GetFinalPathNameByHandleW.restype = ctypes.c_uint32
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    handle: int | None = kernel32.CreateFileW(
        system_directory,
        0x80,
        0x1 | 0x2 | 0x4,
        None,
        3,
        0x02000000,
        None,
    )
    invalid_handle: int | None = ctypes.c_void_p(-1).value
    if handle is None or handle == invalid_handle:
        raise OSError(ctypes.get_last_error(), "Cannot open Windows runtime directory")
    else:
        pass
    try:
        information = ctypes.create_string_buffer(24)
        ok: int = int(kernel32.GetFileInformationByHandleEx(
            handle,
            18,
            information,
            len(information),
        ))
        if ok == 0:
            raise OSError(ctypes.get_last_error(), "Cannot identify Windows runtime directory")
        else:
            volume_serial: int = int.from_bytes(information.raw[:8], "little", signed=False)
            file_id: bytes = information.raw[8:24]
        final_buffer = ctypes.create_unicode_buffer(32768)
        final_length: int = int(kernel32.GetFinalPathNameByHandleW(
            handle,
            ctypes.addressof(final_buffer),
            len(final_buffer),
            0,
        ))
        if final_length < 1 or final_length >= len(final_buffer):
            raise OSError(ctypes.get_last_error(), "Cannot canonicalize Windows runtime directory")
        else:
            system_directory = final_buffer.value
    finally:
        kernel32.CloseHandle(handle)
    return volume_serial, file_id, system_directory


def verify_manufacturer_native_worker(executable_path: Path,
                                      manifest_path: Path,
                                      expected_platform: IeeeCigreDllPlatform,
                                      expected_cache_key: str) -> ManufacturerNativeWorkerArtifact:
    """Verify one cached executable and manifest before selection.

    :param executable_path: Candidate worker executable.
    :param manifest_path: Candidate immutable manifest.
    :param expected_platform: Required current host platform.
    :param expected_cache_key: Required source/toolchain identity.
    :return: Verified worker artifact.
    """
    cache_directory: Path = executable_path.parent
    # Verify the directory itself before following any child path. On Windows,
    # junctions are reparse points even when pathlib does not call them symlinks.
    directory_information: os.stat_result = cache_directory.lstat()
    if cache_directory.is_symlink():
        raise RuntimeError("Prepared manufacturer worker cache directory is a link")
    else:
        if os.name == "nt" and directory_information.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise RuntimeError("Prepared manufacturer worker cache directory is a reparse point")
        else:
            pass
    if not executable_path.is_file() or executable_path.is_symlink():
        raise RuntimeError("Prepared manufacturer worker executable is missing")
    elif not manifest_path.is_file() or manifest_path.is_symlink():
        raise RuntimeError("Prepared manufacturer worker manifest is missing")
    else:
        manifest_raw: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest_raw, dict):
        raise TypeError("Prepared manufacturer worker manifest must be an object")
    else:
        manifest: dict[str, object] = manifest_raw
    executable_sha256: str = _file_sha256(executable_path)
    if expected_platform == IeeeCigreDllPlatform.WINDOWS_X86:
        expected_schema: int = 1
    else:
        expected_schema = 2
    if (
            manifest.get("schema", None) != expected_schema
            or manifest.get("cache_key", None) != expected_cache_key
            or manifest.get("platform", None) != expected_platform.value
            or manifest.get("executable_sha256", None) != executable_sha256
    ):
        raise RuntimeError("Prepared manufacturer worker manifest identity differs")
    else:
        pass
    if expected_platform in (
            IeeeCigreDllPlatform.WINDOWS_X86,
            IeeeCigreDllPlatform.WINDOWS_X64,
    ):
        machine: int = inspect_windows_pe_machine(executable_path.read_bytes())
        expected_machine: int = (
            0x014c
            if expected_platform == IeeeCigreDllPlatform.WINDOWS_X86
            else 0x8664
        )
        if machine != expected_machine:
            raise RuntimeError("Prepared manufacturer worker Windows machine differs")
        else:
            volume_serial, file_id, system_directory = _windows_system_identity(
                expected_platform
            )
    else:
        # Apply the same ELF architecture, dependency and RUNPATH policy used
        # for manufacturer libraries before trusting the cached worker.
        _inspect_native_binary(
            path=executable_path,
            platform=IeeeCigreDllPlatform.LINUX_X64,
            maximum_size=64 * 1024 * 1024,
        )
        volume_serial, file_id, system_directory = 0, bytes(16), ""
    return ManufacturerNativeWorkerArtifact(
        executable_path=executable_path,
        content_sha256=executable_sha256,
        platform=expected_platform,
        cache_key=expected_cache_key,
        system_volume_serial=volume_serial,
        system_file_id=file_id,
        system_directory=system_directory,
    )


def _packaged_windows_x86_cache_key(sources: tuple[Path, ...]) -> str:
    """Compute the reviewed packaged PE32 worker identity.

    :param sources: Common worker source set.
    :return: Lowercase SHA-256 package identity.
    """
    # Bind the common sources to the reviewed PE32 target and local tool owner.
    identity: bytes = (
        b"veragrid-manufacturer-worker-windows-x86-v1\x00"
        + bytes.fromhex(_source_digest(sources))
        + b"i686-w64-windows-gnu\x00local_llvm\x00ld.lld"
    )
    return hashlib.sha256(identity).hexdigest()


def resolve_packaged_windows_x86_worker() -> ManufacturerNativeWorkerArtifact:
    """Resolve the reviewed common-protocol PE32 worker without compilation.

    :return: Verified packaged worker for a Windows x64 parent.
    """
    if os.name != "nt" or struct.calcsize("P") != 8:
        raise RuntimeError("Windows x86 worker execution requires a Windows x64 parent")
    else:
        sources: tuple[Path, ...] = _worker_sources()
    cache_key: str = _packaged_windows_x86_cache_key(sources)
    package_directory: Path = Path(__file__).resolve().parent / "native_worker" / "windows_x86"
    return verify_manufacturer_native_worker(
        executable_path=package_directory / "veragrid-manufacturer-worker-x86.exe",
        manifest_path=package_directory / "manifest.json",
        expected_platform=IeeeCigreDllPlatform.WINDOWS_X86,
        expected_cache_key=cache_key,
    )


def resolve_manufacturer_native_worker(
    selection: NativeCompilerSelection | None = None,
    prepare_if_missing: bool = False,
) -> ManufacturerNativeWorkerArtifact:
    """Verify the expected worker and optionally prepare a genuinely absent cache.

    :param selection: Explicit provider selection or saved external LLVM.
    :param prepare_if_missing: Compile only when no entry exists at the cache path.
    :return: Verified cached artifact for the current x64 host.
    """
    platform: IeeeCigreDllPlatform = _host_platform()
    sources: tuple[Path, ...] = _worker_sources()
    if selection is None:
        saved_selection: NativeCompilerSelection | None = load_saved_local_llvm_selection()
        if saved_selection is None:
            raise RuntimeError("Manufacturer native execution requires a configured external LLVM installation")
        else:
            resolved_selection: NativeCompilerSelection = saved_selection
    else:
        resolved_selection = selection
    toolset: NativeCompilerToolset = resolve_native_compiler_toolset(resolved_selection)
    toolset.assert_unchanged()
    cache_key: str = _cache_identity(platform, sources, toolset)
    cache_directory: Path = Path.home() / ".veragrid" / "native-workers" / cache_key
    executable_name: str = "veragrid-manufacturer-worker.exe" if os.name == "nt" else "veragrid-manufacturer-worker"
    if os.path.lexists(cache_directory):
        return verify_manufacturer_native_worker(
            executable_path=cache_directory / executable_name,
            manifest_path=cache_directory / "manifest.json",
            expected_platform=platform,
            expected_cache_key=cache_key,
        )
    else:
        if prepare_if_missing:
            preparation: ManufacturerNativeWorkerPreparation = prepare_manufacturer_native_runtime(
                selection=resolved_selection,
            )
            if preparation.artifact.cache_key == cache_key:
                return preparation.artifact
            else:
                raise RuntimeError("Manufacturer compiler changed while preparing the worker")
        else:
            raise RuntimeError("Prepared manufacturer worker cache is absent")


def prepare_manufacturer_native_runtime(
    timeout_seconds: float = 60.0,
    selection: NativeCompilerSelection | None = None,
) -> ManufacturerNativeWorkerPreparation:
    """Compile and atomically cache the reviewed host-x64 worker when absent.

    :param timeout_seconds: Finite lock and compiler deadline.
    :param selection: Explicit provider selection or saved external LLVM.
    :return: Verified artifact plus whether compilation occurred.
    """
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0.0 or timeout_seconds > 300.0:
        raise ValueError("Manufacturer worker preparation timeout must be in (0, 300]")
    else:
        pass
    platform: IeeeCigreDllPlatform = _host_platform()
    sources: tuple[Path, ...] = _worker_sources()
    if selection is None:
        saved_selection: NativeCompilerSelection | None = load_saved_local_llvm_selection()
        if saved_selection is None:
            raise RuntimeError("Manufacturer worker preparation requires a configured external LLVM installation")
        else:
            resolved_selection: NativeCompilerSelection = saved_selection
    else:
        resolved_selection = selection
    toolset: NativeCompilerToolset = resolve_native_compiler_toolset(resolved_selection)
    toolset.assert_unchanged()
    cache_key: str = _cache_identity(platform, sources, toolset)
    cache_root: Path = Path.home() / ".veragrid" / "native-workers"
    cache_directory: Path = cache_root / cache_key
    executable_name: str = "veragrid-manufacturer-worker.exe" if os.name == "nt" else "veragrid-manufacturer-worker"
    if os.path.lexists(cache_directory):
        artifact: ManufacturerNativeWorkerArtifact = verify_manufacturer_native_worker(
            cache_directory / executable_name,
            cache_directory / "manifest.json",
            platform,
            cache_key,
        )
        return ManufacturerNativeWorkerPreparation(artifact, False)
    else:
        pass

    cache_root.mkdir(parents=True, exist_ok=True)
    lock_directory: Path = cache_root / (cache_key + ".lock")
    deadline: float = time.monotonic() + timeout_seconds
    lock_owned: bool = False
    while not lock_owned:
        try:
            lock_directory.mkdir()
            lock_owned = True
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError("Timed out waiting for manufacturer worker preparation lock")
            else:
                time.sleep(0.05)
    build_directory: Path = cache_root / (cache_key + ".building-" + str(os.getpid()))
    try:
        if os.path.lexists(cache_directory):
            artifact = verify_manufacturer_native_worker(
                cache_directory / executable_name,
                cache_directory / "manifest.json",
                platform,
                cache_key,
            )
            return ManufacturerNativeWorkerPreparation(artifact, False)
        else:
            pass
        if build_directory.exists():
            shutil.rmtree(build_directory)
        else:
            pass
        build_directory.mkdir()
        output_path: Path = build_directory / executable_name
        toolset.assert_unchanged()
        arguments: tuple[str, ...] = _compiler_arguments(platform, sources, output_path, toolset)
        completed: subprocess.CompletedProcess[str] = subprocess.run(
            [str(toolset.compiler_path), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=max(1.0, deadline - time.monotonic()),
            shell=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "The selected native compiler could not prepare the manufacturer worker: "
                + completed.stderr[-4096:]
            )
        else:
            pass
        executable_sha256: str = _file_sha256(output_path)
        manifest: dict[str, object] = {
            "schema": 2,
            "cache_key": cache_key,
            "platform": platform.value,
            "source_sha256": _source_digest(sources),
            "compiler_framework": toolset.framework.value,
            "compiler_provider_version": toolset.provider_version,
            "compiler_path": str(toolset.compiler_path),
            "compiler_tool_sha256": list(toolset.tool_hashes),
            "arguments": list(arguments),
            "executable_sha256": executable_sha256,
        }
        (build_directory / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        verify_manufacturer_native_worker(
            output_path,
            build_directory / "manifest.json",
            platform,
            cache_key,
        )
        if os.path.lexists(cache_directory):
            artifact = verify_manufacturer_native_worker(
                cache_directory / executable_name,
                cache_directory / "manifest.json",
                platform,
                cache_key,
            )
            return ManufacturerNativeWorkerPreparation(artifact, False)
        else:
            pass
        build_directory.replace(cache_directory)
        artifact = verify_manufacturer_native_worker(
            cache_directory / executable_name,
            cache_directory / "manifest.json",
            platform,
            cache_key,
        )
        return ManufacturerNativeWorkerPreparation(artifact, True)
    finally:
        if build_directory.exists():
            shutil.rmtree(build_directory)
        else:
            pass
        if lock_owned and lock_directory.exists():
            lock_directory.rmdir()
        else:
            pass
