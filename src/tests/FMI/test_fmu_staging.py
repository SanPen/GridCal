# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Focused tests for private, content-bound FMU staging."""

from __future__ import annotations

import os
from pathlib import Path
import zipfile

import pytest

from VeraGridEngine.IO.fmu.Elements.inspection import (
    FmuArchiveInspectionPolicy,
    FmuInspectionResult,
    inspect_fmu,
)
from VeraGridEngine.IO.fmu.staging import (
    FmuStagingArea,
    revalidate_fmu_staging_area,
    stage_fmu_source,
)


def _fmi_two_xml() -> bytes:
    """Return one minimal FMI 2.0 model description accepted by inspection.

    :return: UTF-8 XML bytes for a Co-Simulation FMU.
    """

    return (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<fmiModelDescription fmiVersion="2.0" modelName="stage" guid="stage-guid" '
        b'numberOfEventIndicators="0">\n'
        b'  <CoSimulation modelIdentifier="stage_model"/>\n'
        b'  <ModelVariables/>\n'
        b'</fmiModelDescription>\n'
    )


def _write_archive(
    path: Path,
    resource_bytes: bytes = b"resource-a",
    binary_bytes: bytes = b"native-a",
) -> Path:
    """Write one deterministic stored FMU archive for staging tests.

    :param path: Destination `.fmu` path.
    :param resource_bytes: Bytes stored below ``resources``.
    :param binary_bytes: Bytes stored below the Windows binary platform.
    :return: Written archive path.
    """

    entries: tuple[tuple[str, bytes], ...] = (
        ("modelDescription.xml", _fmi_two_xml()),
        ("resources/data.bin", resource_bytes),
        ("binaries/win64/stage_model.dll", binary_bytes),
        ("empty/", b""),
    )
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_STORED) as archive:
        entry: tuple[str, bytes]
        for entry in entries:
            info: zipfile.ZipInfo = zipfile.ZipInfo(entry[0], date_time=(2024, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, entry[1])
    return path


def _write_directory(path: Path, resource_bytes: bytes = b"resource-a") -> Path:
    """Write one extracted FMU tree including an empty directory.

    :param path: Root directory to create.
    :param resource_bytes: Bytes stored below ``resources``.
    :return: Created FMU directory.
    """

    resource_directory: Path = path / "resources"
    binary_directory: Path = path / "binaries" / "win64"
    empty_directory: Path = path / "empty"
    resource_directory.mkdir(parents=True)
    binary_directory.mkdir(parents=True)
    empty_directory.mkdir()
    (path / "modelDescription.xml").write_bytes(_fmi_two_xml())
    (resource_directory / "data.bin").write_bytes(resource_bytes)
    (binary_directory / "stage_model.dll").write_bytes(b"native-a")
    return path


def _staging_children(parent: Path) -> tuple[Path, ...]:
    """Return the current private staging children below one test parent.

    :param parent: Caller-owned staging parent.
    :return: Sorted child paths whose names use the staging prefix.
    """

    children: tuple[Path, ...] = tuple(sorted(parent.glob("veragrid_fmu_stage_*")))
    return children


def test_archive_staging_retains_exact_private_source_and_tree(tmp_path: Path) -> None:
    """Verify a ZIP is copied, extracted, and retained below one owned child.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_archive(tmp_path / "source.fmu")
    source_bytes: bytes = source.read_bytes()
    inspection: FmuInspectionResult = inspect_fmu(source)
    staging_parent: Path = tmp_path / "staging"
    sentinel: Path = staging_parent / "keep.txt"
    staging_parent.mkdir()
    sentinel.write_text("caller-owned", encoding="utf-8")

    with stage_fmu_source(source, inspection.receipt, staging_parent=staging_parent) as staging:
        assert isinstance(staging, FmuStagingArea)
        assert staging.get_root().parent == staging_parent.resolve()
        assert staging.get_root() != staging_parent.resolve()
        assert staging.get_source_copy() is not None
        assert staging.get_source_copy().read_bytes() == source_bytes
        assert staging.get_source_receipt().path == staging.get_source_copy()
        assert staging.get_fmu_directory_receipt().path == staging.get_fmu_directory()
        assert revalidate_fmu_staging_area(staging).path == staging.get_fmu_directory()
        assert (staging.get_fmu_directory() / "resources" / "data.bin").read_bytes() == b"resource-a"
        assert (staging.get_fmu_directory() / "empty").is_dir()
        assert sentinel.read_text(encoding="utf-8") == "caller-owned"
        owned_root: Path = staging.get_root()

    assert not owned_root.exists()
    assert sentinel.read_text(encoding="utf-8") == "caller-owned"
    assert source.read_bytes() == source_bytes


def test_directory_staging_is_a_private_snapshot(tmp_path: Path) -> None:
    """Verify an extracted source is copied and no longer consumed in place.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_directory(tmp_path / "source")
    inspection: FmuInspectionResult = inspect_fmu(source)
    staging: FmuStagingArea = stage_fmu_source(
        source,
        inspection.receipt,
        staging_parent=tmp_path / "staging",
    )
    staged_resource: Path = staging.get_fmu_directory() / "resources" / "data.bin"
    try:
        assert staging.get_source_copy() is None
        assert staging.get_fmu_directory() != source.resolve()
        assert staging.get_source_receipt().path == staging.get_fmu_directory()
        assert staging.get_fmu_directory_receipt().path == staging.get_fmu_directory()
        assert staged_resource.read_bytes() == b"resource-a"
        (source / "resources" / "data.bin").write_bytes(b"resource-b")
        assert staged_resource.read_bytes() == b"resource-a"
    finally:
        staging.close()


def test_archive_changed_after_inspection_is_rejected_and_cleaned(tmp_path: Path) -> None:
    """Verify a same-size source replacement cannot reach private extraction.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_archive(tmp_path / "changed.fmu", resource_bytes=b"resource-a")
    inspection: FmuInspectionResult = inspect_fmu(source)
    original_size: int = source.stat().st_size
    _write_archive(source, resource_bytes=b"resource-b")
    replacement_size: int = source.stat().st_size
    staging_parent: Path = tmp_path / "staging"

    assert replacement_size == original_size
    with pytest.raises(ValueError, match="content changed"):
        stage_fmu_source(source, inspection.receipt, staging_parent=staging_parent)
    assert _staging_children(staging_parent) == tuple()


def test_directory_changed_after_inspection_is_rejected_and_cleaned(tmp_path: Path) -> None:
    """Verify a same-size directory mutation cannot become the private snapshot.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_directory(tmp_path / "changed", resource_bytes=b"resource-a")
    inspection: FmuInspectionResult = inspect_fmu(source)
    (source / "resources" / "data.bin").write_bytes(b"resource-b")
    staging_parent: Path = tmp_path / "staging"

    with pytest.raises(ValueError, match="content changed"):
        stage_fmu_source(source, inspection.receipt, staging_parent=staging_parent)
    assert _staging_children(staging_parent) == tuple()


def test_receipt_from_another_source_is_rejected_before_staging(tmp_path: Path) -> None:
    """Verify receipt ownership is checked before allocating a private child.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    first_source: Path = _write_archive(tmp_path / "first.fmu")
    second_source: Path = _write_archive(tmp_path / "second.fmu")
    first_inspection: FmuInspectionResult = inspect_fmu(first_source)
    staging_parent: Path = tmp_path / "staging"

    with pytest.raises(ValueError, match="different source path"):
        stage_fmu_source(second_source, first_inspection.receipt, staging_parent=staging_parent)
    assert not staging_parent.exists()


def test_copy_limit_failure_removes_only_private_child(tmp_path: Path) -> None:
    """Verify a bounded-copy failure preserves its caller-owned parent and sibling.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_archive(tmp_path / "limited.fmu")
    inspection: FmuInspectionResult = inspect_fmu(source)
    staging_parent: Path = tmp_path / "staging"
    staging_parent.mkdir()
    sentinel: Path = staging_parent / "keep.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    restrictive_policy: FmuArchiveInspectionPolicy = FmuArchiveInspectionPolicy(
        max_archive_bytes=source.stat().st_size - 1
    )

    with pytest.raises(ValueError, match="byte limit"):
        stage_fmu_source(
            source,
            inspection.receipt,
            staging_parent=staging_parent,
            inspection_policy=restrictive_policy,
        )
    assert _staging_children(staging_parent) == tuple()
    assert sentinel.read_text(encoding="utf-8") == "preserve"


