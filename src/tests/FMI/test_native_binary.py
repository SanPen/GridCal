# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Tests for fail-closed FMI native binary selection."""

from __future__ import annotations

import platform
from pathlib import Path
import sys
import zipfile

import pytest

from VeraGridEngine.IO.fmu.Elements.bindings import FmuImportConfig
from VeraGridEngine.IO.fmu.Elements.inspection import FmuInspectionReceipt, inspect_fmu
from VeraGridEngine.IO.fmu.native_binary import (
    _resolve_legacy_host_binary,
    _resolve_fmi_three_binary_platform,
    resolve_fmi_three_host_binary,
    validate_fmi_three_native_binary,
    validate_fmi_two_native_binary,
    validate_native_binary,
)
from VeraGridEngine.IO.fmu.host import open_fmu_runtime_host
from VeraGridEngine.IO.fmu.staging import FmuStagingArea, stage_fmu_source
from VeraGridEngine.enumerations import FmiVersion


def _write_fmu_archive(
    path: Path,
    xml_bytes: bytes,
    binary_entries: tuple[str, ...],
    include_sources: bool,
) -> Path:
    """Write common inspected FMU entries without duplicating ZIP mechanics.

    :param path: Destination FMU archive path.
    :param xml_bytes: Version-specific model-description bytes.
    :param binary_entries: Native binary entries written to the archive.
    :param include_sources: Whether to add a source file.
    :return: Written archive path.
    """

    archive: zipfile.ZipFile
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("modelDescription.xml", xml_bytes)
        binary_entry: str
        for binary_entry in binary_entries:
            archive.writestr(binary_entry, b"native-test-binary")
        if include_sources:
            archive.writestr("sources/model.c", b"int model_source = 1;\n")
        else:
            pass
    return path


def _write_fmi_two_archive(
    path: Path,
    binary_entries: tuple[str, ...],
    include_sources: bool = False,
    model_identifier: str = "NativeModel",
) -> Path:
    """Write a metadata-valid FMI 2 archive with selected binary paths.

    :param path: Destination FMU archive path.
    :param binary_entries: Native binary entries written to the archive.
    :param include_sources: Whether to add a source file.
    :param model_identifier: Co-Simulation identifier declared by the metadata.
    :return: Written archive path.
    """

    xml_text: str = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<fmiModelDescription fmiVersion="2.0" modelName="NativeModel" '
        'guid="native-guid">\n'
        f'  <CoSimulation modelIdentifier="{model_identifier}"/>\n'
        '  <ModelVariables/>\n'
        '</fmiModelDescription>\n'
    )
    xml_bytes: bytes = xml_text.encode("utf-8")
    return _write_fmu_archive(path, xml_bytes, binary_entries, include_sources)


def _write_fmi_three_archive(
    path: Path,
    binary_entries: tuple[str, ...],
    include_sources: bool = False,
    model_identifier: str = "NativeModel",
) -> Path:
    """Write a metadata-valid FMI 3 archive with selected binary paths.

    :param path: Destination FMU archive path.
    :param binary_entries: Native binary entries written to the archive.
    :param include_sources: Whether to add a source file.
    :param model_identifier: Co-Simulation identifier declared by the metadata.
    :return: Written archive path.
    """

    xml_text: str = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<fmiModelDescription fmiVersion="3.0" modelName="NativeModel" '
        'instantiationToken="native-token">\n'
        f'  <CoSimulation modelIdentifier="{model_identifier}"/>\n'
        '  <ModelVariables>\n'
        '    <Float64 name="time" valueReference="0" causality="independent" '
        'variability="continuous"/>\n'
        '  </ModelVariables>\n'
        '  <ModelStructure/>\n'
        '</fmiModelDescription>\n'
    )
    xml_bytes: bytes = xml_text.encode("utf-8")
    return _write_fmu_archive(path, xml_bytes, binary_entries, include_sources)


