# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Compiled, schema, ABI, and loopback evidence for FMI 1 exports."""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as element_tree
import zipfile

import numpy as np
import pytest
from fmpy import simulate_fmu
from fmpy.validation import validate_fmu

from VeraGridEngine.enumerations import FmiVersion, InterfaceType
from VeraGridEngine.IO.fmu.compiler import fmu_compiler_available
from VeraGridEngine.IO.fmu.config import (
    binary_directory,
    detect_target_platform,
    library_suffix,
)
from VeraGridEngine.IO.fmu.interface import export_model_as_fmu
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.IO.fmu.config import ExportConfig as CsExportConfig
from VeraGridEngine.IO.fmu.config import ExportConfig as MeExportConfig


@pytest.mark.skipif(not fmu_compiler_available(), reason="No usable FMU compiler is configured")
@pytest.mark.parametrize("build_index", range(20))
def test_fmi_one_co_simulation_export_is_schema_valid_and_loopback_ready(
    tmp_path: Path, build_index: int,
) -> None:
    """Compile and execute twenty real multi-file FMI 1 FMUs in one test process.

    :param tmp_path: Isolated export and simulation directory from pytest.
    :param build_index: Repetition index that gives each FMU a distinct path.
    :return: None.
    """

    state: Var = Var("x")
    derivative: Var = Var("dx", base_var=state)
    source_block: Block = Block(
        state_vars=list((state,)),
        state_eqs=list((Const(1.0),)),
        diff_vars=list((derivative,)),
        init_values=dict(((state, Const(0.0)),)),
        out_vars=list((state,)),
        name="FmiOneCs",
    )
    model_identifier: str = "FmiOneCertifiedCs"
    archive_path: Path = export_model_as_fmu(
        source_block,
        CsExportConfig(
            model_name=model_identifier,
            output_path=tmp_path / (model_identifier + f"_{build_index}.fmu"),
            fixed_step=1.0e-3,
            fmi_version=FmiVersion.FMI_1_0,
            build_dir=tmp_path / "build",
        ),
    )

    # Keep the generated source tree to prove that each export exercises the
    # five C units and seven headers involved in the original native crash.
    source_root: Path = tmp_path / "build" / "source"
    expected_c_names: tuple[str, ...] = (
        "src/generated_model.c",
        "src/generated_procedural.c",
        "src/model_instance.c",
        "src/runtime_fmi1.c",
        "src/solver.c",
    )
    expected_h_names: tuple[str, ...] = (
        "include/fmiFunctions.h",
        "include/fmiPlatformTypes.h",
        "src/generated_metadata.h",
        "src/generated_model.h",
        "src/model_instance.h",
        "src/runtime_fmi1.h",
        "src/runtime_support.h",
    )
    observed_c_names: tuple[str, ...] = tuple(sorted(
        source_path.relative_to(source_root).as_posix()
        for source_path in source_root.rglob("*.c")
    ))
    observed_h_names: tuple[str, ...] = tuple(sorted(
        source_path.relative_to(source_root).as_posix()
        for source_path in source_root.rglob("*.h")
    ))
    assert observed_c_names == expected_c_names
    assert observed_h_names == expected_h_names

    assert validate_fmu(str(archive_path)) == list()
    expected_binary: str = (
        "binaries/"
        + binary_directory(detect_target_platform(), FmiVersion.FMI_1_0)
        + "/"
        + model_identifier
        + library_suffix(detect_target_platform())
    )
    with zipfile.ZipFile(archive_path) as archive:
        archive_names: set[str] = set(archive.namelist())
        root = element_tree.fromstring(archive.read("modelDescription.xml"))
    assert expected_binary in archive_names
    assert root.attrib["fmiVersion"] == "1.0"
    assert root.attrib["modelIdentifier"] == model_identifier
    assert root.attrib["numberOfContinuousStates"] == "0"
    assert root.find("CoSimulation") is None
    assert root.find("ModelStructure") is None
    standalone = root.find("./Implementation/CoSimulation_StandAlone")
    assert standalone is not None
    capabilities = standalone.find("Capabilities")
    assert capabilities is not None
    assert capabilities.attrib["canHandleVariableCommunicationStepSize"] == "true"
    assert capabilities.attrib["canRunAsynchronuously"] == "false"
    assert "initial=" not in element_tree.tostring(root, encoding="unicode")

    result: np.ndarray = simulate_fmu(
        filename=str(archive_path),
        stop_time=3.0e-3,
        step_size=1.0e-3,
        output=("x",),
    )
    np.testing.assert_allclose(
        result["x"],
        result["time"],
        rtol=0.0,
        atol=1.0e-12,
    )


@pytest.mark.skipif(not fmu_compiler_available(), reason="No usable FMU compiler is configured")
def test_fmi_one_model_exchange_export_is_schema_valid_and_loopback_ready(
    tmp_path: Path,
) -> None:
    """Compile, validate, inspect, and execute one FMI 1 Model Exchange FMU.

    :param tmp_path: Isolated export and simulation directory from pytest.
    :return: None.
    """

    state: Var = Var("x")
    derivative: Var = Var("dx", base_var=state)
    source_block: Block = Block(
        state_vars=list((state,)),
        state_eqs=list((Const(1.0),)),
        diff_vars=list((derivative,)),
        init_values=dict(((state, Const(0.0)),)),
        out_vars=list((state,)),
        name="FmiOneMe",
    )
    model_identifier: str = "FmiOneCertifiedMe"
    archive_path: Path = export_model_as_fmu(
        source_block,
        MeExportConfig(
            interface_type=InterfaceType.MODEL_EXCHANGE,
            model_name=model_identifier,
            output_path=tmp_path / (model_identifier + ".fmu"),
            fixed_step=1.0e-3,
            fmi_version=FmiVersion.FMI_1_0,
        ),
    )

    assert validate_fmu(str(archive_path)) == list()
    expected_binary: str = (
        "binaries/"
        + binary_directory(detect_target_platform(), FmiVersion.FMI_1_0)
        + "/"
        + model_identifier
        + library_suffix(detect_target_platform())
    )
    with zipfile.ZipFile(archive_path) as archive:
        archive_names: set[str] = set(archive.namelist())
        root = element_tree.fromstring(archive.read("modelDescription.xml"))
    assert expected_binary in archive_names
    assert root.attrib["fmiVersion"] == "1.0"
    assert root.attrib["modelIdentifier"] == model_identifier
    assert root.attrib["numberOfContinuousStates"] == "1"
    assert root.find("Implementation") is None
    assert root.find("ModelExchange") is None
    assert root.find("ModelStructure") is None
    assert "initial=" not in element_tree.tostring(root, encoding="unicode")

    result: np.ndarray = simulate_fmu(
        filename=str(archive_path),
        stop_time=3.0e-3,
        step_size=1.0e-3,
        output=("x",),
    )
    np.testing.assert_allclose(
        result["x"],
        result["time"],
        rtol=0.0,
        atol=1.0e-8,
    )
