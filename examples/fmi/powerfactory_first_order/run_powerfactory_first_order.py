"""Run the reproducible VeraGrid first-order FMI matrix in PowerFactory.

The recipe imports the unmodified FMI 2 FMUs and narrowly derived FMI 3 FMUs,
executes the sealed event profile, and preserves raw result tables outside the
checkout.  Numerical certification is deliberately delegated to the companion
validator so execution evidence cannot certify itself.
"""

from __future__ import annotations

import argparse
import csv
from contextlib import ExitStack
from datetime import datetime, timezone
from enum import Enum
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
from typing import Protocol, cast
from xml.etree import ElementTree
import zipfile

from VeraGridEngine.IO.fmu.compiler import FmuBinaryInterface, Compiler, compile_fmu_shared_library


class PowerFactoryCompatibilityProfile(Enum):
    """Identify the single reviewed PowerFactory FMI 3 compatibility profile."""

    FMI_THREE_CONFIGURATION_MODE = "fmi_three_configuration_mode"


class PowerFactoryObject(Protocol):
    """Describe the bounded vendor object methods used by this probe."""

    def GetParent(self) -> PowerFactoryObject | None:
        """Return the direct vendor database parent."""

    def GetFullName(self) -> str:
        """Return the stable full vendor database name."""

    def GetClassName(self) -> str:
        """Return the vendor object class name."""

    def GetContents(self, query: str, recursive: int = 0) -> list[PowerFactoryObject]:
        """Return children matching a vendor query."""

    def CreateObject(self, class_name: str, name: str) -> PowerFactoryObject | None:
        """Create one child object of the requested class."""

    def GetAttribute(self, name: str) -> object:
        """Read one vendor attribute."""

    def SetAttribute(self, name: str, value: object) -> int | None:
        """Set one vendor attribute."""

    def GetAttributeType(self, name: str) -> object:
        """Read the declared vendor attribute type."""

    def GetAttributeDescription(self, name: str) -> object:
        """Read the declared vendor attribute description."""

    def GetAttributeValueRange(self, name: str) -> object:
        """Read the declared vendor value range."""

    def Check(self) -> int:
        """Run the vendor model consistency check."""

    def Execute(self) -> int:
        """Execute the selected vendor command."""

    def Activate(self) -> int:
        """Activate this vendor context object."""

    def Deactivate(self) -> int:
        """Deactivate this vendor context object."""

    def Delete(self) -> int:
        """Delete this exact vendor object."""

    def IsCalcRelevant(self) -> int:
        """Report whether the object participates in calculation."""

    def GetNumberOfRows(self) -> int:
        """Return retained result row count."""

    def GetValue(self, row: int, column: int) -> tuple[int, object]:
        """Return one result-table value."""

    def Load(self) -> int | None:
        """Load retained result data."""

    def Release(self) -> None:
        """Release retained result data."""

    def Clear(self) -> int | None:
        """Clear retained result definitions."""

    def AddVars(self, target: PowerFactoryObject, variable: str) -> int:
        """Add one result variable for a target object."""

    def WriteChangesToDb(self) -> int | None:
        """Persist current result-variable definitions."""


class PowerFactoryApplication(Protocol):
    """Describe the bounded application methods used by this probe."""

    def GetCurrentUser(self) -> PowerFactoryObject | None:
        """Return the authenticated current user."""

    def GetActiveProject(self) -> PowerFactoryObject | None:
        """Return the active project."""

    def GetActiveStudyCase(self) -> PowerFactoryObject | None:
        """Return the active study case."""

    def CreateProject(self, name: str, grid_name: str) -> PowerFactoryObject | None:
        """Create one project and its initial grid."""

    def ActivateProject(self, project_name: str) -> int:
        """Activate one project by exact name."""

    def GetProjectFolder(self, code: str, create: int = 0) -> PowerFactoryObject | None:
        """Return a project folder by vendor code."""

    def GetFromStudyCase(self, class_name: str) -> PowerFactoryObject | None:
        """Return one object from the active study case."""

    def GetCalcRelevantObjects(self, query: str) -> list[PowerFactoryObject]:
        """Return calculation-relevant objects matching a query."""

    def ResGetIndex(
        self,
        result: PowerFactoryObject,
        target: PowerFactoryObject,
        variable: str,
    ) -> int:
        """Resolve a retained result variable column."""

    def FlushOutputWindow(self) -> None:
        """Flush vendor output to the worker streams."""


class PowerFactoryModule(Protocol):
    """Describe the external compiled module entry point and identity."""

    __version__: str
    __file__: str

    def GetApplicationExt(self) -> PowerFactoryApplication:
        """Start one external engine and return its owned application reference."""


def verify_probe_inputs(
    manifest_path: Path,
    binding_path: Path,
) -> tuple[tuple[str, Path, str, str], ...]:
    """Authenticate six generated cells and select the four supported imports.

    :param manifest_path: Fresh six-cell generator manifest.
    :param binding_path: Explicit PowerFactory compiled Python binding.
    :return: Four tuples containing cell id, FMU path, FMI version and interface.
    """

    manifest_bytes: bytes = manifest_path.resolve(strict=True).read_bytes()
    manifest_value: object = json.loads(manifest_bytes.decode("utf-8"))
    if isinstance(manifest_value, dict):
        manifest: dict[str, object] = cast(dict[str, object], manifest_value)
    else:
        raise ValueError("Generator manifest must be a JSON object")
    manifest_is_valid: bool = bool(
        manifest.get("status", None) == "PASS"
        and manifest.get("cell_count", None) == 6
        and manifest.get("pass_count", None) == 6
    )
    if manifest_is_valid:
        pass
    else:
        raise ValueError("Fresh generator manifest identity or status is invalid")
    cells_value: object = manifest.get("cells", None)
    if isinstance(cells_value, list) and len(cells_value) == 6:
        cells: list[object] = cast(list[object], cells_value)
    else:
        raise ValueError("Generator manifest must contain six cells")

    selected_ids: tuple[str, ...] = ("fmi20_cs", "fmi20_me", "fmi30_cs", "fmi30_me")
    selected: list[tuple[str, Path, str, str]] = list()
    cell_value: object
    for cell_value in cells:
        if isinstance(cell_value, dict):
            cell: dict[str, object] = cast(dict[str, object], cell_value)
        else:
            raise ValueError("Generator cell must be a JSON object")
        cell_id: str = str(cell.get("cell_id", ""))
        fmu_name: str = str(cell.get("fmu_name", ""))
        declared_size: int = int(cell.get("fmu_size_bytes", -1))
        declared_digest: str = str(cell.get("fmu_sha256", ""))
        fmu_path: Path = manifest_path.parent / "fmus" / fmu_name
        fmu_bytes: bytes = fmu_path.resolve(strict=True).read_bytes()
        cell_is_authentic: bool = bool(
            cell.get("status", None) == "PASS"
            and len(fmu_bytes) == declared_size
            and hashlib.sha256(fmu_bytes).hexdigest() == declared_digest
        )
        if cell_is_authentic:
            pass
        else:
            raise ValueError(f"Generated FMU identity failed for {cell_id}")
        if cell_id in selected_ids:
            version: str = str(cell.get("fmi_version_requested", ""))
            interface: str = str(cell.get("interface_requested", ""))
            selected.append((cell_id, fmu_path.resolve(strict=True), version, interface))
        else:
            if cell_id in ("fmi10_cs", "fmi10_me"):
                pass
            else:
                raise ValueError(f"Unexpected six-cell identity {cell_id}")
    selected.sort()
    if tuple(item[0] for item in selected) == selected_ids:
        pass
    else:
        raise ValueError("Deterministic four-cell selection is incomplete")

    resolved_binding_path: Path = binding_path.resolve(strict=True)
    if resolved_binding_path.is_file() and not resolved_binding_path.is_symlink():
        pass
    else:
        raise ValueError("PowerFactory binding must be one explicit regular file")
    return tuple(selected)


def hash_source_closure(
    source_roots: tuple[tuple[str, Path], ...],
) -> dict[str, object]:
    """Hash the bounded FMI 3 source closure with UUID normalization.

    :param source_roots: Ordered interface identifiers and generated roots.
    :return: Raw entries and the normalized deterministic closure digest.
    """

    manifest_lines: list[str] = list()
    raw_entries: list[dict[str, object]] = list()
    uuid_pattern: re.Pattern[bytes] = re.compile(
        rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    )
    interface_record: tuple[str, Path]
    for interface_record in source_roots:
        interface_id: str = interface_record[0]
        source_root: Path = interface_record[1].resolve(strict=True)
        material_paths: list[Path] = list()
        candidate: Path
        for candidate in source_root.rglob("*"):
            relative_parts: tuple[str, ...] = candidate.relative_to(source_root).parts
            ignored_cache: bool = bool("__pycache__" in relative_parts)
            if candidate.is_file() and not candidate.is_symlink() and not ignored_cache:
                material_paths.append(candidate)
            else:
                if ignored_cache or candidate.is_dir():
                    pass
                elif candidate.is_symlink():
                    raise ValueError("Generated source closure contains a symbolic link")
                else:
                    pass
        material_paths.sort()
        if len(material_paths) == 15:
            pass
        else:
            raise ValueError("Generated FMI 3 source closure must contain 15 materials")
        material_path: Path
        for material_path in material_paths:
            relative_path: str = material_path.relative_to(source_root).as_posix()
            raw_bytes: bytes = material_path.read_bytes()
            normalized_bytes: bytes = raw_bytes
            if relative_path == "src/generated_metadata.h":
                uuid_matches: list[bytes] = uuid_pattern.findall(raw_bytes)
                if len(uuid_matches) == 1:
                    normalized_bytes = uuid_pattern.sub(
                        b"00000000-0000-0000-0000-000000000000",
                        raw_bytes,
                        count=1,
                    )
                else:
                    raise ValueError("Generated metadata must contain exactly one UUID")
            else:
                pass
            normalized_sha256: str = hashlib.sha256(normalized_bytes).hexdigest()
            manifest_lines.append(
                interface_id
                + "/"
                + relative_path
                + "|"
                + str(len(raw_bytes))
                + "|"
                + normalized_sha256
            )
            raw_entries.append(
                {
                    "interface": interface_id,
                    "path": relative_path,
                    "size_bytes": len(raw_bytes),
                    "raw_sha256": hashlib.sha256(raw_bytes).hexdigest(),
                    "normalized_sha256": normalized_sha256,
                }
            )
    serialized_manifest: bytes = ("\n".join(manifest_lines) + "\n").encode("utf-8")
    return {
        "material_count": len(raw_entries),
        "entries": raw_entries,
        "manifest_lines": manifest_lines,
        "normalized_closure_sha256": hashlib.sha256(serialized_manifest).hexdigest(),
    }


