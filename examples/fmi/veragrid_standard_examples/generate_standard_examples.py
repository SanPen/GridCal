# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Build and validate the public GENSAL, TGOV1, and ESDC2A FMU catalog."""

from __future__ import annotations
from VeraGridEngine.enumerations import InterfaceType

import argparse
import csv
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

import fmpy
from fmpy import read_model_description, simulate_fmu
import numpy as np

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import FmiVersion
from VeraGridEngine.IO.fmu.compiler import Compiler
from VeraGridEngine.IO.fmu.config import TargetPlatform
from VeraGridEngine.IO.fmu.interface import export_model_as_fmu
from VeraGridEngine.IO.fmu.config import ExportConfig as CsExportConfig
from VeraGridEngine.IO.fmu.config import detect_target_platform as detect_cs_target_platform
from VeraGridEngine.IO.fmu.config import ExportConfig as MeExportConfig
from VeraGridEngine.IO.fmu.config import detect_target_platform as detect_me_target_platform
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.esdc2a import build_esdc2a_template
from VeraGridEngine.Templates.Rms.international_standards.governors.tgov1 import build_tgov1_template
from VeraGridEngine.Templates.Rms.international_standards.synchronous_machines.gensal import build_gensal_template


class ExampleFamily(Enum):
    """Distinct physical model families published by this recipe."""

    GENSAL = "GENSAL"
    TGOV1 = "TGOV1"
    ESDC2A = "ESDC2A"


class ExampleDefinition:
    """Immutable numerical description of one standard-model experiment."""

    __slots__ = ("family", "stop_time", "input_names", "output_names", "input_rows")

    def __init__(
        self: "ExampleDefinition",
        family: ExampleFamily,
        stop_time: float,
        input_names: tuple[str, ...],
        output_names: tuple[str, ...],
        input_rows: tuple[tuple[float, ...], ...],
    ) -> None:
        """Store one fully explicit input/output experiment.

        :param family: Physical model family.
        :param stop_time: Experiment stop time in seconds.
        :param input_names: Ordered FMU input variable names.
        :param output_names: Ordered FMU output variable names.
        :param input_rows: Right-continuous input samples with time first.
        :return: None.
        """
        self.family: ExampleFamily = family
        self.stop_time: float = stop_time
        self.input_names: tuple[str, ...] = input_names
        self.output_names: tuple[str, ...] = output_names
        self.input_rows: tuple[tuple[float, ...], ...] = input_rows


class ExampleCellResult:
    """Validated identity and trace for one FMI version/interface cell."""

    __slots__ = (
        "family", "version", "interface", "model_name", "model_identifier",
        "fmu_path", "trace", "fmu_sha256", "status", "metrics",
    )

    def __init__(
        self: "ExampleCellResult",
        family: ExampleFamily,
        version: FmiVersion,
        interface: str,
        model_name: str,
        model_identifier: str,
        fmu_path: Path,
        trace: np.ndarray,
        fmu_sha256: str,
        status: str,
        metrics: dict[str, float],
    ) -> None:
        """Store one completed cell without changing its collection sizes later.

        :param family: Physical model family.
        :param version: FMI standard version.
        :param interface: ``cs`` or ``me``.
        :param model_name: Published model name.
        :param model_identifier: Native FMI model identifier.
        :param fmu_path: Candidate FMU path outside the checkout.
        :param trace: Common-grid time and output array.
        :param fmu_sha256: FMU content hash after notice injection.
        :param status: Local validation status.
        :param metrics: Named numerical evidence.
        :return: None.
        """
        self.family: ExampleFamily = family
        self.version: FmiVersion = version
        self.interface: str = interface
        self.model_name: str = model_name
        self.model_identifier: str = model_identifier
        self.fmu_path: Path = fmu_path
        self.trace: np.ndarray = trace
        self.fmu_sha256: str = fmu_sha256
        self.status: str = status
        self.metrics: dict[str, float] = metrics


