# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import hashlib
import stat
import struct
import zipfile
from pathlib import Path

import pytest

from VeraGridEngine.IO.fmu.Elements.inspection import (
    FmuArchiveInspectionPolicy,
    FmuInspectionResult,
    inspect_fmu,
)
from VeraGridEngine.enumerations import FmuSourceKind


def _fmi_two_xml() -> bytes:
    """Return one minimal valid FMI 2 model-description fixture.

    :return: UTF-8 XML payload.
    """

    return (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<fmiModelDescription fmiVersion="2.0" modelName="Safe" guid="safe-guid">'
        b'<CoSimulation modelIdentifier="safe_model"/>'
        b'<ModelVariables/>'
        b'</fmiModelDescription>'
    )


def _write_fmu(
    path: Path,
    entries: tuple[tuple[str, bytes], ...],
    compression: int = zipfile.ZIP_DEFLATED,
) -> None:
    """Write one controlled FMU ZIP fixture.

    :param path: Output FMU path.
    :param entries: Ordered portable names and payload bytes.
    :param compression: ZIP compression method.
    :return: None.
    """

    with zipfile.ZipFile(path, mode="w", compression=compression) as archive:
        entry_name: str
        payload: bytes
        for entry_name, payload in entries:
            archive.writestr(entry_name, payload)


def test_repository_fmu_passes_default_inspection_policy() -> None:
    """Verify an existing project artifact passes the hardened boundary."""

    fmu_path: Path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "fmi"
        / "artifacts"
        / "FrequencyLoadPilot.fmu"
    )

    result: FmuInspectionResult = inspect_fmu(fmu_path)

    assert result.receipt.source_kind is FmuSourceKind.ZIP
    assert result.receipt.entry_count > 0
    assert result.receipt.model_description_size > 0
    assert result.receipt.get_contains_native_code() is True


def test_zip_inspection_returns_observed_source_receipt(tmp_path: Path) -> None:
    """Verify ZIP metadata, classification, and digests bind to its bytes.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "safe.fmu"
    _write_fmu(
        fmu_path,
        (
            ("modelDescription.xml", _fmi_two_xml()),
            ("binaries/win64/safe_model.dll", b"not-executed"),
            ("sources/safe_model.c", b"int safe_model(void) { return 0; }"),
        ),
    )

    result: FmuInspectionResult = inspect_fmu(fmu_path)

    assert result.model_description_xml == _fmi_two_xml()
    assert result.receipt.sha256 == hashlib.sha256(fmu_path.read_bytes()).hexdigest()
    assert result.receipt.model_description_sha256 == hashlib.sha256(_fmi_two_xml()).hexdigest()
    assert result.receipt.platforms == ("win64",)
    assert result.receipt.get_contains_native_code() is True
    assert result.receipt.get_contains_source_code() is True


def test_directory_inspection_has_deterministic_receipt(tmp_path: Path) -> None:
    """Verify extracted-directory inspection is deterministic and bounded.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    root: Path = tmp_path / "safe"
    binary_directory: Path = root / "binaries" / "linux64"
    binary_directory.mkdir(parents=True)
    (root / "modelDescription.xml").write_bytes(_fmi_two_xml())
    (binary_directory / "safe_model.so").write_bytes(b"not-executed")

    first: FmuInspectionResult = inspect_fmu(root)
    second: FmuInspectionResult = inspect_fmu(root)

    assert first.receipt.source_kind is FmuSourceKind.DIRECTORY
    assert first.receipt.sha256 == second.receipt.sha256
    assert first.receipt.platforms == ("linux64",)


def test_directory_receipt_includes_empty_directories(tmp_path: Path) -> None:
    """Verify empty directory changes alter the observed tree receipt.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    root: Path = tmp_path / "directory-receipt"
    root.mkdir()
    (root / "modelDescription.xml").write_bytes(_fmi_two_xml())
    before: FmuInspectionResult = inspect_fmu(root)
    (root / "resources").mkdir()
    after: FmuInspectionResult = inspect_fmu(root)

    assert before.receipt.sha256 != after.receipt.sha256
    assert before.receipt.entry_count + 1 == after.receipt.entry_count


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    """Verify archive entries cannot escape a future staging directory.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "traversal.fmu"
    _write_fmu(fmu_path, (("modelDescription.xml", _fmi_two_xml()), ("../escape.dll", b"x")))

    with pytest.raises(ValueError, match="not normalized"):
        inspect_fmu(fmu_path)


