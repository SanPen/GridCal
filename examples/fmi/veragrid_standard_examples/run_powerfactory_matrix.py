"""Execute the immutable standard electrical FMUs in licensed PowerFactory.

All PowerFactory database mutations are confined to one uniquely named,
disposable current-user project. Raw evidence stays outside the checkout.
"""

from __future__ import annotations
from VeraGridEngine.enumerations import InterfaceType

import argparse
import csv
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import struct
import sys
import time
from typing import cast
import zipfile
from xml.etree import ElementTree

import numpy as np

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.enumerations import FmiVersion
from VeraGridEngine.IO.fmu.compiler import Compiler
from VeraGridEngine.IO.fmu.interface import export_model_as_fmu
from VeraGridEngine.IO.fmu.config import ExportConfig as CsExportConfig
from VeraGridEngine.IO.fmu.config import detect_target_platform as detect_cs_target_platform
from VeraGridEngine.IO.fmu.config import ExportConfig as MeExportConfig
from VeraGridEngine.IO.fmu.config import detect_target_platform as detect_me_target_platform

from examples.fmi.powerfactory_first_order.run_powerfactory_first_order import (
    PowerFactoryApplication,
    PowerFactoryCompatibilityProfile,
    PowerFactoryObject,
    assert_owned,
    bootstrap_probe_project,
    build_powerfactory_compatibility_fmu,
    cleanup_probe_project,
    create_owned_object,
    inspect_attributes,
    inspect_process_inventory,
    hash_source_closure,
    load_powerfactory,
    set_owned_attribute,
    verify_active_cell,
)
from examples.fmi.veragrid_standard_examples.generate_standard_examples import (
    ExampleFamily,
    build_example_model,
    embed_redistribution_notices,
)
from examples.fmi.veragrid_standard_examples.validate_powerfactory_matrix import load_numeric_csv


class PowerFactoryCell:
    """Own one authenticated catalog cell and its named physical schedule."""

    __slots__ = ("family", "version", "interface", "model_name", "fmu_path", "fmu_sha256", "input_names", "output_names", "schedule_path", "reference_path", "stop_time")

    def __init__(
        self,
        family: str,
        version: str,
        interface: str,
        model_name: str,
        fmu_path: Path,
        fmu_sha256: str,
        input_names: tuple[str, ...],
        output_names: tuple[str, ...],
        schedule_path: Path,
        reference_path: Path,
        stop_time: float,
    ) -> None:
        """Store the immutable authenticated identity of one runnable cell.

        :param family: Published electrical family.
        :param version: FMI version string.
        :param interface: CS or ME token.
        :param model_name: Exact FMU model name.
        :param fmu_path: Exact published FMU path.
        :param fmu_sha256: Expected archive hash.
        :param input_names: Published semantic input names.
        :param output_names: Published semantic output names.
        :param schedule_path: Published physical input CSV.
        :param reference_path: Published FMPy output CSV.
        :param stop_time: Published simulation horizon.
        :return: None.
        """
        self.family: str = family
        self.version: str = version
        self.interface: str = interface
        self.model_name: str = model_name
        self.fmu_path: Path = fmu_path
        self.fmu_sha256: str = fmu_sha256
        self.input_names: tuple[str, ...] = input_names
        self.output_names: tuple[str, ...] = output_names
        self.schedule_path: Path = schedule_path
        self.reference_path: Path = reference_path
        self.stop_time: float = stop_time


class PowerFactoryRunJob:
    """Immutable owner of one isolated PowerFactory simulation."""

    __slots__ = ("job_index", "job_id", "cell", "integration_step")

    def __init__(
        self,
        job_index: int,
        job_id: str,
        cell: PowerFactoryCell,
        integration_step: float,
    ) -> None:
        """Store one exact catalog cell and numerical step.

        :param job_index: Zero-based position in the fixed 24-job plan.
        :param job_id: Stable filesystem-safe job identity.
        :param cell: Authenticated runnable catalog cell.
        :param integration_step: Exact PowerFactory integration step.
        :return: None.
        """
        self.job_index: int = job_index
        self.job_id: str = job_id
        self.cell: PowerFactoryCell = cell
        self.integration_step: float = integration_step