def verify_generated_source_closure(manifest_path: Path) -> dict[str, object]:
    """Verify both generated FMI 3 source roots and XML identity tokens.

    :param manifest_path: Authenticated six-cell generator manifest.
    :return: Verified source roots, UUID observations, and closure hashes.
    """

    build_root: Path = manifest_path.resolve(strict=True).parent / "build"
    source_roots: tuple[tuple[str, Path], ...] = (
        ("fmi30_cs", build_root / "fmi30_cs" / "source"),
        ("fmi30_me", build_root / "fmi30_me" / "source"),
    )
    closure: dict[str, object] = hash_source_closure(source_roots)
    manifest_value: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    if isinstance(manifest_value, dict):
        manifest: dict[str, object] = cast(dict[str, object], manifest_value)
    else:
        raise ValueError("Generator manifest must be a JSON object")
    cells_value: object = manifest.get("cells", None)
    if isinstance(cells_value, list):
        cells: list[object] = cast(list[object], cells_value)
    else:
        raise ValueError("Generator manifest cells are unavailable")
    uuid_pattern: re.Pattern[str] = re.compile(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    )
    identities: list[dict[str, str]] = list()
    source_record: tuple[str, Path]
    for source_record in source_roots:
        metadata_text: str = (source_record[1] / "src" / "generated_metadata.h").read_text(
            encoding="utf-8"
        )
        metadata_matches: list[str] = uuid_pattern.findall(metadata_text)
        matching_names: list[str] = list()
        cell_value: object
        for cell_value in cells:
            if isinstance(cell_value, dict) and cell_value.get("cell_id", None) == source_record[0]:
                matching_names.append(str(cell_value.get("fmu_name", "")))
            else:
                pass
        if len(matching_names) == 1 and matching_names[0] != "":
            fmu_path: Path = manifest_path.parent / "fmus" / matching_names[0]
        else:
            raise ValueError("Generated FMI 3 FMU identity is ambiguous")
        with zipfile.ZipFile(fmu_path, "r") as archive:
            xml_root: ElementTree.Element = ElementTree.fromstring(
                archive.read("modelDescription.xml")
            )
        instantiation_token: str = str(xml_root.attrib.get("instantiationToken", ""))
        if len(metadata_matches) == 1 and metadata_matches[0] == instantiation_token:
            pass
        else:
            raise ValueError("Generated source UUID does not match the FMU XML token")
        identities.append(
            {
                "interface": source_record[0],
                "uuid": metadata_matches[0],
                "instantiation_token": instantiation_token,
            }
        )
    closure["source_roots"] = [str(item[1]) for item in source_roots]
    closure["identities"] = identities
    return closure


def extract_checked_fmu(fmu_path: Path, destination: Path) -> tuple[str, ...]:
    """Extract one FMU while rejecting unsafe or ambiguous ZIP members.

    :param fmu_path: Existing FMU archive to extract.
    :param destination: New empty extraction directory.
    :return: Sorted logical member names.
    """

    if destination.exists():
        raise FileExistsError("FMU extraction destination already exists")
    else:
        destination.mkdir(parents=True, exist_ok=False)
    seen_names: set[str] = set()
    material_names: list[str] = list()
    with zipfile.ZipFile(fmu_path.resolve(strict=True), "r") as archive:
        member: zipfile.ZipInfo
        for member in archive.infolist():
            normalized_name: str = member.filename.replace("\\", "/")
            name_parts: tuple[str, ...] = tuple(
                part for part in normalized_name.split("/") if len(part) > 0
            )
            unix_mode: int = (member.external_attr >> 16) & 0o170000
            unsafe: bool = bool(
                normalized_name.startswith("/")
                or re.match(r"^[A-Za-z]:", normalized_name) is not None
                or ".." in name_parts
                or normalized_name in seen_names
                or unix_mode == 0o120000
            )
            if unsafe:
                raise ValueError("FMU archive contains an unsafe or duplicate member")
            else:
                seen_names.add(normalized_name)
            target_path: Path = destination.joinpath(*name_parts)
            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(archive.read(member))
                material_names.append(normalized_name)
    material_names.sort()
    return tuple(material_names)


def compile_compatibility_binary(
    source_root: Path,
    output_path: Path,
    interface: str,
    model_identifier: str,
    compiler: Compiler,
) -> Path:
    """Compile one derived FMI 3 binary through the VeraGrid public API.

    :param source_root: Copied and narrowly patched generated source root.
    :param output_path: Expected native shared-library destination.
    :param interface: FMI interface identifier, ``cs`` or ``me``.
    :param model_identifier: XML-declared binary model identifier.
    :param compiler: Caller-owned sequential compiler session.
    :return: Validated compiled binary path.
    """

    source_files: tuple[Path, ...] = (
        source_root / "src" / "runtime_fmi3.c",
        source_root / "src" / "model_instance.c",
        source_root / "src" / "solver.c",
        source_root / "src" / "generated_model.c",
        source_root / "src" / "generated_procedural.c",
    )
    include_directories: tuple[Path, ...] = (
        source_root / "include",
        source_root / "src",
    )
    if interface == "cs":
        binary_interface: FmuBinaryInterface = FmuBinaryInterface.FMI_THREE_CO_SIMULATION
    else:
        if interface == "me":
            binary_interface = FmuBinaryInterface.FMI_THREE_MODEL_EXCHANGE
        else:
            raise ValueError("PowerFactory compatibility build supports only FMI 3 CS or ME")
    return compile_fmu_shared_library(
        source_files,
        include_directories,
        output_path,
        binary_interface,
        model_identifier,
        compiler,
    )