@pytest.mark.parametrize(
    "entry_name",
    ("resources/CON.txt", "resources/a//b.txt", "resources/a/./b.txt", "resources/a?.txt"),
)
def test_non_portable_paths_are_rejected(tmp_path: Path, entry_name: str) -> None:
    """Verify entries unsafe on supported platforms fail closed.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param entry_name: Non-portable path under test.
    :return: None.
    """

    fmu_path: Path = tmp_path / "non-portable.fmu"
    _write_fmu(fmu_path, (("modelDescription.xml", _fmi_two_xml()), (entry_name, b"x")))

    with pytest.raises(ValueError, match="non-portable|reserved|not normalized"):
        inspect_fmu(fmu_path)


def test_raw_backslash_path_is_rejected_before_host_normalization(tmp_path: Path) -> None:
    """Verify Windows normalization cannot hide a raw ZIP backslash.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "raw-backslash.fmu"
    _write_fmu(
        fmu_path,
        (("modelDescription.xml", _fmi_two_xml()), ("resources/data.txt", b"x")),
    )
    portable_name: bytes = b"resources/data.txt"
    raw_name: bytes = b"resources\\data.txt"
    archive_bytes: bytes = fmu_path.read_bytes()
    assert archive_bytes.count(portable_name) == 2
    fmu_path.write_bytes(archive_bytes.replace(portable_name, raw_name))

    with pytest.raises(ValueError, match="non-portable path separator"):
        inspect_fmu(fmu_path)


def test_casefolded_duplicate_path_is_rejected(tmp_path: Path) -> None:
    """Verify case-insensitive platforms cannot observe ambiguous payloads.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "duplicate.fmu"
    _write_fmu(
        fmu_path,
        (
            ("modelDescription.xml", _fmi_two_xml()),
            ("resources/Data.txt", b"one"),
            ("resources/data.txt", b"two"),
        ),
    )

    with pytest.raises(ValueError, match="duplicate portable path"):
        inspect_fmu(fmu_path)


def test_unicode_normalized_duplicate_path_is_rejected(tmp_path: Path) -> None:
    """Verify canonically equivalent Unicode paths cannot be ambiguous.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "unicode-duplicate.fmu"
    _write_fmu(
        fmu_path,
        (
            ("modelDescription.xml", _fmi_two_xml()),
            ("resources/é.txt", b"one"),
            ("resources/e\u0301.txt", b"two"),
        ),
    )

    with pytest.raises(ValueError, match="duplicate portable path"):
        inspect_fmu(fmu_path)


def test_archive_file_cannot_be_another_entry_ancestor(tmp_path: Path) -> None:
    """Verify a file/directory conflict cannot produce platform-specific trees.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "ancestor-conflict.fmu"
    _write_fmu(
        fmu_path,
        (
            ("modelDescription.xml", _fmi_two_xml()),
            ("binaries", b"file"),
            ("binaries/win64/model.dll", b"binary"),
        ),
    )

    with pytest.raises(ValueError, match="file ancestor"):
        inspect_fmu(fmu_path)


def test_symbolic_link_zip_entry_is_rejected(tmp_path: Path) -> None:
    """Verify ZIP metadata cannot introduce a symbolic link.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "link.fmu"
    with zipfile.ZipFile(fmu_path, mode="w") as archive:
        archive.writestr("modelDescription.xml", _fmi_two_xml())
        link_info: zipfile.ZipInfo = zipfile.ZipInfo("resources/link")
        link_info.create_system = 3
        link_info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link_info, "../../outside")

    with pytest.raises(ValueError, match="links are not accepted"):
        inspect_fmu(fmu_path)


def test_regular_file_metadata_with_directory_path_is_rejected(tmp_path: Path) -> None:
    """Verify ZIP file-type metadata agrees with a trailing directory slash.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "file-directory-conflict.fmu"
    with zipfile.ZipFile(fmu_path, mode="w") as archive:
        archive.writestr("modelDescription.xml", _fmi_two_xml())
        file_info: zipfile.ZipInfo = zipfile.ZipInfo("resources/")
        file_info.create_system = 3
        file_info.external_attr = (stat.S_IFREG | 0o644) << 16
        archive.writestr(file_info, b"")

    with pytest.raises(ValueError, match="file metadata conflicts"):
        inspect_fmu(fmu_path)


def test_unsupported_compression_method_is_rejected(tmp_path: Path) -> None:
    """Verify the boundary accepts only the portable FMU ZIP methods.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "bzip2.fmu"
    _write_fmu(
        fmu_path,
        (("modelDescription.xml", _fmi_two_xml()),),
        compression=zipfile.ZIP_BZIP2,
    )

    with pytest.raises(ValueError, match="Unsupported ZIP compression method"):
        inspect_fmu(fmu_path)


def test_corrupt_payload_crc_is_rejected(tmp_path: Path) -> None:
    """Verify optional full streaming detects payload corruption.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "bad-crc.fmu"
    payload: bytes = b"unique-crc-payload"
    _write_fmu(
        fmu_path,
        (("modelDescription.xml", _fmi_two_xml()), ("resources/data.bin", payload)),
        compression=zipfile.ZIP_STORED,
    )
    archive_bytes: bytes = fmu_path.read_bytes()
    assert archive_bytes.count(payload) == 1
    fmu_path.write_bytes(archive_bytes.replace(payload, b"changed-crc-value!"))

    with pytest.raises(ValueError, match="Could not inspect FMU archive"):
        inspect_fmu(fmu_path)


