# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import hashlib
import math
import os
import stat
import struct
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from VeraGridEngine.enumerations import FmuSourceKind


class FmuArchiveInspectionPolicy:
    """Define finite resource limits for safe FMU inspection.

    The policy never disables path, link, encryption, or compression-method
    validation. Callers may only adjust finite resource ceilings. Every ZIP
    payload is streamed once so its size and CRC are verified.

    :param max_archive_bytes: Maximum compressed FMU file size.
    :param max_entries: Maximum number of archive or directory entries.
    :param max_central_directory_bytes: Maximum ZIP central-directory size.
    :param max_total_uncompressed_bytes: Maximum combined payload size.
    :param max_entry_uncompressed_bytes: Maximum individual payload size.
    :param max_model_description_bytes: Maximum ``modelDescription.xml`` size.
    :param max_compression_ratio: Maximum permitted expansion ratio per entry.
    :param max_path_depth: Maximum number of portable path components.
    :param max_path_length: Maximum portable entry path length.
    :param read_chunk_bytes: Bounded streaming chunk size.
    """

    __slots__ = (
        "max_archive_bytes",
        "max_entries",
        "max_central_directory_bytes",
        "max_total_uncompressed_bytes",
        "max_entry_uncompressed_bytes",
        "max_model_description_bytes",
        "max_compression_ratio",
        "max_path_depth",
        "max_path_length",
        "read_chunk_bytes",
    )

    def __init__(
        self,
        max_archive_bytes: int = 512 * 1024 * 1024,
        max_entries: int = 4096,
        max_central_directory_bytes: int = 64 * 1024 * 1024,
        max_total_uncompressed_bytes: int = 1024 * 1024 * 1024,
        max_entry_uncompressed_bytes: int = 256 * 1024 * 1024,
        max_model_description_bytes: int = 16 * 1024 * 1024,
        max_compression_ratio: float = 200.0,
        max_path_depth: int = 32,
        max_path_length: int = 1024,
        read_chunk_bytes: int = 1024 * 1024,
    ) -> None:
        """Store validated resource limits for one inspection operation.

        :param max_archive_bytes: Maximum compressed FMU file size.
        :param max_entries: Maximum number of archive or directory entries.
        :param max_central_directory_bytes: Maximum central-directory size.
        :param max_total_uncompressed_bytes: Maximum combined payload size.
        :param max_entry_uncompressed_bytes: Maximum individual payload size.
        :param max_model_description_bytes: Maximum model-description size.
        :param max_compression_ratio: Maximum expansion ratio per entry.
        :param max_path_depth: Maximum portable path depth.
        :param max_path_length: Maximum portable path length.
        :param read_chunk_bytes: Streaming chunk size used for bounded reads.
        :return: None.
        :raises ValueError: If a configured limit is not positive.
        """

        integer_limits: tuple[tuple[str, int], ...] = (
            ("max_archive_bytes", max_archive_bytes),
            ("max_entries", max_entries),
            ("max_central_directory_bytes", max_central_directory_bytes),
            ("max_total_uncompressed_bytes", max_total_uncompressed_bytes),
            ("max_entry_uncompressed_bytes", max_entry_uncompressed_bytes),
            ("max_model_description_bytes", max_model_description_bytes),
            ("max_path_depth", max_path_depth),
            ("max_path_length", max_path_length),
            ("read_chunk_bytes", read_chunk_bytes),
        )
        limit_name: str
        limit_value: int
        for limit_name, limit_value in integer_limits:
            if limit_value > 0:
                pass
            else:
                raise ValueError(f"{limit_name} must be positive")
        if math.isfinite(max_compression_ratio) and max_compression_ratio >= 1.0:
            pass
        else:
            raise ValueError("max_compression_ratio must be at least 1.0")

        self.max_archive_bytes: int = max_archive_bytes
        self.max_entries: int = max_entries
        self.max_central_directory_bytes: int = max_central_directory_bytes
        self.max_total_uncompressed_bytes: int = max_total_uncompressed_bytes
        self.max_entry_uncompressed_bytes: int = max_entry_uncompressed_bytes
        self.max_model_description_bytes: int = max_model_description_bytes
        self.max_compression_ratio: float = max_compression_ratio
        self.max_path_depth: int = max_path_depth
        self.max_path_length: int = max_path_length
        self.read_chunk_bytes: int = read_chunk_bytes


