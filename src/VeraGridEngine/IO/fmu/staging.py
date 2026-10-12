# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Private, content-bound staging for inspected FMU sources."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from types import TracebackType
from typing import BinaryIO
import zipfile

from VeraGridEngine.enumerations import FmuSourceKind
from VeraGridEngine.IO.fmu.Elements.inspection import (
    FmuArchiveInspectionPolicy,
    FmuInspectionReceipt,
    FmuInspectionResult,
    hash_fmu_stream,
    inspect_fmu,
    is_fmu_link_or_reparse_point,
    validate_fmu_zip_entry,
)


class FmuStagingArea:
    """Own one temporary FMU snapshot and its complete lifetime.

    Staging proves that the private snapshot matches an earlier inspection.
    It does not approve native code and does not provide process isolation.

    :param root: Exact private staging child owned by this instance.
    :param staging_parent: Caller-owned parent that cleanup must preserve.
    :param fmu_directory: Private extracted or copied FMU directory.
    :param source_copy: Private copy of the source archive, when applicable.
    :param source_receipt: Receipt for the private source representation.
    :param fmu_directory_receipt: Receipt for the private tree a runtime may consume.
    """

    __slots__ = (
        "_root",
        "_staging_parent",
        "_fmu_directory",
        "_source_copy",
        "_source_receipt",
        "_fmu_directory_receipt",
        "_closed",
    )

    def __init__(
        self,
        root: Path,
        staging_parent: Path,
        fmu_directory: Path,
        source_copy: Path | None,
        source_receipt: FmuInspectionReceipt,
        fmu_directory_receipt: FmuInspectionReceipt,
    ) -> None:
        """Store the verified snapshot and its unique cleanup owner.

        :param root: Exact private staging child owned by this instance.
        :param staging_parent: Caller-owned parent that cleanup must preserve.
        :param fmu_directory: Private extracted or copied FMU directory.
        :param source_copy: Private source archive or ``None`` for a directory source.
        :param source_receipt: Receipt for the private source representation.
        :param fmu_directory_receipt: Receipt for the private runtime tree.
        :return: None.
        """

        self._root: Path = root.resolve()
        self._staging_parent: Path = staging_parent.resolve()
        self._fmu_directory: Path = fmu_directory
        self._source_copy: Path | None = source_copy
        self._source_receipt: FmuInspectionReceipt = source_receipt
        self._fmu_directory_receipt: FmuInspectionReceipt = fmu_directory_receipt
        self._closed: bool = False

    def get_root(self) -> Path:
        """Return the exact temporary child owned by this staging area.

        :return: Private staging root removed by :meth:`close`.
        """

        return self._root

    def get_fmu_directory(self) -> Path:
        """Return the private FMU directory intended for a future runtime.

        :return: Verified extracted or copied FMU directory.
        """

        return self._fmu_directory

    def get_source_copy(self) -> Path | None:
        """Return the retained private archive copy when the source was a ZIP.

        :return: Private archive path or ``None`` for a directory source.
        """

        return self._source_copy

    def get_source_receipt(self) -> FmuInspectionReceipt:
        """Return the receipt produced from the private source representation.

        :return: Archive-copy receipt, or tree receipt for a directory source.
        """

        return self._source_receipt

    def get_fmu_directory_receipt(self) -> FmuInspectionReceipt:
        """Return the receipt for the private tree a future runtime may consume.

        :return: Receipt whose path is always :meth:`get_fmu_directory`.
        """

        return self._fmu_directory_receipt

    def is_closed(self) -> bool:
        """Return whether the private staging child has been released.

        :return: ``True`` after :meth:`close` completed.
        """

        return self._closed

    def close(self) -> None:
        """Remove only the unique temporary child owned by this instance.

        :return: None.
        """

        if self._closed:
            pass
        else:
            # Revalidate the allocation boundary before deletion so only the
            # unique child created for this owner can ever become the target.
            if (
                self._root.parent == self._staging_parent
                and self._root.name.startswith("veragrid_fmu_stage_")
            ):
                pass
            else:
                raise ValueError("FMU staging ownership boundary is invalid")
            try:
                shutil.rmtree(self._root)
            except FileNotFoundError:
                # An already absent exact child is equivalent to completed
                # cleanup, while every other filesystem error remains visible.
                pass
            self._closed = True

    def __enter__(self) -> "FmuStagingArea":
        """Return this staging owner for context-manager use.

        :return: Active staging owner.
        """

        return self

    def __exit__(
        self,
        exc_tpe: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback_value: TracebackType | None,
    ) -> None:
        """Release the private staging child when leaving its scope.

        :param exc_tpe: Exception type raised inside the context, if any.
        :param exc_value: Exception raised inside the context, if any.
        :param traceback_value: Exception traceback raised inside the context, if any.
        :return: None.
        """

        self.close()