def build_powerfactory_compatibility_fmu(
    cell: tuple[str, Path, str, str],
    source_root: Path,
    output_dir: Path,
    profile: PowerFactoryCompatibilityProfile,
    compiler: Compiler,
) -> tuple[Path, dict[str, object]]:
    """Build one byte-traceable FMI 3 derivative for PowerFactory import.

    :param cell: Authenticated standard FMI 3 cell.
    :param source_root: Matching authenticated generated source root.
    :param output_dir: External execution directory.
    :param profile: Reviewed compatibility profile.
    :param compiler: Caller-owned sequential compiler session.
    :return: Derived FMU path and build receipt.
    """

    if profile is PowerFactoryCompatibilityProfile.FMI_THREE_CONFIGURATION_MODE:
        pass
    else:
        raise ValueError("Unsupported PowerFactory compatibility profile")
    build_root: Path = output_dir / "compatibility_build" / cell[0]
    copied_source: Path = build_root / "source"
    extracted_fmu: Path = build_root / "fmu"
    copied_source.mkdir(parents=True, exist_ok=False)
    source_path: Path
    for source_path in source_root.rglob("*"):
        relative_path: Path = source_path.relative_to(source_root)
        if "__pycache__" in relative_path.parts:
            pass
        else:
            if source_path.is_file() and not source_path.is_symlink():
                copied_path: Path = copied_source / relative_path
                copied_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_path, copied_path)
            else:
                if source_path.is_dir():
                    pass
                else:
                    raise ValueError("Generated source contains a non-regular material")
    runtime_path: Path = copied_source / "src" / "runtime_fmi3.c"
    runtime_before: bytes = runtime_path.read_bytes()
    first_line: bytes = b"VG_UNSUPPORTED_INSTANCE_FUNCTION(fmi3EnterConfigurationMode)"
    second_line: bytes = b"VG_UNSUPPORTED_INSTANCE_FUNCTION(fmi3ExitConfigurationMode)"
    if runtime_before.count(first_line) == 1 and runtime_before.count(second_line) == 1:
        pass
    else:
        raise ValueError("FMI 3 compatibility patch anchors are not exact")
    implementation: bytes = (
        b"fmi3Status fmi3EnterConfigurationMode(fmi3Instance instance) {\n"
        b"    ModelInstance* model = (ModelInstance*)instance;\n"
        b"    if (vg_allowed_state(model, VG_STATE_INSTANTIATED)) {\n"
        b"        return fmi3OK;\n"
        b"    }\n"
        b"    return vg_state_error(model);\n"
        b"}\n\n"
        b"fmi3Status fmi3ExitConfigurationMode(fmi3Instance instance) {\n"
        b"    ModelInstance* model = (ModelInstance*)instance;\n"
        b"    if (vg_allowed_state(model, VG_STATE_INSTANTIATED)) {\n"
        b"        return fmi3OK;\n"
        b"    }\n"
        b"    return vg_state_error(model);\n"
        b"}"
    )
    runtime_after: bytes = runtime_before.replace(first_line + b"\r\n" + second_line, implementation)
    if runtime_after == runtime_before:
        runtime_after = runtime_before.replace(first_line + b"\n" + second_line, implementation)
    else:
        pass
    if runtime_after != runtime_before and runtime_after.count(implementation) == 1:
        runtime_path.write_bytes(runtime_after)
    else:
        raise ValueError("FMI 3 compatibility patch did not apply exactly once")
    members: tuple[str, ...] = extract_checked_fmu(cell[1], extracted_fmu)
    xml_path: Path = extracted_fmu / "modelDescription.xml"
    xml_root: ElementTree.Element = ElementTree.fromstring(xml_path.read_bytes())
    interface_tag: str = "CoSimulation" if cell[3] == "cs" else "ModelExchange"
    interface_node: ElementTree.Element | None = xml_root.find(interface_tag)
    if interface_node is not None:
        model_identifier: str = str(interface_node.attrib.get("modelIdentifier", ""))
    else:
        raise ValueError("FMI 3 XML lacks its declared interface")
    binary_members: list[str] = [name for name in members if name.endswith(".dll")]
    if len(binary_members) == 1:
        binary_path: Path = extracted_fmu.joinpath(*binary_members[0].split("/"))
    else:
        raise ValueError("Standard FMU must contain exactly one Windows binary")
    compile_compatibility_binary(copied_source, binary_path, cell[3], model_identifier, compiler)
    compatibility_dir: Path = output_dir / "compatibility_fmus"
    compatibility_dir.mkdir(parents=True, exist_ok=True)
    output_fmu: Path = compatibility_dir / (cell[1].stem + "_PowerFactory.fmu")
    with zipfile.ZipFile(output_fmu, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        member_name: str
        for member_name in members:
            # Compiler extraction is build evidence, never an FMU member.
            material_path: Path = extracted_fmu.joinpath(*member_name.split("/"))
            archive.write(material_path, member_name)
    with zipfile.ZipFile(cell[1], "r") as standard_archive:
        with zipfile.ZipFile(output_fmu, "r") as derivative_archive:
            if tuple(sorted(standard_archive.namelist())) == tuple(sorted(derivative_archive.namelist())):
                pass
            else:
                raise ValueError("PowerFactory derivative changed the FMU member topology")
            unchanged_member: str
            for unchanged_member in members:
                if unchanged_member == binary_members[0]:
                    pass
                else:
                    if standard_archive.read(unchanged_member) == derivative_archive.read(unchanged_member):
                        pass
                    else:
                        raise ValueError("PowerFactory derivative changed a non-binary FMU member")
    output_bytes: bytes = output_fmu.read_bytes()
    receipt: dict[str, object] = {
        "cell_id": cell[0],
        "profile": profile.value,
        "standard_fmu_sha256": hashlib.sha256(cell[1].read_bytes()).hexdigest(),
        "derived_fmu_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "derived_fmu_size_bytes": len(output_bytes),
        "runtime_before_sha256": hashlib.sha256(runtime_before).hexdigest(),
        "runtime_after_sha256": hashlib.sha256(runtime_after).hexdigest(),
        "patch_sha256": hashlib.sha256(implementation).hexdigest(),
        "source_closure_sha256": hash_source_closure(((cell[0], source_root),))["normalized_closure_sha256"],
        "changed_source": "src/runtime_fmi3.c",
        "changed_function_count": 2,
        "member_topology_preserved": True,
        "xml_and_resources_byte_identical": True,
        "status": "PASS",
    }
    return output_fmu.resolve(strict=True), receipt


def verify_runtime_inputs(
    manifest_path: Path,
    binding_path: Path,
    output_dir: Path,
) -> tuple[tuple[str, Path, str, str], ...]:
    """Authenticate inputs and build the two FMI 3 PowerFactory derivatives.

    :param manifest_path: Fresh six-cell generator manifest.
    :param binding_path: Exact licensed PowerFactory binding.
    :param output_dir: External execution directory.
    :return: Four runnable FMI 2/3 CS/ME cells.
    """

    selected: tuple[tuple[str, Path, str, str], ...] = verify_probe_inputs(
        manifest_path,
        binding_path,
    )
    closure: dict[str, object] = verify_generated_source_closure(manifest_path)
    runnable: list[tuple[str, Path, str, str]] = list()
    builds: list[dict[str, object]] = list()
    compiler: Compiler = Compiler()
    try:
        cell: tuple[str, Path, str, str]
        for cell in selected:
            if cell[2] == "3.0":
                source_root: Path = manifest_path.parent / "build" / cell[0] / "source"
                derived_path: Path
                build_receipt: dict[str, object]
                derived_path, build_receipt = build_powerfactory_compatibility_fmu(
                    cell,
                    source_root,
                    output_dir,
                    PowerFactoryCompatibilityProfile.FMI_THREE_CONFIGURATION_MODE,
                    compiler,
                )
                runnable.append((cell[0], derived_path, cell[2], cell[3]))
                builds.append(build_receipt)
            else:
                runnable.append(cell)
    except BaseException as primary_error:
        raise
    receipt: dict[str, object] = {
        "schema_version": "1.0",
        "source_closure": closure,
        "compiler": {
            "owner": "VeraGridEngine.IO.fmu.compiler.Compiler",
            "selection_policy": "shared Compiler interface",
            "status": "PASS",
        },
        "binding": {
            "size_bytes": binding_path.resolve(strict=True).stat().st_size,
            "sha256": hashlib.sha256(binding_path.resolve(strict=True).read_bytes()).hexdigest(),
        },
        "builds": builds,
        "status": "PASS" if len(builds) == 2 else "FAIL",
    }
    manifest_lines_value: object = closure.get("manifest_lines", None)
    manifest_lines: list[str] = list()
    if (
        isinstance(manifest_lines_value, list)
        and len(manifest_lines_value) == 30
        and all(isinstance(item, str) for item in manifest_lines_value)
    ):
        manifest_line_value: object
        for manifest_line_value in manifest_lines_value:
            if isinstance(manifest_line_value, str):
                manifest_lines.append(manifest_line_value)
            else:
                raise ValueError("Generated source manifest line is not text")
    else:
        raise ValueError("Generated source manifest serialization is unavailable")
    (output_dir / "source-closure-manifest.txt").write_text(
        "\n".join(manifest_lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output_dir / "compatibility-build-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if len(builds) == 2:
        return tuple(runnable)
    else:
        raise RuntimeError("PowerFactory FMI 3 compatibility build is incomplete")


def load_powerfactory(
    binding_path: Path,
    powerfactory_root: Path,
    resources: ExitStack,
) -> PowerFactoryModule:
    """Load the exact compiled vendor binding without environment mutation.

    :param binding_path: Authenticated compiled extension path.
    :param powerfactory_root: Explicit installed PowerFactory root.
    :param resources: Stack retaining the scoped DLL-directory handle.
    :return: Typed view of the loaded compiled vendor module.
    """

    canonical_root: Path = powerfactory_root.resolve(strict=True)
    canonical_binding: Path = binding_path.resolve(strict=True)
    if canonical_binding.is_relative_to(canonical_root):
        pass
    else:
        raise ValueError("PowerFactory binding is outside the explicit root")
    resources.enter_context(os.add_dll_directory(str(canonical_root)))
    module_spec: importlib.machinery.ModuleSpec | None = (
        importlib.util.spec_from_file_location("powerfactory", canonical_binding)
    )
    if module_spec is not None and module_spec.loader is not None:
        pass
    else:
        raise ImportError("Cannot construct compiled PowerFactory module spec")
    module_object: object = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(cast(object, module_object))
    module: PowerFactoryModule = cast(PowerFactoryModule, module_object)
    loaded_path: Path = Path(module.__file__).resolve(strict=True)
    if loaded_path == canonical_binding and str(module.__version__).strip() != "":
        pass
    else:
        raise RuntimeError("Loaded PowerFactory module identity is invalid")
    return module


def inspect_process_inventory(worker_pid: int) -> dict[str, object]:
    """Capture the owned worker and PowerFactory-named process ancestry.

    :param worker_pid: Current isolated Python worker process identifier.
    :return: Parsed read-only process observation with command status.
    """

    powershell_path: Path = Path(
        r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    ).resolve(strict=True)
    script: str = (
        "$ErrorActionPreference='Stop';"
        "$worker="
        + str(worker_pid)
        + ";"
        "$rows=Get-CimInstance Win32_Process | "
        "Where-Object { $_.ProcessId -eq $worker -or $_.Name -like '*PowerFactory*' } | "
        "Select-Object Name,ProcessId,ParentProcessId,CreationDate,ExecutablePath;"
        "$rows | Sort-Object ProcessId | ConvertTo-Json -Compress"
    )
    process: subprocess.CompletedProcess[str] = subprocess.run(
        [str(powershell_path), "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        timeout=30.0,
        check=False,
    )
    if process.returncode == 0 and process.stderr == "":
        pass
    else:
        raise RuntimeError(
            f"Process inventory failed closed: code={process.returncode}; "
            f"stderr={process.stderr.strip()}"
        )
    raw_stdout: str = process.stdout.strip()
    if raw_stdout == "":
        rows: object = list()
    else:
        rows = json.loads(raw_stdout)
    return {
        "worker_pid": worker_pid,
        "worker_executable": str(Path(sys.executable).resolve(strict=True)),
        "worker_executable_sha256": hashlib.sha256(
            Path(sys.executable).resolve(strict=True).read_bytes()
        ).hexdigest(),
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
        "powershell_sha256": hashlib.sha256(powershell_path.read_bytes()).hexdigest(),
    }


def bootstrap_probe_project(
    application: PowerFactoryApplication,
    project_name: str,
    grid_name: str,
    journal_path: Path,
) -> tuple[PowerFactoryObject, PowerFactoryObject, PowerFactoryObject | None, PowerFactoryObject | None]:
    """Create exactly one authenticated temporary project bootstrap.

    :param application: Owned PowerFactory application reference.
    :param project_name: Unique temporary project name.
    :param grid_name: Initial grid name created with the project.
    :param journal_path: Append-only external mutation journal.
    :return: Current user, owned project, prior project and prior study case.
    """

    current_user: PowerFactoryObject | None = application.GetCurrentUser()
    if current_user is not None:
        pass
    else:
        raise RuntimeError("PowerFactory current user is unavailable")
    prior_project: PowerFactoryObject | None = application.GetActiveProject()
    prior_study: PowerFactoryObject | None = application.GetActiveStudyCase()
    existing_projects: list[PowerFactoryObject] = current_user.GetContents("*.IntPrj", 1)
    existing_names: list[str] = [""] * len(existing_projects)
    existing_index: int
    for existing_index in range(len(existing_projects)):
        existing_names[existing_index] = str(
            existing_projects[existing_index].GetAttribute("loc_name")
        )
    if project_name not in existing_names:
        pass
    else:
        raise RuntimeError("Temporary project name already exists")
    bootstrap_record: dict[str, object] = {
        "operation": "BOOTSTRAP_CREATE_PROJECT",
        "parent_full_name": str(current_user.GetFullName()),
        "parent_class": str(current_user.GetClassName()),
        "name": project_name,
        "grid_name": grid_name,
        "verified_absent": True,
    }
    with journal_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(bootstrap_record, sort_keys=True) + "\n")
    created_project: PowerFactoryObject | None = application.CreateProject(
        project_name, grid_name
    )
    if created_project is not None:
        pass
    else:
        raise RuntimeError("CreateProject returned no project")
    activation_code: int = int(application.ActivateProject(project_name))
    active_project: PowerFactoryObject | None = application.GetActiveProject()
    project_identity_is_valid: bool = bool(
        activation_code == 0
        and active_project is not None
        and str(active_project.GetClassName()) == "IntPrj"
        and str(active_project.GetAttribute("loc_name")) == project_name
        and str(active_project.GetFullName()) == str(created_project.GetFullName())
    )
    if project_identity_is_valid and active_project is not None:
        owned_project: PowerFactoryObject = active_project
    else:
        raise RuntimeError("Created project identity or activation is invalid")
    return current_user, owned_project, prior_project, prior_study


def assert_owned(target: PowerFactoryObject, owned_project: PowerFactoryObject) -> None:
    """Require a target to be the owned project or one of its descendants.

    :param target: Candidate target for a mutation or calculation.
    :param owned_project: Exact temporary project root.
    :return: None. An ancestry mismatch raises before the operation.
    """

    owned_name: str = str(owned_project.GetFullName())
    cursor: PowerFactoryObject | None = target
    depth: int = 0
    found: bool = False
    while cursor is not None and depth < 128 and not found:
        if str(cursor.GetFullName()) == owned_name:
            found = True
        else:
            cursor = cursor.GetParent()
        depth += 1
    if found:
        pass
    else:
        raise RuntimeError("Mutation target is outside the owned project")


def create_owned_object(
    parent: PowerFactoryObject,
    class_name: str,
    name: str,
    owned_project: PowerFactoryObject,
    journal_path: Path,
) -> PowerFactoryObject:
    """Create one object only below the verified temporary project.

    :param parent: Verified destination parent.
    :param class_name: Vendor object class.
    :param name: New object name.
    :param owned_project: Exact temporary project root.
    :param journal_path: Append-only external journal.
    :return: Newly created and ancestry-verified object.
    """

    assert_owned(parent, owned_project)
    record: dict[str, object] = {
        "operation": "CREATE",
        "parent": str(parent.GetFullName()),
        "class": class_name,
        "name": name,
        "owned_root": str(owned_project.GetFullName()),
    }
    with journal_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")
    created: PowerFactoryObject | None = parent.CreateObject(class_name, name)
    if created is not None:
        assert_owned(created, owned_project)
        return created
    else:
        raise RuntimeError(f"CreateObject failed for {class_name}:{name}")


def set_owned_attribute(
    target: PowerFactoryObject,
    attribute_name: str,
    value: object,
    owned_project: PowerFactoryObject,
    journal_path: Path,
) -> None:
    """Set one attribute after exact ancestry and journal checks.

    :param target: Owned target object.
    :param attribute_name: Vendor attribute name.
    :param value: New attribute value.
    :param owned_project: Exact temporary project root.
    :param journal_path: Append-only external journal.
    :return: None.
    """

    assert_owned(target, owned_project)
    record: dict[str, object] = {
        "operation": "SET_ATTRIBUTE",
        "target": str(target.GetFullName()),
        "attribute": attribute_name,
        "value": str(value),
        "owned_root": str(owned_project.GetFullName()),
    }
    with journal_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")
    result: int | None = target.SetAttribute(attribute_name, value)
    if result is None or int(result) == 0:
        pass
    else:
        raise RuntimeError(
            f"SetAttribute failed for {attribute_name} with code {result}"
        )


def inspect_attributes(
    target: PowerFactoryObject,
    attribute_names: tuple[str, ...],
) -> dict[str, object]:
    """Observe values and metadata without guessing unsupported attributes.

    :param target: Vendor object to inspect.
    :param attribute_names: Exact candidate attribute names.
    :return: JSON-ready observations, including explicit per-attribute errors.
    """

    observations: dict[str, object] = dict()
    attribute_name: str
    for attribute_name in attribute_names:
        record: dict[str, object] = dict()
        try:
            record["value"] = str(target.GetAttribute(attribute_name))
        except Exception as exception:
            record["value_error"] = (
                f"{exception.__class__.__name__}: {exception}"
            )
        try:
            record["type"] = str(target.GetAttributeType(attribute_name))
        except Exception as exception:
            record["type_error"] = (
                f"{exception.__class__.__name__}: {exception}"
            )
        try:
            record["description"] = str(
                target.GetAttributeDescription(attribute_name)
            )
        except Exception as exception:
            record["description_error"] = (
                f"{exception.__class__.__name__}: {exception}"
            )
        try:
            record["range"] = str(target.GetAttributeValueRange(attribute_name))
        except Exception as exception:
            record["range_error"] = (
                f"{exception.__class__.__name__}: {exception}"
            )
        observations[attribute_name] = record
    return observations


def inspect_import(
    application: PowerFactoryApplication,
    owned_project: PowerFactoryObject,
    grid: PowerFactoryObject,
    cell: tuple[str, Path, str, str],
    xml_observation: dict[str, object],
    journal_path: Path,
) -> dict[str, object]:
    """Import and inspect one cell, with a bounded initialisation attempt.

    :param application: Owned PowerFactory application reference.
    :param owned_project: Exact temporary project root.
    :param grid: Owned project grid.
    :param cell: Authenticated cell identity tuple.
    :param xml_observation: Fail-closed archive declaration observation.
    :param journal_path: Append-only external mutation journal.
    :return: JSON-ready vendor observations for this one cell.
    """

    cell_id: str = cell[0]
    fmu_path: Path = cell[1]
    model_folder: PowerFactoryObject | None = application.GetProjectFolder("blk", 1)
    if model_folder is not None:
        assert_owned(model_folder, owned_project)
    else:
        raise RuntimeError("Owned model folder is unavailable")
    model: PowerFactoryObject = create_owned_object(
        model_folder, "TypMdl", cell_id + "_Type", owned_project, journal_path
    )
    set_owned_attribute(model, "modelType", 1, owned_project, journal_path)
    set_owned_attribute(
        model, "cfilePath", str(fmu_path), owned_project, journal_path
    )
    assert_owned(model, owned_project)
    check_record: dict[str, object] = {
        "operation": "CHECK",
        "target": str(model.GetFullName()),
        "owned_root": str(owned_project.GetFullName()),
    }
    with journal_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(check_record, sort_keys=True) + "\n")
    type_check: int = int(model.Check())
    model_observation: dict[str, object] = inspect_attributes(
        model,
        (
            "cmodelInformation",
            "cinputAll",
            "coutputAll",
            "inputInitFmu",
            "outputInitFmu",
            "inputInit",
            "outputInit",
            "localInputDefinition",
            "initEquation",
            "initAlgorithm",
        ),
    )

    frame: PowerFactoryObject = create_owned_object(
        model_folder, "BlkDef", cell_id + "_Frame", owned_project, journal_path
    )
    slot: PowerFactoryObject = create_owned_object(
        frame, "BlkSlot", "FMU", owned_project, journal_path
    )
    composite: PowerFactoryObject = create_owned_object(
        grid, "ElmComp", cell_id + "_Composite", owned_project, journal_path
    )
    instance: PowerFactoryObject = create_owned_object(
        composite, "ElmMdl", cell_id + "_Instance", owned_project, journal_path
    )
    set_owned_attribute(instance, "typ_id", model, owned_project, journal_path)
    set_owned_attribute(composite, "typ_id", frame, owned_project, journal_path)
    set_owned_attribute(
        composite, "pblk", list((slot,)), owned_project, journal_path
    )
    set_owned_attribute(
        composite, "pelm", list((instance,)), owned_project, journal_path
    )
    assert_owned(instance, owned_project)
    instance_check_record: dict[str, object] = {
        "operation": "CHECK",
        "target": str(instance.GetFullName()),
        "owned_root": str(owned_project.GetFullName()),
    }
    with journal_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(instance_check_record, sort_keys=True) + "\n")
    instance_check: int = int(instance.Check())
    instance_observation: dict[str, object] = inspect_attributes(
        instance,
        (
            "fmuType",
            "cfmuType",
            "inputInitFmu",
            "outputInitFmu",
            "fmuSamplingTime",
            "samplingTimeFmu",
            "outserv",
            "s:u",
            "s:x",
        ),
    )

    event_observation: dict[str, object] = dict()
    event_folder: PowerFactoryObject | None = application.GetFromStudyCase("IntEvt")
    if event_folder is not None:
        assert_owned(event_folder, owned_project)
        event: PowerFactoryObject = create_owned_object(
            event_folder,
            "EvtParam",
            cell_id + "_Inactive_Input_Probe",
            owned_project,
            journal_path,
        )
        try:
            set_owned_attribute(event, "outserv", 1, owned_project, journal_path)
            event_observation = inspect_attributes(
                event,
                (
                    "p_target",
                    "variable",
                    "varname",
                    "cVariable",
                    "newval",
                    "value",
                    "time",
                    "outserv",
                ),
            )
        finally:
            assert_owned(event, owned_project)
            delete_record: dict[str, object] = {
                "operation": "DELETE_INACTIVE_EVENT",
                "target": str(event.GetFullName()),
                "owned_root": str(owned_project.GetFullName()),
            }
            with journal_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(delete_record, sort_keys=True) + "\n")
            event.Delete()
    else:
        event_observation["folder_error"] = "IntEvt is unavailable"

    command_observation: dict[str, object] = dict()
    command_class: str
    for command_class in ("ComLdf", "ComInc", "ComSim", "ElmRes"):
        command: PowerFactoryObject | None = application.GetFromStudyCase(command_class)
        if command is not None:
            assert_owned(command, owned_project)
            if command_class == "ComInc":
                names: tuple[str, ...] = (
                    "iopt_sim",
                    "dtgrd",
                    "dtout",
                    "iopt_adapt",
                    "iopt_method",
                    "iopt_alg",
                    "tstart",
                )
            elif command_class == "ComSim":
                names = ("tstop",)
            else:
                names = tuple()
            command_observation[command_class] = {
                "full_name": str(command.GetFullName()),
                "attributes": inspect_attributes(command, names),
            }
        else:
            command_observation[command_class] = {"error": "UNAVAILABLE"}

    initialization: dict[str, object] = {
        "attempted": False,
        "reason": "PRECONDITIONS_NOT_EVALUATED",
    }
    input_start_is_zero: bool = bool(
        xml_observation.get("input_u_start", None) == 0.0
        and xml_observation.get("input_u_scalar_real", None) is True
    )
    if input_start_is_zero and type_check == 0 and instance_check == 0:
        exactly_one_active: dict[str, object] = verify_active_cell(
            application, owned_project, instance
        )
        initialization["active_set"] = exactly_one_active
        if exactly_one_active.get("status", None) == "PASS":
            load_flow: PowerFactoryObject | None = application.GetFromStudyCase(
                "ComLdf"
            )
            initial_conditions: PowerFactoryObject | None = (
                application.GetFromStudyCase("ComInc")
            )
            if load_flow is not None and initial_conditions is not None:
                assert_owned(load_flow, owned_project)
                assert_owned(initial_conditions, owned_project)
                set_owned_attribute(
                    initial_conditions,
                    "iopt_sim",
                    "rms",
                    owned_project,
                    journal_path,
                )
                set_owned_attribute(
                    initial_conditions,
                    "dtgrd",
                    0.001,
                    owned_project,
                    journal_path,
                )
                set_owned_attribute(
                    initial_conditions,
                    "dtout",
                    0.001,
                    owned_project,
                    journal_path,
                )
                for command_target in (load_flow, initial_conditions):
                    execute_record: dict[str, object] = {
                        "operation": "EXECUTE",
                        "target": str(command_target.GetFullName()),
                        "owned_root": str(owned_project.GetFullName()),
                    }
                    with journal_path.open(
                        "a", encoding="utf-8", newline="\n"
                    ) as stream:
                        stream.write(
                            json.dumps(execute_record, sort_keys=True) + "\n"
                        )
                load_flow_code: int = int(load_flow.Execute())
                if load_flow_code == 0:
                    cominc_code: int | None = int(initial_conditions.Execute())
                else:
                    cominc_code = None
                initialization = {
                    "attempted": True,
                    "load_flow_code": load_flow_code,
                    "cominc_code": cominc_code,
                    "observed_instance": inspect_attributes(
                        instance, ("s:u", "s:x")
                    ),
                    "no_comsim": True,
                }
            else:
                initialization["reason"] = "COMMAND_UNAVAILABLE"
        else:
            initialization["reason"] = "ACTIVE_SET_NOT_EXACT"
    else:
        initialization["reason"] = "XML_OR_IMPORT_PRECONDITION_FAILED"

    observation: dict[str, object] = {
        "cell_id": cell_id,
        "fmi_version": cell[2],
        "interface": cell[3],
        "fmu_path": str(fmu_path),
        "xml": xml_observation,
        "type_check": type_check,
        "instance_check": instance_check,
        "model": model_observation,
        "instance": instance_observation,
        "event": event_observation,
        "commands": command_observation,
        "initialization": initialization,
    }

    for target in (instance, composite, slot, frame, model):
        assert_owned(target, owned_project)
        delete_record = {
            "operation": "DELETE_CELL_OBJECT",
            "target": str(target.GetFullName()),
            "owned_root": str(owned_project.GetFullName()),
        }
        with journal_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(delete_record, sort_keys=True) + "\n")
        target.Delete()
    return observation


