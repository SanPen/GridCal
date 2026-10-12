# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Functional export tests for the maintained FMI 3 CS and ME pipelines."""
from __future__ import annotations
from VeraGridEngine.enumerations import InterfaceType

from pathlib import Path
import xml.etree.ElementTree as element_tree
import zipfile

import numpy as np
import pytest
from fmpy import simulate_fmu
from fmpy.validation import validate_fmu

from VeraGridEngine.enumerations import FmiVersion
from VeraGridEngine.IO.fmu.compiler import fmu_compiler_available
from VeraGridEngine.IO.fmu.interface import export_model_as_fmu
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.IO.fmu.config import ExportConfig as CsExportConfig
from VeraGridEngine.IO.fmu.config import (
    binary_directory,
    detect_target_platform,
    library_suffix,
)
from VeraGridEngine.IO.fmu.config import ExportConfig as MeExportConfig


@pytest.mark.skipif(not fmu_compiler_available(), reason="No usable FMU compiler is configured")
def test_fmi_three_smooth_cs_and_me_exports_follow_same_oracle(tmp_path: Path) -> None:
    """Compile and execute smooth FMI 3 CS and ME models against ``x=t``.

    :param tmp_path: Isolated directory for both generated FMU archives.
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
        name="FmiThreeSmooth",
    )
    cs_path: Path = export_model_as_fmu(
        source_block,
        CsExportConfig(
            model_name="FmiThreeSmoothCs",
            output_path=tmp_path / "FmiThreeSmoothCs.fmu",
            fixed_step=1.0e-3,
            fmi_version=FmiVersion.FMI_3_0,
        ),
    )
    me_path: Path = export_model_as_fmu(
        source_block,
        MeExportConfig(interface_type=InterfaceType.MODEL_EXCHANGE, 
            model_name="FmiThreeSmoothMe",
            output_path=tmp_path / "FmiThreeSmoothMe.fmu",
            fixed_step=1.0e-3,
            fmi_version=FmiVersion.FMI_3_0,
        ),
    )

    assert validate_fmu(str(cs_path)) == list()
    assert validate_fmu(str(me_path)) == list()
    expected_archives: tuple[tuple[Path, str], ...] = (
        (cs_path, "FmiThreeSmoothCs"),
        (me_path, "FmiThreeSmoothMe"),
    )
    platform_directory: str = binary_directory(
        detect_target_platform(),
        FmiVersion.FMI_3_0,
    )
    platform_library_suffix: str = library_suffix(detect_target_platform())
    for archive_path, model_identifier in expected_archives:
        with zipfile.ZipFile(archive_path, "r") as archive:
            member_names: tuple[str, ...] = tuple(archive.namelist())
            expected_binary: str = (
                f"binaries/{platform_directory}/{model_identifier}{platform_library_suffix}"
            )
            assert expected_binary in member_names
            model_description: element_tree.Element = element_tree.fromstring(
                archive.read("modelDescription.xml")
            )
            assert model_description.attrib["fmiVersion"] == "3.0"
            assert model_description.attrib["modelName"] == model_identifier
    cs_result: np.ndarray = simulate_fmu(
        str(cs_path), stop_time=0.05, output_interval=1.0e-3, output=list(("x",))
    )
    me_result: np.ndarray = simulate_fmu(
        str(me_path), stop_time=0.05, output_interval=1.0e-3, output=list(("x",))
    )
    np.testing.assert_allclose(cs_result["x"], cs_result["time"], rtol=1.0e-7, atol=1.0e-8)
    np.testing.assert_allclose(me_result["x"], me_result["time"], rtol=1.0e-7, atol=1.0e-8)
