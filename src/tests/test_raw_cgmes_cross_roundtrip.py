# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os

import numpy as np
from GridCalEngine.IO import FileSave
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile
from GridCalEngine.IO.file_handler import FileSavingOptions, FileOpenOptions, FileOpen
from GridCalEngine.Simulations import PowerFlowOptions
from GridCalEngine.Simulations.results_template import DriverToSave
from GridCalEngine.enumerations import CGMESVersions, SolverType, SimulationTypes
from GridCalEngine.basic_structures import Logger
import GridCalEngine.api as gce


def create_file_save_options(boundary_zip_path: str) -> FileSavingOptions:
    """

    :param boundary_zip_path:
    :return:
    """
    options = FileSavingOptions()
    options.one_file_per_profile = False
    options.cgmes_profiles = [cgmesProfile.EQ,
                              cgmesProfile.OP,
                              cgmesProfile.TP,
                              cgmesProfile.SV,
                              cgmesProfile.SSH]
    options.cgmes_version = CGMESVersions.v2_4_15
    options.cgmes_boundary_set = boundary_zip_path

    return options


def create_file_open_options() -> FileOpenOptions:
    """
    :return:
    """
    options = FileOpenOptions()
    options.cgmes_map_areas_like_raw = True
    options.try_to_map_dc_to_hvdc_line = True

    return options


def run_raw_to_cgmes(import_path: str | list[str],
                     export_fname: str,
                     boundary_zip_path: str):
    """

    :param import_path:
    :param export_fname:
    :param boundary_zip_path:
    :return:
    """
    # RAW model import to MultiCircuit
    circuit1 = gce.open_file(import_path)

    # detect substation from the raw file
    gce.detect_substations(grid=circuit1)

    # run power flow
    # pf_options = PowerFlowOptions()
    pf_options = None
    # pf1_res = gce.power_flow(circuit1, pf_options)
    pf1_res = None

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

    open_options = create_file_open_options()
    file_open = FileOpen(file_name=[export_fname, boundary_zip_path],
                         options=open_options)

    circuit2 = file_open.open()

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
        print('Buses')
        print(nc1.bus_names)
        print(nc2.bus_names)
        print('Loads')
        print(nc1.load_names)
        print(nc2.load_names)
        print('Gens')
        print(nc1.generator_names)
        print(nc2.generator_names)
        print('Sbus1')
        print(nc1.Sbus)
        print('Sbus2')
        print(nc2.Sbus)
        print('S_diff')
        print(nc2.Sbus - nc1.Sbus)
        print('Y1')
        print(nc1.Ybus.A)
        print('Y2')
        print(nc2.Ybus.A)
        print('Y_diff')
        print(nc2.Ybus.A - nc1.Ybus.A)

    assert np.allclose(np.abs(pf1_res.voltage), np.abs(pf2_res.voltage), atol=1e-5)

    assert ok


def test_raw_to_cgmes_cross_roundtrip():
    """
    Importing from RAW and export to CGMES, importing back it.
    Comparing the RAW import with the CGMES import.

    :return:
    """
    script_path = os.path.abspath(__file__)

    # test_grid_name = 'IEEE 14 bus'  # PASSEED
    # boundary_relative_path = os.path.join('data', 'grids', 'CGMES_2_4_15', 'BD_IEEE_Grids.zip')

    # test_grid_name = 'IEEE_14_v35_3_nudox_1_hvdc_desf_rates_fs_ss'
    # boundary_relative_path = os.path.join('data', 'grids', 'CGMES_2_4_15', 'BD_IEEE_Grids.zip')

    test_grid_name = 'DACF_20240404_00_IGM'
    boundary_relative_path = os.path.join('data', 'grids', 'CGMES_2_4_15', 'DACF_20240404_Boundary.zip')

    # test_grid_name = 'IEEE 30 bus'              # FAILED
    # Error     Different snapshot values    Transformer      rate  5.9091    65.0
    # Converted line to trafo due to excessice voltage difference !??
    # test_grid_name = 'IEEE 118 Bus' # v2?     # PASSEED

    boundary_path = os.path.abspath(os.path.join(os.path.dirname(script_path), boundary_relative_path))

    raw_relative_path = os.path.join('data', 'grids', 'RAW', f"{test_grid_name}.raw")
    raw_path = os.path.abspath(os.path.join(os.path.dirname(script_path), raw_relative_path))

    export_relative_path = os.path.join('data/output/raw_to_cgmes_export_results', f'{test_grid_name}_from_raw_GC.zip')
    export_name = os.path.abspath(os.path.join(os.path.dirname(script_path), export_relative_path))
    if not os.path.exists(os.path.dirname(export_name)):
        os.makedirs(os.path.dirname(export_name))

    run_raw_to_cgmes(raw_path, export_name, boundary_path)
