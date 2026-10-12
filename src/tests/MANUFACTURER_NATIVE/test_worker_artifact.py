# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from VeraGridEngine.enumerations import IeeeCigreDllPlatform, NativeCompilerFramework
from VeraGridEngine.IO.manufacturer_native.worker_artifact import (
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


@pytest.mark.usefixtures("_supported_worker_host")
def test_prepare_then_resolve_reuses_verified_content_cache() -> None:
    """Prepare explicitly once and resolve the identical artifact without compilation.

    :return: None.
    """
    selection: NativeCompilerSelection | None = load_saved_local_llvm_selection()
    if selection is None:
        pytest.skip("External LLVM is not configured")
    else:
        pass
    first = prepare_manufacturer_native_runtime(timeout_seconds=60.0, selection=selection)
    second = prepare_manufacturer_native_runtime(timeout_seconds=60.0, selection=selection)
    resolved = resolve_manufacturer_native_worker(selection=selection)

    assert first.artifact.cache_key == second.artifact.cache_key
    assert second.compiled is False
    assert resolved.cache_key == first.artifact.cache_key
    assert resolved.content_sha256 == first.artifact.content_sha256
    assert resolved.executable_path == first.artifact.executable_path


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