def inspect_pe_timestamp_normalized_binary(data: bytes) -> tuple[bytes, dict[str, object]]:
    """Parse and normalize only structurally authenticated PE timestamps.

    :param data: Complete Windows DLL bytes.
    :return: Timestamp-normalized copy and exact structural evidence.
    """
    if len(data) >= 64 and data[0:2] == b"MZ":
        pe_offset: int = int(struct.unpack_from("<I", data, 0x3C)[0])
    else:
        raise ValueError("PE image lacks a complete MZ header")
    if pe_offset >= 64 and pe_offset + 24 <= len(data) and data[pe_offset:pe_offset + 4] == b"PE\x00\x00":
        pass
    else:
        raise ValueError("PE signature offset or value is invalid")
    coff_offset: int = pe_offset + 4
    section_count: int = int(struct.unpack_from("<H", data, coff_offset + 2)[0])
    optional_size: int = int(struct.unpack_from("<H", data, coff_offset + 16)[0])
    optional_offset: int = coff_offset + 20
    section_table_offset: int = optional_offset + optional_size
    if section_count > 0 and section_count <= 96 and optional_size > 0 and section_table_offset + section_count * 40 <= len(data):
        pass
    else:
        raise ValueError("PE optional header or section table is invalid")
    magic: int = int(struct.unpack_from("<H", data, optional_offset)[0])
    if magic == 0x20B:
        directory_count_offset: int = optional_offset + 108
        directory_table_offset: int = optional_offset + 112
    else:
        if magic == 0x10B:
            directory_count_offset = optional_offset + 92
            directory_table_offset = optional_offset + 96
        else:
            raise ValueError("PE optional-header magic is unsupported")
    if directory_count_offset + 4 <= optional_offset + optional_size:
        directory_count: int = int(struct.unpack_from("<I", data, directory_count_offset)[0])
    else:
        raise ValueError("PE data-directory count is outside the optional header")
    debug_entry_offset: int = directory_table_offset + 6 * 8
    if directory_count > 6 and debug_entry_offset + 8 <= optional_offset + optional_size:
        debug_rva: int = int(struct.unpack_from("<I", data, debug_entry_offset)[0])
        debug_size: int = int(struct.unpack_from("<I", data, debug_entry_offset + 4)[0])
    else:
        raise ValueError("PE debug data-directory entry is absent")
    if debug_rva > 0 and debug_size > 0 and debug_size % 28 == 0 and debug_size // 28 <= 64:
        pass
    else:
        raise ValueError("PE debug-directory size or cardinality is invalid")
    mapped_offsets: list[int] = list()
    section_index: int
    for section_index in range(section_count):
        section_offset: int = section_table_offset + section_index * 40
        virtual_size: int = int(struct.unpack_from("<I", data, section_offset + 8)[0])
        virtual_address: int = int(struct.unpack_from("<I", data, section_offset + 12)[0])
        raw_size: int = int(struct.unpack_from("<I", data, section_offset + 16)[0])
        raw_offset: int = int(struct.unpack_from("<I", data, section_offset + 20)[0])
        mapped_size: int = max(virtual_size, raw_size)
        if debug_rva >= virtual_address and debug_rva + debug_size <= virtual_address + mapped_size:
            candidate_offset: int = raw_offset + (debug_rva - virtual_address)
            if candidate_offset >= raw_offset and candidate_offset + debug_size <= raw_offset + raw_size and candidate_offset + debug_size <= len(data):
                mapped_offsets.append(candidate_offset)
            else:
                raise ValueError("PE debug RVA maps outside section raw data")
        else:
            pass
    if len(mapped_offsets) == 1:
        debug_file_offset: int = mapped_offsets[0]
    else:
        raise ValueError("PE debug RVA must map to exactly one section")
    coff_timestamp_offset: int = coff_offset + 4
    timestamp_ranges: list[tuple[int, int, int]] = [(coff_timestamp_offset, 4, int(struct.unpack_from("<I", data, coff_timestamp_offset)[0]))]
    debug_index: int
    for debug_index in range(debug_size // 28):
        timestamp_offset: int = debug_file_offset + debug_index * 28 + 4
        timestamp_ranges.append((timestamp_offset, 4, int(struct.unpack_from("<I", data, timestamp_offset)[0])))
    ordered_ranges: list[tuple[int, int, int]] = sorted(timestamp_ranges)
    range_index: int
    for range_index in range(len(ordered_ranges)):
        current_range: tuple[int, int, int] = ordered_ranges[range_index]
        current_end: int = current_range[0] + current_range[1]
        if current_range[0] >= 0 and current_end <= len(data):
            pass
        else:
            raise ValueError("PE timestamp range is outside the file")
        if range_index == 0 or ordered_ranges[range_index - 1][0] + ordered_ranges[range_index - 1][1] <= current_range[0]:
            pass
        else:
            raise ValueError("PE timestamp ranges overlap")
    normalized: bytearray = bytearray(data)
    timestamp_range: tuple[int, int, int]
    range_receipts: list[dict[str, int]] = list()
    for timestamp_range in ordered_ranges:
        normalized[timestamp_range[0]:timestamp_range[0] + timestamp_range[1]] = b"\x00" * timestamp_range[1]
        range_receipts.append({"offset": timestamp_range[0], "length": timestamp_range[1], "value": timestamp_range[2]})
    normalized_bytes: bytes = bytes(normalized)
    receipt: dict[str, object] = {
        "binary_size": len(data),
        "binary_sha256": hashlib.sha256(data).hexdigest(),
        "normalized_binary_sha256": hashlib.sha256(normalized_bytes).hexdigest(),
        "timestamp_ranges": range_receipts,
    }
    return normalized_bytes, receipt


def load_catalog_cells(catalog_root: Path) -> tuple[PowerFactoryCell, ...]:
    """Authenticate and select the twelve standard FMI 2/3 catalog cells.

    :param catalog_root: Exact published win64 catalog directory.
    :return: Selected immutable cells in manifest order.
    """
    root: Path = catalog_root.resolve(strict=True)
    manifest_path: Path = root / "manifest.json"
    manifest_bytes: bytes = manifest_path.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() == "7099296e4360555daa1ca14f854f3c6b7f11b1c6b0ba38e5e603b9896e726113":
        pass
    else:
        raise ValueError("Published catalog manifest identity changed")
    manifest: dict[str, object] = json.loads(manifest_bytes.decode("utf-8"))
    cells_value: object = manifest.get("cells", None)
    if isinstance(cells_value, list):
        rows: list[object] = cells_value
    else:
        raise ValueError("Catalog cell table is absent")
    selected: list[PowerFactoryCell] = list()
    item: object
    for item in rows:
        if isinstance(item, dict) and item.get("fmi_version", None) in ("2.0", "3.0"):
            cell_row: dict[str, object] = item
            version: str = str(cell_row["fmi_version"])
            interface: str = str(cell_row["interface"])
            family: str = str(cell_row["family"])
            model_name: str = str(cell_row["model_name"])
            relative_path: Path = Path(str(cell_row["fmu_path"]))
            fmu_path: Path = (root / relative_path).resolve(strict=True)
            if fmu_path.is_relative_to(root) and fmu_path.suffix == ".fmu":
                pass
            else:
                raise ValueError("FMU path escapes authenticated catalog")
            digest: str = hashlib.sha256(fmu_path.read_bytes()).hexdigest()
            if digest == cell_row["fmu_sha256"] and cell_row["status"] == "PASS":
                pass
            else:
                raise ValueError("Published FMU hash or local status mismatch")
            schedule_path: Path = fmu_path.parent / (model_name + "_in.csv")
            reference_path: Path = fmu_path.parent / (model_name + "_ref.csv")
            schedule = load_numeric_csv(schedule_path)
            reference = load_numeric_csv(reference_path)
            if schedule.dtype.names is not None and reference.dtype.names is not None:
                input_names: tuple[str, ...] = tuple(name for name in schedule.dtype.names if name != "time")
                output_names: tuple[str, ...] = tuple(name for name in reference.dtype.names if name != "time")
            else:
                raise ValueError("Published CSV headers are absent")
            selected.append(PowerFactoryCell(family, version, interface, model_name, fmu_path, digest, input_names, output_names, schedule_path, reference_path, float(reference["time"][-1])))
        else:
            pass
    if len(selected) == 12:
        return tuple(selected)
    else:
        raise ValueError("PowerFactory requires exactly twelve applicable cells")


def build_powerfactory_initialization_derivative(
    cell: PowerFactoryCell,
    source_fmu_path: Path,
    output_dir: Path,
) -> tuple[Path, dict[str, object]]:
    """Build one PowerFactory-only CS derivative with physical input starts.

    The canonical FMU remains immutable. FMI 2 derivatives may differ from it
    only in ``modelDescription.xml``. FMI 3 derivatives consume the already
    reviewed callback derivative and may therefore differ from the canonical
    archive in exactly its Windows binary and ``modelDescription.xml``.

    :param cell: Authenticated canonical catalog cell and physical schedule.
    :param source_fmu_path: Canonical FMI 2 FMU or reviewed FMI 3 callback derivative.
    :param output_dir: Fresh external campaign directory.
    :return: Initialization derivative path and exact member/change receipt.
    """
    expected_rows: tuple[tuple[str, str, str, str, str, tuple[tuple[str, float], ...]], ...] = (
        ("VGTGOV1_FMI20_CS", "TGOV1", "2.0", "4f7370e6f85244cc7abe219413055fd9ec7609d1a8e112fb4134a87006aee61a", "25e11bc2276a6037e8bcb95ed71a7fdb3672f4dd25414699ad436a6f35a0a710", (("OmegaPu_TGOV1", 1.0), ("PRefPu_TGOV1", 0.5))),
        ("VGTGOV1_FMI30_CS", "TGOV1", "3.0", "6d06925febf31d3e46d774167ca187455ee178967ff48b18faba7d91f6958ee1", "25e11bc2276a6037e8bcb95ed71a7fdb3672f4dd25414699ad436a6f35a0a710", (("OmegaPu_TGOV1", 1.0), ("PRefPu_TGOV1", 0.5))),
        ("VGESDC2A_FMI20_CS", "ESDC2A", "2.0", "9f0285f42d99a67c1861f98b421be0fe988b962b654427c7900e9bcbbe8b7134", "e90ee7b74a10735ed80d26533c942590a70ab13a2e09b3256b9c8d2a6e64bffa", (("UsPu_ESDC2A", 1.0), ("UsRefPu_ESDC2A", 1.0125))),
        ("VGESDC2A_FMI30_CS", "ESDC2A", "3.0", "8bee82a53a103612179a36fb93e21d50522cc1143d5620878c78b59fd6b95545", "e90ee7b74a10735ed80d26533c942590a70ab13a2e09b3256b9c8d2a6e64bffa", (("UsPu_ESDC2A", 1.0), ("UsRefPu_ESDC2A", 1.0125))),
    )
    matching_rows: list[tuple[str, str, str, str, str, tuple[tuple[str, float], ...]]] = [
        row for row in expected_rows if row[0] == cell.model_name
    ]
    if len(matching_rows) == 1 and cell.interface == "cs":
        expected_row: tuple[str, str, str, str, str, tuple[tuple[str, float], ...]] = matching_rows[0]
    else:
        raise ValueError("PowerFactory initialization derivative is limited to four reviewed CS cells")
    canonical_path: Path = cell.fmu_path.resolve(strict=True)
    source_path: Path = source_fmu_path.resolve(strict=True)
    canonical_bytes: bytes = canonical_path.read_bytes()
    schedule_bytes: bytes = cell.schedule_path.resolve(strict=True).read_bytes()
    schedule_sections: list[bytes] = schedule_bytes.split(b"\n", 1)
    if len(schedule_sections) == 2:
        schedule_body_sha256: str = hashlib.sha256(schedule_sections[1]).hexdigest()
    else:
        raise ValueError("Physical schedule does not contain a CSV header")
    if (
        cell.family == expected_row[1]
        and cell.version == expected_row[2]
        and hashlib.sha256(canonical_bytes).hexdigest() == expected_row[3]
        and cell.fmu_sha256 == expected_row[3]
        # Authenticate the numerical schedule independently from its required
        # FMI tools-list header presentation.
        and schedule_body_sha256 == expected_row[4]
    ):
        pass
    else:
        raise ValueError("Canonical cell or physical schedule identity changed")
    with zipfile.ZipFile(canonical_path, "r") as canonical_archive:
        canonical_infos: tuple[zipfile.ZipInfo, ...] = tuple(canonical_archive.infolist())
        canonical_members: tuple[str, ...] = tuple(sorted(info.filename for info in canonical_infos))
        canonical_material: tuple[tuple[str, bytes], ...] = tuple(
            (info.filename, canonical_archive.read(info.filename)) for info in canonical_infos
        )
    with zipfile.ZipFile(source_path, "r") as source_archive:
        source_infos: tuple[zipfile.ZipInfo, ...] = tuple(source_archive.infolist())
        source_members: tuple[str, ...] = tuple(sorted(info.filename for info in source_infos))
        source_material: tuple[tuple[str, bytes], ...] = tuple(
            (info.filename, source_archive.read(info.filename)) for info in source_infos
        )
    if canonical_members == source_members:
        pass
    else:
        raise ValueError("Initialization source changed the FMU member topology")
    canonical_by_name: dict[str, bytes] = dict(canonical_material)
    source_by_name: dict[str, bytes] = dict(source_material)
    source_differences: tuple[str, ...] = tuple(
        name for name in canonical_members if canonical_by_name[name] != source_by_name[name]
    )
    binary_members: tuple[str, ...] = tuple(name for name in canonical_members if name.endswith(".dll"))
    if cell.version == "2.0" and source_differences == tuple() and source_path == canonical_path:
        pass
    else:
        if cell.version == "3.0" and len(binary_members) == 1 and source_differences == binary_members:
            pass
        else:
            raise ValueError("Initialization source does not match the reviewed prior derivative contract")
    source_xml: bytes = source_by_name["modelDescription.xml"]
    xml_root: ElementTree.Element = ElementTree.fromstring(source_xml)
    schedule: np.ndarray = load_numeric_csv(cell.schedule_path)
    expected_inputs: tuple[tuple[str, float], ...] = expected_row[5]
    if cell.family == "TGOV1":
        expected_all_inputs: tuple[str, ...] = ("OmegaPu_TGOV1", "PRefPu_TGOV1")
    else:
        expected_all_inputs = ("UPssPu_ESDC2A", "UUelPu_ESDC2A", "UsPu_ESDC2A", "UsRefPu_ESDC2A")
    if schedule.dtype.names is not None and schedule.size > 0:
        schedule_input_names: tuple[str, ...] = tuple(name for name in schedule.dtype.names if name != "time")
    else:
        raise ValueError("Physical schedule has no named initial row")
    if cell.input_names == expected_all_inputs and schedule_input_names == expected_all_inputs:
        pass
    else:
        raise ValueError("Reviewed CS input set is missing, reordered or extended")
    source_xml_nodes: list[ElementTree.Element] = list(xml_root.iter())
    changed_inputs: list[dict[str, object]] = list()
    changed_coordinates: list[tuple[int, str, str, str]] = list()
    expected_input: tuple[str, float]
    for expected_input in expected_inputs:
        input_name: str = expected_input[0]
        expected_value: float = expected_input[1]
        schedule_value: float = float(schedule[0][input_name])
        if math.isclose(schedule_value, expected_value, rel_tol=0.0, abs_tol=0.0):
            pass
        else:
            raise ValueError("Physical schedule initial value changed")
        if cell.version == "2.0":
            variable_nodes: list[ElementTree.Element] = [
                node for node in xml_root.findall("./ModelVariables/ScalarVariable") if node.attrib.get("name", "") == input_name
            ]
            if len(variable_nodes) == 1 and len(variable_nodes[0]) == 1:
                start_node: ElementTree.Element = variable_nodes[0][0]
            else:
                raise ValueError("FMI 2 input start coordinate is absent or ambiguous")
        else:
            variable_nodes = [
                node for node in xml_root.findall("./ModelVariables/*") if node.attrib.get("name", "") == input_name
            ]
            if len(variable_nodes) == 1:
                start_node = variable_nodes[0]
            else:
                raise ValueError("FMI 3 input start coordinate is absent or ambiguous")
        prior_start: str = str(start_node.attrib.get("start", ""))
        if float(prior_start) == 0.0:
            formatted_value: str = format(expected_value, ".17g")
            node_index: int = source_xml_nodes.index(start_node)
            start_node.set("start", formatted_value)
            changed_inputs.append({"name": input_name, "before": prior_start, "after": formatted_value})
            changed_coordinates.append((node_index, input_name, prior_start, formatted_value))
        else:
            raise ValueError("Reviewed input start is no longer zero")
    if len(changed_inputs) == 2 and len(changed_coordinates) == 2 and changed_coordinates[0][0] != changed_coordinates[1][0]:
        pass
    else:
        raise ValueError("Initialization derivative must change exactly two input starts")
    derived_xml: bytes = ElementTree.tostring(xml_root, encoding="utf-8", xml_declaration=True)
    source_xml_root_for_comparison: ElementTree.Element = ElementTree.fromstring(source_xml)
    derived_xml_root_for_comparison: ElementTree.Element = ElementTree.fromstring(derived_xml)
    comparison_source_nodes: list[ElementTree.Element] = list(source_xml_root_for_comparison.iter())
    comparison_derived_nodes: list[ElementTree.Element] = list(derived_xml_root_for_comparison.iter())
    authorized_xml_changes: dict[int, tuple[str, str, str]] = dict(
        (coordinate[0], (coordinate[1], coordinate[2], coordinate[3])) for coordinate in changed_coordinates
    )
    if len(comparison_source_nodes) == len(comparison_derived_nodes) and len(authorized_xml_changes) == 2:
        pass
    else:
        raise ValueError("Initialization derivative changed XML node cardinality")
    comparison_index: int
    for comparison_index in range(len(comparison_source_nodes)):
        comparison_source_node: ElementTree.Element = comparison_source_nodes[comparison_index]
        comparison_derived_node: ElementTree.Element = comparison_derived_nodes[comparison_index]
        expected_attributes: dict[str, str] = dict(comparison_source_node.attrib)
        authorized_change: tuple[str, str, str] | None = authorized_xml_changes.get(comparison_index, None)
        if authorized_change is not None:
            coordinate_name_matches: bool = cell.version == "2.0" or expected_attributes.get("name", "") == authorized_change[0]
            if coordinate_name_matches and expected_attributes.get("start", "") == authorized_change[1]:
                expected_attributes["start"] = authorized_change[2]
            else:
                raise ValueError("Authorized XML coordinate does not match its source node")
        else:
            pass
        if (
            comparison_source_node.tag == comparison_derived_node.tag
            and comparison_source_node.text == comparison_derived_node.text
            and comparison_source_node.tail == comparison_derived_node.tail
            and len(comparison_source_node) == len(comparison_derived_node)
            and expected_attributes == comparison_derived_node.attrib
        ):
            pass
        else:
            raise ValueError("Initialization derivative changed XML outside an authorized start coordinate")
    derivative_dir: Path = output_dir / "compatibility_fmus"
    derivative_dir.mkdir(parents=True, exist_ok=True)
    output_path: Path = derivative_dir / (cell.model_name + "_PowerFactoryInit.fmu")
    if output_path.exists():
        raise FileExistsError("Initialization derivative output already exists")
    else:
        pass
    with zipfile.ZipFile(output_path, "x") as derivative_archive:
        source_info: zipfile.ZipInfo
        for source_info in source_infos:
            member_bytes: bytes = derived_xml if source_info.filename == "modelDescription.xml" else source_by_name[source_info.filename]
            derivative_archive.writestr(source_info, member_bytes)
    with zipfile.ZipFile(output_path, "r") as derivative_archive:
        derivative_members: tuple[str, ...] = tuple(sorted(derivative_archive.namelist()))
        derivative_material: dict[str, bytes] = dict(
            (name, derivative_archive.read(name)) for name in derivative_members
        )
    derivative_differences_from_source: tuple[str, ...] = tuple(
        name for name in source_members if source_by_name[name] != derivative_material[name]
    )
    derivative_differences_from_canonical: tuple[str, ...] = tuple(
        name for name in canonical_members if canonical_by_name[name] != derivative_material[name]
    )
    expected_canonical_differences: tuple[str, ...] = ("modelDescription.xml",) if cell.version == "2.0" else tuple(sorted(binary_members + ("modelDescription.xml",)))
    if (
        derivative_members == source_members
        and derivative_differences_from_source == ("modelDescription.xml",)
        and tuple(sorted(derivative_differences_from_canonical)) == expected_canonical_differences
    ):
        pass
    else:
        raise ValueError("Initialization derivative member differences exceed the reviewed contract")
    output_bytes: bytes = output_path.read_bytes()
    receipt: dict[str, object] = {
        "cell_id": cell.model_name,
        "canonical_fmu_sha256": hashlib.sha256(canonical_bytes).hexdigest(),
        "source_fmu_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "derived_fmu_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "schedule_sha256": hashlib.sha256(schedule_bytes).hexdigest(),
        "schedule_body_sha256": schedule_body_sha256,
        "source_member_differences_from_canonical": source_differences,
        "derived_member_differences_from_source": derivative_differences_from_source,
        "derived_member_differences_from_canonical": derivative_differences_from_canonical,
        "changed_inputs": changed_inputs,
        "changed_xml_coordinates": changed_coordinates,
        "changed_input_count": len(changed_inputs),
        "member_topology_preserved": True,
        "status": "PASS",
    }
    return output_path.resolve(strict=True), receipt


def prepare_powerfactory_compatibility_cells(
    cells: tuple[PowerFactoryCell, ...],
    repository_root: Path,
    output_dir: Path,
) -> tuple[PowerFactoryCell, ...]:
    """Build callback and CS-initialization derivatives for PowerFactory.

    :param cells: Twelve authenticated canonical FMI 2/3 cells.
    :param repository_root: Exact VeraGrid checkout root.
    :param output_dir: Fresh external campaign directory.
    :return: Twelve runnable cells with only reviewed external paths substituted.
    """
    owner_rows: tuple[tuple[str, str], ...] = (
        ("examples/fmi/veragrid_standard_examples/generate_standard_examples.py", "9fa600d96ca9f0929820463ed7fb81b5ec983762281b6dd611e0847133990ba4"),
        ("src/VeraGridEngine/IO/fmu/exporter/api.py", "276981d1c40d482fc6144fceeec1b3d58cbe20bd57570fb87deb599faad8e1ed"),
        ("src/VeraGridEngine/IO/fmu/exporter/config.py", "3bc32e73dfe472933498b453c3c62a2aacde630b2754a07659953feccf47b6d5"),
        ("src/VeraGridEngine/IO/fmu/exporter/build.py", "68def82a73b6fa964821c1d2ee11c8fe6896278c4106420420813f8254cc3f87"),
        ("src/VeraGridEngine/IO/fmu/exporter/xml_writer.py", "2ffb8e8f58368b288f67a543fbb306507a1b43348991d2d876e00f6c25938987"),
        ("src/VeraGridEngine/IO/fmu/exporter_me/api.py", "b09797009daa8f4878e80c7f790dd1003ba781bf4d6d434f0a70670b65db91c9"),
        ("src/VeraGridEngine/IO/fmu/exporter_me/config.py", "511eac9e978954263a5d855e0fb944839df287188e30ff5303d199be8fac281b"),
        ("src/VeraGridEngine/IO/fmu/exporter_me/build.py", "bdd2f696bc92a8ddd7acff363d205a0f837fbbb64671ced135c7019d3394f62f"),
        ("src/VeraGridEngine/IO/fmu/exporter_me/xml_writer.py", "f95670416de9210f717a06d1fe17bfa8a19a35c143e46a02e28614cd371487f2"),
        ("src/VeraGridEngine/Templates/Rms/international_standards/synchronous_machines/gensal.py", "65c20dcb3765a97c7b3d7724048b8b589106e05cf92bdaa4b81b9fce12f79174"),
        ("src/VeraGridEngine/Templates/Rms/international_standards/governors/tgov1.py", "8521c8f3becae28751be71dd6a499a003cc843bda383bf2071e7c3aa0dded587"),
        ("src/VeraGridEngine/Templates/Rms/international_standards/excitation_systems/esdc2a.py", "100d03d8267d0ad08e08835cb345bb548fc1193f6cf36e38270db3b359e0c15d"),
    )
    owner_receipts: list[dict[str, object]] = list()
    owner_row: tuple[str, str]
    for owner_row in owner_rows:
        owner_path: Path = (repository_root / owner_row[0]).resolve(strict=True)
        owner_hash: str = hashlib.sha256(owner_path.read_bytes()).hexdigest()
        if owner_path.is_relative_to(repository_root) and owner_hash == owner_row[1]:
            owner_receipts.append({"path": owner_row[0], "sha256": owner_hash})
        else:
            raise ValueError("FMI 3 source owner identity changed")
    runnable: list[PowerFactoryCell] = list()
    build_receipts: list[dict[str, object]] = list()
    initialization_receipts: list[dict[str, object]] = list()
    compiler: Compiler = Compiler()
    try:
        cell: PowerFactoryCell
        for cell in cells:
            if cell.version == "3.0":
                with zipfile.ZipFile(cell.fmu_path, "r") as canonical_archive:
                    canonical_members: tuple[str, ...] = tuple(sorted(canonical_archive.namelist()))
                    xml_bytes: bytes = canonical_archive.read("modelDescription.xml")
                    xml_root: ElementTree.Element = ElementTree.fromstring(xml_bytes)
                    token: str = str(xml_root.attrib.get("instantiationToken", ""))
                    interface_tag: str = "CoSimulation" if cell.interface == "cs" else "ModelExchange"
                    interface_node: ElementTree.Element | None = xml_root.find(interface_tag)
                    source_text: str = canonical_archive.read("documentation/SOURCE.md").decode("utf-8")
                    license_bytes: bytes = canonical_archive.read("documentation/LICENSE.md")
                    if token != "" and interface_node is not None:
                        model_identifier: str = str(interface_node.attrib.get("modelIdentifier", ""))
                    else:
                        raise ValueError("Canonical FMI 3 identity is incomplete")
                    canonical_material: tuple[tuple[str, bytes], ...] = tuple(
                        (member_name, canonical_archive.read(member_name)) for member_name in canonical_members
                    )
                canonical_binary_rows: list[tuple[str, bytes]] = [member_row for member_row in canonical_material if member_row[0].endswith(".dll")]
                if len(canonical_binary_rows) == 1:
                    canonical_binary_member: str = canonical_binary_rows[0][0]
                    canonical_binary: bytes = canonical_binary_rows[0][1]
                else:
                    raise ValueError("Canonical FMI 3 must contain exactly one Windows binary")
                canonical_normalized_binary: bytes
                canonical_binary_receipt: dict[str, object]
                canonical_normalized_binary, canonical_binary_receipt = inspect_pe_timestamp_normalized_binary(canonical_binary)
                debug_snapshot_members: tuple[str, ...] = (
                    "resources/export_model.json",
                    "resources/snapshot.json",
                )
                canonical_debug_snapshot_rows: list[tuple[str, bytes]] = [
                    member_row for member_row in canonical_material if member_row[0] in debug_snapshot_members
                ]
                if len(canonical_debug_snapshot_rows) == 2:
                    pass
                else:
                    raise ValueError("Canonical FMI 3 debug snapshots are absent or duplicated")
                cell_root: Path = output_dir / "source_regeneration" / cell.model_name
                cell_root.mkdir(parents=True, exist_ok=False)
                license_path: Path = cell_root / "canonical-LICENSE.md"
                license_path.write_bytes(license_bytes)
                regeneration_hashes: list[str] = list()
                regenerated_binary_hashes: list[str] = list()
                binary_comparisons: list[dict[str, object]] = list()
                debug_snapshot_receipts: list[dict[str, object]] = list()
                first_source_root: Path | None = None
                pass_index: int
                for pass_index in range(2):
                    pass_root: Path = cell_root / ("pass-" + str(pass_index + 1))
                    candidate_path: Path = pass_root / (cell.model_name + ".fmu")
                    build_root: Path = pass_root / "build-root"
                    staging_root: Path = pass_root / "staging"
                    pass_root.mkdir(parents=True, exist_ok=False)
                    model: RmsModelTemplate = build_example_model(ExampleFamily[cell.family])
                    if cell.interface == "cs":
                        generated_path: Path = export_model_as_fmu(
                            model.block,
                            CsExportConfig(
                                model_name=cell.model_name,
                                output_path=candidate_path,
                                guid=token,
                                target_platform=detect_cs_target_platform(),
                                fixed_step=0.001,
                                build_dir=build_root,
                                staging_dir=staging_root,
                                model_identifier=model_identifier,
                                keep_build_dir=True,
                                fmi_version=FmiVersion.FMI_3_0,
                            ),
                            compiler,
                        )
                    else:
                        generated_path = export_model_as_fmu(
                            model.block,
                            MeExportConfig(interface_type=InterfaceType.MODEL_EXCHANGE, 
                                model_name=cell.model_name,
                                output_path=candidate_path,
                                guid=token,
                                target_platform=detect_me_target_platform(),
                                fixed_step=0.001,
                                build_dir=build_root,
                                staging_dir=staging_root,
                                model_identifier=model_identifier,
                                keep_build_dir=True,
                                fmi_version=FmiVersion.FMI_3_0,
                            ),
                            compiler,
                        )
                    embed_redistribution_notices(generated_path, license_path, source_text)
                    with zipfile.ZipFile(generated_path, "r") as candidate_archive:
                        candidate_members: tuple[str, ...] = tuple(sorted(candidate_archive.namelist()))
                        if candidate_members == canonical_members:
                            pass
                        else:
                            raise ValueError("Regenerated FMI 3 member topology differs")
                        member_row: tuple[str, bytes]
                        for member_row in canonical_material:
                            if member_row[0] == canonical_binary_member:
                                pass
                            else:
                                candidate_member: bytes = candidate_archive.read(member_row[0])
                                if member_row[0] in debug_snapshot_members:
                                    canonical_snapshot_rows: list[bytes] = [
                                        snapshot_row[1]
                                        for snapshot_row in canonical_debug_snapshot_rows
                                        if snapshot_row[0] == member_row[0]
                                    ]
                                    if len(canonical_snapshot_rows) == 1:
                                        canonical_snapshot: bytes = canonical_snapshot_rows[0]
                                    else:
                                        raise ValueError("Canonical debug snapshot identity is ambiguous")
                                    debug_snapshot_receipts.append({
                                        "pass_index": pass_index + 1,
                                        "member": member_row[0],
                                        "canonical_size": len(canonical_snapshot),
                                        "canonical_sha256": hashlib.sha256(canonical_snapshot).hexdigest(),
                                        "regenerated_size": len(candidate_member),
                                        "regenerated_sha256": hashlib.sha256(candidate_member).hexdigest(),
                                        "status": "RAW_PROVENANCE_ONLY",
                                    })
                                else:
                                    if candidate_member == member_row[1]:
                                        pass
                                    else:
                                        raise ValueError("Regenerated FMI 3 deterministic non-binary member differs: " + member_row[0])
                        candidate_binary: bytes = candidate_archive.read(canonical_binary_member)
                    candidate_normalized_binary: bytes
                    candidate_binary_receipt: dict[str, object]
                    candidate_normalized_binary, candidate_binary_receipt = inspect_pe_timestamp_normalized_binary(candidate_binary)
                    if len(candidate_binary) == len(canonical_binary) and candidate_normalized_binary == canonical_normalized_binary:
                        pass
                    else:
                        raise ValueError("Regenerated FMI 3 normalized binary differs")
                    differences: list[int] = [byte_index for byte_index in range(len(canonical_binary)) if canonical_binary[byte_index] != candidate_binary[byte_index]]
                    allowed_offsets: set[int] = set()
                    ranges_value: object = candidate_binary_receipt.get("timestamp_ranges", None)
                    if isinstance(ranges_value, list):
                        range_value: object
                        for range_value in ranges_value:
                            if isinstance(range_value, dict):
                                range_offset: int = int(range_value.get("offset", -1))
                                range_length: int = int(range_value.get("length", -1))
                                if range_offset >= 0 and range_length == 4:
                                    allowed_offsets.update(range(range_offset, range_offset + range_length))
                                else:
                                    raise ValueError("Regenerated PE timestamp range is invalid")
                            else:
                                raise ValueError("Regenerated PE timestamp receipt is malformed")
                    else:
                        raise ValueError("Regenerated PE timestamp ranges are absent")
                    if len(differences) > 0 and set(differences).issubset(allowed_offsets):
                        pass
                    else:
                        raise ValueError("Regenerated binary differences escape parsed PE timestamps")
                    regenerated_binary_hashes.append(str(candidate_binary_receipt["normalized_binary_sha256"]))
                    binary_comparisons.append({"pass_index": pass_index + 1, "canonical": canonical_binary_receipt, "regenerated": candidate_binary_receipt, "different_offsets": differences, "difference_count": len(differences), "status": "PASS"})
                    source_root: Path = build_root / "source"
                    closure: dict[str, object] = hash_source_closure(((cell.model_name, source_root),))
                    closure_hash: str = str(closure.get("normalized_closure_sha256", ""))
                    if closure_hash != "":
                        regeneration_hashes.append(closure_hash)
                    else:
                        raise ValueError("Normalized source closure is unavailable")
                    if pass_index == 0:
                        first_source_root = source_root
                    else:
                        pass
                if len(regeneration_hashes) == 2 and regeneration_hashes[0] == regeneration_hashes[1] and len(regenerated_binary_hashes) == 2 and regenerated_binary_hashes[0] == regenerated_binary_hashes[1] == str(canonical_binary_receipt["normalized_binary_sha256"]) and len(debug_snapshot_receipts) == 4 and first_source_root is not None:
                    pass
                else:
                    raise ValueError("Repeated FMI 3 source regeneration is not deterministic")
                derived_path, derivative_receipt = build_powerfactory_compatibility_fmu(
                    (cell.model_name, cell.fmu_path, cell.version, cell.interface),
                    first_source_root,
                    output_dir,
                    PowerFactoryCompatibilityProfile.FMI_THREE_CONFIGURATION_MODE,
                    compiler,
                )
                derivative_receipt["canonical_instantiation_token"] = token
                derivative_receipt["normalized_source_sha256"] = regeneration_hashes[0]
                derivative_receipt["normalized_prepatch_binary_sha256"] = regenerated_binary_hashes[0]
                derivative_receipt["prepatch_binary_comparisons"] = binary_comparisons
                derivative_receipt["regenerated_debug_snapshot_provenance"] = debug_snapshot_receipts
                derivative_receipt["regeneration_count"] = 2
                build_receipts.append(derivative_receipt)
                runnable_path: Path = derived_path
            else:
                runnable_path = cell.fmu_path
            if cell.interface == "cs" and cell.family in ("TGOV1", "ESDC2A"):
                initialized_path: Path
                initialization_receipt: dict[str, object]
                initialized_path, initialization_receipt = build_powerfactory_initialization_derivative(
                    cell,
                    runnable_path,
                    output_dir,
                )
                initialization_receipts.append(initialization_receipt)
                runnable_path = initialized_path
            else:
                pass
            runnable.append(PowerFactoryCell(cell.family, cell.version, cell.interface, cell.model_name, runnable_path, hashlib.sha256(runnable_path.read_bytes()).hexdigest(), cell.input_names, cell.output_names, cell.schedule_path, cell.reference_path, cell.stop_time))
    finally:
        pass
    receipt: dict[str, object] = {
        "schema_version": "1.0",
        "sealed_dossier_sha256": "4b3aa0ccd496daa7cfbcc3b2d80639724ee0d0255b4b2e2a6763dc5894e57edc",
        "owners": owner_receipts,
        "builds": build_receipts,
        "initialization_builds": initialization_receipts,
        "status": "PASS" if len(build_receipts) == 6 and len(initialization_receipts) == 4 and len(runnable) == 12 else "FAIL",
    }
    (output_dir / "compatibility-build-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if receipt["status"] == "PASS":
        return tuple(runnable)
    else:
        raise RuntimeError("PowerFactory compatibility preparation is incomplete")


def parse_named_values(raw_names: str, expected_names: tuple[str, ...]) -> tuple[str, ...]:
    """Accept a unique semantic name set and retain the vendor's port order.

    :param raw_names: Comma-separated vendor input or output names.
    :param expected_names: Exact catalog semantic names.
    :return: Vendor names in the observed order.
    """
    observed: tuple[str, ...] = tuple(part.strip() for part in raw_names.split(","))
    if len(observed) == len(expected_names) and len(set(observed)) == len(observed) and set(observed) == set(expected_names):
        return observed
    else:
        raise ValueError("PowerFactory port names are missing, duplicate or unknown")


def configure_standard_cell(
    application: PowerFactoryApplication,
    owned_project: PowerFactoryObject,
    grid: PowerFactoryObject,
    cell: PowerFactoryCell,
    journal_path: Path,
) -> tuple[PowerFactoryObject, PowerFactoryObject, PowerFactoryObject, PowerFactoryObject, PowerFactoryObject, tuple[str, ...], tuple[str, ...], tuple[float, ...]]:
    """Create one imported FMU instance without using the unsafe initialization field.

    :param application: Acquired licensed vendor application.
    :param owned_project: Verified disposable project root.
    :param grid: Owned calculation grid.
    :param cell: Exact standard catalog cell.
    :param journal_path: Append-only mutation journal.
    :return: Instance, type, frame, slot, composite, port orders and raw initialization readback.
    """
    model_folder: PowerFactoryObject | None = application.GetProjectFolder("blk", 1)
    if model_folder is not None:
        assert_owned(model_folder, owned_project)
    else:
        raise RuntimeError("Owned model folder is unavailable")
    created_objects: list[PowerFactoryObject] = list()
    try:
        model: PowerFactoryObject = create_owned_object(model_folder, "TypMdl", cell.model_name + "_Type", owned_project, journal_path)
        created_objects.append(model)
        set_owned_attribute(model, "modelType", 1, owned_project, journal_path)
        set_owned_attribute(model, "cfilePath", str(cell.fmu_path), owned_project, journal_path)
        if int(model.Check()) == 0:
            pass
        else:
            raise RuntimeError("PowerFactory could not import the standard FMU")
        observed_inputs: tuple[str, ...] = parse_named_values(str(model.GetAttribute("cinputAll")), cell.input_names)
        observed_outputs: tuple[str, ...] = parse_named_values(str(model.GetAttribute("coutputAll")), cell.output_names)
        # PowerFactory 2025 SP4 crashes natively during ComInc when this field is
        # populated for these FMUs. Physical initialization is therefore
        # expressed through owned, active parameter events at t=0 instead.
        readback_value: object = model.GetAttribute("inputInitFmu")
        if isinstance(readback_value, (list, tuple)) and len(readback_value) == 0:
            raw_input_initialization: tuple[float, ...] = tuple()
            pass
        else:
            raise RuntimeError("PowerFactory inputInitFmu must remain empty")
        frame: PowerFactoryObject = create_owned_object(model_folder, "BlkDef", cell.model_name + "_Frame", owned_project, journal_path)
        created_objects.append(frame)
        slot: PowerFactoryObject = create_owned_object(frame, "BlkSlot", "FMU", owned_project, journal_path)
        created_objects.append(slot)
        composite: PowerFactoryObject = create_owned_object(grid, "ElmComp", cell.model_name + "_Composite", owned_project, journal_path)
        created_objects.append(composite)
        instance: PowerFactoryObject = create_owned_object(composite, "ElmMdl", cell.model_name + "_Instance", owned_project, journal_path)
        created_objects.append(instance)
        set_owned_attribute(instance, "typ_id", model, owned_project, journal_path)
        set_owned_attribute(composite, "typ_id", frame, owned_project, journal_path)
        set_owned_attribute(composite, "pblk", list((slot,)), owned_project, journal_path)
        set_owned_attribute(composite, "pelm", list((instance,)), owned_project, journal_path)
        if int(instance.Check()) == 0:
            return instance, model, frame, slot, composite, observed_inputs, observed_outputs, raw_input_initialization
        else:
            raise RuntimeError("PowerFactory FMU instance check failed")
    except Exception:
        target: PowerFactoryObject
        for target in reversed(created_objects):
            assert_owned(target, owned_project)
            target.Delete()
        raise


def create_named_event_profile(
    application: PowerFactoryApplication,
    owned_project: PowerFactoryObject,
    instance: PowerFactoryObject,
    cell: PowerFactoryCell,
    journal_path: Path,
) -> tuple[PowerFactoryObject, ...]:
    """Create named initialization and change events for every physical input.

    :param application: Licensed vendor application.
    :param owned_project: Verified disposable project.
    :param instance: Current FMU instance.
    :param cell: Published schedule owner.
    :param journal_path: Append-only mutation journal.
    :return: Events created under the owned study case.
    """
    event_folder: PowerFactoryObject | None = application.GetFromStudyCase("IntEvt")
    if event_folder is not None:
        assert_owned(event_folder, owned_project)
    else:
        raise RuntimeError("Owned event folder is unavailable")
    schedule = load_numeric_csv(cell.schedule_path)
    events: list[PowerFactoryObject] = list()
    event_descriptors: list[tuple[str, float, float, str]] = list()
    input_name: str
    for input_name in cell.input_names:
        event_descriptors.append((input_name, float(schedule[0][input_name]), 0.0, "initial"))
    try:
        row_index: int
        for row_index in range(1, schedule.size):
            current_time: float = float(schedule[row_index]["time"])
            previous_time: float = float(schedule[row_index - 1]["time"])
            if abs(current_time - previous_time) <= 5e-12:
                input_name: str
                for input_name in cell.input_names:
                    old_value: float = float(schedule[row_index - 1][input_name])
                    new_value: float = float(schedule[row_index][input_name])
                    if old_value != new_value:
                        event_descriptors.append((input_name, new_value, current_time, str(row_index)))
                    else:
                        pass
            else:
                pass
        descriptor: tuple[str, float, float, str]
        for descriptor in event_descriptors:
            event: PowerFactoryObject = create_owned_object(event_folder, "EvtParam", cell.model_name + "_" + descriptor[0] + "_" + descriptor[3], owned_project, journal_path)
            events.append(event)
            set_owned_attribute(event, "p_target", instance, owned_project, journal_path)
            set_owned_attribute(event, "variable", descriptor[0], owned_project, journal_path)
            set_owned_attribute(event, "value", format(descriptor[1], ".17g"), owned_project, journal_path)
            set_owned_attribute(event, "time", descriptor[2], owned_project, journal_path)
            set_owned_attribute(event, "outserv", 0, owned_project, journal_path)
    except Exception:
        event: PowerFactoryObject
        for event in reversed(events):
            assert_owned(event, owned_project)
            event.Delete()
        raise
    return tuple(events)


def add_result_variables(
    result: PowerFactoryObject,
    instance: PowerFactoryObject,
    cell: PowerFactoryCell,
) -> dict[str, int]:
    """Request every named input and output from one vendor result object.

    :param result: Owned PowerFactory result object.
    :param instance: Sole active FMU instance.
    :param cell: Exact semantic catalog cell.
    :return: Per-variable AddVars status codes.
    """
    result.Clear()
    codes: dict[str, int] = dict()
    variable_name: str
    for variable_name in cell.input_names:
        codes[variable_name] = int(result.AddVars(instance, "s:" + variable_name))
    for variable_name in cell.output_names:
        codes[variable_name] = int(result.AddVars(instance, "s:" + variable_name))
    result.WriteChangesToDb()
    return codes


def read_named_result_rows(
    application: PowerFactoryApplication,
    result: PowerFactoryObject,
    instance: PowerFactoryObject,
    cell: PowerFactoryCell,
    output_path: Path,
) -> dict[str, object]:
    """Write the exact raw vendor rows and their content identity.

    :param application: Licensed vendor application.
    :param result: Executed result object.
    :param instance: Current sole FMU instance.
    :param cell: Named column owner.
    :param output_path: New external CSV destination.
    :return: Hash and row-count evidence.
    """
    load_code: int | None = result.Load()
    if load_code is None or load_code == 0:
        pass
    else:
        raise RuntimeError("PowerFactory result load failed")
    try:
        names: tuple[str, ...] = cell.input_names + cell.output_names
        indexes: list[int] = [int(application.ResGetIndex(result, instance, "s:" + name)) for name in names]
        if all(index >= 0 for index in indexes):
            pass
        else:
            raise RuntimeError("A named PowerFactory result column is absent")
        row_count: int = int(result.GetNumberOfRows())
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("x", encoding="utf-8", newline="") as stream:
            writer: csv.writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(("time",) + names)
            row_index: int
            for row_index in range(row_count):
                values: list[float] = [float(result.GetValue(row_index, -1)[1])]
                column_index: int
                for column_index in indexes:
                    values.append(float(result.GetValue(row_index, column_index)[1]))
                if all(math.isfinite(value) for value in values):
                    writer.writerow([format(value, ".17g") for value in values])
                else:
                    raise RuntimeError("PowerFactory result contains non-finite data")
        content: bytes = output_path.read_bytes()
        return {"raw_csv": output_path.name, "row_count": row_count, "raw_sha256": hashlib.sha256(content).hexdigest()}
    finally:
        result.Release()


def run_standard_cell(
    application: PowerFactoryApplication,
    owned_project: PowerFactoryObject,
    grid: PowerFactoryObject,
    cell: PowerFactoryCell,
    integration_step: float,
    output_dir: Path,
    journal_path: Path,
) -> dict[str, object]:
    """Run one standard cell and preserve explicit success or failure.

    :param application: Acquired licensed application.
    :param owned_project: Exact disposable project.
    :param grid: Owned calculation grid.
    :param cell: Authenticated standard FMU.
    :param integration_step: Fixed internal RMS step.
    :param output_dir: External execution directory.
    :param journal_path: Append-only mutation journal.
    :return: Per-run import, command and raw-trace observation.
    """
    phase_path: Path = output_dir / "native-phase-log.jsonl"
    phase_record: dict[str, object] = {"model_name": cell.model_name, "integration_step_s": integration_step, "phase": "ENTER"}
    with phase_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(phase_record, sort_keys=True) + "\n")
    objects: tuple[PowerFactoryObject, ...] = tuple()
    events: tuple[PowerFactoryObject, ...] = tuple()
    outcome: dict[str, object] = {"model_name": cell.model_name, "family": cell.family, "fmi_version": cell.version, "interface": cell.interface, "integration_step_s": integration_step, "finest": cell.interface == "cs" or integration_step == 0.00003125, "status": "FAIL"}
    try:
        instance, model, frame, slot, composite, observed_inputs, observed_outputs, raw_input_initialization = configure_standard_cell(application, owned_project, grid, cell, journal_path)
        objects = (instance, composite, slot, frame, model)
        phase_record["phase"] = "CONFIGURED"
        with phase_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(phase_record, sort_keys=True) + "\n")
        outcome["observed_inputs"] = observed_inputs
        outcome["observed_outputs"] = observed_outputs
        outcome["raw_input_initialization"] = raw_input_initialization
        outcome["explicit_input_initialization_assigned"] = False
        active: dict[str, object] = verify_active_cell(application, owned_project, instance)
        if active.get("status", None) == "PASS":
            pass
        else:
            raise RuntimeError("PowerFactory active FMU set is not exact")
        events = create_named_event_profile(application, owned_project, instance, cell, journal_path)
        phase_record["phase"] = "EVENTS_CREATED"
        with phase_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(phase_record, sort_keys=True) + "\n")
        load_flow: PowerFactoryObject | None = application.GetFromStudyCase("ComLdf")
        initial_conditions: PowerFactoryObject | None = application.GetFromStudyCase("ComInc")
        simulation: PowerFactoryObject | None = application.GetFromStudyCase("ComSim")
        result: PowerFactoryObject | None = application.GetFromStudyCase("ElmRes")
        if load_flow is not None and initial_conditions is not None and simulation is not None and result is not None:
            pass
        else:
            raise RuntimeError("PowerFactory study-case commands are incomplete")
        command: PowerFactoryObject
        for command in (load_flow, initial_conditions, simulation, result):
            assert_owned(command, owned_project)
        set_owned_attribute(initial_conditions, "iopt_sim", "rms", owned_project, journal_path)
        set_owned_attribute(initial_conditions, "errseq", 0.000001, owned_project, journal_path)
        set_owned_attribute(initial_conditions, "iopt_adapt", 0, owned_project, journal_path)
        set_owned_attribute(initial_conditions, "dtgrd", integration_step, owned_project, journal_path)
        set_owned_attribute(initial_conditions, "dtout", 0.001, owned_project, journal_path)
        set_owned_attribute(initial_conditions, "iopt_sync", 1, owned_project, journal_path)
        set_owned_attribute(initial_conditions, "syncperiod", 0.001, owned_project, journal_path)
        set_owned_attribute(initial_conditions, "ciopt_sample", 2, owned_project, journal_path)
        set_owned_attribute(initial_conditions, "tstart", 0.0, owned_project, journal_path)
        set_owned_attribute(simulation, "tstop", cell.stop_time, owned_project, journal_path)
        phase_record["phase"] = "BEFORE_ADD_VARS"
        with phase_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(phase_record, sort_keys=True) + "\n")
        codes: dict[str, int] = add_result_variables(result, instance, cell)
        phase_record["phase"] = "AFTER_ADD_VARS"
        with phase_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(phase_record, sort_keys=True) + "\n")
        if all(code == 0 for code in codes.values()):
            pass
        else:
            raise RuntimeError("PowerFactory rejected a named result variable")
        phase_record["phase"] = "BEFORE_COMLDF"
        with phase_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(phase_record, sort_keys=True) + "\n")
        load_code: int = int(load_flow.Execute())
        phase_record["phase"] = "AFTER_COMLDF"
        phase_record["command_code"] = load_code
        with phase_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(phase_record, sort_keys=True) + "\n")
        if load_code == 0:
            phase_record["phase"] = "BEFORE_COMINC"
            with phase_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(phase_record, sort_keys=True) + "\n")
            init_code: int | None = int(initial_conditions.Execute())
            phase_record["phase"] = "AFTER_COMINC"
            phase_record["command_code"] = init_code
            with phase_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(phase_record, sort_keys=True) + "\n")
        else:
            init_code = None
        if init_code == 0:
            phase_record["phase"] = "BEFORE_COMSIM"
            with phase_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(phase_record, sort_keys=True) + "\n")
            sim_code: int | None = int(simulation.Execute())
            phase_record["phase"] = "AFTER_COMSIM"
            phase_record["command_code"] = sim_code
            with phase_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(phase_record, sort_keys=True) + "\n")
        else:
            sim_code = None
        outcome["command_codes"] = {"ComLdf": load_code, "ComInc": init_code, "ComSim": sim_code}
        if load_code == 0 and init_code == 0 and sim_code == 0:
            pass
        else:
            raise RuntimeError("PowerFactory dynamic command failed")
        step_tag: str = format(integration_step, ".9f").replace(".", "p")
        raw_path: Path = output_dir / "raw_traces" / (cell.model_name + "_h_" + step_tag + ".csv")
        raw_evidence: dict[str, object] = read_named_result_rows(application, result, instance, cell, raw_path)
        phase_record["phase"] = "RESULTS_RETAINED"
        with phase_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(phase_record, sort_keys=True) + "\n")
        outcome["raw_csv"] = raw_path.relative_to(output_dir).as_posix()
        outcome["raw_sha256"] = raw_evidence["raw_sha256"]
        outcome["row_count"] = raw_evidence["row_count"]
        outcome["event_count"] = len(events)
        outcome["status"] = "PASS"
    except Exception as exception:
        outcome["error"] = f"{exception.__class__.__name__}: {exception}"
    finally:
        event: PowerFactoryObject
        for event in events:
            assert_owned(event, owned_project)
            event.Delete()
        target: PowerFactoryObject
        for target in objects:
            assert_owned(target, owned_project)
            target.Delete()
    return outcome