def _raise_staging_walk_error(error: OSError) -> None:
    """Translate a directory traversal failure to the FMI import boundary.

    :param error: Filesystem error raised while traversing a source or snapshot.
    :return: None.
    :raises ValueError: Always, with the original error attached.
    """

    raise ValueError(f"Could not traverse an FMU during staging: {error}") from error


def _validate_matching_receipts(
    expected: FmuInspectionReceipt,
    observed: FmuInspectionReceipt,
    operation: str,
) -> None:
    """Require two receipts to describe identical source representations.

    Paths are intentionally excluded because staging creates a private copy.
    The receipt owns the single definition of source-content identity.

    :param expected: Receipt obtained before staging began.
    :param observed: Receipt obtained from the private or re-read source.
    :param operation: Human-readable operation used in validation errors.
    :return: None.
    :raises ValueError: If the observed representation differs.
    """

    matches: bool = expected.has_same_source_content(observed)
    if matches:
        pass
    else:
        raise ValueError(f"FMU content changed during {operation}")


def _validate_source_receipt(source: Path, receipt: FmuInspectionReceipt) -> None:
    """Require an inspection receipt to belong to the requested source path.

    :param source: Resolved regular archive or directory source.
    :param receipt: Earlier bounded-inspection receipt.
    :return: None.
    :raises ValueError: If the receipt belongs to another path or kind.
    """

    if source == receipt.path:
        pass
    else:
        raise ValueError("FMU staging receipt belongs to a different source path")
    if source.is_file():
        actual_kind: FmuSourceKind = FmuSourceKind.ZIP
    else:
        actual_kind = FmuSourceKind.DIRECTORY
    if actual_kind == receipt.source_kind:
        pass
    else:
        raise ValueError("FMU staging receipt source kind does not match the source")


def _validate_path_components(path: Path, operation: str) -> None:
    """Reject links and reparse points in every existing path component.

    :param path: Source or staging-parent path to validate without resolving links.
    :param operation: Human-readable path role used in validation errors.
    :return: None.
    :raises ValueError: If an existing component redirects traversal.
    """

    absolute_path: Path = path.absolute()
    current_path: Path = Path(absolute_path.anchor)
    path_parts: tuple[str, ...] = absolute_path.parts
    component_index: int = 1
    while component_index < len(path_parts):
        current_path = current_path / path_parts[component_index]
        if current_path.exists() or current_path.is_symlink():
            if is_fmu_link_or_reparse_point(current_path):
                raise ValueError(
                    f"FMU {operation} path links are not accepted: {current_path}"
                )
            else:
                pass
        else:
            pass
        component_index += 1


def _copy_stream_limited(
    source_stream: BinaryIO,
    destination_stream: BinaryIO,
    byte_limit: int,
    chunk_size: int,
    source_name: str,
) -> int:
    """Copy one stream while enforcing a measured byte limit.

    :param source_stream: Open source stream positioned at its beginning.
    :param destination_stream: Exclusive destination stream.
    :param byte_limit: Maximum number of bytes permitted for this stream.
    :param chunk_size: Maximum bytes requested from the source per read.
    :param source_name: Source name included in validation errors.
    :return: Exact number of bytes copied.
    :raises ValueError: If the stream exceeds its limit.
    """

    copied_bytes: int = 0
    reading: bool = True
    while reading:
        requested_bytes: int = min(chunk_size, byte_limit + 1 - copied_bytes)
        chunk: bytes = source_stream.read(requested_bytes)
        if len(chunk) == 0:
            reading = False
        else:
            copied_bytes += len(chunk)
            if copied_bytes <= byte_limit:
                destination_stream.write(chunk)
            else:
                raise ValueError(f"FMU staging byte limit exceeded: {source_name}")
    return copied_bytes