def test_staging_areas_have_unique_children_and_idempotent_cleanup(tmp_path: Path) -> None:
    """Verify independent owners never share or over-delete temporary state.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_archive(tmp_path / "unique.fmu")
    inspection: FmuInspectionResult = inspect_fmu(source)
    staging_parent: Path = tmp_path / "staging"
    first: FmuStagingArea = stage_fmu_source(source, inspection.receipt, staging_parent=staging_parent)
    second: FmuStagingArea = stage_fmu_source(source, inspection.receipt, staging_parent=staging_parent)
    first_root: Path = first.get_root()
    second_root: Path = second.get_root()
    try:
        assert first_root != second_root
        assert first_root.exists()
        assert second_root.exists()
        first.close()
        first.close()
        assert first.is_closed()
        assert not first_root.exists()
        assert second_root.exists()
    finally:
        first.close()
        second.close()
    assert not second_root.exists()


def test_unclosed_staging_survives_owner_garbage_collection(tmp_path: Path) -> None:
    """Verify garbage collection cannot erase explicitly retained diagnostics.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_archive(tmp_path / "retained.fmu")
    inspection: FmuInspectionResult = inspect_fmu(source)
    staging: FmuStagingArea = stage_fmu_source(
        source,
        inspection.receipt,
        staging_parent=tmp_path / "staging",
    )
    staging_root: Path = staging.get_root()

    del staging
    assert staging_root.is_dir()


