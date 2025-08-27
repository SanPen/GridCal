# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
import pytest
import numpy as np
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType
from VeraGridEngine.IO.file_handler import FileSavingOptions, FileOpenOptions, FileOpen, FileSave
from VeraGridEngine.Simulations import PowerFlowOptions
from VeraGridEngine.Simulations.results_template import DriverToSave
from VeraGridEngine.enumerations import CGMESVersions, SolverType, SimulationTypes
from VeraGridEngine.basic_structures import Logger
import VeraGridEngine.api as gce


def create_file_save_options(boundary_zip_path: str) -> FileSavingOptions:
    """

    :param boundary_zip_path:
    :return:
    """
    options = FileSavingOptions()
    options.one_file_per_profile = False
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
        retry_with_other_methods=False,  # default True
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


def run_raw_to_cgmes(import_path: str | list[str],
                     export_fname: str,
                     boundary_zip_path: str):
    """

    :param import_path:
    :param export_fname:
    :param boundary_zip_path:
    :return:
    """
    file_open_options = create_file_open_options()

    # RAW model import to MultiCircuit
    file_open_1 = FileOpen(file_name=import_path,
                           options=file_open_options)
    circuit1 = file_open_1.open()

    # run power flow
    pf_options = get_power_flow_options()
    pf1_res = gce.power_flow(circuit1, pf_options)
    # pf_options = None
    # pf1_res = None
    assert pf1_res.converged

    logger_saving = Logger()
    pf_session_data = DriverToSave(name="powerflow results",
                                   tpe=SimulationTypes.PowerFlow_run,
                                   results=pf1_res,
                                   logger=logger_saving)
    # Export
    # export_dir = os.path.join(os.path.curdir, "/export_result")
    # export_name = os.path.join(export_dir, export_name)
    file_save_options = create_file_save_options(boundary_zip_path)
    file_save_options.sessions_data.append(pf_session_data)

    cgmes_export = FileSave(circuit=circuit1,
                            file_name=export_fname,
                            options=file_save_options)
    cgmes_export.save_cgmes()
    logger_saving.print()

    # OPEN CGMES model
    file_open_2 = FileOpen(file_name=[export_fname, boundary_zip_path],
                           options=file_open_options)
    circuit2 = file_open_2.open()

    # run power flow
    pf2_res = gce.power_flow(circuit2, pf_options)

    ok, logger_mc = circuit1.compare_circuits(circuit2)
    if not ok:
        print("\nMulti Circuits are not equal!\n")
        logger_mc.print()

    nc1 = gce.compile_numerical_circuit_at(circuit1)
    nc2 = gce.compile_numerical_circuit_at(circuit2)

    # COMPARING Numerical Circuits
    ok, logger_nc = nc1.compare(nc_2=nc2, tol=1e-6)  # 1e-6

    if ok:
        print("\nOK! SUCCESS for Numerical Circuit!\n")
    else:
        print("\nNumerical Circuits are not equal!\n")
        logger_nc.print()

        # FOR DEBUG
        adm1 = nc1.get_admittance_matrices()
        adm2 = nc2.get_admittance_matrices()
        Sbus1 = nc1.get_power_injections()
        Sbus2 = nc2.get_power_injections()
        print('Buses')
        print(nc1.bus_data.names)
        print(nc2.bus_data.names)
        print('Loads')
        print(nc1.load_data.names)
        print(nc2.load_data.names)
        print('Gens')
        print(nc1.generator_data.names)
        print(nc2.generator_data.names)
        print('Sbus1')
        print(Sbus1)
        print('Sbus2')
        print(Sbus2)
        print('S_diff')
        print(Sbus1 - Sbus2)
        print('Y1')
        print(adm1.Ybus.A)
        print('Y2')
        print(adm2.Ybus.A)
        Y_diff = adm2.Ybus.A - adm1.Ybus.A
        print('Y_diff', Y_diff)
        # mask = Y_diff != 0
        mask = ~np.isclose(adm1.Ybus.A, adm2.Ybus.A, atol=1e-4, rtol=0)
        # print('mask \n', mask)
        print("Y1_elements", adm1.Ybus.A[mask])
        print("Y2_elements", adm2.Ybus.A[mask])
        print("Y_diff", adm1.Ybus.A[mask] - adm2.Ybus.A[mask])

    assert ok

    pf_ok = np.allclose(np.abs(pf1_res.voltage), np.abs(pf2_res.voltage), atol=1e-5)
    if pf_ok:
        print("\nOK! SUCCESS for PowerFlow results!\n")
    else:
        print("Tap modules")
        print(pf1_res.tap_module)
        print(pf2_res.tap_module)
        print("Tap phase")
        print(pf1_res.tap_angle)
        print(pf2_res.tap_angle)

        print("\nVoltages")
        print(np.abs(pf1_res.voltage))
        print(np.abs(pf2_res.voltage))
        print("Voltage abs diff")
        print(np.abs(pf2_res.voltage) - np.abs(pf1_res.voltage))

    assert pf_ok


