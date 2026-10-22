# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import struct
from typing import BinaryIO

import pytest

from VeraGridEngine.enumerations import IeeeCigreDllPlatform, NativeCompilerFramework
from VeraGridEngine.IO.manufacturer_native.worker_artifact import (
    ManufacturerNativeWorkerArtifact,
    ManufacturerNativeWorkerPreparation,
    _host_platform,
    _worker_sources,
    prepare_manufacturer_native_runtime,
    resolve_manufacturer_native_worker,
    verify_manufacturer_native_worker,
)
from VeraGridEngine.IO.native_compiler.compiler_interface import NativeCompilerSelection
from VeraGridEngine.IO.native_compiler.selected_interface import load_saved_local_llvm_selection


@pytest.fixture
def _supported_worker_host() -> IeeeCigreDllPlatform:
    """Admit worker runtime tests through the existing host selector.

    :return: Supported host platform, or a pytest skip for an unsupported host.
    """
    try:
        platform: IeeeCigreDllPlatform = _host_platform()
    except RuntimeError as error:
        pytest.skip(str(error))
    else:
        return platform


def test_worker_source_package_is_complete_and_source_only() -> None:
    """Require every reviewed C unit and exclude compiled artifacts.

    :return: None.
    """
    sources: tuple[Path, ...] = _worker_sources()
    names: set[str] = {source.name for source in sources}
    expected_names: set[str] = {
        "worker.c",
        "platform_windows.c",
        "platform_linux.c",
        "adapter_ieee_cigre_v1_1.c",
        "adapter_ieee_cigre_v1_0.c",
        "adapter_iec_ese.c",
        "platform.h",
        "platform_hash.c",
        "protocol.h",
        "protocol.c",
        "adapter_ieee_cigre_v1_1.h",
        "adapter_common.h",
        "adapter_ieee_cigre_v1_0.h",
        "adapter_iec_ese.h",
    }

    assert names == expected_names
    source: Path
    for source in sources:
        assert source.is_file()
        assert not source.is_symlink()
        assert source.suffix in (".c", ".h")
        assert "SPDX-License-Identifier: MPL-2.0" in source.read_text(encoding="utf-8")
    assert not tuple(sources[0].parent.parent.rglob("*.exe"))


def _write_x86_worker_cache_candidate(
    candidate: Path,
    manifest_path: Path,
    artifact: ManufacturerNativeWorkerArtifact,
    content: bytes,
) -> None:
    """Write a private candidate with matching metadata to test PE32 admission.

    :param candidate: Owned executable copy to mutate.
    :param manifest_path: Owned cache manifest copy.
    :param artifact: Verified worker supplying the original cache metadata.
    :param content: Candidate bytes whose headers or dependencies may be invalid.
    :return: None.
    """
    candidate.write_bytes(content)
    manifest_raw: object = json.loads(
        (artifact.executable_path.parent / "manifest.json").read_text(encoding="utf-8")
    )
    assert isinstance(manifest_raw, dict)
    manifest: dict[str, object] = manifest_raw
    # Keep the digest consistent so header/dependency rejection is exercised
    # independently of the earlier cache-integrity check.
    manifest["executable_sha256"] = hashlib.sha256(content).hexdigest()
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")


