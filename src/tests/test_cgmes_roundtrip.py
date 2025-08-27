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
from VeraGridEngine.enumerations import CGMESVersions, SimulationTypes, \
    SolverType
from VeraGridEngine.basic_structures import Logger
import VeraGridEngine.api as gc


def create_file_save_options(boundary_zip_path: str) -> FileSavingOptions:
    """

    :param boundary_zip_path:
    :return:
    """
    options = FileSavingOptions()
    options.cgmes_one_file_per_profile = False
    options.cgmes_profiles = [CgmesProfileType.EQ,
                              CgmesProfileType.OP,
                              CgmesProfileType.TP,
                              CgmesProfileType.SV,
                              CgmesProfileType.SSH]
    options.cgmes_version = CGMESVersions.v2_4_15
    options.cgmes_boundary_set = boundary_zip_path

    return options


def create_file_open_options() -> FileOpenOptions:
    """
    :return:
    """
    options = FileOpenOptions(
        cgmes_map_areas_like_raw=True,
        try_to_map_dc_to_hvdc_line=True,
        # crash_on_errors=True,
        adjust_taps_to_discrete_positions=True,
    )

    return options


def get_power_flow_options() -> PowerFlowOptions:
    """

    :return:
    """
    pfo = PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,     # default: True
        # verbose=0,
        # initialize_with_existing_solution=False,
        # tolerance=1e-6,
        # max_iter=25,
        # max_outer_loop_iter=100,
        # control_q=True,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=False,
        # orthogonalize_controls=True,
        # apply_temperature_correction=True,
        # branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
        # distributed_slack=False,
        ignore_single_node_islands=True,
        # trust_radius=1.0,
        # backtracking_parameter=0.05,
        # use_stored_guess=False,
        # generate_report=False
    )
    return pfo


def run_import_export_test(import_path: str | list[str],
                           export_fname: str,
                           boundary_zip_path: str):
    """

    :param import_path:
    :param export_fname:
    :param boundary_zip_path:
    :return:
    """
    logger = Logger()
    # Import 1 ----------------------------------------------------
    # CGMES model import to MultiCircuit
    circuit_1 = gc.FileOpen(file_name=import_path, options=FileOpenOptions()).open()
    circuit_1.buses.sort(key=lambda obj: obj.name, reverse=False)      # SORTING
    # circuit_1.buses.sort(key=lambda obj: obj.idtag)     # SORTING by idtag
    nc_1 = gc.compile_numerical_circuit_at(circuit_1)
    # run power flow
    pf_options = get_power_flow_options()
    pf_results = gc.power_flow(circuit_1, pf_options)

    # assert pf_results.converged

    pf_session_data = DriverToSave(name="powerflow results",
                                   tpe=SimulationTypes.PowerFlow_run,
                                   results=pf_results,
                                   logger=logger)

    # Export -----------------------------------------------------------
    # export_dir = os.path.join(os.path.curdir, "/export_result")
    # export_name = os.path.join(export_dir, export_name)
    options = create_file_save_options(boundary_zip_path)
    options.sessions_data.append(pf_session_data)

    cgmes_export = FileSave(circuit=circuit_1,
                            file_name=export_fname,
                            options=options)
    cgmes_export.save_cgmes()

    # Import 2 ---------------------------------------------
    circuit_2 = gc.FileOpen(file_name=[export_fname, boundary_zip_path], options=FileOpenOptions()).open()
    circuit_2.buses.sort(key=lambda obj: obj.name, reverse=False)      # SORTING
    # Move the first element to the last position, if sorting doesn't work
    if not circuit_1.buses[0].name == circuit_2.buses[0].name:
        circuit_2.buses.append(circuit_2.buses.pop(0))
    nc_2 = gc.compile_numerical_circuit_at(circuit_2)

    # COMPARING Multi Circuits ------------------------------------------------
    ok, logger = circuit_1.compare_circuits(circuit_2)
    if ok:
        print("/nOK! SUCCESS for Multi Circuit!/n")
    else:
        logger.print()

    # COMPARING Numerical Circuits
    ok, logger = nc_1.compare(nc_2=nc_2, tol=1e-4)      # 1e-6

    if ok:
        print("\nOK! SUCCESS for Numerical Circuit!\n")
    else:
        logger.print()

        # FOR DEBUG
        print('Buses')
        print(nc_1.bus_data.names)
        print(nc_2.bus_data.names)
        print('Loads')
        print(nc_1.load_data.names)
        print(nc_2.load_data.names)
        print('Gens')
        print(nc_1.generator_data.names)
        print(nc_2.generator_data.names)

        Sbus1 = nc_1.get_power_injections_pu()
        Sbus2 = nc_2.get_power_injections_pu()
        adm1 = nc_1.get_admittance_matrices()
        adm2 = nc_2.get_admittance_matrices()

        print('Sbus1')
        print(Sbus1)
        print('Sbus2')
        print(Sbus2)
        print('S_diff')
        print(Sbus2 - Sbus1)
        print('Y1')
        print(adm1.Ybus.A)
        print('Y2')
        print(adm2.Ybus.A)
        print('Y_diff')
        print(adm2.Ybus.A - adm1.Ybus.A)

    assert ok

@pytest.mark.skip(reason="Not passing because VeraGrid ConnectivityNodes were removed and this needs rethinking")
def test_cgmes_roundtrip():
    """

    :return:
    """
    test_grid_name = 'micro_grid_NL_T1.zip'
    boundary_set_name = 'micro_grid_BD.zip'

    # PASSED
    # test_grid_name = 'micro_grid_assmb_base.zip'
    # boundary_set_name = 'micro_grid_BD.zip'

    # Not PASSED ?
    # test_grid_name = 'TestConfigurations_packageCASv2.0/MicroGrid/Type2_T2/CGMES_v2.4.15_MicroGridTestConfiguration_T2_Assembled_Complete_v2.zip'
    # boundary_set_name = 'micro_grid_BD.zip'

    # PASSED
    # test_grid_name = 'TestConfigurations_packageCASv2.0/MicroGrid/BaseCase_BC/CGMES_v2.4.15_MicroGridTestConfiguration_BC_Assembled_v2.zip'
    # boundary_set_name = 'micro_grid_BD.zip'

    # test_grid_name = 'IEEE 14 bus.zip'
    # boundary_set_name = 'BD_IEEE_Grids.zip'

    # test_grid_name = 'IEEE_14_v35_3_nudox_1_hvdc_desf_rates_fs_ss.zip'
    # boundary_set_name = 'BD_IEEE_Grids.zip'

    script_path = os.path.abspath(__file__)

    cgmes_files_relative_path = os.path.join('data', 'grids', 'CGMES_2_4_15', test_grid_name)
    cgmes_path = os.path.abspath(os.path.join(os.path.dirname(script_path), cgmes_files_relative_path))

    boundary_relative_path = os.path.join('data', 'grids', 'CGMES_2_4_15', boundary_set_name)
    boundary_path = os.path.abspath(os.path.join(os.path.dirname(script_path), boundary_relative_path))

    export_relative_path = os.path.join('data/output/cgmes_export_result', f'{test_grid_name[:-4]}_GC.zip')
    export_name = os.path.abspath(os.path.join(os.path.dirname(script_path), export_relative_path))
    if not os.path.exists(os.path.dirname(export_name)):
        os.makedirs(os.path.dirname(export_name))

    run_import_export_test(cgmes_path, export_name, boundary_path)