def configure_cell(
    application: PowerFactoryApplication,
    owned_project: PowerFactoryObject,
    grid: PowerFactoryObject,
    cell: tuple[str, Path, str, str],
    journal_path: Path,
) -> tuple[
    PowerFactoryObject,
    PowerFactoryObject,
    PowerFactoryObject,
    PowerFactoryObject,
    PowerFactoryObject,
    dict[str, object],
]:
    """Create and validate one owned PowerFactory FMU model instance.

    :param application: Owned licensed PowerFactory application.
    :param owned_project: Exact disposable project root.
    :param grid: Owned calculation grid.
    :param cell: Authenticated runnable cell.
    :param journal_path: Append-only external mutation journal.
    :return: Instance, model, frame, slot, composite, and import observation.
    """

    cell_id: str = cell[0]
    model_folder: PowerFactoryObject | None = application.GetProjectFolder("blk", 1)
    if model_folder is not None:
        assert_owned(model_folder, owned_project)
    else:
        raise RuntimeError("Owned model folder is unavailable")
    model: PowerFactoryObject = create_owned_object(
        model_folder,
        "TypMdl",
        cell_id + "_Type",
        owned_project,
        journal_path,
    )
    set_owned_attribute(model, "modelType", 1, owned_project, journal_path)
    set_owned_attribute(model, "cfilePath", str(cell[1]), owned_project, journal_path)
    type_check: int = int(model.Check())
    information: str = str(model.GetAttribute("cmodelInformation"))
    if type_check == 0 and "u" in str(model.GetAttribute("cinputAll")) and "x" in str(model.GetAttribute("coutputAll")):
        pass
    else:
        raise RuntimeError("PowerFactory FMU type import failed or lacks u/x")
    frame: PowerFactoryObject = create_owned_object(
        model_folder,
        "BlkDef",
        cell_id + "_Frame",
        owned_project,
        journal_path,
    )
    slot: PowerFactoryObject = create_owned_object(
        frame,
        "BlkSlot",
        "FMU",
        owned_project,
        journal_path,
    )
    composite: PowerFactoryObject = create_owned_object(
        grid,
        "ElmComp",
        cell_id + "_Composite",
        owned_project,
        journal_path,
    )
    instance: PowerFactoryObject = create_owned_object(
        composite,
        "ElmMdl",
        cell_id + "_Instance",
        owned_project,
        journal_path,
    )
    set_owned_attribute(instance, "typ_id", model, owned_project, journal_path)
    set_owned_attribute(composite, "typ_id", frame, owned_project, journal_path)
    set_owned_attribute(composite, "pblk", list((slot,)), owned_project, journal_path)
    set_owned_attribute(composite, "pelm", list((instance,)), owned_project, journal_path)
    instance_check: int = int(instance.Check())
    if instance_check == 0:
        pass
    else:
        raise RuntimeError("PowerFactory FMU instance check failed")
    observation: dict[str, object] = {
        "type_check_code": type_check,
        "instance_check_code": instance_check,
        "type_information": information,
        "model": str(model.GetFullName()),
        "instance": str(instance.GetFullName()),
        "model_attributes": inspect_attributes(
            model,
            ("cmodelInformation", "cinputAll", "coutputAll"),
        ),
        "instance_attributes": inspect_attributes(
            instance,
            ("fmuType", "cfmuType", "s:u", "s:x"),
        ),
    }
    return instance, model, frame, slot, composite, observation