def test_cached_worker_rejects_invalid_identity(tmp_path: Path) -> None:
    """Require cache metadata and reject malformed or redirected PE32 bytes.

    :param tmp_path: Owned directory for damaged copies of the cached worker.
    :return: None; invalid arguments/images fail before any worker launch.
    """
    candidate: Path = tmp_path / "worker.exe"
    manifest_path: Path = tmp_path / "manifest.json"
    with pytest.raises(RuntimeError, match="executable is missing"):
        verify_manufacturer_native_worker(candidate, manifest_path, IeeeCigreDllPlatform.WINDOWS_X86, "0" * 64)
    if os.name != "nt" or struct.calcsize("P") != 8:
        pytest.skip("Cached PE32 image checks require a Windows x64 parent")
    else:
        pass
    artifact: ManufacturerNativeWorkerArtifact = resolve_manufacturer_native_worker(
        prepare_if_missing=True,
        platform=IeeeCigreDllPlatform.WINDOWS_X86,
    )
    original: bytes = artifact.executable_path.read_bytes()
    offset: int = struct.unpack_from("<I", original, 0x3c)[0]
    # Both the machine field and optional-header format belong to the full PE
    # admission policy. Neither a digest nor the protocol may admit bad headers.
    field_offset: int
    replacement: int
    for field_offset, replacement in ((offset + 4, 0x8664), (offset + 24, 0x20b)):
        damaged: bytearray = bytearray(original)
        struct.pack_into("<H", damaged, field_offset, replacement)
        _write_x86_worker_cache_candidate(candidate, manifest_path, artifact, bytes(damaged))
        with pytest.raises(ValueError, match="does not match"):
            verify_manufacturer_native_worker(candidate, manifest_path, IeeeCigreDllPlatform.WINDOWS_X86, artifact.cache_key)
    _write_x86_worker_cache_candidate(candidate, manifest_path, artifact, original[:64])
    with pytest.raises(ValueError):
        verify_manufacturer_native_worker(candidate, manifest_path, IeeeCigreDllPlatform.WINDOWS_X86, artifact.cache_key)
    original_lower: bytes = original.lower()
    dependency_offset: int = original_lower.find(b"kernel32.dll")
    assert dependency_offset >= 0
    damaged = bytearray(original)
    # The executable may also carry the OS basename in diagnostic strings.
    # Alter every occurrence so the actual import name is included as well.
    while dependency_offset >= 0:
        damaged[dependency_offset:dependency_offset + 12] = b"evil0000.dll"
        dependency_offset = original_lower.find(b"kernel32.dll", dependency_offset + 12)
    _write_x86_worker_cache_candidate(candidate, manifest_path, artifact, bytes(damaged))
    with pytest.raises(ValueError, match="outside"):
        verify_manufacturer_native_worker(candidate, manifest_path, IeeeCigreDllPlatform.WINDOWS_X86, artifact.cache_key)
    _write_x86_worker_cache_candidate(candidate, manifest_path, artifact, original)
    with pytest.raises(RuntimeError, match="manifest is missing"):
        verify_manufacturer_native_worker(candidate, tmp_path / "absent.json", IeeeCigreDllPlatform.WINDOWS_X86, artifact.cache_key)
    with pytest.raises(RuntimeError, match="manifest identity differs"):
        verify_manufacturer_native_worker(candidate, manifest_path, IeeeCigreDllPlatform.WINDOWS_X86, "0" * 64)
    # A legacy x86 cache cannot bypass the common schema2 manifest checks.
    manifest_raw: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest_raw, dict)
    manifest: dict[str, object] = manifest_raw
    manifest["schema"] = 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="manifest identity differs"):
        verify_manufacturer_native_worker(candidate, manifest_path, IeeeCigreDllPlatform.WINDOWS_X86, artifact.cache_key)
    _write_x86_worker_cache_candidate(candidate, manifest_path, artifact, original)
    stream: BinaryIO
    with candidate.open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(RuntimeError, match="manifest identity differs"):
        verify_manufacturer_native_worker(candidate, manifest_path, IeeeCigreDllPlatform.WINDOWS_X86, artifact.cache_key)
    _write_x86_worker_cache_candidate(candidate, manifest_path, artifact, original)
    redirected: Path = tmp_path / "redirected"
    try:
        redirected.symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pass
    else:
        with pytest.raises(RuntimeError, match="cache directory is a link"):
            verify_manufacturer_native_worker(redirected / candidate.name, redirected / manifest_path.name, IeeeCigreDllPlatform.WINDOWS_X86, artifact.cache_key)


@pytest.mark.usefixtures("_supported_worker_host")
@pytest.mark.parametrize("platform", (None, IeeeCigreDllPlatform.WINDOWS_X86))
def test_prepare_then_resolve_reuses_verified_content_cache(
    platform: IeeeCigreDllPlatform | None,
) -> None:
    """Prepare explicitly once and resolve the identical artifact without compilation.

    :param platform: Native default or explicit PE32 cache target.
    :return: None.
    """
    selection: NativeCompilerSelection | None = load_saved_local_llvm_selection()
    if selection is None:
        pytest.skip("External LLVM is not configured")
    else:
        pass
    if platform == IeeeCigreDllPlatform.WINDOWS_X86 and _host_platform() != IeeeCigreDllPlatform.WINDOWS_X64:
        pytest.skip("PE32 cache preparation requires a Windows x64 parent")
    else:
        pass
    first: ManufacturerNativeWorkerPreparation = prepare_manufacturer_native_runtime(
        timeout_seconds=60.0, selection=selection, platform=platform,
    )
    modification_time: int = first.artifact.executable_path.stat().st_mtime_ns
    second: ManufacturerNativeWorkerPreparation = prepare_manufacturer_native_runtime(
        timeout_seconds=60.0, selection=selection, platform=platform,
    )
    resolved: ManufacturerNativeWorkerArtifact = resolve_manufacturer_native_worker(
        selection=selection, platform=platform,
    )

    assert first.artifact.cache_key == second.artifact.cache_key
    assert second.compiled is False
    assert resolved.cache_key == first.artifact.cache_key
    assert resolved.content_sha256 == first.artifact.content_sha256
    assert resolved.executable_path == first.artifact.executable_path
    assert resolved.executable_path.stat().st_mtime_ns == modification_time