def test_shallow_binary_path_is_not_reported_as_a_platform(tmp_path: Path) -> None:
    """Verify only ``binaries/<platform>/<file>`` declares a platform.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "shallow-binary.fmu"
    _write_fmu(
        fmu_path,
        (("modelDescription.xml", _fmi_two_xml()), ("binaries/model.dll", b"binary")),
    )

    result: FmuInspectionResult = inspect_fmu(fmu_path)

    assert result.receipt.platforms == tuple()
    assert result.receipt.binary_entries == tuple()


def test_mis_cased_binary_directory_is_not_reported_as_a_platform(tmp_path: Path) -> None:
    """Verify FMI payload directory classification is case-sensitive.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "mis-cased-binary.fmu"
    _write_fmu(
        fmu_path,
        (("modelDescription.xml", _fmi_two_xml()), ("Binaries/win64/model.dll", b"binary")),
    )

    result: FmuInspectionResult = inspect_fmu(fmu_path)

    assert result.receipt.platforms == tuple()
    assert result.receipt.binary_entries == tuple()


def test_compression_ratio_limit_is_rejected(tmp_path: Path) -> None:
    """Verify highly expanding entries fail before extraction.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "ratio.fmu"
    _write_fmu(
        fmu_path,
        (("modelDescription.xml", _fmi_two_xml()), ("resources/repeated.bin", b"0" * 100_000)),
    )
    policy: FmuArchiveInspectionPolicy = FmuArchiveInspectionPolicy(max_compression_ratio=5.0)

    with pytest.raises(ValueError, match="compression-ratio limit"):
        inspect_fmu(fmu_path, policy=policy)


def test_entry_count_limit_is_rejected(tmp_path: Path) -> None:
    """Verify central-directory cardinality is bounded before payload reads.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "entries.fmu"
    _write_fmu(fmu_path, (("modelDescription.xml", _fmi_two_xml()), ("resources/a", b"a")))
    policy: FmuArchiveInspectionPolicy = FmuArchiveInspectionPolicy(max_entries=1)

    with pytest.raises(ValueError, match="policy maximum"):
        inspect_fmu(fmu_path, policy=policy)


def test_declared_entry_bomb_is_rejected_during_bounded_preflight(tmp_path: Path) -> None:
    """Verify EOCD entry limits act before ``ZipFile`` builds ``ZipInfo`` objects.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "metadata-bomb.fmu"
    _write_fmu(fmu_path, (("modelDescription.xml", _fmi_two_xml()),))
    archive_bytes: bytearray = bytearray(fmu_path.read_bytes())
    eocd_index: int = archive_bytes.rfind(b"PK\x05\x06")
    assert eocd_index >= 0
    struct.pack_into("<H", archive_bytes, eocd_index + 8, 5000)
    struct.pack_into("<H", archive_bytes, eocd_index + 10, 5000)
    fmu_path.write_bytes(bytes(archive_bytes))

    with pytest.raises(ValueError, match="declares 5000 entries"):
        inspect_fmu(fmu_path)


def test_underdeclared_entry_count_cannot_bypass_preflight_limit(tmp_path: Path) -> None:
    """Verify actual central headers, not only EOCD claims, enforce cardinality.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "underdeclared-entries.fmu"
    _write_fmu(
        fmu_path,
        (("modelDescription.xml", _fmi_two_xml()), ("resources/data.bin", b"data")),
    )
    archive_bytes: bytearray = bytearray(fmu_path.read_bytes())
    eocd_index: int = archive_bytes.rfind(b"PK\x05\x06")
    assert eocd_index >= 0
    struct.pack_into("<H", archive_bytes, eocd_index + 8, 1)
    struct.pack_into("<H", archive_bytes, eocd_index + 10, 1)
    fmu_path.write_bytes(bytes(archive_bytes))
    policy: FmuArchiveInspectionPolicy = FmuArchiveInspectionPolicy(max_entries=1)

    with pytest.raises(ValueError, match="more than 1 central-file headers"):
        inspect_fmu(fmu_path, policy=policy)