def create_event_profile(
    application: PowerFactoryApplication,
    owned_project: PowerFactoryObject,
    instance: PowerFactoryObject,
    cell_id: str,
    journal_path: Path,
) -> tuple[PowerFactoryObject, ...]:
    """Create the sealed three-event input profile for one FMU instance.

    :param application: Owned licensed PowerFactory application.
    :param owned_project: Exact disposable project root.
    :param instance: Target FMU model instance.
    :param cell_id: Stable cell identity used in event names.
    :param journal_path: Append-only external mutation journal.
    :return: Three created event objects in time order.
    """

    event_folder: PowerFactoryObject | None = application.GetFromStudyCase("IntEvt")
    if event_folder is not None:
        assert_owned(event_folder, owned_project)
    else:
        raise RuntimeError("PowerFactory event folder is unavailable")
    schedule: tuple[tuple[float, str], ...] = (
        (0.2, "1"),
        (0.5, "-0.5"),
        (0.8, "0.25"),
    )
    events: list[PowerFactoryObject] = list()
    event_index: int = 0
    schedule_row: tuple[float, str]
    for schedule_row in schedule:
        event: PowerFactoryObject = create_owned_object(
            event_folder,
            "EvtParam",
            cell_id + "_Input_" + str(event_index + 1),
            owned_project,
            journal_path,
        )
        set_owned_attribute(event, "p_target", instance, owned_project, journal_path)
        set_owned_attribute(event, "variable", "u", owned_project, journal_path)
        set_owned_attribute(event, "value", schedule_row[1], owned_project, journal_path)
        set_owned_attribute(event, "time", schedule_row[0], owned_project, journal_path)
        set_owned_attribute(event, "outserv", 0, owned_project, journal_path)
        events.append(event)
        event_index += 1
    return tuple(events)


