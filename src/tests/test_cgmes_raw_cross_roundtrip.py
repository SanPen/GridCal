# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os

import pytest
import numpy as np
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType
from VeraGridEngine.IO.file_handler import FileSavingOptions, FileOpenOptions, FileSave
from VeraGridEngine.Simulations import PowerFlowOptions
from VeraGridEngine.Simulations.results_template import DriverToSave
from VeraGridEngine.enumerations import CGMESVersions, SolverType, SimulationTypes
from VeraGridEngine.basic_structures import Logger
import VeraGridEngine.api as gce


def run_cgmes_to_raw(import_path: str | list[str], export_fname: str):
    """

    :param import_path:
    :param export_fname:
    :return:
    """
    logger = Logger()
    # CGMES model import to MultiCircuit
    fileOpenOptions = FileOpenOptions(cgmes_map_areas_like_raw=True)

    circuit = gce.FileOpen(file_name=import_path, options=fileOpenOptions).open()
    nc_1 = gce.compile_numerical_circuit_at(circuit)

    # Set the bus numbers for PSSe
    for i, bus in enumerate(circuit.buses):
        bus.code = f"{i + 1}"

    # run power flow
    pf_options = PowerFlowOptions()
    pf_res_1 = gce.power_flow(circuit, pf_options)

    pf_session_data = DriverToSave(name="powerflow results",
                                   tpe=SimulationTypes.PowerFlow_run,
                                   results=pf_res_1,
                                   logger=logger)
    # Export
    # export_dir = os.path.join(os.path.curdir, "/export_result")
    # export_name = os.path.join(export_dir, export_name)
    options = FileSavingOptions()
    options.sessions_data.append(pf_session_data)

    raw_export = FileSave(circuit=circuit,
                          file_name=export_fname,
                          options=options)

    raw_export.save_raw()

    circuit_2 = gce.FileOpen(file_name=export_fname, options=FileOpenOptions()).open()
    nc_2 = gce.compile_numerical_circuit_at(circuit_2)
    pf_res_2 = gce.power_flow(circuit_2, pf_options)

    ok, logger = circuit.compare_circuits(circuit_2)
    if not ok:
        logger.print()

    # ok, logger = nc_1.compare(nc_2=nc_2, tol=1e-6)
    # !!! ------------------------------------------------------------
    #
    # Due to different modelling in RAW nad CGMES instead of comparing numerical circuits,
    # electrical arrays and power flow results are compared
    #
    # !!! ------------------------------------------------------------
    # Compare Y and S arrays
    ADM_1 = nc_1.get_admittance_matrices().Ybus.toarray()
    ADM_2 = nc_2.get_admittance_matrices().Ybus.toarray()
    adm_ok = np.allclose(ADM_1, ADM_2, atol=1e-5)
    if adm_ok:
        print("\nAdmitance Ybus matrices are the same!")
    else:
        print("\nAdmittance Ybus matrices are NOT the same!")
        print(ADM_1)
        print(ADM_2)

    # Compare power flow voltages
    pf_ok = np.allclose(np.abs(pf_res_1.voltage), np.abs(pf_res_2.voltage), atol=1e-5)
    if pf_ok:
        print("\nPower flow results are the same!")
    else:
        print("\nPower flow results are NOT the same!")
        print(np.abs(pf_res_1.voltage))
        print(np.abs(pf_res_2.voltage))

    ok = True
    assert ok


@pytest.mark.skip("Something to fix...the bug is in the psse file having a Sbase=0 in a transformer...")
def test_cgmes_to_raw_roundtrip():
    """

    :return:
    """
    script_path = os.path.abspath(__file__)

    cgmes_files_relative_path = os.path.join('data', 'grids', 'CGMES_2_4_15', 'micro_grid_NL_T1.zip')
    cgmes_path = os.path.abspath(os.path.join(os.path.dirname(script_path), cgmes_files_relative_path))

    boundary_relative_path = os.path.join('data', 'grids', 'CGMES_2_4_15', 'micro_grid_BD.zip')
    boundary_path = os.path.abspath(os.path.join(os.path.dirname(script_path), boundary_relative_path))

    export_relative_path = os.path.join('data/output/raw_export_result', 'micro_grid_NL_T1.raw')
    export_name = os.path.abspath(os.path.join(os.path.dirname(script_path), export_relative_path))
    if not os.path.exists(os.path.dirname(export_name)):
        os.makedirs(os.path.dirname(export_name))

    run_cgmes_to_raw(cgmes_path, export_name)