def test_central_directory_byte_limit_is_rejected_before_zip_open(tmp_path: Path) -> None:
    """Verify ZIP metadata bytes have a pre-materialization limit.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "large-directory.fmu"
    _write_fmu(fmu_path, (("modelDescription.xml", _fmi_two_xml()),))
    policy: FmuArchiveInspectionPolicy = FmuArchiveInspectionPolicy(
        max_central_directory_bytes=1
    )

    with pytest.raises(ValueError, match="central directory exceeds"):
        inspect_fmu(fmu_path, policy=policy)


def test_zip64_end_record_is_preflighted_and_accepted(tmp_path: Path) -> None:
    """Verify bounded metadata preflight preserves valid ZIP64 interoperability.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "zip64.fmu"
    _write_fmu(fmu_path, (("modelDescription.xml", _fmi_two_xml()),))
    archive_bytes: bytes = fmu_path.read_bytes()
    eocd_index: int = archive_bytes.rfind(b"PK\x05\x06")
    assert eocd_index >= 0
    eocd: tuple[bytes, int, int, int, int, int, int, int] = struct.unpack_from(
        "<4s4H2LH",
        archive_bytes,
        eocd_index,
    )
    zip64_record: bytes = struct.pack(
        "<4sQ2H2L4Q",
        b"PK\x06\x06",
        44,
        45,
        45,
        0,
        0,
        eocd[3],
        eocd[4],
        eocd[5],
        eocd[6],
    )
    zip64_locator: bytes = struct.pack(
        "<4sLQL",
        b"PK\x06\x07",
        0,
        eocd_index,
        1,
    )
    classic_eocd: bytearray = bytearray(archive_bytes[eocd_index:])
    struct.pack_into("<H", classic_eocd, 8, 0xFFFF)
    struct.pack_into("<H", classic_eocd, 10, 0xFFFF)
    struct.pack_into("<L", classic_eocd, 12, 0xFFFFFFFF)
    struct.pack_into("<L", classic_eocd, 16, 0xFFFFFFFF)
    fmu_path.write_bytes(
        archive_bytes[:eocd_index]
        + zip64_record
        + zip64_locator
        + bytes(classic_eocd)
    )

    result: FmuInspectionResult = inspect_fmu(fmu_path)

    assert result.receipt.entry_count == 1


def test_model_description_size_limit_is_rejected(tmp_path: Path) -> None:
    """Verify XML bytes have an independent conservative limit.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "large-xml.fmu"
    _write_fmu(fmu_path, (("modelDescription.xml", _fmi_two_xml()),))
    policy: FmuArchiveInspectionPolicy = FmuArchiveInspectionPolicy(
        max_model_description_bytes=32
    )

    with pytest.raises(ValueError, match="modelDescription.xml exceeds"):
        inspect_fmu(fmu_path, policy=policy)


def test_root_model_description_is_required(tmp_path: Path) -> None:
    """Verify a nested XML file cannot impersonate the FMU root declaration.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "nested.fmu"
    _write_fmu(fmu_path, (("nested/modelDescription.xml", _fmi_two_xml()),))

    with pytest.raises(ValueError, match="root modelDescription.xml"):
        inspect_fmu(fmu_path)


@pytest.mark.parametrize(
    ("argument_name", "argument_value"),
    (
        ("max_entries", 0),
        ("max_central_directory_bytes", 0),
        ("max_path_depth", -1),
        ("read_chunk_bytes", 0),
    ),
)
def test_non_positive_integer_policy_limits_are_rejected(
    argument_name: str,
    argument_value: int,
) -> None:
    """Verify policy construction cannot disable finite resource limits.

    :param argument_name: Policy argument represented by the test case.
    :param argument_value: Invalid non-positive limit.
    :return: None.
    """

    if argument_name == "max_entries":
        with pytest.raises(ValueError, match="max_entries must be positive"):
            FmuArchiveInspectionPolicy(max_entries=argument_value)
    elif argument_name == "max_central_directory_bytes":
        with pytest.raises(ValueError, match="max_central_directory_bytes must be positive"):
            FmuArchiveInspectionPolicy(max_central_directory_bytes=argument_value)
    elif argument_name == "max_path_depth":
        with pytest.raises(ValueError, match="max_path_depth must be positive"):
            FmuArchiveInspectionPolicy(max_path_depth=argument_value)
    else:
        with pytest.raises(ValueError, match="read_chunk_bytes must be positive"):
            FmuArchiveInspectionPolicy(read_chunk_bytes=argument_value)


@pytest.mark.parametrize("ratio", (float("inf"), float("nan"), 0.5))
def test_non_finite_or_too_small_compression_ratio_is_rejected(ratio: float) -> None:
    """Verify the compression-ratio limit cannot be disabled.

    :param ratio: Invalid expansion-ratio ceiling.
    :return: None.
    """

    with pytest.raises(ValueError, match="max_compression_ratio must be at least"):
        FmuArchiveInspectionPolicy(max_compression_ratio=ratio)