def read_result_rows(
    application: PowerFactoryApplication,
    result: PowerFactoryObject,
    instance: PowerFactoryObject,
    output_path: Path,
) -> dict[str, object]:
    """Read and preserve the raw PowerFactory u/x result table.

    :param application: Owned licensed PowerFactory application.
    :param result: Executed PowerFactory result object.
    :param instance: FMU instance whose variables were recorded.
    :param output_path: New external CSV destination.
    :return: Row count, column indexes, finiteness, and content identity.
    """

    load_code: int | None = result.Load()
    loaded: bool = bool(load_code is None or load_code == 0)
    try:
        if loaded:
            pass
        else:
            raise RuntimeError("PowerFactory result table could not be loaded")
        u_column: int = int(application.ResGetIndex(result, instance, "s:u"))
        x_column: int = int(application.ResGetIndex(result, instance, "s:x"))
        if u_column >= 0 and x_column >= 0:
            pass
        else:
            raise RuntimeError("PowerFactory result variables s:u/s:x are unavailable")
        row_count: int = int(result.GetNumberOfRows())
        output_path.parent.mkdir(parents=True, exist_ok=True)
        finite: bool = True
        with output_path.open("x", encoding="utf-8", newline="") as stream:
            writer: csv.writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(("time", "u", "x"))
            row_index: int
            for row_index in range(row_count):
                time_value: float = float(result.GetValue(row_index, -1)[1])
                u_value: float = float(result.GetValue(row_index, u_column)[1])
                x_value: float = float(result.GetValue(row_index, x_column)[1])
                if math.isfinite(time_value) and math.isfinite(u_value) and math.isfinite(x_value):
                    pass
                else:
                    finite = False
                writer.writerow((format(time_value, ".17g"), format(u_value, ".17g"), format(x_value, ".17g")))
        output_bytes: bytes = output_path.read_bytes()
        return {
            "raw_trace_name": output_path.name,
            "raw_trace_size_bytes": len(output_bytes),
            "raw_trace_sha256": hashlib.sha256(output_bytes).hexdigest(),
            "row_count": row_count,
            "u_column": u_column,
            "x_column": x_column,
            "finite": finite,
            "status": "PASS" if row_count >= 1201 and finite else "FAIL",
        }
    finally:
        if loaded:
            result.Release()
        else:
            pass


def run_dynamic_cell(
    application: PowerFactoryApplication,
    owned_project: PowerFactoryObject,
    grid: PowerFactoryObject,
    cell: tuple[str, Path, str, str],
    integration_step: float,
    output_dir: Path,
    journal_path: Path,
) -> dict[str, object]:
    """Execute one PowerFactory dynamic cell and preserve its raw trace.

    :param application: Owned licensed PowerFactory application.
    :param owned_project: Exact disposable project root.
    :param grid: Owned calculation grid.
    :param cell: Authenticated runnable cell.
    :param integration_step: PowerFactory RMS integration grid in seconds.
    :param output_dir: External evidence directory.
    :param journal_path: Append-only external mutation journal.
    :return: Import, command, event, and raw-result observations.
    """

    instance: PowerFactoryObject
    model: PowerFactoryObject
    frame: PowerFactoryObject
    slot: PowerFactoryObject
    composite: PowerFactoryObject
    import_observation: dict[str, object]
    instance, model, frame, slot, composite, import_observation = configure_cell(
        application,
        owned_project,
        grid,
        cell,
        journal_path,
    )
    events: tuple[PowerFactoryObject, ...] = tuple()
    result_loaded: bool = False
    try:
        active_observation: dict[str, object] = verify_active_cell(
            application,
            owned_project,
            instance,
        )
        if active_observation.get("status", None) == "PASS":
            pass
        else:
            raise RuntimeError("PowerFactory active FMU set is not exact")
        events = create_event_profile(
            application,
            owned_project,
            instance,
            cell[0],
            journal_path,
        )
        load_flow: PowerFactoryObject | None = application.GetFromStudyCase("ComLdf")
        initial_conditions: PowerFactoryObject | None = application.GetFromStudyCase("ComInc")
        simulation: PowerFactoryObject | None = application.GetFromStudyCase("ComSim")
        result: PowerFactoryObject | None = application.GetFromStudyCase("ElmRes")
        if load_flow is not None and initial_conditions is not None and simulation is not None and result is not None:
            pass
        else:
            raise RuntimeError("PowerFactory dynamic study-case commands are incomplete")
        command_target: PowerFactoryObject
        for command_target in (load_flow, initial_conditions, simulation, result):
            assert_owned(command_target, owned_project)
        set_owned_attribute(initial_conditions, "iopt_sim", "rms", owned_project, journal_path)
        # Tighten only the equation residual requested by the commercial
        # verification; keep PowerFactory's trapezoidal damping default.
        set_owned_attribute(initial_conditions, "errseq", 0.000001, owned_project, journal_path)
        set_owned_attribute(initial_conditions, "iopt_adapt", 0, owned_project, journal_path)
        set_owned_attribute(initial_conditions, "dtgrd", integration_step, owned_project, journal_path)
        set_owned_attribute(initial_conditions, "dtout", 0.001, owned_project, journal_path)
        # PowerFactory interrupts may restart the integration grid.  Enforced
        # synchronisation preserves exact 1 ms result points independently of
        # the smaller ME refinement step, and records only those points.
        set_owned_attribute(initial_conditions, "iopt_sync", 1, owned_project, journal_path)
        set_owned_attribute(initial_conditions, "syncperiod", 0.001, owned_project, journal_path)
        set_owned_attribute(initial_conditions, "ciopt_sample", 2, owned_project, journal_path)
        set_owned_attribute(initial_conditions, "tstart", 0.0, owned_project, journal_path)
        set_owned_attribute(simulation, "tstop", 1.2, owned_project, journal_path)
        errseq_percent: float = float(initial_conditions.GetAttribute("errseq"))
        alpha_rms: float = float(initial_conditions.GetAttribute("alpha_rms"))
        if math.isclose(errseq_percent, 0.000001, rel_tol=0.0, abs_tol=1e-15) and alpha_rms == 1.0:
            pass
        else:
            raise RuntimeError("PowerFactory errseq or alpha_rms readback is invalid")
        result.Clear()
        add_u_code: int = int(result.AddVars(instance, "s:u"))
        add_x_code: int = int(result.AddVars(instance, "s:x"))
        result.WriteChangesToDb()
        load_flow_code: int = int(load_flow.Execute())
        if load_flow_code == 0:
            cominc_code: int | None = int(initial_conditions.Execute())
        else:
            cominc_code = None
        if cominc_code == 0:
            comsim_code: int | None = int(simulation.Execute())
        else:
            comsim_code = None
        if load_flow_code == 0 and cominc_code == 0 and comsim_code == 0:
            pass
        else:
            raise RuntimeError(
                "PowerFactory dynamic execution failed: "
                + str((load_flow_code, cominc_code, comsim_code))
            )
        step_tag: str = format(integration_step, ".9f").replace(".", "p")
        raw_path: Path = output_dir / "raw_traces" / (cell[0] + "_h_" + step_tag + ".csv")
        result_observation: dict[str, object] = read_result_rows(
            application,
            result,
            instance,
            raw_path,
        )
        result_loaded = False
        status: str = "PASS" if result_observation.get("status", None) == "PASS" else "FAIL"
        return {
            "cell_id": cell[0],
            "fmi_version": cell[2],
            "interface": cell[3],
            "integration_step_s": integration_step,
            "output_step_s": 0.001,
            "errseq_percent": errseq_percent,
            "alpha_rms": alpha_rms,
            "event_count": len(events),
            "load_flow_code": load_flow_code,
            "cominc_code": cominc_code,
            "comsim_code": comsim_code,
            "add_u_code": add_u_code,
            "add_x_code": add_x_code,
            "active_set": active_observation,
            "import": import_observation,
            "result": result_observation,
            "status": status,
        }
    finally:
        if result_loaded:
            pass
        else:
            pass
        event: PowerFactoryObject
        for event in events:
            assert_owned(event, owned_project)
            event.Delete()
        cleanup_target: PowerFactoryObject
        for cleanup_target in (instance, composite, slot, frame, model):
            assert_owned(cleanup_target, owned_project)
            cleanup_target.Delete()