def _inspect_receipt(path: Path) -> FmuInspectionReceipt:
    """Inspect one test FMU and return its bounded receipt.

    :param path: Archive or extracted-directory source path.
    :return: Bounded inspection receipt.
    """

    receipt: FmuInspectionReceipt = inspect_fmu(path).receipt
    return receipt


def _co_simulation_artifact() -> Path:
    """Return the certified repository FMI 2 Co-Simulation artifact.

    :return: Absolute artifact path.
    """

    tests_root: Path = Path(__file__).resolve().parents[1]
    return tests_root / "data" / "fmi" / "artifacts" / "FrequencyLoadPilot.fmu"


def _model_exchange_artifact() -> Path:
    """Return the repository FMI 2 Model Exchange artifact.

    :return: Absolute artifact path.
    """

    tests_root: Path = Path(__file__).resolve().parents[1]
    return (
        tests_root
        / "data"
        / "fmi"
        / "artifacts"
        / "ExampleRmsMeDevice.fmu"
    )


def test_host_binary_contract_matches_process_platform_and_bitness() -> None:
    """Verify FMI 2 host selection uses the process ABI naming convention.

    :return: None.
    """

    platform_name: str
    library_suffix: str
    platform_name, library_suffix = _resolve_legacy_host_binary()
    if sys.maxsize <= 2**32:
        expected_bitness: str = "32"
    else:
        expected_bitness = "64"
    if sys.platform.startswith("win"):
        expected_platform: str = f"win{expected_bitness}"
        expected_suffix: str = ".dll"
    elif sys.platform.startswith("linux"):
        expected_platform = f"linux{expected_bitness}"
        expected_suffix = ".so"
    elif sys.platform == "darwin":
        expected_platform = f"darwin{expected_bitness}"
        expected_suffix = ".dylib"
    else:
        pytest.skip("The FMI 2 native host does not support this operating system")

    assert platform_name == expected_platform
    assert library_suffix == expected_suffix


def test_fmi_three_host_binary_contract_matches_process_architecture_and_system() -> None:
    """Verify FMI 3 host selection uses the process platform tuple.

    :return: None.
    """

    platform_tuple: str
    library_suffix: str
    platform_tuple, library_suffix = resolve_fmi_three_host_binary()
    expected_platform_tuple: str
    expected_suffix: str
    expected_platform_tuple, expected_suffix = _resolve_fmi_three_binary_platform(
        machine_name=platform.machine(),
        is_32_bit_process=sys.maxsize <= 2**32,
        python_platform_name=sys.platform,
    )

    assert platform_tuple == expected_platform_tuple
    assert library_suffix == expected_suffix


@pytest.mark.parametrize(
    (
        "machine_name",
        "is_32_bit_process",
        "python_platform_name",
        "expected_platform_tuple",
        "expected_suffix",
    ),
    (
        ("AMD64", False, "win32", "x86_64-windows", ".dll"),
        ("AMD64", True, "win32", "x86-windows", ".dll"),
        ("x86_64", False, "linux", "x86_64-linux", ".so"),
        ("i686", True, "linux", "x86-linux", ".so"),
        ("arm64", False, "darwin", "aarch64-darwin", ".dylib"),
        ("aarch64", False, "linux", "aarch64-linux", ".so"),
        ("arm64", False, "win32", "aarch64-windows", ".dll"),
    ),
)
def test_fmi_three_platform_matrix_matches_standard_binary_tuples(
    machine_name: str,
    is_32_bit_process: bool,
    python_platform_name: str,
    expected_platform_tuple: str,
    expected_suffix: str,
) -> None:
    """Verify supported process identities map to canonical FMI 3 tuples.

    :param machine_name: Machine spelling supplied by the test case.
    :param is_32_bit_process: Whether the test case represents a 32-bit process.
    :param python_platform_name: Python platform spelling supplied by the test case.
    :param expected_platform_tuple: Canonical FMI 3 tuple expected for the case.
    :param expected_suffix: Native-library suffix expected for the case.
    :return: None.
    """

    # Exercise the pure owner without mutating process-global platform state.
    platform_tuple: str
    library_suffix: str
    platform_tuple, library_suffix = _resolve_fmi_three_binary_platform(
        machine_name=machine_name,
        is_32_bit_process=is_32_bit_process,
        python_platform_name=python_platform_name,
    )
    assert platform_tuple == expected_platform_tuple
    assert library_suffix == expected_suffix