def _copy_regular_file(
    source: Path,
    destination: Path,
    byte_limit: int,
    chunk_size: int,
) -> int:
    """Copy one regular file exclusively without following declared links.

    :param source: Source file inside an inspected FMU representation.
    :param destination: New file path inside the private staging child.
    :param byte_limit: Maximum number of bytes permitted for the file.
    :param chunk_size: Maximum bytes copied per read.
    :return: Exact number of bytes copied.
    :raises ValueError: If the source is not regular or copying fails.
    """

    if is_fmu_link_or_reparse_point(source) or not source.is_file():
        raise ValueError(f"FMU staging source is not a regular file: {source}")
    else:
        pass
    try:
        with source.open("rb") as source_stream, destination.open("xb") as destination_stream:
            copied_bytes: int = _copy_stream_limited(
                source_stream,
                destination_stream,
                byte_limit,
                chunk_size,
                str(source),
            )
    except OSError as error:
        raise ValueError(f"Could not copy FMU staging source {source}") from error
    return copied_bytes


def _validate_private_archive_identity(
    archive_path: Path,
    receipt: FmuInspectionReceipt,
    policy: FmuArchiveInspectionPolicy,
) -> None:
    """Re-hash a private archive without decompressing its payload again.

    :param archive_path: Private archive retained by the staging owner.
    :param receipt: Receipt that defines the expected archive identity.
    :param policy: Bounded read limits used for the final hash.
    :return: None.
    :raises ValueError: If the private archive changed or exceeds limits.
    """

    try:
        with archive_path.open("rb") as archive_stream:
            observed_sha256: str
            observed_size: int
            observed_sha256, observed_size = hash_fmu_stream(
                archive_stream,
                str(archive_path),
                policy.max_archive_bytes,
                policy.read_chunk_bytes,
            )
    except OSError as error:
        raise ValueError(f"Could not revalidate private FMU archive {archive_path}") from error
    if observed_sha256 == receipt.sha256 and observed_size == receipt.source_size:
        pass
    else:
        raise ValueError("Private FMU archive changed after inspection")


def _resolve_staging_target(destination: Path, entry_name: str) -> Path:
    """Resolve one validated portable entry below a private destination.

    :param destination: Private extraction directory.
    :param entry_name: Portable path returned by archive inspection validation.
    :return: Contained destination path.
    :raises ValueError: If resolution escapes the private destination.
    """

    relative_path: PurePosixPath = PurePosixPath(entry_name)
    target: Path = destination.joinpath(*relative_path.parts)
    destination_text: str = str(destination.resolve())
    target_text: str = str(target.resolve(strict=False))
    try:
        common_path: str = os.path.commonpath((destination_text, target_text))
    except ValueError as error:
        raise ValueError(f"FMU staging target escapes its root: {entry_name!r}") from error
    if os.path.normcase(common_path) == os.path.normcase(destination_text):
        pass
    else:
        raise ValueError(f"FMU staging target escapes its root: {entry_name!r}")
    return target