@pytest.mark.usefixtures("_supported_worker_host")
def test_worker_verification_rejects_changed_executable(tmp_path: Path) -> None:
    """Reject changed worker bytes and redirected cache directories.

    :param tmp_path: Private pytest directory used for the tampered copy.
    :return: None.
    """
    broken: bool
    for broken in (False, True):
        target_directory: Path = tmp_path / ("target-broken" if broken else "target-live")
        target_directory.mkdir()
        cache_directory: Path = tmp_path / ("cache-broken" if broken else "cache-live")
        try:
            cache_directory.symlink_to(target_directory, target_is_directory=True)
        except OSError:
            linked: bool = False
        else:
            linked = True
        if linked:
            if broken:
                target_directory.rmdir()
            else:
                pass
            with pytest.raises(RuntimeError, match="cache directory is a link"):
                verify_manufacturer_native_worker(
                    executable_path=cache_directory / "worker.exe",
                    manifest_path=cache_directory / "manifest.json",
                    expected_platform=IeeeCigreDllPlatform.WINDOWS_X64,
                    expected_cache_key="0" * 64,
                )
        else:
            pass
    selection: NativeCompilerSelection | None = load_saved_local_llvm_selection()
    if selection is None:
        pytest.skip("External LLVM is not configured")
    else:
        pass
    prepared = prepare_manufacturer_native_runtime(timeout_seconds=60.0, selection=selection)
    source_manifest: Path = prepared.artifact.executable_path.parent / "manifest.json"
    copied_executable: Path = tmp_path / prepared.artifact.executable_path.name
    copied_manifest: Path = tmp_path / "manifest.json"
    shutil.copyfile(prepared.artifact.executable_path, copied_executable)
    shutil.copyfile(source_manifest, copied_manifest)
    with copied_executable.open("ab") as stream:
        stream.write(b"tampered")

    manifest: object = json.loads(copied_manifest.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)
    with pytest.raises(RuntimeError, match="manifest identity differs"):
        verify_manufacturer_native_worker(
            executable_path=copied_executable,
            manifest_path=copied_manifest,
            expected_platform=prepared.artifact.platform,
            expected_cache_key=prepared.artifact.cache_key,
        )


@pytest.mark.usefixtures("_supported_worker_host")
def test_worker_artifact_uses_local_llvm() -> None:
    """Build and resolve the worker with an explicit LOCAL_LLVM provider."""

    local_selection: NativeCompilerSelection | None = load_saved_local_llvm_selection()
    if local_selection is None:
        pytest.skip("External LLVM is not configured")
    else:
        pass
    prepared: ManufacturerNativeWorkerPreparation = prepare_manufacturer_native_runtime(
        selection=local_selection
    )
    resolved = resolve_manufacturer_native_worker(selection=local_selection)
    manifest_raw: object = json.loads(
        (prepared.artifact.executable_path.parent / "manifest.json").read_text(encoding="utf-8")
    )
    assert isinstance(manifest_raw, dict)
    assert manifest_raw.get("compiler_framework", None) == NativeCompilerFramework.LOCAL_LLVM.value
    assert resolved.cache_key == prepared.artifact.cache_key




@pytest.mark.usefixtures("_supported_worker_host")
def test_worker_artifact_rebuilds_legacy_manifest_schema(tmp_path: Path) -> None:
    """Reject a stale manifest without altering a user's real worker cache.

    :param tmp_path: Private directory for the invalid cache copy.
    :return: None.
    """

    local_selection: NativeCompilerSelection | None = load_saved_local_llvm_selection()
    if local_selection is None:
        pytest.skip("External LLVM is not configured")
    else:
        pass
    initial: ManufacturerNativeWorkerPreparation = prepare_manufacturer_native_runtime(
        selection=local_selection
    )
    copied_executable: Path = tmp_path / initial.artifact.executable_path.name
    manifest_path: Path = tmp_path / "manifest.json"
    shutil.copyfile(initial.artifact.executable_path, copied_executable)
    shutil.copyfile(initial.artifact.executable_path.parent / "manifest.json", manifest_path)
    manifest_raw: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest_raw, dict)
    manifest_raw["schema"] = 1
    manifest_path.write_text(
        json.dumps(manifest_raw, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="manifest identity differs"):
        verify_manufacturer_native_worker(
            executable_path=copied_executable,
            manifest_path=manifest_path,
            expected_platform=initial.artifact.platform,
            expected_cache_key=initial.artifact.cache_key,
        )