class FmuInspectionReceipt:
    """Record the observed outcome of bounded FMU inspection.

    :param path: Resolved inspected source path.
    :param source_kind: ZIP or extracted-directory source kind.
    :param sha256_digest: Digest of the observed archive or directory payload.
    :param model_description_sha256: Digest of ``modelDescription.xml``.
    :param source_size: Compressed ZIP size or combined directory file size.
    :param entry_count: Number of validated entries.
    :param total_uncompressed_size: Combined uncompressed file size.
    :param model_description_size: Model-description byte size.
    :param platforms: Sorted binary platform folder names.
    :param binary_entries: Sorted native payload entries.
    :param source_entries: Sorted source payload entries.
    :param compression_methods: Sorted ZIP compression method identifiers.
    :param max_observed_compression_ratio: Largest entry expansion ratio.
    """

    __slots__ = (
        "path",
        "source_kind",
        "sha256",
        "model_description_sha256",
        "source_size",
        "entry_count",
        "total_uncompressed_size",
        "model_description_size",
        "platforms",
        "binary_entries",
        "source_entries",
        "compression_methods",
        "max_observed_compression_ratio",
    )

    def __init__(
        self,
        path: Path,
        source_kind: FmuSourceKind,
        sha256_digest: str,
        model_description_sha256: str,
        source_size: int,
        entry_count: int,
        total_uncompressed_size: int,
        model_description_size: int,
        platforms: tuple[str, ...],
        binary_entries: tuple[str, ...],
        source_entries: tuple[str, ...],
        compression_methods: tuple[int, ...],
        max_observed_compression_ratio: float,
    ) -> None:
        """Store one observed inspection receipt.

        :param path: Resolved inspected source path.
        :param source_kind: ZIP or extracted-directory source kind.
        :param sha256_digest: Digest of the observed source payload.
        :param model_description_sha256: Model-description digest.
        :param source_size: Compressed or directory source size.
        :param entry_count: Number of validated entries.
        :param total_uncompressed_size: Combined payload size.
        :param model_description_size: Model-description size.
        :param platforms: Sorted platform names.
        :param binary_entries: Sorted binary entries.
        :param source_entries: Sorted source entries.
        :param compression_methods: Sorted compression methods.
        :param max_observed_compression_ratio: Largest expansion ratio.
        :return: None.
        """

        self.path: Path = path
        self.source_kind: FmuSourceKind = source_kind
        self.sha256: str = sha256_digest
        self.model_description_sha256: str = model_description_sha256
        self.source_size: int = source_size
        self.entry_count: int = entry_count
        self.total_uncompressed_size: int = total_uncompressed_size
        self.model_description_size: int = model_description_size
        self.platforms: tuple[str, ...] = platforms
        self.binary_entries: tuple[str, ...] = binary_entries
        self.source_entries: tuple[str, ...] = source_entries
        self.compression_methods: tuple[int, ...] = compression_methods
        self.max_observed_compression_ratio: float = max_observed_compression_ratio

    def has_same_source_content(self, other: "FmuInspectionReceipt") -> bool:
        """Return whether another receipt identifies the same source content.

        Source paths are intentionally excluded because a private staging copy
        has a different location. The source kind and SHA-256 digest define the
        representation identity; size is retained as an explicit diagnostic
        guard for bounded copy operations.

        :param other: Receipt to compare with this observed source.
        :return: ``True`` when kind, digest, and exact source size match.
        """

        matches: bool = (
            self.source_kind == other.source_kind
            and self.sha256 == other.sha256
            and self.source_size == other.source_size
        )
        return matches

    def get_contains_native_code(self) -> bool:
        """Return whether the inspected FMU carries native code.

        :return: ``True`` when at least one binary payload exists.
        """

        return len(self.binary_entries) > 0

    def get_contains_source_code(self) -> bool:
        """Return whether the inspected FMU carries source code.

        :return: ``True`` when at least one source payload exists.
        """

        return len(self.source_entries) > 0


class FmuInspectionResult:
    """Return inspected XML bytes together with their inspection receipt.

    :param model_description_xml: Validated model-description bytes.
    :param receipt: Receipt describing the observed source bytes.
    """

    __slots__ = ("model_description_xml", "receipt")

    def __init__(
        self,
        model_description_xml: bytes,
        receipt: FmuInspectionReceipt,
    ) -> None:
        """Store one completed inspection result.

        :param model_description_xml: Validated model-description bytes.
        :param receipt: Receipt describing the observed source bytes.
        :return: None.
        """

        self.model_description_xml: bytes = model_description_xml
        self.receipt: FmuInspectionReceipt = receipt


def _is_windows_reserved_name(stem: str) -> bool:
    """Return whether a case-folded path stem is reserved on Windows.

    :param stem: Case-folded component stem without its extension.
    :return: ``True`` when Windows cannot represent the component portably.
    """

    if stem == "aux" or stem == "con" or stem == "nul" or stem == "prn":
        reserved: bool = True
    elif len(stem) == 4 and (stem.startswith("com") or stem.startswith("lpt")):
        suffix: str = stem[3]
        reserved = suffix >= "1" and suffix <= "9"
    else:
        reserved = False
    return reserved