def write_execution_receipt(
    output_dir: Path,
    observations: dict[str, object],
    artifact_paths: tuple[Path, ...],
) -> dict[str, object]:
    """Write the execution receipt only after all referenced evidence exists.

    :param output_dir: External execution directory.
    :param observations: Complete execution observation payload.
    :param artifact_paths: Existing evidence files to authenticate.
    :return: Reopened execution receipt.
    """

    observations_path: Path = output_dir / "observations.json"
    observations_path.write_text(
        json.dumps(observations, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    artifacts: list[dict[str, object]] = list()
    artifact_path: Path
    for artifact_path in artifact_paths + (observations_path,):
        artifact_bytes: bytes = artifact_path.resolve(strict=True).read_bytes()
        artifacts.append(
            {
                "name": artifact_path.relative_to(output_dir).as_posix(),
                "size_bytes": len(artifact_bytes),
                "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
            }
        )
    cells_value: object = observations.get("cells", None)
    if isinstance(cells_value, list):
        cells: list[object] = cells_value
    else:
        cells = list()
    complete: bool = bool(
        observations.get("error", None) is None
        and isinstance(observations.get("cleanup", None), dict)
        and cast(dict[str, object], observations["cleanup"]).get("status", None) == "PASS"
        and len(cells) == 8
        and all(isinstance(item, dict) and item.get("status", None) == "PASS" for item in cells)
    )
    receipt: dict[str, object] = {
        "schema_version": "1.0",
        "status": "EXECUTION_EVIDENCE_COMPLETE" if complete else "COMPLETED_WITH_FINDINGS",
        "numerical_verdict": "PENDING_INDEPENDENT_VALIDATION",
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    receipt_path: Path = output_dir / "execution-receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    reopened_value: object = json.loads(receipt_path.read_text(encoding="utf-8"))
    if isinstance(reopened_value, dict) and reopened_value == receipt:
        return cast(dict[str, object], reopened_value)
    else:
        raise RuntimeError("PowerFactory execution receipt reopen mismatch")


def verify_active_cell(
    application: PowerFactoryApplication,
    owned_project: PowerFactoryObject,
    expected_instance: PowerFactoryObject,
) -> dict[str, object]:
    """Require exactly one calculation-relevant FMU instance.

    :param application: Owned PowerFactory application reference.
    :param owned_project: Exact temporary project root.
    :param expected_instance: Sole expected active FMU model.
    :return: Active-set identities and PASS or finding status.
    """

    active_models: list[PowerFactoryObject] = application.GetCalcRelevantObjects(
        "*.ElmMdl"
    )
    names: list[str] = [""] * len(active_models)
    index: int
    owned: bool = True
    for index in range(len(active_models)):
        names[index] = str(active_models[index].GetFullName())
        try:
            assert_owned(active_models[index], owned_project)
        except RuntimeError:
            owned = False
    expected_name: str = str(expected_instance.GetFullName())
    passed: bool = bool(owned and names == [expected_name])
    return {
        "status": "PASS" if passed else "UNKNOWN_ACTIVE_SET",
        "active_models": names,
        "expected": expected_name,
        "all_owned": owned,
    }


def cleanup_probe_project(
    application: PowerFactoryApplication,
    current_user: PowerFactoryObject,
    owned_project: PowerFactoryObject,
    project_name: str,
    prior_project: PowerFactoryObject | None,
    prior_study: PowerFactoryObject | None,
    journal_path: Path,
) -> dict[str, object]:
    """Delete only the verified owned root and restore captured context.

    :param application: Owned PowerFactory application reference.
    :param current_user: Authenticated bootstrap parent.
    :param owned_project: Exact temporary project root.
    :param project_name: Exact temporary name.
    :param prior_project: Captured prior project, when any.
    :param prior_study: Captured prior study case, when any.
    :param journal_path: Append-only external journal.
    :return: Cleanup and narrow restoration evidence.
    """

    assert_owned(owned_project, current_user)
    if str(owned_project.GetAttribute("loc_name")) == project_name:
        pass
    else:
        raise RuntimeError("Owned root name changed; deletion prohibited")
    delete_record: dict[str, object] = {
        "operation": "DELETE_OWNED_ROOT",
        "target": str(owned_project.GetFullName()),
        "bootstrap_parent": str(current_user.GetFullName()),
        "name": project_name,
    }
    with journal_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(delete_record, sort_keys=True) + "\n")
    # Vendor project deletion must not leave the owned project active.
    deactivate_result: int | None = owned_project.Deactivate()
    deactivate_code: int = 0 if deactivate_result is None else int(deactivate_result)
    if deactivate_code == 0:
        pass
    else:
        return {"status": "FAIL", "deactivate_code": deactivate_code,
                "deletion_prohibited": True, "project_name": project_name}
    delete_result: int | None = owned_project.Delete()
    delete_code: int = 0 if delete_result is None else int(delete_result)
    # Recursive enumeration also includes the recycle bin.  The contract asks
    # for absence only from the current user's live direct project children.
    refreshed_user: PowerFactoryObject | None = application.GetCurrentUser()
    if refreshed_user is not None:
        pass
    else:
        raise RuntimeError("PowerFactory current user is unavailable after cleanup")
    remaining_projects: list[PowerFactoryObject] = refreshed_user.GetContents(
        "*.IntPrj", 0
    )
    remaining_names: list[str] = [""] * len(remaining_projects)
    index: int
    for index in range(len(remaining_projects)):
        remaining_names[index] = str(
            remaining_projects[index].GetAttribute("loc_name")
        )
    absent: bool = project_name not in remaining_names

    restoration: dict[str, object] = {
        "prior_project": None,
        "prior_study": None,
        "project_code": None,
        "study_code": None,
    }
    if prior_project is not None:
        prior_name: str = str(prior_project.GetAttribute("loc_name"))
        restoration["prior_project"] = str(prior_project.GetFullName())
        restoration["project_code"] = int(application.ActivateProject(prior_name))
        if prior_study is not None:
            restoration["prior_study"] = str(prior_study.GetFullName())
            restoration["study_code"] = int(prior_study.Activate())
        else:
            pass
    else:
        pass
    return {
        "deactivate_code": deactivate_code,
        "delete_code": delete_code,
        "project_absent_after": absent,
        "remaining_project_count": len(remaining_names),
        "context_restoration": restoration,
        "status": "PASS" if delete_code == 0 and absent else "FAIL",
    }


def parse_arguments() -> argparse.Namespace:
    """Parse the standalone PowerFactory replay arguments.

    :return: Explicit runner arguments supplied on the command line.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Reproducible PowerFactory first-order FMI 2/3 matrix."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--powerfactory-root", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main(
    arguments: argparse.Namespace | None = None,
    run_nonce: str | None = None,
) -> int:
    """Run the sealed PowerFactory matrix and write its receipt last.

    :param arguments: Parsed arguments supplied by the parent supervisor, or
        ``None`` for standalone command-line parsing.
    :param run_nonce: Parent-origin 64-hex run nonce, or ``None`` for a
        standalone locally generated nonce.
    :return: Zero for complete execution evidence, non-zero for findings.
    """

    if arguments is None:
        effective_arguments: argparse.Namespace = parse_arguments()
    else:
        effective_arguments = arguments
    if run_nonce is None:
        effective_run_nonce: str = secrets.token_hex(32)
    elif re.fullmatch(r"[0-9a-f]{64}", run_nonce) is not None:
        effective_run_nonce = run_nonce
    else:
        raise ValueError("Run nonce must be exactly 64 lowercase hex characters")

    if sys.dont_write_bytecode:
        pass
    else:
        raise ValueError("Run this probe with python -B")
    output_dir: Path = effective_arguments.output_dir.resolve(strict=False)
    if output_dir.exists():
        raise FileExistsError("Probe output directory already exists")
    else:
        output_dir.mkdir(parents=True, exist_ok=False)
    journal_path: Path = output_dir / "mutation-journal.jsonl"
    journal_path.write_text("", encoding="utf-8")
    observations_path: Path = output_dir / "observations.json"
    worker_pid: int = os.getpid()
    selected: tuple[tuple[str, Path, str, str], ...] = verify_runtime_inputs(
        effective_arguments.manifest,
        effective_arguments.binding,
        output_dir,
    )

    xml_by_cell: dict[str, object] = dict()
    cell: tuple[str, Path, str, str]
    for cell in selected:
        with zipfile.ZipFile(cell[1], "r") as archive:
            xml_bytes: bytes = archive.read("modelDescription.xml")
        root: ElementTree.Element = ElementTree.fromstring(xml_bytes)
        namespace_prefix: str = ""
        input_start: float | None = None
        input_scalar_real: bool = False
        output_scalar_real: bool = False
        if cell[2] == "2.0":
            scalar: ElementTree.Element
            for scalar in root.findall(namespace_prefix + ".//ScalarVariable"):
                name: str = str(scalar.attrib.get("name", ""))
                causality: str = str(scalar.attrib.get("causality", ""))
                real_child: ElementTree.Element | None = scalar.find("Real")
                if name == "u" and causality == "input" and real_child is not None:
                    input_scalar_real = True
                    start_text: str | None = real_child.attrib.get("start", None)
                    if start_text is not None:
                        input_start = float(start_text)
                    else:
                        pass
                elif name == "x" and causality == "output" and real_child is not None:
                    output_scalar_real = True
                else:
                    pass
        elif cell[2] == "3.0":
            float_variable: ElementTree.Element
            for float_variable in root.findall(namespace_prefix + ".//Float64"):
                name = str(float_variable.attrib.get("name", ""))
                causality = str(float_variable.attrib.get("causality", ""))
                if name == "u" and causality == "input":
                    input_scalar_real = True
                    start_text = float_variable.attrib.get("start", None)
                    if start_text is not None:
                        input_start = float(start_text)
                    else:
                        pass
                elif name == "x" and causality == "output":
                    output_scalar_real = True
                else:
                    pass
        else:
            raise ValueError("Selected cell has unsupported FMI version")
        xml_by_cell[cell[0]] = {
            "fmi_version": str(root.attrib.get("fmiVersion", "")),
            "input_u_scalar_real": input_scalar_real,
            "input_u_start": input_start,
            "output_x_scalar_real": output_scalar_real,
            "xml_sha256": hashlib.sha256(xml_bytes).hexdigest(),
        }

    before_inventory: dict[str, object] = inspect_process_inventory(worker_pid)
    before_path: Path = output_dir / "process-before.json"
    before_path.write_text(
        json.dumps(before_inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    after_path: Path = output_dir / "process-after-acquire.json"
    cleanup_receipt_path: Path = output_dir / "cleanup-receipt.json"
    checkpoint_path: Path = output_dir / "release-checkpoint.json"

    application: PowerFactoryApplication | None = None
    current_user: PowerFactoryObject | None = None
    owned_project: PowerFactoryObject | None = None
    prior_project: PowerFactoryObject | None = None
    prior_study: PowerFactoryObject | None = None
    cleanup: dict[str, object] = {"status": "NOT_STARTED"}
    engine_after_acquire: dict[str, object] = dict()
    engine_after_release: dict[str, object] = dict()
    cell_observations: list[object] = list()
    scaffold_observation: dict[str, object] = dict()
    project_name: str = "VG_FirstOrder_Matrix_" + effective_run_nonce[:12]
    error: str | None = None

    with ExitStack() as resources:
        module: PowerFactoryModule = load_powerfactory(
            effective_arguments.binding, effective_arguments.powerfactory_root, resources
        )
        try:
            # Refuse an existing native session before acquiring the engine.
            before_rows_value: object = before_inventory["rows"]
            before_rows: list[object] = (
                before_rows_value if isinstance(before_rows_value, list)
                else list((before_rows_value,))
            )
            before_row: object
            for before_row in before_rows:
                if isinstance(before_row, dict):
                    if "PowerFactory" in str(before_row.get("Name", "")):
                        raise RuntimeError("Existing native session; acquisition prohibited")
                    else:
                        pass
                else:
                    raise RuntimeError("Process inventory identity is ambiguous")
            application = module.GetApplicationExt()
            engine_after_acquire = inspect_process_inventory(worker_pid)
            after_path.write_text(
                json.dumps(engine_after_acquire, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            acquired_rows_value: object = engine_after_acquire["rows"]
            acquired_rows: list[object] = (
                acquired_rows_value if isinstance(acquired_rows_value, list)
                else list((acquired_rows_value,))
            )
            acquired_row: object
            for acquired_row in acquired_rows:
                if isinstance(acquired_row, dict):
                    if "PowerFactory" in str(acquired_row.get("Name", "")):
                        if int(acquired_row.get("ParentProcessId", -1)) == worker_pid:
                            pass
                        else:
                            raise RuntimeError("Native ancestry is ambiguous; project operations prohibited")
                    else:
                        pass
                else:
                    raise RuntimeError("Acquired inventory identity is ambiguous")
            current_user, owned_project, prior_project, prior_study = (
                bootstrap_probe_project(
                    application,
                    project_name,
                    "FirstOrderMatrixGrid",
                    journal_path,
                )
            )
            network_folder: PowerFactoryObject | None = (
                application.GetProjectFolder("netdat", 1)
            )
            if network_folder is not None:
                assert_owned(network_folder, owned_project)
            else:
                raise RuntimeError("Owned network folder is unavailable")
            grids: list[PowerFactoryObject] = network_folder.GetContents(
                "*.ElmNet", 1
            )
            grid: PowerFactoryObject | None = None
            grid_candidate: PowerFactoryObject
            for grid_candidate in grids:
                if (
                    str(grid_candidate.GetAttribute("loc_name"))
                    == "FirstOrderMatrixGrid"
                ):
                    grid = grid_candidate
                else:
                    pass
            if grid is not None:
                assert_owned(grid, owned_project)
            else:
                raise RuntimeError("Owned initial grid is unavailable")

            bus: PowerFactoryObject = create_owned_object(
                grid,
                "ElmTerm",
                "FirstOrder_110kV_Bus",
                owned_project,
                journal_path,
            )
            set_owned_attribute(bus, "uknom", 110.0, owned_project, journal_path)
            cubicle: PowerFactoryObject = create_owned_object(
                bus, "StaCubic", "ExternalGrid", owned_project, journal_path
            )
            source: PowerFactoryObject = create_owned_object(
                grid,
                "ElmXnet",
                "FirstOrder_External_Grid",
                owned_project,
                journal_path,
            )
            set_owned_attribute(
                source, "bus1", cubicle, owned_project, journal_path
            )
            set_owned_attribute(
                source, "usetp", 1.0, owned_project, journal_path
            )
            scaffold_observation: dict[str, object] = {
                "bus": inspect_attributes(
                    bus, ("uknom", "outserv", "iUsage", "cpSubstat")
                ),
                "cubicle": inspect_attributes(cubicle, ("obj_id", "cterm")),
                "source": inspect_attributes(
                    source, ("bus1", "usetp", "outserv", "bustp")
                ),
                "fmu_electrical_connections": [],
                "normalised_fmu_uncoupled": True,
            }

            for cell in selected:
                if cell[3] == "me":
                    integration_steps: tuple[float, ...] = (
                        0.000125,
                        0.0000625,
                        0.00003125,
                    )
                else:
                    integration_steps = (0.001,)
                integration_step: float
                for integration_step in integration_steps:
                    cell_observations.append(
                        run_dynamic_cell(
                            application,
                            owned_project,
                            grid,
                            cell,
                            integration_step,
                            output_dir,
                            journal_path,
                        )
                    )
        except Exception as exception:
            error = f"{exception.__class__.__name__}: {exception}"
        finally:
            # Clean partial imports only when bootstrap identity was verified.
            if application is not None:
                if current_user is not None and owned_project is not None:
                    try:
                        cleanup = cleanup_probe_project(
                            application, current_user, owned_project,
                            project_name, prior_project, prior_study, journal_path,
                        )
                    except Exception as cleanup_exception:
                        cleanup = {
                            "status": "FAIL",
                            "error": f"{cleanup_exception.__class__.__name__}: {cleanup_exception}",
                            "project_name": project_name,
                            "deletion_not_retried": True,
                        }
                else:
                    cleanup = {"status": "NO_VERIFIED_ROOT", "deletion_prohibited": True}
                try:
                    application.FlushOutputWindow()
                except Exception as flush_exception:
                    cleanup["flush_error"] = f"{flush_exception.__class__.__name__}: {flush_exception}"
            else:
                cleanup = {"status": "NOT_ACQUIRED"}
            cleanup_receipt: dict[str, object] = {
                "schema_version": "1.0",
                "cleanup": cleanup,
                "status": (
                    "PASS" if cleanup.get("status", None) == "PASS" else "FAIL"
                ),
            }
            cleanup_receipt_path.write_text(
                json.dumps(cleanup_receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            # Preserve every result required for parent-side finalization before
            # releasing the vendor application, because the native release may
            # terminate the embedded Python interpreter without returning.
            observations: dict[str, object] = {
                "schema_version": "1.0",
                "claim": "PowerFactory execution evidence; numerical verdict pending independent validation",
                "run_nonce": effective_run_nonce,
                "project_name": project_name,
                "selected_cells": [item[0] for item in selected],
                "fmi1_imported": False,
                "fixture": {
                    "equation": "tau*dx/dt=u-x",
                    "tau_s": 0.1,
                    "initial_x": 0.0,
                    "stop_s": 1.2,
                    "output_step_s": 0.001,
                    "input_schedule": (
                        (0.0, 0.0),
                        (0.2, 1.0),
                        (0.5, -0.5),
                        (0.8, 0.25),
                    ),
                },
                "xml": xml_by_cell,
                "scaffold": scaffold_observation,
                "cells": cell_observations,
                "cleanup": cleanup,
                "error": error,
                "comsim_executed": len(cell_observations) == 8,
                "event_executed": len(cell_observations) == 8,
            }
            raw_names: tuple[str, ...] = (
                "fmi20_cs_h_0p001000000.csv",
                "fmi20_me_h_0p000125000.csv",
                "fmi20_me_h_0p000062500.csv",
                "fmi20_me_h_0p000031250.csv",
                "fmi30_cs_h_0p001000000.csv",
                "fmi30_me_h_0p000125000.csv",
                "fmi30_me_h_0p000062500.csv",
                "fmi30_me_h_0p000031250.csv",
            )
            pre_release_artifact_paths: tuple[Path, ...] = (
                before_path,
                after_path,
                cleanup_receipt_path,
                journal_path,
                output_dir / "compatibility-build-receipt.json",
                output_dir / "source-closure-manifest.txt",
                *((output_dir / "raw_traces" / name) for name in raw_names),
            )
            cells_complete: bool = bool(
                error is None
                and cleanup.get("status", None) == "PASS"
                and len(cell_observations) == 8
                and all(
                    isinstance(item, dict)
                    and item.get("status", None) == "PASS"
                    for item in cell_observations
                )
            )
            if cells_complete:
                artifact_records: list[dict[str, object]] = [dict()] * len(
                    pre_release_artifact_paths
                )
                artifact_index: int
                for artifact_index in range(len(pre_release_artifact_paths)):
                    artifact_path: Path = pre_release_artifact_paths[artifact_index]
                    artifact_bytes: bytes = artifact_path.resolve(strict=True).read_bytes()
                    artifact_records[artifact_index] = {
                        "name": artifact_path.relative_to(output_dir).as_posix(),
                        "size_bytes": len(artifact_bytes),
                        "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
                    }
                checkpoint: dict[str, object] = {
                    "schema_version": "1.0",
                    "record_kind": "powerfactory_pre_release_checkpoint",
                    "run_nonce": effective_run_nonce,
                    "worker_pid": worker_pid,
                    "observations": observations,
                    "artifacts": artifact_records,
                    "status": "READY_FOR_NATIVE_RELEASE",
                }
                checkpoint_temporary_path: Path = output_dir / (
                    "release-checkpoint.json.tmp-" + effective_run_nonce
                )
                checkpoint_temporary_path.write_text(
                    json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                os.replace(checkpoint_temporary_path, checkpoint_path)
            else:
                pass
            application = None
            try:
                engine_after_release = inspect_process_inventory(worker_pid)
            except Exception as inventory_exception:
                engine_after_release = {
                    "status": "FAIL",
                    "error": (
                        f"{inventory_exception.__class__.__name__}: "
                        f"{inventory_exception}"
                    ),
                }

    release_path: Path = output_dir / "process-after-release.json"
    release_path.write_text(
        json.dumps(engine_after_release, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    artifact_paths: tuple[Path, ...] = (
        *pre_release_artifact_paths,
        checkpoint_path,
        release_path,
    )
    receipt: dict[str, object] = write_execution_receipt(
        output_dir,
        observations,
        artifact_paths,
    )
    completed_cleanly: bool = bool(
        receipt.get("status", None) == "EXECUTION_EVIDENCE_COMPLETE"
        and error is None
        and cleanup.get("status", None) == "PASS"
        and len(cell_observations) == 8
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0 if completed_cleanly else 2


if __name__ == "__main__":
    raise SystemExit(main())