def test_file_staging_parent_is_rejected_without_modification(tmp_path: Path) -> None:
    """Verify a caller-owned file cannot be reinterpreted as a staging parent.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_archive(tmp_path / "source.fmu")
    inspection: FmuInspectionResult = inspect_fmu(source)
    invalid_parent: Path = tmp_path / "parent.txt"
    invalid_parent.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="prepare FMU staging parent"):
        stage_fmu_source(source, inspection.receipt, staging_parent=invalid_parent)
    assert invalid_parent.read_text(encoding="utf-8") == "keep"


def test_source_link_is_rejected_before_private_allocation(tmp_path: Path) -> None:
    """Verify source links never become staging inputs when the host permits links.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_archive(tmp_path / "source.fmu")
    inspection: FmuInspectionResult = inspect_fmu(source)
    source_link: Path = tmp_path / "source-link.fmu"
    staging_parent: Path = tmp_path / "staging"
    try:
        os.symlink(source, source_link)
        link_created: bool = True
    except OSError:
        link_created = False

    if link_created:
        with pytest.raises(ValueError, match="source path links"):
            stage_fmu_source(source_link, inspection.receipt, staging_parent=staging_parent)
        assert not staging_parent.exists()
    else:
        pytest.skip("The current host does not permit symbolic-link creation")


def test_original_archive_and_directory_remain_unchanged(tmp_path: Path) -> None:
    """Verify staging performs no writes to either supported source representation.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    archive_source: Path = _write_archive(tmp_path / "source.fmu")
    directory_source: Path = _write_directory(tmp_path / "source-directory")
    archive_bytes: bytes = archive_source.read_bytes()
    directory_receipt: str = inspect_fmu(directory_source).receipt.sha256
    archive_inspection: FmuInspectionResult = inspect_fmu(archive_source)
    directory_inspection: FmuInspectionResult = inspect_fmu(directory_source)

    archive_staging: FmuStagingArea = stage_fmu_source(archive_source, archive_inspection.receipt)
    directory_staging: FmuStagingArea = stage_fmu_source(directory_source, directory_inspection.receipt)
    assert archive_staging.get_root().parent == archive_source.parent.resolve()
    assert directory_staging.get_root().parent == directory_source.parent.resolve()
    archive_staging.close()
    directory_staging.close()

    assert archive_source.read_bytes() == archive_bytes
    assert inspect_fmu(directory_source).receipt.sha256 == directory_receipt


def test_revalidation_rejects_same_size_resource_mutation(tmp_path: Path) -> None:
    """Verify the staged tree receipt detects changed bytes of equal length.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_archive(tmp_path / "source.fmu", resource_bytes=b"resource-a")
    inspection: FmuInspectionResult = inspect_fmu(source)
    staging: FmuStagingArea = stage_fmu_source(source, inspection.receipt)
    staged_resource: Path = staging.get_fmu_directory() / "resources" / "data.bin"
    try:
        staged_resource.write_bytes(b"resource-b")
        assert staged_resource.stat().st_size == len(b"resource-a")
        with pytest.raises(ValueError, match="differs from its archive"):
            revalidate_fmu_staging_area(staging)
    finally:
        staging.close()