def _portable_entry_name(raw_name: str, policy: FmuArchiveInspectionPolicy) -> str:
    """Validate one archive-relative path and return its NFC form.

    :param raw_name: Entry name supplied by the ZIP or directory.
    :param policy: Finite inspection limits.
    :return: Portable NFC-normalized relative path.
    :raises ValueError: If the entry cannot be represented safely.
    """

    if "\x00" in raw_name:
        raise ValueError("FMU entry names must not contain NUL bytes")
    else:
        pass
    if "\\" in raw_name:
        raise ValueError(f"FMU entry uses a non-portable path separator: {raw_name!r}")
    else:
        pass

    normalized_name: str = unicodedata.normalize("NFC", raw_name)
    if normalized_name.endswith("/"):
        comparable_name: str = normalized_name[:-1]
    else:
        comparable_name = normalized_name
    if len(comparable_name) > 0 and len(comparable_name) <= policy.max_path_length:
        pass
    else:
        raise ValueError(f"FMU entry path length is invalid: {raw_name!r}")
    if comparable_name.startswith("/"):
        raise ValueError(f"FMU entry path must be relative: {raw_name!r}")
    else:
        pass

    portable_path: PurePosixPath = PurePosixPath(comparable_name)
    parts: tuple[str, ...] = portable_path.parts
    if len(parts) > 0 and len(parts) <= policy.max_path_depth:
        pass
    else:
        raise ValueError(f"FMU entry path depth exceeds the inspection policy: {raw_name!r}")
    if "/".join(parts) == comparable_name:
        pass
    else:
        raise ValueError(f"FMU entry path is not normalized: {raw_name!r}")

    part: str
    for part in parts:
        if part == "" or part == "." or part == "..":
            raise ValueError(f"FMU entry path is not normalized: {raw_name!r}")
        else:
            pass
        if len(part) <= 255 and not part.endswith((" ", ".")):
            pass
        else:
            raise ValueError(f"FMU entry has a non-portable component: {raw_name!r}")
        contains_control_character: bool = False
        contains_windows_reserved_character: bool = False
        character: str
        for character in part:
            if ord(character) < 32:
                contains_control_character = True
            else:
                pass
            if character in '<>"|?*:':
                contains_windows_reserved_character = True
            else:
                pass
        if contains_windows_reserved_character or contains_control_character:
            raise ValueError(f"FMU entry has a non-portable component: {raw_name!r}")
        else:
            pass
        reserved_stem: str = part.split(".", maxsplit=1)[0].casefold()
        if _is_windows_reserved_name(reserved_stem):
            raise ValueError(f"FMU entry uses a reserved path component: {raw_name!r}")
        else:
            pass

    return comparable_name


def _classify_payload(
    entry_name: str,
    platforms: set[str],
    binary_entries: list[str],
    source_entries: list[str],
) -> None:
    """Classify one portable file entry without executing its content.

    :param entry_name: Validated portable file path.
    :param platforms: Mutable platform-name accumulator.
    :param binary_entries: Mutable binary-entry accumulator.
    :param source_entries: Mutable source-entry accumulator.
    :return: None.
    """

    parts: tuple[str, ...] = PurePosixPath(entry_name).parts
    if len(parts) >= 3 and parts[0] == "binaries":
        binary_entries.append(entry_name)
        platforms.add(parts[1])
    elif len(parts) >= 2 and parts[0] == "sources":
        source_entries.append(entry_name)
    else:
        pass


def _register_archive_path(
    entry_name: str,
    is_directory: bool,
    seen_names: set[str],
    file_names: set[str],
) -> None:
    """Register one portable ZIP path and reject ambiguous file trees.

    :param entry_name: Validated portable ZIP entry name.
    :param is_directory: Whether the entry represents a directory.
    :param seen_names: Case-folded paths already registered.
    :param file_names: Case-folded file paths already registered.
    :return: None.
    :raises ValueError: If the path duplicates or conflicts with a file.
    """

    portable_key: str = entry_name.casefold()
    if portable_key in seen_names:
        raise ValueError(
            f"FMU archive contains a duplicate portable path: {entry_name!r}"
        )
    else:
        pass

    parts: tuple[str, ...] = PurePosixPath(portable_key).parts
    part_index: int
    for part_index in range(1, len(parts)):
        ancestor: str = "/".join(parts[:part_index])
        if ancestor in file_names:
            raise ValueError(
                f"FMU archive path has a file ancestor: {entry_name!r}"
            )
        else:
            pass

    if is_directory:
        pass
    else:
        descendant_prefix: str = portable_key + "/"
        registered_name: str
        for registered_name in seen_names:
            if registered_name.startswith(descendant_prefix):
                raise ValueError(
                    f"FMU archive file conflicts with an existing path: {entry_name!r}"
                )
            else:
                pass
        file_names.add(portable_key)
    seen_names.add(portable_key)


def validate_fmu_zip_entry(
    info: zipfile.ZipInfo,
    policy: FmuArchiveInspectionPolicy,
) -> str:
    """Validate one ZIP entry and return its portable relative name.

    :param info: ZIP central-directory entry.
    :param policy: Finite inspection limits.
    :return: Validated portable entry name.
    :raises ValueError: If encryption, compression, or file type is unsafe.
    """

    # ``zipfile`` normalizes backslashes in ``filename`` on Windows, while
    # ``orig_filename`` retains the central-directory spelling. Validate the
    # original spelling so safety does not depend on the inspection host.
    entry_name: str = _portable_entry_name(info.orig_filename, policy)
    if info.flag_bits & 0x1:
        raise ValueError(f"Encrypted FMU entries are not accepted: {entry_name!r}")
    else:
        pass
    if info.compress_type == zipfile.ZIP_STORED or info.compress_type == zipfile.ZIP_DEFLATED:
        pass
    else:
        raise ValueError(
            f"Unsupported ZIP compression method {info.compress_type} for {entry_name!r}"
        )

    unix_mode: int = (info.external_attr >> 16) & 0xFFFF
    file_type: int = stat.S_IFMT(unix_mode)
    if file_type == stat.S_IFLNK:
        raise ValueError(f"FMU archive links are not accepted: {entry_name!r}")
    else:
        pass
    if file_type == 0 or file_type == stat.S_IFREG or file_type == stat.S_IFDIR:
        pass
    else:
        raise ValueError(f"FMU archive special files are not accepted: {entry_name!r}")
    if file_type == stat.S_IFDIR and not info.is_dir():
        raise ValueError(
            f"FMU archive directory metadata conflicts with its path: {entry_name!r}"
        )
    else:
        pass
    if file_type == stat.S_IFREG and info.is_dir():
        raise ValueError(
            f"FMU archive file metadata conflicts with its path: {entry_name!r}"
        )
    else:
        pass
    return entry_name