def build_example_definition(family: ExampleFamily) -> ExampleDefinition:
    """Return the sealed event profile for one physical family.

    :param family: Model family whose experiment is requested.
    :return: Exact inputs, outputs, stop time, and event samples.
    """
    if family is ExampleFamily.GENSAL:
        return ExampleDefinition(
            family=family,
            stop_time=2.0,
            input_names=("IdPu_GENSAL", "IqPu_GENSAL", "EfdPu_GENSAL", "PmPu_GENSAL"),
            output_names=("UdPu_GENSAL", "UqPu_GENSAL", "PePu_GENSAL", "OmegaPu_GENSAL"),
            input_rows=(
                (0.0, 0.0, 0.0, 1.0, 0.0),
                (0.2, 0.0, 0.0, 1.0, 0.0), (0.2, 0.0, 0.2, 1.0, 0.0),
                (0.5, 0.0, 0.2, 1.0, 0.0), (0.5, 0.0, 0.2, 1.0, 0.2),
                (0.8, 0.0, 0.2, 1.0, 0.2), (0.8, 0.0, 0.2, 1.05, 0.2),
                (1.2, 0.0, 0.2, 1.05, 0.2), (1.2, 0.0, 0.0, 1.0, 0.0),
                (2.0, 0.0, 0.0, 1.0, 0.0),
            ),
        )
    elif family is ExampleFamily.TGOV1:
        return ExampleDefinition(
            family=family,
            stop_time=2.0,
            input_names=("OmegaPu_TGOV1", "PRefPu_TGOV1"),
            output_names=("PmPu_TGOV1", "ValvePu_TGOV1"),
            input_rows=(
                (0.0, 1.0, 0.5),
                (0.2, 1.0, 0.5), (0.2, 1.01, 0.5),
                (0.8, 1.01, 0.5), (0.8, 0.99, 0.5),
                (1.4, 0.99, 0.5), (1.4, 1.0, 0.5),
                (2.0, 1.0, 0.5),
            ),
        )
    else:
        return ExampleDefinition(
            family=family,
            stop_time=1.5,
            input_names=("UPssPu_ESDC2A", "UUelPu_ESDC2A", "UsPu_ESDC2A", "UsRefPu_ESDC2A"),
            output_names=("EfdPu_ESDC2A",),
            input_rows=(
                (0.0, 0.0, 0.0, 1.0, 1.0125),
                (0.2, 0.0, 0.0, 1.0, 1.0125), (0.2, 0.0, 0.0, 0.95, 1.0125),
                (0.5, 0.0, 0.0, 0.95, 1.0125), (0.5, 0.0, 0.0, 1.0, 1.0125),
                (0.8, 0.0, 0.0, 1.0, 1.0125), (0.8, 0.02, 0.0, 1.0, 1.0125),
                (1.1, 0.02, 0.0, 1.0, 1.0125), (1.1, 0.0, 0.0, 1.0, 1.0125),
                (1.5, 0.0, 0.0, 1.0, 1.0125),
            ),
        )


def build_example_model(family: ExampleFamily) -> RmsModelTemplate:
    """Build a fresh existing VeraGrid standard model.

    :param family: Model family to construct.
    :return: Newly allocated model template with catalog defaults unchanged.
    """
    variable_factory: VarFactory = VarFactory()
    if family is ExampleFamily.GENSAL:
        return build_gensal_template(vf=variable_factory, name="GENSAL")
    elif family is ExampleFamily.TGOV1:
        return build_tgov1_template(vf=variable_factory, name="TGOV1")
    else:
        return build_esdc2a_template(vf=variable_factory, name="ESDC2A")


def build_input_table(definition: ExampleDefinition) -> np.ndarray:
    """Build the structured FMPy input table from sealed rows.

    :param definition: Physical experiment definition.
    :return: Structured NumPy array with ``time`` followed by FMU inputs.
    """
    dtype_fields: list[tuple[str, type[np.float64]]] = [("time", np.float64)]
    input_name: str
    for input_name in definition.input_names:
        dtype_fields.append((input_name, np.float64))
    input_dtype: np.dtype = np.dtype(dtype_fields)
    # NumPy treats an outer tuple as one structured scalar in this context;
    # materialize only the record container so each inner tuple remains one row.
    return np.array(list(definition.input_rows), dtype=input_dtype)


def embed_redistribution_notices(fmu_path: Path, license_path: Path, source_text: str) -> None:
    """Embed MPL-2.0 and corresponding-source notices in one FMU.

    :param fmu_path: FMU archive to replace in place.
    :param license_path: Repository MPL-2.0 license.
    :param source_text: Version-bound instructions for obtaining source.
    :return: None.
    """
    temporary_path: Path = fmu_path.with_suffix(".noticed.zip")
    with zipfile.ZipFile(fmu_path, "r") as source_archive:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED) as target_archive:
            member_name: str
            for member_name in sorted(source_archive.namelist()):
                target_archive.writestr(member_name, source_archive.read(member_name))
            target_archive.writestr("documentation/LICENSE.md", license_path.read_bytes())
            target_archive.writestr("documentation/SOURCE.md", source_text.encode("utf-8"))
    temporary_path.replace(fmu_path)


def write_input_csv(path: Path, definition: ExampleDefinition) -> None:
    """Write the exact right-continuous input trajectory.

    :param path: Destination CSV path.
    :param definition: Experiment definition.
    :return: None.
    """
    with path.open("w", encoding="utf-8", newline="") as stream:
        # The FMI tools-list compatibility format requires every variable name
        # in the header to be quoted while numeric samples remain unquoted.
        header_names: tuple[str, ...] = ("time",) + definition.input_names
        quoted_header: str = ",".join(f'"{header_name}"' for header_name in header_names)
        stream.write(quoted_header + "\n")
        writer: csv.writer = csv.writer(stream, lineterminator="\n")
        writer.writerows(definition.input_rows)