def test_fmi_three_platform_matrix_rejects_unknown_identity() -> None:
    """Verify unknown architectures and systems remain fail-closed.

    :return: None.
    """

    with pytest.raises(RuntimeError, match="host architecture 'riscv64'"):
        _resolve_fmi_three_binary_platform(
            machine_name="riscv64",
            is_32_bit_process=False,
            python_platform_name="linux",
        )
    with pytest.raises(RuntimeError, match="host platform 'freebsd14'"):
        _resolve_fmi_three_binary_platform(
            machine_name="x86_64",
            is_32_bit_process=False,
            python_platform_name="freebsd14",
        )


def test_fmi_three_exact_main_binary_is_selected_from_multi_binary_archive(
    tmp_path: Path,
) -> None:
    """Verify FMI 3 accepts the exact interface library among dependencies.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    platform_tuple: str
    library_suffix: str
    platform_tuple, library_suffix = resolve_fmi_three_host_binary()
    expected_entry: str = f"binaries/{platform_tuple}/NativeModel{library_suffix}"
    source: Path = _write_fmi_three_archive(
        tmp_path / "fmi3-multi-platform.fmu",
        (
            expected_entry,
            f"binaries/{platform_tuple}/dependency{library_suffix}",
            "binaries/vendor-platform/NativeModel.vendor",
        ),
        include_sources=True,
    )

    receipt: FmuInspectionReceipt = _inspect_receipt(source)
    validate_fmi_three_native_binary(receipt, "NativeModel")
    validate_native_binary(
        receipt,
        FmiVersion.FMI_3_0,
        "NativeModel",
    )


def test_fmi_three_noncanonical_main_binary_locations_fail_closed(
    tmp_path: Path,
) -> None:
    """Verify the FMI 3 tuple, identifier, case, and depth are exact.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    platform_tuple: str
    library_suffix: str
    platform_tuple, library_suffix = resolve_fmi_three_host_binary()
    invalid_entries: tuple[str, ...] = (
        f"binaries/other-platform/NativeModel{library_suffix}",
        f"binaries/{platform_tuple}/OtherModel{library_suffix}",
        f"Binaries/{platform_tuple}/NativeModel{library_suffix}",
        f"binaries/{platform_tuple.upper()}/NativeModel{library_suffix}",
        f"binaries/{platform_tuple}/nativemodel{library_suffix}",
        f"binaries/{platform_tuple}/nested/NativeModel{library_suffix}",
    )
    invalid_index: int
    invalid_entry: str
    for invalid_index, invalid_entry in enumerate(invalid_entries):
        source: Path = _write_fmi_three_archive(
            tmp_path / f"fmi3-invalid-{invalid_index}.fmu",
            (invalid_entry,),
        )
        with pytest.raises(RuntimeError, match="required current-host binary"):
            validate_fmi_three_native_binary(_inspect_receipt(source), "NativeModel")


def test_fmi_three_source_only_archive_reports_unconnected_compilation(
    tmp_path: Path,
) -> None:
    """Verify FMI 3 source-bearing FMUs do not trigger compilation.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_fmi_three_archive(
        tmp_path / "fmi3-source-only.fmu",
        tuple(),
        include_sources=True,
    )

    with pytest.raises(RuntimeError, match="source compilation is not connected"):
        validate_fmi_three_native_binary(_inspect_receipt(source), "NativeModel")


def test_fmi_three_nested_model_identifier_fails_closed(tmp_path: Path) -> None:
    """Verify an FMI 3 identifier cannot introduce another path component.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    platform_tuple: str
    library_suffix: str
    platform_tuple, library_suffix = resolve_fmi_three_host_binary()
    source: Path = _write_fmi_three_archive(
        tmp_path / "fmi3-nested-identifier.fmu",
        (f"binaries/{platform_tuple}/nested/NativeModel{library_suffix}",),
        model_identifier="nested/NativeModel",
    )

    with pytest.raises(RuntimeError, match="required current-host binary"):
        validate_fmi_three_native_binary(
            _inspect_receipt(source),
            "nested/NativeModel",
        )