def _read_limited(
    stream: BinaryIO,
    limit: int,
    chunk_size: int,
    entry_name: str,
) -> bytes:
    """Read one stream while enforcing an actual byte limit.

    :param stream: Binary payload stream.
    :param limit: Maximum permitted bytes.
    :param chunk_size: Maximum bytes requested per read.
    :param entry_name: Entry name used in validation errors.
    :return: Complete payload bytes.
    :raises ValueError: If the stream exceeds its byte limit.
    """

    chunks: list[bytes] = list()
    total: int = 0
    reading: bool = True
    while reading:
        chunk: bytes = stream.read(min(chunk_size, limit + 1 - total))
        if len(chunk) == 0:
            reading = False
        else:
            chunks.append(chunk)
            total += len(chunk)
            if total <= limit:
                pass
            else:
                raise ValueError(f"FMU entry exceeds the inspection byte limit: {entry_name!r}")
    return b"".join(chunks)


def _drain_limited(
    stream: BinaryIO,
    limit: int,
    chunk_size: int,
    entry_name: str,
) -> int:
    """Consume one stream while enforcing an actual byte limit.

    :param stream: Binary payload stream.
    :param limit: Maximum permitted bytes.
    :param chunk_size: Maximum bytes requested per read.
    :param entry_name: Entry name used in validation errors.
    :return: Number of bytes consumed.
    :raises ValueError: If the stream exceeds its byte limit.
    """

    total: int = 0
    reading: bool = True
    while reading:
        chunk: bytes = stream.read(min(chunk_size, limit + 1 - total))
        if len(chunk) == 0:
            reading = False
        else:
            total += len(chunk)
            if total <= limit:
                pass
            else:
                raise ValueError(f"FMU entry exceeds the inspection byte limit: {entry_name!r}")
    return total


def hash_fmu_stream(
    stream: BinaryIO,
    source_name: str,
    limit: int,
    chunk_size: int,
) -> tuple[str, int]:
    """Hash one seekable source stream with a hard byte limit.

    :param stream: Open source stream positioned at its beginning.
    :param source_name: Source name used in validation errors.
    :param limit: Maximum permitted bytes.
    :param chunk_size: Maximum bytes requested per read.
    :return: Hexadecimal digest and bytes consumed.
    :raises ValueError: If the stream exceeds its byte limit.
    """

    digest = hashlib.sha256()
    total: int = 0
    reading: bool = True
    while reading:
        chunk: bytes = stream.read(min(chunk_size, limit + 1 - total))
        if len(chunk) == 0:
            reading = False
        else:
            total += len(chunk)
            if total <= limit:
                digest.update(chunk)
            else:
                raise ValueError(
                    f"FMU source exceeds the inspection byte limit: {source_name}"
                )
    return digest.hexdigest(), total


def _read_exact_at(
    stream: BinaryIO,
    offset: int,
    size: int,
    source_name: str,
) -> bytes:
    """Read an exact bounded region from a seekable archive stream.

    :param stream: Open FMU archive stream.
    :param offset: Absolute byte offset to read.
    :param size: Exact number of bytes required.
    :param source_name: Source name used in validation errors.
    :return: Requested archive bytes.
    :raises ValueError: If the region lies outside the archive.
    """

    if offset >= 0 and size >= 0:
        stream.seek(offset)
        data: bytes = stream.read(size)
    else:
        raise ValueError(f"Invalid ZIP record offset in {source_name}")
    if len(data) == size:
        pass
    else:
        raise ValueError(f"Truncated ZIP record in {source_name}")
    return data