def write_reference_csv(path: Path, output_names: tuple[str, ...], trace: np.ndarray) -> None:
    """Write one common-grid local reference trace.

    :param path: Destination reference CSV.
    :param output_names: Ordered output columns.
    :param trace: Time in column zero and outputs in remaining columns.
    :return: None.
    """
    # Keep reference values byte-stable while emitting the quoted header
    # required for FMI tools-list compatibility information.
    header_names: tuple[str, ...] = ("time",) + output_names
    header: str = ",".join(f'"{header_name}"' for header_name in header_names)
    np.savetxt(path, trace, delimiter=",", header=header, comments="", fmt="%.17g")


def write_reference_options(path: Path, stop_time: float) -> None:
    """Write archived Cross-Check-shaped numerical comparison options.

    :param path: Destination options file.
    :param stop_time: Experiment stop time in seconds.
    :return: None.
    """
    options_text: str = (
        f"StartTime,0.0\nStopTime,{stop_time:.17g}\nStepSize,0.001\n"
        "RelTol,0.005\nAbsTol,0.005\nSolverType,FixedStep\nOutputIntervalLength,0.01\n"
    )
    path.write_text(options_text, encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of one regular file.

    :param path: File to hash.
    :return: Lowercase hexadecimal SHA-256 digest.
    """
    digest: hashlib._Hash = hashlib.sha256()
    with path.open("rb") as stream:
        chunk: bytes = stream.read(1024 * 1024)
        while chunk != b"":
            digest.update(chunk)
            chunk = stream.read(1024 * 1024)
    return digest.hexdigest()


def resolve_publication_layout(
    repository_root: Path,
    publication_root: Path,
    cs_target_platform: TargetPlatform,
    me_target_platform: TargetPlatform,
) -> tuple[TargetPlatform, Path]:
    """Validate one host-native publication destination before compilation.

    :param repository_root: Exact VeraGrid checkout root.
    :param publication_root: Requested catalog destination.
    :param cs_target_platform: Platform selected by the CS exporter owner.
    :param me_target_platform: Platform selected by the ME exporter owner.
    :return: Shared host platform and adjacent atomic staging path.
    """
    # Both exporter owners must describe the same host before a catalog can
    # claim one platform identity across all eighteen cells.
    if cs_target_platform is me_target_platform:
        target_platform: TargetPlatform = cs_target_platform
    else:
        raise RuntimeError("CS and ME exporters selected different host platforms")

    platform_key: str = target_platform.value
    expected_publication: Path = (
        repository_root / "examples" / "fmi" / "veragrid_standard_examples"
        / "published" / platform_key
    ).resolve(strict=False)
    stage_root: Path = expected_publication.parent / ("." + platform_key + "-stage")
    if publication_root == expected_publication:
        pass
    else:
        raise ValueError(
            "Publication root must be the contracted published/" + platform_key + " path"
        )
    if not publication_root.exists():
        pass
    else:
        raise FileExistsError("Publication root already exists")
    if not stage_root.exists():
        pass
    else:
        raise FileExistsError("Publication stage already exists")
    return target_platform, stage_root


def build_and_validate_cell(
    definition: ExampleDefinition,
    version: FmiVersion,
    interface: str,
    target_platform: TargetPlatform,
    candidate_root: Path,
    build_root: Path,
    license_path: Path,
    source_text: str,
    compiler: Compiler,
) -> ExampleCellResult:
    """Export, license, execute, and verify one FMI cell.

    :param definition: Sealed family experiment.
    :param version: FMI export version.
    :param interface: ``cs`` or ``me``.
    :param target_platform: Shared host-native platform for the complete catalog.
    :param candidate_root: External candidate catalog root.
    :param build_root: External compiler workspace.
    :param license_path: Repository MPL license.
    :param source_text: Corresponding-source notice.
    :param compiler: Shared sequential compiler session.
    :return: Completed cell result; failures raise and prevent publication.
    """
    version_token: str = version.value.replace(".", "")
    cell_id: str = f"fmi{version_token}_{interface}"
    model_name: str = f"VG{definition.family.value}_{cell_id.upper()}"
    cell_dir: Path = candidate_root / definition.family.value / cell_id
    cell_dir.mkdir(parents=True, exist_ok=False)
    fmu_path: Path = cell_dir / f"{model_name}.fmu"
    model: RmsModelTemplate = build_example_model(definition.family)

    # The existing exporter remains the only owner of FMI C generation.
    if interface == "cs":
        generated_path: Path = export_model_as_fmu(
            model.block,
            CsExportConfig(
                model_name=model_name, output_path=fmu_path,
                target_platform=target_platform, compile_binary=True,
                fixed_step=0.001, keep_build_dir=True,
                build_dir=build_root / cell_id / "build",
                staging_dir=build_root / cell_id / "staging",
                fmi_version=version,
            ),
            compiler,
        )
        fmi_type: str = "CoSimulation"
    elif interface == "me":
        generated_path = export_model_as_fmu(
            model.block,
            MeExportConfig(interface_type=InterfaceType.MODEL_EXCHANGE, 
                model_name=model_name, output_path=fmu_path,
                target_platform=target_platform, compile_binary=True,
                fixed_step=0.001, keep_build_dir=True,
                build_dir=build_root / cell_id / "build",
                staging_dir=build_root / cell_id / "staging",
                fmi_version=version,
            ),
            compiler,
        )
        fmi_type = "ModelExchange"
    else:
        raise ValueError(f"Unsupported interface {interface!r}")

    embed_redistribution_notices(generated_path, license_path, source_text)
    model_description: object = read_model_description(str(generated_path), validate=True)
    declared_interface: object
    if interface == "cs":
        declared_interface = model_description.coSimulation
    else:
        declared_interface = model_description.modelExchange
    if declared_interface is None:
        raise RuntimeError("Requested FMI interface is absent")
    else:
        pass

    declared_inputs: tuple[str, ...] = tuple(
        variable.name for variable in model_description.modelVariables if variable.causality == "input"
    )
    declared_outputs: tuple[str, ...] = tuple(
        variable.name for variable in model_description.modelVariables if variable.causality == "output"
    )
    # FMI variable order belongs to the exporter symbol table; the experiment
    # binds values by name, so require exact membership without inventing an
    # ordering contract that the public FMI API does not provide.
    if (
        len(declared_inputs) == len(definition.input_names)
        and len(declared_outputs) == len(definition.output_names)
        and set(declared_inputs) == set(definition.input_names)
        and set(declared_outputs) == set(definition.output_names)
    ):
        pass
    else:
        raise RuntimeError(f"FMI variables differ: inputs={declared_inputs}, outputs={declared_outputs}")

    # Normalize every runtime to the public 0.01 s grid while integrating at 0.001 s.
    raw_result: np.ndarray = simulate_fmu(
        filename=str(generated_path), validate=True, start_time=0.0,
        stop_time=definition.stop_time, solver="Euler", step_size=0.001,
        output_interval=0.001, record_events=True, fmi_type=fmi_type,
        input=build_input_table(definition), output=list(definition.output_names),
    )
    target_count: int = int(round(definition.stop_time / 0.01)) + 1
    target_time: np.ndarray = np.linspace(0.0, definition.stop_time, target_count, dtype=np.float64)
    trace: np.ndarray = np.empty((target_count, len(definition.output_names) + 1), dtype=np.float64)
    trace[:, 0] = target_time
    output_index: int
    for output_index in range(len(definition.output_names)):
        output_name: str = definition.output_names[output_index]
        trace[:, output_index + 1] = np.interp(target_time, raw_result["time"], raw_result[output_name])
    if bool(np.all(np.isfinite(trace))):
        pass
    else:
        raise RuntimeError("FMU output contains non-finite values")

    response_range: float = float(np.max(np.ptp(trace[:, 1:], axis=0)))
    metrics: dict[str, float] = dict()
    metrics["maximum_output_range"] = response_range
    if response_range > 1.0e-8:
        pass
    else:
        raise RuntimeError("Physical event profile produced no dynamic output")
    if definition.family is ExampleFamily.GENSAL:
        pe_index: int = definition.output_names.index("PePu_GENSAL") + 1
        metrics["pe_range"] = float(np.ptp(trace[:, pe_index]))
        if metrics["pe_range"] > 1.0e-8:
            pass
        else:
            raise RuntimeError("GENSAL electrical power remained constant")
    elif definition.family is ExampleFamily.ESDC2A:
        metrics["efd_initial_error"] = abs(float(trace[0, 1]) - 1.0)
        if metrics["efd_initial_error"] <= 1.0e-4:
            pass
        else:
            raise RuntimeError("ESDC2A did not initialize at Efd=1.0 pu")
    else:
        pass

    write_input_csv(cell_dir / f"{model_name}_in.csv", definition)
    write_reference_csv(cell_dir / f"{model_name}_ref.csv", definition.output_names, trace)
    write_reference_options(cell_dir / f"{model_name}_ref.opt", definition.stop_time)
    (cell_dir / "Readme.txt").write_text(
        f"{model_name}\n\n"
        f"VeraGrid {definition.family.value} standard electrical example exported as "
        f"FMI {version.value} {fmi_type} for {target_platform.value}.\n\n"
        "The input trajectory exercises physical events and the reference solution "
        "contains the expected VeraGrid/FMPy response. Compatibility results are "
        "vendor-provided evidence, not official certification by the Modelica "
        "Association or FMI Project.\n\n"
        "See the root README.md, LICENSE.md and SOURCE.md for validation, licensing "
        "and corresponding-source information.\n",
        encoding="utf-8", newline="\n",
    )
    return ExampleCellResult(
        family=definition.family, version=version, interface=interface,
        model_name=model_name, model_identifier=str(declared_interface.modelIdentifier),
        fmu_path=generated_path, trace=trace, fmu_sha256=sha256_file(generated_path),
        status="PASS", metrics=metrics,
    )


def compare_family_traces(results: tuple[ExampleCellResult, ...]) -> dict[str, float]:
    """Compare all six variants with interface-aware causal event gates.

    :param results: Six completed cells for one family.
    :return: Same-interface, cross-interface, boundary, and startup errors.
    """
    reference_cs: ExampleCellResult | None = None
    reference_me: ExampleCellResult | None = None
    result: ExampleCellResult
    for result in results:
        if result.version is FmiVersion.FMI_2_0 and result.interface == "cs":
            reference_cs = result
        elif result.version is FmiVersion.FMI_2_0 and result.interface == "me":
            reference_me = result
        else:
            pass
    if reference_cs is not None and reference_me is not None:
        pass
    else:
        raise RuntimeError("FMI 2 CS or ME family reference is missing")

    definition: ExampleDefinition = build_example_definition(results[0].family)
    event_times: tuple[float, ...] = tuple(
        definition.input_rows[row_index][0]
        for row_index in range(1, len(definition.input_rows))
        if definition.input_rows[row_index][0] == definition.input_rows[row_index - 1][0]
        and definition.input_rows[row_index][0] > 0.0
    )
    metrics: dict[str, float] = dict()
    maximum_same_absolute: float = 0.0
    maximum_same_normalized: float = 0.0
    maximum_cross_absolute: float = 0.0
    maximum_cross_normalized: float = 0.0
    maximum_boundary_absolute: float = 0.0
    maximum_boundary_normalized: float = 0.0

    for result in results:
        if result.interface == "cs":
            same_reference: ExampleCellResult = reference_cs
        else:
            same_reference = reference_me
        cell_token: str = f"fmi{result.version.value.replace('.', '')}_{result.interface}"
        output_index: int
        for output_index in range(len(definition.output_names)):
            output_name: str = definition.output_names[output_index]
            column_index: int = output_index + 1
            same_normalization: float = max(
                1.0, float(np.ptp(same_reference.trace[:, column_index]))
            )
            same_difference: np.ndarray = np.abs(
                result.trace[:, column_index] - same_reference.trace[:, column_index]
            )
            same_absolute: float = float(np.max(same_difference))
            same_normalized: float = same_absolute / same_normalization
            metrics[f"{cell_token}_{output_name}_same_absolute"] = same_absolute
            metrics[f"{cell_token}_{output_name}_same_normalized"] = same_normalized
            maximum_same_absolute = max(maximum_same_absolute, same_absolute)
            maximum_same_normalized = max(maximum_same_normalized, same_normalized)

            if result.interface == "cs":
                cross_normalization: float = max(
                    1.0, float(np.ptp(reference_me.trace[:, column_index]))
                )
                cross_difference: np.ndarray = np.abs(
                    result.trace[:, column_index] - reference_me.trace[:, column_index]
                )
                non_boundary_mask: np.ndarray = np.logical_not(
                    np.isclose(result.trace[:, 0], 0.0, atol=1.0e-12, rtol=0.0)
                )
                event_time: float
                for event_time in event_times:
                    non_boundary_mask = np.logical_and(
                        non_boundary_mask,
                        np.logical_not(
                            np.isclose(result.trace[:, 0], event_time, atol=1.0e-12, rtol=0.0)
                        ),
                    )
                cross_absolute: float = float(np.max(cross_difference[non_boundary_mask]))
                cross_normalized: float = cross_absolute / cross_normalization
                metrics[f"{cell_token}_{output_name}_cross_non_boundary_absolute"] = cross_absolute
                metrics[f"{cell_token}_{output_name}_cross_non_boundary_normalized"] = cross_normalized
                metrics[f"{cell_token}_{output_name}_raw_t0_difference"] = float(cross_difference[0])
                maximum_cross_absolute = max(maximum_cross_absolute, cross_absolute)
                maximum_cross_normalized = max(maximum_cross_normalized, cross_normalized)

                for event_time in event_times:
                    boundary_indices: np.ndarray = np.flatnonzero(
                        np.isclose(result.trace[:, 0], event_time, atol=1.0e-12, rtol=0.0)
                    )
                    if boundary_indices.size == 1 and boundary_indices[0] > 0:
                        boundary_index: int = int(boundary_indices[0])
                    else:
                        raise RuntimeError(f"Missing unique public-grid event at {event_time}")
                    pre_absolute: float = abs(
                        float(result.trace[boundary_index, column_index])
                        - float(reference_me.trace[boundary_index - 1, column_index])
                    )
                    post_absolute: float = abs(
                        float(result.trace[boundary_index, column_index])
                        - float(reference_me.trace[boundary_index, column_index])
                    )
                    boundary_absolute: float = min(pre_absolute, post_absolute)
                    boundary_normalized: float = boundary_absolute / cross_normalization
                    event_token: str = f"{event_time:.6f}".rstrip("0").rstrip(".").replace(".", "p")
                    metrics[f"{cell_token}_{output_name}_event_{event_token}_pre_absolute"] = pre_absolute
                    metrics[f"{cell_token}_{output_name}_event_{event_token}_post_absolute"] = post_absolute
                    metrics[f"{cell_token}_{output_name}_event_{event_token}_envelope_absolute"] = boundary_absolute
                    metrics[f"{cell_token}_{output_name}_event_{event_token}_envelope_normalized"] = boundary_normalized
                    maximum_boundary_absolute = max(maximum_boundary_absolute, boundary_absolute)
                    maximum_boundary_normalized = max(maximum_boundary_normalized, boundary_normalized)
            else:
                pass

        if result.interface == "cs" and result.family is ExampleFamily.GENSAL:
            startup_indices: np.ndarray = np.flatnonzero(
                np.isclose(result.trace[:, 0], 0.01, atol=1.0e-12, rtol=0.0)
            )
            if startup_indices.size == 1:
                startup_index: int = int(startup_indices[0])
            else:
                raise RuntimeError("GENSAL startup sample at 0.01 s is missing")
            uq_index: int = definition.output_names.index("UqPu_GENSAL") + 1
            startup_error: float = abs(float(result.trace[startup_index, uq_index]) - 1.0)
            metrics[f"{cell_token}_UqPu_GENSAL_startup_absolute"] = startup_error
            if startup_error <= 5.0e-3:
                pass
            else:
                raise RuntimeError(f"GENSAL CS startup Uq error is {startup_error}")
        else:
            pass

    metrics["maximum_same_interface_absolute_error"] = maximum_same_absolute
    metrics["maximum_same_interface_normalized_error"] = maximum_same_normalized
    metrics["maximum_cross_non_boundary_absolute_error"] = maximum_cross_absolute
    metrics["maximum_cross_non_boundary_normalized_error"] = maximum_cross_normalized
    metrics["maximum_event_envelope_absolute_error"] = maximum_boundary_absolute
    metrics["maximum_event_envelope_normalized_error"] = maximum_boundary_normalized
    if (
        maximum_same_absolute <= 5.0e-3
        and maximum_same_normalized <= 5.0e-3
        and maximum_cross_absolute <= 5.0e-3
        and maximum_cross_normalized <= 5.0e-3
        and maximum_boundary_absolute <= 5.0e-3
        and maximum_boundary_normalized <= 5.0e-3
    ):
        pass
    else:
        raise RuntimeError(
            "Family variants diverged: "
            f"same=({maximum_same_absolute}, {maximum_same_normalized}), "
            f"cross=({maximum_cross_absolute}, {maximum_cross_normalized}), "
            f"event=({maximum_boundary_absolute}, {maximum_boundary_normalized})"
        )
    return metrics


def write_manifest(
    path: Path,
    source_commit: str,
    source_tree_sha256: str,
    recipe_sha256: str,
    platform_key: str,
    results: tuple[ExampleCellResult, ...],
    family_metrics: dict[str, dict[str, float]],
) -> None:
    """Write the complete local catalog identity and verdict manifest.

    :param path: Manifest destination.
    :param source_commit: Git source commit.
    :param source_tree_sha256: Authenticated source tree digest.
    :param recipe_sha256: Executed recipe content hash.
    :param platform_key: Existing ``TargetPlatform.value`` for this catalog.
    :param results: Eighteen validated cells.
    :param family_metrics: Pointwise cross-version comparisons.
    :return: None.
    """
    cells: list[dict[str, object]] = [dict()] * len(results)
    result_index: int
    for result_index in range(len(results)):
        result: ExampleCellResult = results[result_index]
        cells[result_index] = {
            "family": result.family.value,
            "fmi_version": result.version.value,
            "interface": result.interface,
            "model_name": result.model_name,
            "model_identifier": result.model_identifier,
            "fmu_path": result.fmu_path.relative_to(path.parent).as_posix(),
            "fmu_sha256": result.fmu_sha256,
            "status": result.status,
            "metrics": result.metrics,
        }
    manifest: dict[str, object] = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_origin": "https://github.com/SanPen/VeraGrid",
        "source_commit": source_commit,
        "source_tree_sha256": source_tree_sha256,
        "recipe_sha256": recipe_sha256,
        "platform": platform_key,
        "distribution_status": "PENDING_PUBLIC_URL_ACTIVATION_AFTER_INTEGRATION",
        "local_status": "PASS",
        "presentation_status": "FMI_TOOLS_GUIDE_CONFORMANT",
        "interoperability_evidence": "../../../INTEROPERABILITY_STATUS.md",
        "family_metrics": family_metrics,
        "cells": cells,
    }
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    """Generate, validate, and atomically install the complete local catalog.

    :return: None. Any failed cell prevents the publication root from appearing.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--git-executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--publication-root", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-source-tree-sha256", required=True)
    arguments: argparse.Namespace = parser.parse_args()

    repository_root: Path = arguments.repository_root.resolve(strict=True)
    work_dir: Path = arguments.work_dir.resolve(strict=False)
    publication_root: Path = arguments.publication_root.resolve(strict=False)
    cs_target_platform: TargetPlatform = detect_cs_target_platform()
    me_target_platform: TargetPlatform = detect_me_target_platform()
    target_platform: TargetPlatform
    stage_root: Path
    target_platform, stage_root = resolve_publication_layout(
        repository_root, publication_root, cs_target_platform, me_target_platform,
    )
    platform_key: str = target_platform.value
    if work_dir.is_relative_to(repository_root):
        raise ValueError("Work directory must be outside the repository")
    else:
        pass
    if not work_dir.exists():
        work_dir.mkdir(parents=True, exist_ok=False)
    elif len(list(work_dir.iterdir())) == 0:
        pass
    else:
        raise ValueError("External work directory must be absent or empty")

    # Bind execution to the sealed source identity without consulting mutable environment state.
    head_process: subprocess.CompletedProcess[str] = subprocess.run(
        [str(arguments.git_executable.resolve(strict=True)), "rev-parse", "HEAD"],
        cwd=repository_root, env=dict(), capture_output=True, text=True, check=False,
    )
    if head_process.returncode == 0 and head_process.stdout.strip() == arguments.expected_head:
        pass
    else:
        raise RuntimeError("Git HEAD differs from the sealed source commit")
    tree_process: subprocess.CompletedProcess[bytes] = subprocess.run(
        [str(arguments.git_executable.resolve(strict=True)), "ls-tree", "-r", "-z", "HEAD"],
        cwd=repository_root, env=dict(), capture_output=True, check=False,
    )
    observed_tree_sha256: str = hashlib.sha256(tree_process.stdout).hexdigest()
    if tree_process.returncode == 0 and observed_tree_sha256 == arguments.expected_source_tree_sha256:
        pass
    else:
        raise RuntimeError("Source-tree digest differs from the sealed contract")
    # A matching tree object does not expose untracked or staged files. Native
    # evidence therefore requires a detached and completely clean checkout.
    detached_process: subprocess.CompletedProcess[bytes] = subprocess.run(
        [str(arguments.git_executable.resolve(strict=True)), "symbolic-ref", "-q", "HEAD"],
        cwd=repository_root, env=dict(), capture_output=True, check=False,
    )
    if detached_process.returncode == 1 and detached_process.stdout == b"":
        pass
    else:
        raise RuntimeError("Native generation requires a detached Git checkout")
    status_process: subprocess.CompletedProcess[bytes] = subprocess.run(
        [
            str(arguments.git_executable.resolve(strict=True)), "status",
            "--porcelain=v1", "--untracked-files=all",
        ],
        cwd=repository_root, env=dict(), capture_output=True, check=False,
    )
    if status_process.returncode == 0 and status_process.stdout == b"":
        pass
    else:
        raise RuntimeError("Native generation requires a clean Git checkout")

    recipe_path: Path = Path(__file__).resolve(strict=True)
    license_path: Path = repository_root / "LICENSE.md"
    recipe_sha256: str = sha256_file(recipe_path)
    source_text: str = (
        "# Corresponding source\n\n"
        "This catalog contains vendor-provided FMU examples built from VeraGrid source under MPL-2.0.\n\n"
        "Origin: https://github.com/SanPen/VeraGrid\n"
        f"Source commit: {arguments.expected_head}\n"
        f"Recipe SHA-256: {recipe_sha256}\n"
        "Relevant source: src/VeraGridEngine/data/fmu and src/VeraGridEngine/Templates/Rms/international_standards.\n"
        "Recipe: examples/fmi/veragrid_standard_examples/generate_standard_examples.py\n\n"
        "Distribution status: PENDING_PUBLIC_URL_ACTIVATION_AFTER_INTEGRATION.\n"
    )
    candidate_root: Path = work_dir / "candidate"
    build_root: Path = work_dir / "build"
    candidate_root.mkdir(parents=True, exist_ok=False)
    build_root.mkdir(parents=True, exist_ok=False)
    versions: tuple[FmiVersion, ...] = (FmiVersion.FMI_1_0, FmiVersion.FMI_2_0, FmiVersion.FMI_3_0)
    interfaces: tuple[str, ...] = ("cs", "me")
    results_list: list[ExampleCellResult] = list()
    family_metrics: dict[str, dict[str, float]] = dict()
    compiler: Compiler = Compiler()
    try:
        family: ExampleFamily
        for family in ExampleFamily:
            definition: ExampleDefinition = build_example_definition(family)
            family_results: list[ExampleCellResult] = list()
            version: FmiVersion
            interface: str
            for version in versions:
                for interface in interfaces:
                    cell_result: ExampleCellResult = build_and_validate_cell(
                        definition, version, interface, target_platform, candidate_root, build_root,
                        license_path, source_text, compiler,
                    )
                    family_results.append(cell_result)
                    results_list.append(cell_result)
                    print(f"{family.value} FMI {version.value} {interface}: PASS", flush=True)
            family_metrics[family.value] = compare_family_traces(tuple(family_results))
    finally:
        pass

    results: tuple[ExampleCellResult, ...] = tuple(results_list)
    if len(results) == 18 and all(result.status == "PASS" for result in results):
        pass
    else:
        raise RuntimeError("The complete 18-cell publication gate did not pass")
    (candidate_root / "LICENSE.md").write_bytes(license_path.read_bytes())
    (candidate_root / "SOURCE.md").write_text(source_text, encoding="utf-8", newline="\n")
    (candidate_root / "README.md").write_text(
        "# VeraGrid standard electrical FMU examples\n\n"
        "Three physical families (GENSAL, TGOV1, ESDC2A), each exported as FMI 1/2/3 CS/ME for "
        f"{platform_key}. All 18 cells passed local FMPy preflight. "
        "Measured commercial-tool and VeraGrid-importer results are maintained in "
        "`../../../INTEROPERABILITY_STATUS.md`. The catalog becomes reachable from "
        "the FMI tools list after its stable public examplesURL is active.\n\n"
        f"These downloadable archives contain {platform_key} binaries. Native generation and "
        "execution are verified separately on Windows, Linux, and macOS; this catalog "
        "does not claim downloadable Linux or macOS binaries.\n\n"
        "Rebuild from a clean VeraGrid checkout with the generator at "
        "`examples/fmi/veragrid_standard_examples/generate_standard_examples.py`. "
        "Run it as a Python module with `--repository-root`, `--git-executable`, an empty `--work-dir` outside Git, "
        f"the exact `--publication-root` under `published/{platform_key}`, "
        "`--expected-head` from `git rev-parse HEAD`, "
        "and `--expected-source-tree-sha256` equal to SHA-256 of the binary `git ls-tree -r -z HEAD` output. "
        "The publication root must be absent. The generator checks all 18 executions and every staged file before publication.\n\n"
        "The `_in.csv` files retain right-continuous events; `_ref.csv` files retain raw 0.01 s output samples, "
        "including CS pre-first-step visibility at t=0. The manifest records same-interface all-sample errors, "
        "cross-interface non-boundary errors, both pre/post errors and causal-envelope gates at each event. "
        "CS t=0 is reported but is not claimed as initialized physical output. "
        "Each cell uses the FMI tools-list Readme.txt and CSV presentation rules. "
        "These are vendor-provided compatibility results, not official certification.\n",
        encoding="utf-8", newline="\n",
    )
    write_manifest(
        candidate_root / "manifest.json", arguments.expected_head,
        arguments.expected_source_tree_sha256, recipe_sha256, platform_key,
        results, family_metrics,
    )
    candidate_files: list[Path] = sorted(path for path in candidate_root.rglob("*") if path.is_file())
    checksum_lines: list[str] = [""] * len(candidate_files)
    file_index: int
    for file_index in range(len(candidate_files)):
        candidate_file: Path = candidate_files[file_index]
        checksum_lines[file_index] = f"{sha256_file(candidate_file)}  {candidate_file.relative_to(candidate_root).as_posix()}"
    (candidate_root / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8", newline="\n")

    # Install all-or-nothing: only a verified same-volume stage is renamed into visibility.
    stage_root.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(candidate_root, stage_root)
        staged_files: list[Path] = sorted(path for path in stage_root.rglob("*") if path.is_file())
        if len(staged_files) == len(candidate_files) + 1:
            pass
        else:
            raise RuntimeError("Staged catalog file count changed")
        candidate_file: Path
        for candidate_file in candidate_files:
            relative_file: Path = candidate_file.relative_to(candidate_root)
            staged_file: Path = stage_root / relative_file
            if staged_file.is_file() and sha256_file(staged_file) == sha256_file(candidate_file):
                pass
            else:
                raise RuntimeError(f"Staged file identity changed: {relative_file}")
        if sha256_file(stage_root / "SHA256SUMS") == sha256_file(candidate_root / "SHA256SUMS"):
            pass
        else:
            raise RuntimeError("Staged checksum ledger identity changed")
        stage_root.rename(publication_root)
    except BaseException:
        if stage_root.exists() and not publication_root.exists():
            shutil.rmtree(stage_root)
        else:
            pass
        raise
    print(f"Published 18/18 local cells at {publication_root}", flush=True)


if __name__ == "__main__":
    main()