def test_revalidation_rejects_missing_and_unexpected_files(tmp_path: Path) -> None:
    """Verify exact revalidation rejects both missing and additional payloads.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_archive(tmp_path / "source.fmu")
    inspection: FmuInspectionResult = inspect_fmu(source)
    missing_staging: FmuStagingArea = stage_fmu_source(source, inspection.receipt)
    extra_staging: FmuStagingArea = stage_fmu_source(source, inspection.receipt)
    try:
        (missing_staging.get_fmu_directory() / "resources" / "data.bin").unlink()
        with pytest.raises(ValueError, match="unavailable"):
            revalidate_fmu_staging_area(missing_staging)

        unexpected_file: Path = extra_staging.get_fmu_directory() / "resources" / "extra.bin"
        unexpected_file.write_bytes(b"extra")
        with pytest.raises(ValueError, match="missing or unexpected paths"):
            revalidate_fmu_staging_area(extra_staging)
    finally:
        missing_staging.close()
        extra_staging.close()


def test_revalidation_rejects_unexpected_empty_directory(tmp_path: Path) -> None:
    """Verify exact tree comparison includes empty directory structure.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_archive(tmp_path / "source.fmu")
    inspection: FmuInspectionResult = inspect_fmu(source)
    staging: FmuStagingArea = stage_fmu_source(source, inspection.receipt)
    try:
        (staging.get_fmu_directory() / "unexpected-empty").mkdir()
        with pytest.raises(ValueError, match="missing or unexpected paths"):
            revalidate_fmu_staging_area(staging)
    finally:
        staging.close()


def test_linked_ancestor_is_rejected_for_source_and_parent(tmp_path: Path) -> None:
    """Verify no existing ancestor can redirect source or staging traversal.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    real_root: Path = tmp_path / "real"
    real_root.mkdir()
    source: Path = _write_archive(real_root / "source.fmu")
    inspection: FmuInspectionResult = inspect_fmu(source)
    linked_root: Path = tmp_path / "linked"
    try:
        os.symlink(real_root, linked_root, target_is_directory=True)
        link_created: bool = True
    except OSError:
        link_created = False

    if link_created:
        with pytest.raises(ValueError, match="source path links"):
            stage_fmu_source(linked_root / "source.fmu", inspection.receipt)
        with pytest.raises(ValueError, match="staging parent path links"):
            stage_fmu_source(source, inspection.receipt, staging_parent=linked_root / "stage")
        assert not (real_root / "stage").exists()
    else:
        pytest.skip("The current host does not permit directory-link creation")


def test_directory_link_introduced_after_inspection_is_rejected(tmp_path: Path) -> None:
    """Verify a linked payload cannot replace an inspected regular source file.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_directory(tmp_path / "source")
    inspection: FmuInspectionResult = inspect_fmu(source)
    resource: Path = source / "resources" / "data.bin"
    external_resource: Path = tmp_path / "external.bin"
    external_resource.write_bytes(resource.read_bytes())
    resource.unlink()
    try:
        os.symlink(external_resource, resource)
        link_created: bool = True
    except OSError:
        link_created = False

    if link_created:
        staging_parent: Path = tmp_path / "staging"
        with pytest.raises(ValueError, match="not a regular file"):
            stage_fmu_source(source, inspection.receipt, staging_parent=staging_parent)
        assert _staging_children(staging_parent) == tuple()
        assert external_resource.read_bytes() == b"resource-a"
    else:
        pytest.skip("The current host does not permit symbolic-link creation")


def test_directory_source_rejects_nested_staging_parents_before_writing(tmp_path: Path) -> None:
    """Verify staging cannot recursively create its snapshot below the source.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_directory(tmp_path / "source")
    inspection: FmuInspectionResult = inspect_fmu(source)
    original_digest: str = inspection.receipt.sha256
    nested_parents: tuple[Path, ...] = (
        source,
        source / "runtime",
        source / "resources",
    )

    nested_parent: Path
    for nested_parent in nested_parents:
        with pytest.raises(ValueError, match="cannot be inside"):
            stage_fmu_source(source, inspection.receipt, staging_parent=nested_parent)
        assert inspect_fmu(source).receipt.sha256 == original_digest
    assert not (source / "runtime").exists()