def _count_central_directory_entries(
    stream: BinaryIO,
    central_directory_offset: int,
    central_directory_size: int,
    policy: FmuArchiveInspectionPolicy,
    source_name: str,
) -> int:
    """Count framed central-file headers before ``ZipFile`` allocates objects.

    Only the fixed 46-byte header and its three variable-length fields are
    interpreted. Names, extra records, and comments remain opaque because
    semantic ZIP validation still belongs to ``zipfile`` after this bounded
    cardinality preflight.

    :param stream: Open FMU archive stream.
    :param central_directory_offset: Actual central-directory byte offset.
    :param central_directory_size: Exact central-directory byte size.
    :param policy: Finite inspection limits.
    :param source_name: Source name used in validation errors.
    :return: Number of structurally framed central-file headers.
    :raises ValueError: If framing is invalid or has too many entries.
    """

    current_offset: int = central_directory_offset
    end_offset: int = central_directory_offset + central_directory_size
    entry_count: int = 0
    while current_offset < end_offset:
        header: bytes = _read_exact_at(stream, current_offset, 46, source_name)
        if header[:4] == b"PK\x01\x02":
            pass
        else:
            raise ValueError(
                f"Invalid ZIP central-file header in {source_name}"
            )
        variable_lengths: tuple[int, int, int] = struct.unpack_from("<3H", header, 28)
        record_size: int = 46 + sum(variable_lengths)
        next_offset: int = current_offset + record_size
        if next_offset <= end_offset:
            pass
        else:
            raise ValueError(
                f"ZIP central-file header exceeds directory bounds in {source_name}"
            )
        entry_count += 1
        if entry_count <= policy.max_entries:
            current_offset = next_offset
        else:
            raise ValueError(
                f"FMU archive has more than {policy.max_entries} central-file headers"
            )
    if current_offset == end_offset:
        pass
    else:
        raise ValueError(f"Invalid ZIP central-directory framing in {source_name}")
    return entry_count


def _preflight_zip_central_directory(
    stream: BinaryIO,
    archive_size: int,
    policy: FmuArchiveInspectionPolicy,
    source_name: str,
) -> int:
    """Bound ZIP metadata before ``zipfile`` materializes every entry.

    Both classic EOCD and ZIP64 EOCD records are read from bounded regions.
    The declared entry count and central-directory byte size are rejected
    before constructing ``ZipFile``, which prevents metadata-only ZIP bombs
    from bypassing the public inspection policy.

    :param stream: Open FMU archive stream.
    :param archive_size: Already bounded archive byte size.
    :param policy: Finite inspection limits.
    :param source_name: Source name used in validation errors.
    :return: Declared number of central-directory entries.
    :raises ValueError: If ZIP metadata is malformed or exceeds policy.
    """

    if archive_size >= 22:
        tail_size: int = min(archive_size, 22 + 65535)
    else:
        raise ValueError(f"FMU source is too small to be a ZIP archive: {source_name}")
    tail_offset: int = archive_size - tail_size
    tail: bytes = _read_exact_at(stream, tail_offset, tail_size, source_name)

    # A ZIP comment may contain the EOCD signature. Search backwards until the
    # declared comment length makes the candidate end exactly at end-of-file.
    signature: bytes = b"PK\x05\x06"
    search_end: int = len(tail)
    eocd_index: int = -1
    searching: bool = True
    while searching:
        candidate_index: int = tail.rfind(signature, 0, search_end)
        if candidate_index >= 0:
            if candidate_index + 22 <= len(tail):
                candidate_comment_length: int = struct.unpack_from(
                    "<H",
                    tail,
                    candidate_index + 20,
                )[0]
                if candidate_index + 22 + candidate_comment_length == len(tail):
                    eocd_index = candidate_index
                    searching = False
                else:
                    search_end = candidate_index
            else:
                search_end = candidate_index
        else:
            searching = False
    if eocd_index >= 0:
        pass
    else:
        raise ValueError(f"FMU source has no valid ZIP end record: {source_name}")

    eocd: tuple[bytes, int, int, int, int, int, int, int] = struct.unpack_from(
        "<4s4H2LH",
        tail,
        eocd_index,
    )
    disk_number: int = eocd[1]
    central_directory_disk: int = eocd[2]
    disk_entry_count: int = eocd[3]
    entry_count: int = eocd[4]
    central_directory_size: int = eocd[5]
    central_directory_offset: int = eocd[6]
    eocd_absolute_offset: int = tail_offset + eocd_index
    uses_zip64: bool = (
        disk_entry_count == 0xFFFF
        or entry_count == 0xFFFF
        or central_directory_size == 0xFFFFFFFF
        or central_directory_offset == 0xFFFFFFFF
    )

    if uses_zip64:
        locator_offset: int = eocd_absolute_offset - 20
        locator_data: bytes = _read_exact_at(stream, locator_offset, 20, source_name)
        locator: tuple[bytes, int, int, int] = struct.unpack("<4sLQL", locator_data)
        if locator[0] == b"PK\x06\x07" and locator[1] == 0 and locator[3] == 1:
            zip64_offset: int = locator[2]
        else:
            raise ValueError(f"Invalid ZIP64 locator in {source_name}")
        zip64_data: bytes = _read_exact_at(stream, zip64_offset, 56, source_name)
        zip64: tuple[bytes, int, int, int, int, int, int, int, int, int] = struct.unpack(
            "<4sQ2H2L4Q",
            zip64_data,
        )
        zip64_record_size: int = zip64[1]
        if (
            zip64[0] == b"PK\x06\x06"
            and zip64_record_size >= 44
            and zip64_offset + 12 + zip64_record_size == locator_offset
            and zip64[4] == 0
            and zip64[5] == 0
            and zip64[6] == zip64[7]
        ):
            entry_count = zip64[7]
            central_directory_size = zip64[8]
            central_directory_offset = zip64[9]
            central_directory_end_limit: int = zip64_offset
        else:
            raise ValueError(f"Invalid ZIP64 end record in {source_name}")
    else:
        if disk_number == 0 and central_directory_disk == 0 and disk_entry_count == entry_count:
            central_directory_end_limit = eocd_absolute_offset
        else:
            raise ValueError(f"Multi-disk FMU archives are not accepted: {source_name}")

    if entry_count <= policy.max_entries:
        pass
    else:
        raise ValueError(
            f"FMU archive declares {entry_count} entries; policy maximum is {policy.max_entries}"
        )
    if central_directory_size <= policy.max_central_directory_bytes:
        pass
    else:
        raise ValueError(
            "FMU ZIP central directory exceeds the inspection byte limit"
        )
    if central_directory_offset + central_directory_size <= central_directory_end_limit:
        pass
    else:
        raise ValueError(f"Invalid ZIP central-directory bounds in {source_name}")
    actual_central_directory_offset: int = (
        central_directory_end_limit - central_directory_size
    )
    actual_entry_count: int = _count_central_directory_entries(
        stream,
        actual_central_directory_offset,
        central_directory_size,
        policy,
        source_name,
    )
    if actual_entry_count == entry_count:
        pass
    else:
        raise ValueError(
            "FMU ZIP central-file header count does not match its end record"
        )
    return actual_entry_count