def _extract_private_archive(
    archive_path: Path,
    destination: Path,
    policy: FmuArchiveInspectionPolicy,
) -> None:
    """Extract one inspected private archive with exclusive bounded writes.

    :param archive_path: Private archive copy already matched to its receipt.
    :param destination: Empty directory to receive the FMU payload.
    :param policy: Bounded archive and payload limits.
    :return: None.
    :raises ValueError: If extraction differs from inspected metadata.
    """

    destination.mkdir(mode=0o700)
    total_written: int = 0
    seen_names: set[str] = set()
    try:
        with zipfile.ZipFile(archive_path, mode="r") as archive:
            entries: list[zipfile.ZipInfo] = archive.infolist()
            if len(entries) <= policy.max_entries:
                pass
            else:
                raise ValueError("FMU archive entry count changed before extraction")
            info: zipfile.ZipInfo
            for info in entries:
                entry_name: str = validate_fmu_zip_entry(info, policy)
                portable_key: str = entry_name.casefold()
                if portable_key in seen_names:
                    raise ValueError(f"FMU archive contains a duplicate staging path: {entry_name!r}")
                else:
                    seen_names.add(portable_key)
                target: Path = _resolve_staging_target(destination, entry_name)
                if info.is_dir():
                    target.mkdir(mode=0o700, parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    with archive.open(info, mode="r") as source_stream, target.open("xb") as destination_stream:
                        written_bytes: int = _copy_stream_limited(
                            source_stream,
                            destination_stream,
                            policy.max_entry_uncompressed_bytes,
                            policy.read_chunk_bytes,
                            entry_name,
                        )
                    if written_bytes == info.file_size:
                        pass
                    else:
                        raise ValueError(f"FMU entry size changed during extraction: {entry_name!r}")
                    total_written += written_bytes
                    if total_written <= policy.max_total_uncompressed_bytes:
                        pass
                    else:
                        raise ValueError("FMU extraction exceeds the total byte limit")
    except (KeyError, NotImplementedError, OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise ValueError(f"Could not extract private FMU archive {archive_path}") from error


def _add_expected_parent_directories(entry_name: str, expected_directories: set[str]) -> None:
    """Add every portable parent of one archive entry to an expected set.

    :param entry_name: Validated portable archive entry name.
    :param expected_directories: Mutable set used only during exact verification.
    :return: None.
    """

    entry_parts: tuple[str, ...] = PurePosixPath(entry_name).parts
    parent_depth: int = 1
    while parent_depth < len(entry_parts):
        parent_name: str = "/".join(entry_parts[:parent_depth])
        expected_directories.add(parent_name)
        parent_depth += 1


def _compare_streams(
    archive_stream: BinaryIO,
    file_stream: BinaryIO,
    byte_limit: int,
    chunk_size: int,
    entry_name: str,
) -> int:
    """Compare an archive entry and staged file byte for byte.

    :param archive_stream: Open stream from the private ZIP copy.
    :param file_stream: Open stream from the extracted private tree.
    :param byte_limit: Maximum permitted bytes for the entry.
    :param chunk_size: Maximum bytes requested from each stream per read.
    :param entry_name: Portable entry name included in validation errors.
    :return: Exact number of compared bytes.
    :raises ValueError: If bytes differ or exceed the limit.
    """

    compared_bytes: int = 0
    reading: bool = True
    while reading:
        requested_bytes: int = min(chunk_size, byte_limit + 1 - compared_bytes)
        archive_chunk: bytes = archive_stream.read(requested_bytes)
        file_chunk: bytes = file_stream.read(requested_bytes)
        if archive_chunk == file_chunk:
            pass
        else:
            raise ValueError(f"Extracted FMU entry differs from its archive: {entry_name!r}")
        if len(archive_chunk) == 0:
            reading = False
        else:
            compared_bytes += len(archive_chunk)
            if compared_bytes <= byte_limit:
                pass
            else:
                raise ValueError(f"FMU comparison byte limit exceeded: {entry_name!r}")
    return compared_bytes


def _collect_staged_tree(
    directory: Path,
) -> tuple[set[str], set[str]]:
    """Collect regular files and directories without following filesystem links.

    :param directory: Private staged FMU directory.
    :return: Portable file names and directory names.
    :raises ValueError: If the tree contains links or special files.
    """

    actual_files: set[str] = set()
    actual_directories: set[str] = set()
    walk_item: tuple[str, list[str], list[str]]
    for walk_item in os.walk(directory, topdown=True, followlinks=False, onerror=_raise_staging_walk_error):
        current_root: str = walk_item[0]
        directory_names: list[str] = walk_item[1]
        file_names: list[str] = walk_item[2]
        current_path: Path = Path(current_root)
        directory_name: str
        for directory_name in directory_names:
            directory_path: Path = current_path / directory_name
            if is_fmu_link_or_reparse_point(directory_path) or not directory_path.is_dir():
                raise ValueError(f"Staged FMU directory is not regular: {directory_path}")
            else:
                relative_directory: str = directory_path.relative_to(directory).as_posix()
                actual_directories.add(relative_directory)
        file_name: str
        for file_name in file_names:
            file_path: Path = current_path / file_name
            if is_fmu_link_or_reparse_point(file_path) or not file_path.is_file():
                raise ValueError(f"Staged FMU file is not regular: {file_path}")
            else:
                relative_file: str = file_path.relative_to(directory).as_posix()
                actual_files.add(relative_file)
    return actual_files, actual_directories


def _verify_extracted_archive(
    archive_path: Path,
    directory: Path,
    policy: FmuArchiveInspectionPolicy,
) -> None:
    """Prove that a private tree exactly represents its private ZIP copy.

    :param archive_path: Private archive used for extraction.
    :param directory: Private extracted FMU tree.
    :param policy: Bounded comparison limits.
    :return: None.
    :raises ValueError: If any path, byte, or file type differs.
    """

    expected_files: set[str] = set()
    expected_directories: set[str] = set()
    total_compared: int = 0
    try:
        with zipfile.ZipFile(archive_path, mode="r") as archive:
            entries: list[zipfile.ZipInfo] = archive.infolist()
            info: zipfile.ZipInfo
            for info in entries:
                entry_name: str = validate_fmu_zip_entry(info, policy)
                _add_expected_parent_directories(entry_name, expected_directories)
                if info.is_dir():
                    expected_directories.add(entry_name)
                else:
                    expected_files.add(entry_name)
                    target: Path = _resolve_staging_target(directory, entry_name)
                    if target.exists():
                        target_is_regular: bool = (
                            not is_fmu_link_or_reparse_point(target) and target.is_file()
                        )
                    else:
                        target_is_regular = False
                    if target_is_regular:
                        with archive.open(info, mode="r") as archive_stream, target.open("rb") as file_stream:
                            compared_bytes: int = _compare_streams(
                                archive_stream,
                                file_stream,
                                policy.max_entry_uncompressed_bytes,
                                policy.read_chunk_bytes,
                                entry_name,
                            )
                        total_compared += compared_bytes
                        if total_compared <= policy.max_total_uncompressed_bytes:
                            pass
                        else:
                            raise ValueError("FMU comparison exceeds the total byte limit")
                    else:
                        raise ValueError(f"Extracted FMU entry is unavailable: {entry_name!r}")
    except (KeyError, NotImplementedError, OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise ValueError(f"Could not verify extracted FMU archive {archive_path}") from error

    actual_files: set[str]
    actual_directories: set[str]
    actual_files, actual_directories = _collect_staged_tree(directory)
    if actual_files == expected_files and actual_directories == expected_directories:
        pass
    else:
        raise ValueError("Extracted FMU tree contains missing or unexpected paths")


def _copy_directory_snapshot(
    source: Path,
    destination: Path,
    policy: FmuArchiveInspectionPolicy,
) -> None:
    """Copy one inspected FMU directory into a bounded private snapshot.

    :param source: Resolved inspected FMU directory.
    :param destination: New private directory to create.
    :param policy: Bounded directory and payload limits.
    :return: None.
    :raises ValueError: If the source changes type or exceeds limits.
    """

    destination.mkdir(mode=0o700)
    entry_count: int = 0
    total_copied: int = 0
    walk_item: tuple[str, list[str], list[str]]
    for walk_item in os.walk(source, topdown=True, followlinks=False, onerror=_raise_staging_walk_error):
        current_root: str = walk_item[0]
        directory_names: list[str] = walk_item[1]
        file_names: list[str] = walk_item[2]
        directory_names.sort()
        file_names.sort()
        current_path: Path = Path(current_root)
        relative_root: Path = current_path.relative_to(source)
        destination_root: Path = destination / relative_root

        directory_name: str
        for directory_name in directory_names:
            source_directory: Path = current_path / directory_name
            if is_fmu_link_or_reparse_point(source_directory) or not source_directory.is_dir():
                raise ValueError(f"FMU directory changed during staging: {source_directory}")
            else:
                target_directory: Path = destination_root / directory_name
                target_directory.mkdir(mode=0o700)
                entry_count += 1
        file_name: str
        for file_name in file_names:
            source_file: Path = current_path / file_name
            target_file: Path = destination_root / file_name
            copied_bytes: int = _copy_regular_file(
                source_file,
                target_file,
                policy.max_entry_uncompressed_bytes,
                policy.read_chunk_bytes,
            )
            total_copied += copied_bytes
            entry_count += 1
            if total_copied <= policy.max_total_uncompressed_bytes:
                pass
            else:
                raise ValueError("FMU directory staging exceeds the total byte limit")
        if entry_count <= policy.max_entries:
            pass
        else:
            raise ValueError("FMU directory staging exceeds the entry limit")


def _create_temporary_root(
    staging_parent: str | Path,
) -> Path:
    """Create one unique temporary child below a caller-owned parent.

    :param staging_parent: Parent that must remain untouched by cleanup.
    :return: Exact private child created for this staging operation.
    :raises ValueError: If the requested parent is unsafe or unavailable.
    """

    requested_parent: Path = Path(staging_parent)
    try:
        _validate_path_components(requested_parent, "staging parent")
        requested_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        _validate_path_components(requested_parent, "staging parent")
        if requested_parent.is_dir():
            normalized_parent: Path = requested_parent.resolve()
        else:
            raise ValueError(f"FMU staging parent is not a directory: {requested_parent}")
    except OSError as error:
        raise ValueError(f"Could not prepare FMU staging parent {requested_parent}") from error

    try:
        temporary_path: str = tempfile.mkdtemp(
            prefix="veragrid_fmu_stage_", dir=str(normalized_parent)
        )
    except OSError as error:
        raise ValueError("Could not create a private FMU staging child") from error
    return Path(temporary_path).resolve()


def _validate_staging_parent_location(
    source: Path,
    staging_parent: str | Path,
) -> None:
    """Reject a staging parent located inside a directory source.

    Creating staging below the source would make the new snapshot visible to
    ``os.walk`` and could recursively copy temporary state into itself.

    :param source: Resolved archive or directory source.
    :param staging_parent: Effective parent selected before any directory creation.
    :return: None.
    :raises ValueError: If a directory source contains the staging parent.
    """

    if source.is_dir():
        requested_parent: Path = Path(staging_parent)
        _validate_path_components(requested_parent, "staging parent")
        normalized_parent: Path = requested_parent.resolve(strict=False)
        try:
            normalized_parent.relative_to(source)
            parent_is_inside_source: bool = True
        except ValueError:
            parent_is_inside_source = False
        if parent_is_inside_source:
            raise ValueError("FMU staging parent cannot be inside a directory source")
        else:
            pass
    else:
        pass


def stage_fmu_source(
    path: str | Path,
    expected_receipt: FmuInspectionReceipt,
    staging_parent: str | Path | None = None,
    inspection_policy: FmuArchiveInspectionPolicy | None = None,
) -> FmuStagingArea:
    """Create a private FMU snapshot bound to an earlier inspection receipt.

    Archives are copied, re-inspected, extracted without ``extractall``, and
    compared byte for byte with their private extracted trees. Directory
    sources are copied without following links and both source and destination
    receipts must match. No binary is loaded or executed by this operation.

    :param path: FMU ZIP or extracted directory inspected earlier.
    :param expected_receipt: Receipt whose exact source representation is required.
    :param staging_parent: Optional parent for one uniquely owned temporary child.
        The resolved source parent is used when this value is ``None``.
    :param inspection_policy: Optional finite limits reused for staging validation.
    :return: Owner of the verified private snapshot.
    :raises ValueError: If the source changed or staging cannot be verified.
    """

    requested_source: Path = Path(path)
    try:
        _validate_path_components(requested_source, "source")
        if requested_source.is_file() or requested_source.is_dir():
            source: Path = requested_source.resolve()
        else:
            raise ValueError(f"FMU staging source is unavailable: {requested_source}")
    except OSError as error:
        raise ValueError(f"Could not resolve FMU staging source {requested_source}") from error

    _validate_source_receipt(source, expected_receipt)
    if inspection_policy is None:
        policy: FmuArchiveInspectionPolicy = FmuArchiveInspectionPolicy()
    else:
        policy = inspection_policy

    # The unique child is created only after source and receipt ownership have
    # been checked. Every subsequent failure releases exactly this child.
    effective_staging_parent: str | Path
    if staging_parent is None:
        effective_staging_parent = source.parent
    else:
        effective_staging_parent = staging_parent
    _validate_staging_parent_location(source, effective_staging_parent)
    staging_root: Path = _create_temporary_root(effective_staging_parent)
    normalized_staging_parent: Path = staging_root.parent
    fmu_directory: Path = staging_root / "fmu"
    source_copy: Path | None = None
    try:
        if expected_receipt.source_kind == FmuSourceKind.ZIP:
            source_copy = staging_root / "source.fmu"
            copied_size: int = _copy_regular_file(
                source,
                source_copy,
                policy.max_archive_bytes,
                policy.read_chunk_bytes,
            )
            if copied_size == expected_receipt.source_size:
                pass
            else:
                raise ValueError("FMU archive size changed before private staging")

            # Inspection of the private copy binds every later operation to the
            # bytes that survived the copy rather than reopening the source.
            private_result: FmuInspectionResult = inspect_fmu(source_copy, policy=policy)
            _validate_matching_receipts(expected_receipt, private_result.receipt, "archive staging")
            _extract_private_archive(source_copy, fmu_directory, policy)
            _verify_extracted_archive(source_copy, fmu_directory, policy)
            fmu_directory_result: FmuInspectionResult = inspect_fmu(fmu_directory, policy=policy)
            _validate_private_archive_identity(source_copy, private_result.receipt, policy)
            private_source_receipt: FmuInspectionReceipt = private_result.receipt
            private_directory_receipt: FmuInspectionReceipt = fmu_directory_result.receipt
        else:
            if expected_receipt.source_kind == FmuSourceKind.DIRECTORY:
                _copy_directory_snapshot(source, fmu_directory, policy)
                private_result = inspect_fmu(fmu_directory, policy=policy)
                _validate_matching_receipts(expected_receipt, private_result.receipt, "directory snapshot")
                private_source_receipt = private_result.receipt
                private_directory_receipt = private_result.receipt
            else:
                raise ValueError(f"Unsupported FMU staging source kind {expected_receipt.source_kind!r}")
        return FmuStagingArea(
            root=staging_root,
            staging_parent=normalized_staging_parent,
            fmu_directory=fmu_directory,
            source_copy=source_copy,
            source_receipt=private_source_receipt,
            fmu_directory_receipt=private_directory_receipt,
        )
    except BaseException:
        # Normal failures and cancellations still release the exact private
        # child. A cleanup failure deliberately replaces the original error so
        # the caller cannot mistake uncertain ownership for successful cleanup.
        incomplete_staging: FmuStagingArea = FmuStagingArea(
            root=staging_root,
            staging_parent=normalized_staging_parent,
            fmu_directory=fmu_directory,
            source_copy=source_copy,
            source_receipt=expected_receipt,
            fmu_directory_receipt=expected_receipt,
        )
        incomplete_staging.close()
        raise


def revalidate_fmu_staging_area(
    staging: FmuStagingArea,
    inspection_policy: FmuArchiveInspectionPolicy | None = None,
) -> FmuInspectionReceipt:
    """Revalidate a private FMU tree immediately before a future native load.

    This operation closes the gap between staging creation and consumption. It
    still does not approve or sandbox the FMU; it only confirms that the owned
    snapshot has not changed since creation.

    :param staging: Active private staging owner to revalidate.
    :param inspection_policy: Optional finite limits used during revalidation.
    :return: Fresh receipt for the private runtime tree.
    :raises ValueError: If the staging area is closed or content changed.
    """

    if staging.is_closed():
        raise ValueError("Closed FMU staging areas cannot be revalidated")
    else:
        pass
    if inspection_policy is None:
        policy: FmuArchiveInspectionPolicy = FmuArchiveInspectionPolicy()
    else:
        policy = inspection_policy

    source_copy: Path | None = staging.get_source_copy()
    if source_copy is None:
        if staging.get_source_receipt().source_kind == FmuSourceKind.DIRECTORY:
            pass
        else:
            raise ValueError("FMU staging source receipt is inconsistent")
    else:
        if staging.get_source_receipt().source_kind == FmuSourceKind.ZIP:
            _validate_private_archive_identity(source_copy, staging.get_source_receipt(), policy)
            _verify_extracted_archive(source_copy, staging.get_fmu_directory(), policy)
        else:
            raise ValueError("FMU staging archive receipt is inconsistent")

    current_directory_result: FmuInspectionResult = inspect_fmu(
        staging.get_fmu_directory(),
        policy=policy,
    )
    _validate_matching_receipts(
        staging.get_fmu_directory_receipt(),
        current_directory_result.receipt,
        "staging revalidation",
    )
    return current_directory_result.receipt