def test_fmi_three_execution_gate_blocks_before_native_preflight_and_staging(
    tmp_path: Path,
) -> None:
    """Verify the FMI 2 host rejects FMI 3 before native preflight and staging.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    platform_tuple: str
    library_suffix: str
    platform_tuple, library_suffix = resolve_fmi_three_host_binary()
    source: Path = _write_fmi_three_archive(
        tmp_path / "fmi3-runtime-blocked.fmu",
        (f"binaries/{platform_tuple}/NativeModel{library_suffix}",),
    )
    staging_parent: Path = tmp_path / "runtime"
    staging_parent.mkdir()
    config: FmuImportConfig = FmuImportConfig(
        fmu_path=source,
        extraction_root=staging_parent,
    )

    with pytest.raises(RuntimeError, match="supports FMI 1/2 execution only"):
        open_fmu_runtime_host(config)
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_exact_main_binary_is_selected_from_multi_binary_archive(tmp_path: Path) -> None:
    """Verify extra platforms and dependencies do not make selection ambiguous.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    platform_name: str
    library_suffix: str
    platform_name, library_suffix = _resolve_legacy_host_binary()
    expected_entry: str = f"binaries/{platform_name}/NativeModel{library_suffix}"
    source: Path = _write_fmi_two_archive(
        tmp_path / "multi-platform.fmu",
        (
            expected_entry,
            f"binaries/{platform_name}/dependency{library_suffix}",
            "binaries/vendor-platform/NativeModel.vendor",
        ),
        include_sources=True,
    )

    receipt: FmuInspectionReceipt = _inspect_receipt(source)
    validate_fmi_two_native_binary(receipt, "NativeModel")
    validate_native_binary(receipt, FmiVersion.FMI_2_0, "NativeModel")


def test_fmi_one_native_binary_uses_legacy_layout(tmp_path: Path) -> None:
    """Verify FMI 1 and FMI 2 share the exact legacy binary layout owner.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    platform_name: str
    library_suffix: str
    platform_name, library_suffix = _resolve_legacy_host_binary()
    source: Path = _write_fmi_two_archive(
        tmp_path / "fmi1-dispatch.fmu",
        (f"binaries/{platform_name}/NativeModel{library_suffix}",),
    )

    receipt: FmuInspectionReceipt = _inspect_receipt(source)
    validate_native_binary(receipt, FmiVersion.FMI_1_0, "NativeModel")
    validate_native_binary(receipt, FmiVersion.FMI_2_0, "NativeModel")


def test_noncanonical_main_binary_locations_fail_closed(tmp_path: Path) -> None:
    """Verify platform, identifier, case, and depth must all be exact.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    platform_name: str
    library_suffix: str
    platform_name, library_suffix = _resolve_legacy_host_binary()
    invalid_entries: tuple[str, ...] = (
        f"binaries/other-platform/NativeModel{library_suffix}",
        f"binaries/{platform_name}/OtherModel{library_suffix}",
        f"Binaries/{platform_name}/NativeModel{library_suffix}",
        f"binaries/{platform_name.upper()}/NativeModel{library_suffix}",
        f"binaries/{platform_name}/nativemodel{library_suffix}",
        f"binaries/{platform_name}/nested/NativeModel{library_suffix}",
    )
    invalid_index: int
    invalid_entry: str
    for invalid_index, invalid_entry in enumerate(invalid_entries):
        source: Path = _write_fmi_two_archive(
            tmp_path / f"invalid-{invalid_index}.fmu",
            (invalid_entry,),
        )
        with pytest.raises(RuntimeError, match="required current-host binary"):
            validate_fmi_two_native_binary(_inspect_receipt(source), "NativeModel")