def write_release_checkpoint(
    output_dir: Path,
    observations: dict[str, object],
    run_nonce: str,
    worker_pid: int,
    job: PowerFactoryRunJob,
) -> dict[str, object]:
    """Authenticate one job before the parent permits native release.

    :param output_dir: Exact external execution directory.
    :param observations: Complete licensed-run facts.
    :param run_nonce: Parent-owned unique run token.
    :param worker_pid: Exact worker process identifier.
    :param job: Exact isolated job represented by the evidence.
    :return: Checkpoint matching the bytes written on disk.
    """
    excluded_names: tuple[str, ...] = ("child-checkpoint.json", "parent-checkpoint-ack.json", "worker-ack-validated.json")
    artifact_paths: list[Path] = sorted(path for path in output_dir.rglob("*") if path.is_file() and path.name not in excluded_names)
    artifacts: list[dict[str, object]] = list()
    path: Path
    for path in artifact_paths:
        content: bytes = path.read_bytes()
        artifacts.append({"name": path.relative_to(output_dir).as_posix(), "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    checkpoint: dict[str, object] = {
        "schema_version": "1.0",
        "record_kind": "powerfactory_standard_child_checkpoint",
        "sealed_dossier_sha256": "4b3aa0ccd496daa7cfbcc3b2d80639724ee0d0255b4b2e2a6763dc5894e57edc",
        "run_nonce": run_nonce,
        "worker_pid": worker_pid,
        "job_id": job.job_id,
        "job_index": job.job_index,
        "model_name": job.cell.model_name,
        "fmi_version": job.cell.version,
        "interface": job.cell.interface,
        "integration_step_s": job.integration_step,
        "observations": observations,
        "artifacts": artifacts,
        "status": "READY_FOR_PARENT_ACK",
    }
    checkpoint_path: Path = output_dir / "child-checkpoint.json"
    checkpoint_temp_path: Path = output_dir / ("child-checkpoint.json.tmp-" + run_nonce)
    # Publish the evidence closure atomically so the supervisor can never
    # authenticate a partial checkpoint after the worker process exits.
    with checkpoint_temp_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(checkpoint_temp_path, checkpoint_path)
    return checkpoint


def parse_arguments() -> argparse.Namespace:
    """Read explicit licensed-run paths without PATH or environment search.

    :return: Parsed command-line paths.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--powerfactory-root", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def run_powerfactory_cell_worker(
    arguments: argparse.Namespace,
    job: PowerFactoryRunJob,
    run_nonce: str,
) -> int:
    """Execute one job in one process and one disposable project.

    :param arguments: Parent-supplied explicit runtime paths.
    :param job: Exact isolated simulation job.
    :param run_nonce: Parent-origin authentication nonce.
    :return: This function normally terminates through ``os._exit(0)``.
    """
    return main(arguments, run_nonce, job)


def main(
    arguments: argparse.Namespace | None = None,
    run_nonce: str | None = None,
    job: PowerFactoryRunJob | None = None,
) -> int:
    """Execute exactly one standard cell inside one owned project.

    :param arguments: Parent-supplied explicit paths or parsed CLI arguments.
    :param run_nonce: Parent-origin token or one newly generated token.
    :param job: Parent-owned isolated simulation job.
    :return: Two unless the supervised success path exits natively with zero.
    """
    supervised_worker: bool = run_nonce is not None and job is not None
    effective: argparse.Namespace = parse_arguments() if arguments is None else arguments
    nonce: str = secrets.token_hex(32) if run_nonce is None else run_nonce
    if sys.dont_write_bytecode and len(nonce) == 64 and supervised_worker and job is not None:
        pass
    else:
        raise ValueError("Run requires python -B, one 64-hex nonce and one parent-owned job")
    repository_root: Path = effective.repository_root.resolve(strict=True)
    catalog_root: Path = effective.catalog_root.resolve(strict=True)
    if catalog_root.is_relative_to(repository_root):
        pass
    else:
        raise ValueError("Catalog is outside the explicit repository")
    load_catalog_cells(catalog_root)
    output_dir: Path = effective.output_dir.resolve(strict=False)
    output_dir.mkdir(parents=True, exist_ok=False)
    journal_path: Path = output_dir / "mutation-journal.jsonl"
    journal_path.write_text("", encoding="utf-8")
    worker_pid: int = os.getpid()
    process_before: dict[str, object] = inspect_process_inventory(worker_pid)
    (output_dir / "process-before.json").write_text(json.dumps(process_before, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    process_rows_value: object = process_before["rows"]
    process_rows: list[object] = process_rows_value if isinstance(process_rows_value, list) else list((process_rows_value,))
    if any(isinstance(row, dict) and "PowerFactory" in str(row.get("Name", "")) for row in process_rows):
        raise RuntimeError("Pre-existing native PowerFactory session")
    project_name: str = "VG_StandardCell_" + str(job.job_index).zfill(2) + "_" + nonce[:8]
    cell_observations: list[dict[str, object]] = list()
    cleanup: dict[str, object] = {"status": "NOT_STARTED"}
    runtime: dict[str, object] = dict()
    with ExitStack() as resources:
        module = load_powerfactory(effective.binding, effective.powerfactory_root, resources)
        application: PowerFactoryApplication = module.GetApplicationExt()
        current_user: PowerFactoryObject | None = None
        owned_project: PowerFactoryObject | None = None
        prior_project: PowerFactoryObject | None = None
        prior_study: PowerFactoryObject | None = None
        try:
            process_after: dict[str, object] = inspect_process_inventory(worker_pid)
            (output_dir / "process-after-acquire.json").write_text(json.dumps(process_after, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            runtime = {"vendor_version": str(module.__version__), "binding_sha256": hashlib.sha256(effective.binding.read_bytes()).hexdigest(), "worker_pid": worker_pid, "acquired_at_utc": datetime.now(timezone.utc).isoformat()}
            current_user, owned_project, prior_project, prior_study = bootstrap_probe_project(application, project_name, "StandardMatrixGrid", journal_path)
            network_folder: PowerFactoryObject | None = application.GetProjectFolder("netdat", 1)
            if network_folder is not None:
                assert_owned(network_folder, owned_project)
            else:
                raise RuntimeError("Owned network folder unavailable")
            grids: list[PowerFactoryObject] = network_folder.GetContents("*.ElmNet", 1)
            grid_matches: list[PowerFactoryObject] = [candidate for candidate in grids if str(candidate.GetAttribute("loc_name")) == "StandardMatrixGrid"]
            if len(grid_matches) == 1:
                grid: PowerFactoryObject = grid_matches[0]
                assert_owned(grid, owned_project)
            else:
                raise RuntimeError("Owned grid is ambiguous")
            bus: PowerFactoryObject = create_owned_object(grid, "ElmTerm", "Standard_110kV_Bus", owned_project, journal_path)
            set_owned_attribute(bus, "uknom", 110.0, owned_project, journal_path)
            cubicle: PowerFactoryObject = create_owned_object(bus, "StaCubic", "ExternalGrid", owned_project, journal_path)
            source: PowerFactoryObject = create_owned_object(grid, "ElmXnet", "Standard_External_Grid", owned_project, journal_path)
            set_owned_attribute(source, "bus1", cubicle, owned_project, journal_path)
            set_owned_attribute(source, "usetp", 1.0, owned_project, journal_path)
            cell_observations.append(run_standard_cell(application, owned_project, grid, job.cell, job.integration_step, output_dir, journal_path))
        finally:
            if current_user is not None and owned_project is not None:
                cleanup = cleanup_probe_project(application, current_user, owned_project, project_name, prior_project, prior_study, journal_path)
            else:
                cleanup = {"status": "NO_VERIFIED_PROJECT"}
            observations: dict[str, object] = {"schema_version": "1.0", "sealed_dossier_sha256": "4b3aa0ccd496daa7cfbcc3b2d80639724ee0d0255b4b2e2a6763dc5894e57edc", "provenance": "CURRENT_UNTRACKED_WORKTREE", "manifest_sha256": "7099296e4360555daa1ca14f854f3c6b7f11b1c6b0ba38e5e603b9896e726113", "run_nonce": nonce, "job_id": job.job_id, "job_index": job.job_index, "project_name": project_name, "runtime": runtime, "cells": cell_observations, "cleanup": cleanup}
            (output_dir / "observations.json").write_text(json.dumps(observations, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            (output_dir / "cleanup-receipt.json").write_text(json.dumps(cleanup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            write_release_checkpoint(output_dir, observations, nonce, worker_pid, job)
        execution_complete: bool = len(cell_observations) == 1 and cell_observations[0].get("status", None) == "PASS"
        if supervised_worker and cleanup.get("status", None) == "PASS" and execution_complete:
            checkpoint_path: Path = output_dir / "child-checkpoint.json"
            checkpoint_hash: str = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
            acknowledgement_path: Path = output_dir / "parent-checkpoint-ack.json"
            acknowledgement: dict[str, object] | None = None
            deadline: float = time.monotonic() + 30.0
            while acknowledgement is None and time.monotonic() < deadline:
                if acknowledgement_path.is_file():
                    acknowledgement_value: object = json.loads(acknowledgement_path.read_text(encoding="utf-8"))
                    if isinstance(acknowledgement_value, dict):
                        acknowledgement = acknowledgement_value
                    else:
                        raise ValueError("Parent acknowledgement is malformed")
                else:
                    time.sleep(0.05)
            if acknowledgement is None:
                raise TimeoutError("Parent acknowledgement was not published within 30 seconds")
            ack_valid: bool = bool(
                acknowledgement.get("schema_version", None) == "1.0"
                and acknowledgement.get("record_kind", None) == "powerfactory_parent_checkpoint_ack"
                and acknowledgement.get("sealed_dossier_sha256", None) == "4b3aa0ccd496daa7cfbcc3b2d80639724ee0d0255b4b2e2a6763dc5894e57edc"
                and acknowledgement.get("run_nonce", None) == nonce
                and acknowledgement.get("worker_pid", None) == worker_pid
                and acknowledgement.get("job_id", None) == job.job_id
                and acknowledgement.get("job_index", None) == job.job_index
                and acknowledgement.get("checkpoint_sha256", None) == checkpoint_hash
                and acknowledgement.get("status", None) == "ACKNOWLEDGED"
            )
            if ack_valid:
                pass
            else:
                raise ValueError("Parent acknowledgement identity mismatch")
            acknowledgement_hash: str = hashlib.sha256(acknowledgement_path.read_bytes()).hexdigest()
            raw_hash: str = str(cell_observations[0].get("raw_sha256", ""))
            marker: dict[str, object] = {"schema_version": "1.0", "record_kind": "powerfactory_worker_ack_validated", "sealed_dossier_sha256": "4b3aa0ccd496daa7cfbcc3b2d80639724ee0d0255b4b2e2a6763dc5894e57edc", "run_nonce": nonce, "worker_pid": worker_pid, "job_id": job.job_id, "job_index": job.job_index, "checkpoint_sha256": checkpoint_hash, "ack_sha256": acknowledgement_hash, "raw_sha256": raw_hash, "status": "ACK_VALIDATED"}
            marker_path: Path = output_dir / "worker-ack-validated.json"
            marker_temporary_path: Path = output_dir / ("worker-ack-validated.json.tmp-" + nonce)
            with marker_temporary_path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(marker, indent=2, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(marker_temporary_path, marker_path)
            os._exit(0)
        else:
            pass
        application = cast(PowerFactoryApplication, None)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