def _inspect_zip(
    path: Path,
    policy: FmuArchiveInspectionPolicy,
) -> FmuInspectionResult:
    """Inspect one FMU ZIP without extracting archive entries.

    :param path: Resolved FMU ZIP path.
    :param policy: Finite inspection limits.
    :return: Validated XML bytes and an observed-source receipt.
    :raises ValueError: If the archive violates any inspection rule.
    """

    platforms: set[str] = set()
    binary_entries: list[str] = list()
    source_entries: list[str] = list()
    compression_methods: set[int] = set()
    total_uncompressed_size: int = 0
    max_observed_ratio: float = 1.0
    model_description_info: zipfile.ZipInfo | None = None
    seen_names: set[str] = set()
    file_names: set[str] = set()

    try:
        # Hash and parse through one open descriptor. A second hash on that same
        # descriptor detects in-place mutation during inspection, while a path
        # replacement cannot redirect the already-open source.
        with path.open("rb") as archive_stream:
            archive_sha256: str
            archive_size: int
            archive_sha256, archive_size = hash_fmu_stream(
                archive_stream,
                str(path),
                policy.max_archive_bytes,
                policy.read_chunk_bytes,
            )
            declared_entry_count: int = _preflight_zip_central_directory(
                archive_stream,
                archive_size,
                policy,
                str(path),
            )
            archive_stream.seek(0)
            with zipfile.ZipFile(archive_stream, mode="r") as archive:
                entries: list[zipfile.ZipInfo] = archive.infolist()
                if len(entries) > 0:
                    pass
                else:
                    raise ValueError(f"FMU archive is empty: {path}")
                if len(entries) <= policy.max_entries:
                    pass
                else:
                    raise ValueError(
                        f"FMU archive has {len(entries)} entries; "
                        f"policy maximum is {policy.max_entries}"
                    )
                if len(entries) == declared_entry_count:
                    pass
                else:
                    raise ValueError(
                        "FMU ZIP entry count does not match its end record"
                    )

                info: zipfile.ZipInfo
                for info in entries:
                    entry_name: str = validate_fmu_zip_entry(info, policy)
                    _register_archive_path(
                        entry_name,
                        info.is_dir(),
                        seen_names,
                        file_names,
                    )
                    compression_methods.add(info.compress_type)

                    if info.is_dir():
                        pass
                    else:
                        if info.file_size <= policy.max_entry_uncompressed_bytes:
                            pass
                        else:
                            raise ValueError(
                                f"FMU entry {entry_name!r} exceeds the per-entry inspection limit"
                            )
                        total_uncompressed_size += int(info.file_size)
                        if total_uncompressed_size <= policy.max_total_uncompressed_bytes:
                            pass
                        else:
                            raise ValueError(
                                "FMU archive exceeds the total uncompressed byte limit"
                            )
                        ratio: float = float(info.file_size) / float(max(1, info.compress_size))
                        max_observed_ratio = max(max_observed_ratio, ratio)
                        if ratio <= policy.max_compression_ratio:
                            pass
                        else:
                            raise ValueError(
                                f"FMU entry {entry_name!r} exceeds the compression-ratio limit"
                            )
                        _classify_payload(entry_name, platforms, binary_entries, source_entries)
                        if entry_name == "modelDescription.xml":
                            model_description_info = info
                        else:
                            pass

                if model_description_info is not None:
                    pass
                else:
                    raise ValueError("FMU archive does not contain root modelDescription.xml")
                if model_description_info.file_size <= policy.max_model_description_bytes:
                    pass
                else:
                    raise ValueError(
                        "FMU modelDescription.xml exceeds the inspection byte limit"
                    )

                with archive.open(model_description_info, mode="r") as xml_stream:
                    model_description_xml: bytes = _read_limited(
                        xml_stream,
                        policy.max_model_description_bytes,
                        policy.read_chunk_bytes,
                        "modelDescription.xml",
                    )

                verified_total: int = len(model_description_xml)
                for info in entries:
                    if info.is_dir() or info is model_description_info:
                        pass
                    else:
                        with archive.open(info, mode="r") as payload_stream:
                            verified_total += _drain_limited(
                                payload_stream,
                                policy.max_entry_uncompressed_bytes,
                                policy.read_chunk_bytes,
                                info.filename,
                            )
                        if verified_total <= policy.max_total_uncompressed_bytes:
                            pass
                        else:
                            raise ValueError(
                                "FMU archive exceeds the total verified byte limit"
                            )

            archive_stream.seek(0)
            final_sha256: str
            final_size: int
            final_sha256, final_size = hash_fmu_stream(
                archive_stream,
                str(path),
                policy.max_archive_bytes,
                policy.read_chunk_bytes,
            )
            if final_sha256 == archive_sha256 and final_size == archive_size:
                pass
            else:
                raise ValueError(f"FMU archive changed during inspection: {path}")
    except (KeyError, NotImplementedError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Could not inspect FMU archive {path}") from exc

    receipt: FmuInspectionReceipt = FmuInspectionReceipt(
        path=path,
        source_kind=FmuSourceKind.ZIP,
        sha256_digest=archive_sha256,
        model_description_sha256=hashlib.sha256(model_description_xml).hexdigest(),
        source_size=archive_size,
        entry_count=len(entries),
        total_uncompressed_size=total_uncompressed_size,
        model_description_size=len(model_description_xml),
        platforms=tuple(sorted(platforms)),
        binary_entries=tuple(sorted(binary_entries)),
        source_entries=tuple(sorted(source_entries)),
        compression_methods=tuple(sorted(compression_methods)),
        max_observed_compression_ratio=max_observed_ratio,
    )
    return FmuInspectionResult(model_description_xml=model_description_xml, receipt=receipt)


def _raise_directory_walk_error(error: OSError) -> None:
    """Translate a directory traversal error to the FMI import boundary.

    :param error: Filesystem error reported by ``os.walk``.
    :return: None.
    :raises ValueError: Always, because a partial tree is not inspectable.
    """

    raise ValueError(f"Could not inspect FMU directory: {error}") from error


def is_fmu_link_or_reparse_point(path: Path) -> bool:
    """Return whether an FMU path redirects traversal through filesystem metadata.

    :param path: Source path to inspect without following it.
    :return: ``True`` for symbolic links and Windows reparse points.
    """

    path_status: os.stat_result = path.lstat()
    if stat.S_ISLNK(path_status.st_mode):
        result: bool = True
    elif os.name == "nt":
        result = bool(
            path_status.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
        )
    else:
        result = False
    return result


def _inspect_directory(
    path: Path,
    policy: FmuArchiveInspectionPolicy,
) -> FmuInspectionResult:
    """Inspect one extracted FMU directory without following links.

    :param path: Resolved extracted FMU directory.
    :param policy: Finite inspection limits.
    :return: Validated XML bytes and deterministic directory receipt.
    :raises ValueError: If the directory violates any inspection rule.
    """

    files: list[tuple[str, Path, int]] = list()
    directory_entries: list[str] = list()
    entry_count: int = 0
    total_uncompressed_size: int = 0
    seen_names: set[str] = set()

    current_root: str
    directory_names: list[str]
    file_names: list[str]
    for current_root, directory_names, file_names in os.walk(
        path,
        followlinks=False,
        onerror=_raise_directory_walk_error,
    ):
        root_path: Path = Path(current_root)
        directory_name: str
        for directory_name in directory_names:
            directory_path: Path = root_path / directory_name
            if is_fmu_link_or_reparse_point(directory_path):
                raise ValueError(f"FMU directory links are not accepted: {directory_path}")
            else:
                pass
            relative_directory: str = directory_path.relative_to(path).as_posix()
            portable_directory: str = _portable_entry_name(relative_directory, policy)
            portable_key: str = portable_directory.casefold()
            if portable_key in seen_names:
                raise ValueError(
                    f"FMU directory contains a duplicate portable path: {portable_directory!r}"
                )
            else:
                seen_names.add(portable_key)
                directory_entries.append(portable_directory)
            entry_count += 1
            if entry_count <= policy.max_entries:
                pass
            else:
                raise ValueError(
                    f"FMU directory has more than {policy.max_entries} entries"
                )

        file_name: str
        for file_name in file_names:
            file_path: Path = root_path / file_name
            if is_fmu_link_or_reparse_point(file_path) or not file_path.is_file():
                raise ValueError(f"FMU directory special files are not accepted: {file_path}")
            else:
                pass
            relative_file: str = file_path.relative_to(path).as_posix()
            portable_file: str = _portable_entry_name(relative_file, policy)
            portable_file_key: str = portable_file.casefold()
            if portable_file_key in seen_names:
                raise ValueError(
                    f"FMU directory contains a duplicate portable path: {portable_file!r}"
                )
            else:
                seen_names.add(portable_file_key)
            file_size: int = file_path.stat().st_size
            if file_size <= policy.max_entry_uncompressed_bytes:
                pass
            else:
                raise ValueError(
                    f"FMU entry {portable_file!r} exceeds the per-entry inspection limit"
                )
            files.append((portable_file, file_path, file_size))
            entry_count += 1
            if entry_count <= policy.max_entries:
                pass
            else:
                raise ValueError(
                    f"FMU directory has more than {policy.max_entries} entries"
                )
            total_uncompressed_size += file_size
            if total_uncompressed_size <= policy.max_total_uncompressed_bytes:
                pass
            else:
                raise ValueError("FMU directory exceeds the total byte limit")

    if entry_count > 0:
        pass
    else:
        raise ValueError(f"FMU directory is empty: {path}")

    digest = hashlib.sha256()
    model_description_xml: bytes | None = None
    platforms: set[str] = set()
    binary_entries: list[str] = list()
    source_entries: list[str] = list()
    sorted_directory_entries: list[str] = sorted(directory_entries)
    directory_entry: str
    for directory_entry in sorted_directory_entries:
        digest.update(b"D\x00")
        digest.update(directory_entry.encode("utf-8"))
        digest.update(b"\x00")
    sorted_files: list[tuple[str, Path, int]] = sorted(files)
    verified_total_size: int = 0
    entry_name: str
    file_path: Path
    file_size: int
    for entry_name, file_path, file_size in sorted_files:
        digest.update(b"F\x00")
        digest.update(entry_name.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(str(file_size).encode("ascii"))
        digest.update(b"\x00")
        _classify_payload(entry_name, platforms, binary_entries, source_entries)
        with file_path.open("rb") as stream:
            if entry_name == "modelDescription.xml":
                file_bytes: bytes = _read_limited(
                    stream,
                    policy.max_model_description_bytes,
                    policy.read_chunk_bytes,
                    entry_name,
                )
                digest.update(file_bytes)
                model_description_xml = file_bytes
                consumed_bytes: int = len(file_bytes)
            else:
                reading: bool = True
                consumed_bytes = 0
                while reading:
                    chunk: bytes = stream.read(
                        min(
                            policy.read_chunk_bytes,
                            policy.max_entry_uncompressed_bytes + 1 - consumed_bytes,
                        )
                    )
                    if len(chunk) == 0:
                        reading = False
                    else:
                        consumed_bytes += len(chunk)
                        if consumed_bytes <= policy.max_entry_uncompressed_bytes:
                            digest.update(chunk)
                        else:
                            raise ValueError(
                                f"FMU entry exceeds the inspection byte limit: {entry_name!r}"
                            )
        if consumed_bytes == file_size:
            pass
        else:
            raise ValueError(
                f"FMU directory entry changed during inspection: {entry_name!r}"
            )
        verified_total_size += consumed_bytes
        if verified_total_size <= policy.max_total_uncompressed_bytes:
            pass
        else:
            raise ValueError("FMU directory exceeds the verified total byte limit")

    if model_description_xml is not None:
        pass
    else:
        raise ValueError(f"Directory {path} does not contain root modelDescription.xml")

    receipt: FmuInspectionReceipt = FmuInspectionReceipt(
        path=path,
        source_kind=FmuSourceKind.DIRECTORY,
        sha256_digest=digest.hexdigest(),
        model_description_sha256=hashlib.sha256(model_description_xml).hexdigest(),
        source_size=verified_total_size,
        entry_count=entry_count,
        total_uncompressed_size=verified_total_size,
        model_description_size=len(model_description_xml),
        platforms=tuple(sorted(platforms)),
        binary_entries=tuple(sorted(binary_entries)),
        source_entries=tuple(sorted(source_entries)),
        compression_methods=tuple(),
        max_observed_compression_ratio=1.0,
    )
    return FmuInspectionResult(model_description_xml=model_description_xml, receipt=receipt)


def inspect_fmu(
    path: str | Path,
    policy: FmuArchiveInspectionPolicy | None = None,
) -> FmuInspectionResult:
    """Inspect an FMU archive or directory without extracting or loading code.

    :param path: FMU ZIP or already extracted directory.
    :param policy: Optional finite inspection policy.
    :return: Validated model-description bytes and an observed-source receipt.
    :raises ValueError: If the source is missing, linked, or unsafe.
    """

    source_path: Path = Path(path)
    try:
        if is_fmu_link_or_reparse_point(source_path):
            raise ValueError(f"FMU source links are not accepted: {source_path}")
        else:
            pass
        if source_path.exists():
            pass
        else:
            raise ValueError(f"FMU source not found: {source_path}")
        normalized_path: Path = source_path.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"Could not inspect FMU source {source_path}") from exc
    if policy is None:
        effective_policy: FmuArchiveInspectionPolicy = FmuArchiveInspectionPolicy()
    else:
        effective_policy = policy

    try:
        if normalized_path.is_dir():
            result: FmuInspectionResult = _inspect_directory(normalized_path, effective_policy)
        elif normalized_path.is_file():
            result = _inspect_zip(normalized_path, effective_policy)
        else:
            raise ValueError(
                f"FMU source is not a regular file or directory: {normalized_path}"
            )
    except OSError as exc:
        raise ValueError(f"Could not inspect FMU source {normalized_path}") from exc
    return result