def test_source_only_archive_reports_unconnected_compilation(tmp_path: Path) -> None:
    """Verify source-bearing FMUs do not trigger implicit compilation.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_fmi_two_archive(
        tmp_path / "source-only.fmu",
        tuple(),
        include_sources=True,
    )

    with pytest.raises(RuntimeError, match="source compilation is not connected"):
        validate_fmi_two_native_binary(_inspect_receipt(source), "NativeModel")


def test_archive_without_binary_or_sources_reports_missing_runtime(tmp_path: Path) -> None:
    """Verify metadata-only FMUs fail with a native binary error.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_fmi_two_archive(tmp_path / "metadata-only.fmu", tuple())

    with pytest.raises(RuntimeError, match="required current-host binary"):
        validate_fmi_two_native_binary(_inspect_receipt(source), "NativeModel")


def test_zip_and_directory_receipts_select_the_same_native_entry(tmp_path: Path) -> None:
    """Verify preflight semantics are identical for both accepted source kinds.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    platform_name: str
    library_suffix: str
    platform_name, library_suffix = _resolve_legacy_host_binary()
    expected_entry: str = f"binaries/{platform_name}/NativeModel{library_suffix}"
    source: Path = _write_fmi_two_archive(
        tmp_path / "portable.fmu",
        (expected_entry,),
    )
    archive_receipt: FmuInspectionReceipt = _inspect_receipt(source)
    staging: FmuStagingArea = stage_fmu_source(
        source,
        archive_receipt,
        staging_parent=tmp_path / "staging",
    )
    try:
        directory_receipt: FmuInspectionReceipt = _inspect_receipt(
            staging.get_fmu_directory()
        )
        validate_fmi_two_native_binary(
            archive_receipt,
            "NativeModel",
        )
        validate_fmi_two_native_binary(
            directory_receipt,
            "NativeModel",
        )
    finally:
        staging.close()

    assert expected_entry in archive_receipt.binary_entries
    assert expected_entry in directory_receipt.binary_entries


def test_nested_model_identifier_fails_before_creating_staging(tmp_path: Path) -> None:
    """Verify an identifier cannot convert the main binary into a nested path.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")
    platform_name: str
    library_suffix: str
    platform_name, library_suffix = _resolve_legacy_host_binary()
    source: Path = _write_fmi_two_archive(
        tmp_path / "nested-identifier.fmu",
        (f"binaries/{platform_name}/nested/NativeModel{library_suffix}",),
        model_identifier="nested/NativeModel",
    )
    staging_parent: Path = tmp_path / "runtime"
    staging_parent.mkdir()
    sentinel: Path = staging_parent / "keep.txt"
    sentinel.write_text("caller-owned", encoding="utf-8")
    config: FmuImportConfig = FmuImportConfig(
        fmu_path=source,
        extraction_root=staging_parent,
    )

    with pytest.raises(RuntimeError, match="required current-host binary"):
        open_fmu_runtime_host(config)
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()
    assert sentinel.read_text(encoding="utf-8") == "caller-owned"


def test_repository_fmi_two_artifacts_pass_native_preflight() -> None:
    """Verify both certified FMI 2 interface artifacts remain compatible.

    :return: None.
    """

    if sys.platform.startswith("win"):
        pass
    else:
        pytest.skip("Repository FMI 2 runtime artifacts contain Windows binaries")

    validate_fmi_two_native_binary(
        _inspect_receipt(_co_simulation_artifact()),
        "FrequencyLoadPilot",
    )
    validate_fmi_two_native_binary(
        _inspect_receipt(_model_exchange_artifact()),
        "ExampleRmsMeDevice",
    )