@pytest.mark.skip(reason="Not passing because VeraGrid ConnectivityNodes were removed and this needs rethinking")
def test_raw_to_cgmes_cross_roundtrip():
    """
    Importing from RAW and export to CGMES, importing back it.
    Comparing the RAW import with the CGMES import.

    :return:
    """
    script_path = os.path.abspath(__file__)

    # test_grid_name = 'IEEE 14 bus'  # PASSEED
    # boundary_relative_path = os.path.join('data', 'grids', 'CGMES_2_4_15', 'BD_IEEE_Grids.zip')

    # braches excessive voltage diff: PASSED if these branches are not added as trafos
    # test_grid_name = 'IEEE 30 bus'  # num of transformer 2w??!! (tap_module num error)
    # boundary_relative_path = os.path.join('data', 'grids', 'CGMES_2_4_15', 'BD_IEEE_Grids.zip')

    # PST transformer disabled, COD1 = -3
    # test_grid_name = 'IEEE_14_v35_3_nudox_1_hvdc_desf_rates_fs_ss_wo_pst'
    # boundary_relative_path = os.path.join('data', 'grids', 'CGMES_2_4_15', 'BD_IEEE_Grids.zip')

    # Switched shunts has different size blocks
    # test_grid_name = 'IEEE_14_v35_3_nudox_1_hvdc_desf_rates_fs_ss_wo_pst_SWS'
    # boundary_relative_path = os.path.join('data', 'grids', 'CGMES_2_4_15', 'BD_IEEE_Grids.zip')

    # PST is controlling
    test_grid_name = 'IEEE_14_v35_3_nudox_1_hvdc_desf_rates_fs_ss'
    boundary_relative_path = os.path.join('data', 'grids', 'CGMES_2_4_15', 'BD_IEEE_Grids.zip')

    # test_grid_name = 'DACF_20240404_00_IGM'       # STORE it somewhewre else!
    # boundary_relative_path = os.path.join('data', 'grids', 'CGMES_2_4_15', 'DACF_20240404_Boundary.zip')

    boundary_path = os.path.abspath(os.path.join(os.path.dirname(script_path), boundary_relative_path))

    raw_relative_path = os.path.join('data', 'grids', 'RAW', f"{test_grid_name}.raw")
    raw_path = os.path.abspath(os.path.join(os.path.dirname(script_path), raw_relative_path))

    export_relative_path = os.path.join(
        'data', 'output', 'raw_to_cgmes_export_results',
        f'{test_grid_name}_from_raw_GC.zip'
    )
    export_name = os.path.abspath(os.path.join(os.path.dirname(script_path), export_relative_path))
    if not os.path.exists(os.path.dirname(export_name)):
        os.makedirs(os.path.dirname(export_name))

    # # Non-public test cases
    # raw_path = os.path.join(
    #     # "C:\\Mate",  # Mate's
    #     r"C:\\Work",  # Bence's
    #     "gridDigIt Kft",
    #     "External projects - Documents",
    #     "REE",
    #     "test_models",
    #     # # DACF 1
    #     # "miguel_models_2",
    #     # "DACF_20241205_00_IGM_35.raw"
    #     # DACF 2
    #     "miguel_models_3",
    #     "PLANNING MODELS AND OPERATIONAL PLANNING MODELS",
    #     "DACF_model",
    #     "DACF_20250121_00_IGM_35.raw"
    # )
    # export_relative_path = os.path.join('data', 'output', 'raw_to_cgmes_export_results',
    #                                     f'DACF_20241205_00_IGM_35_from_raw_GC.zip')
    # export_name = os.path.abspath(os.path.join(os.path.dirname(script_path), export_relative_path))
    # boundary_path = os.path.join(
    #     # r"C:\\Mate", # Mate's
    #     r"C:\\Work",  # Bence's
    #     "gridDigIt Kft",
    #     "External projects - Documents",
    #     "REE",
    #     "test_models",
    #     # # DACF 1
    #     # "miguel_models_2",
    #     # "BOUNDARY SET.zip",
    #     # DACF 2
    #     "miguel_models_3",
    #     "PLANNING MODELS AND OPERATIONAL PLANNING MODELS",
    #     "DACF_model",
    #     "20241201T0000Z__ENTSOE.zip"
    # )

    run_raw_to_cgmes(raw_path, export_name, boundary_path)


if __name__ == '__main__':
    test_raw_to_cgmes_cross_roundtrip()
