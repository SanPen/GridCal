from __future__ import annotations

import os

import numpy as np
from GridCalEngine.IO import FileSave
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile
from GridCalEngine.IO.file_handler import FileSavingOptions
from GridCalEngine.Simulations import PowerFlowOptions
from GridCalEngine.Simulations.results_template import DriverToSave
from GridCalEngine.enumerations import CGMESVersions, SolverType, SimulationTypes
from GridCalEngine.basic_structures import Logger
import GridCalEngine.api as gc


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
                              cgmesProfile.SSH,
                              cgmesProfile.SC]
    options.cgmes_version = CGMESVersions.v2_4_15
    options.cgmes_boundary_set = boundary_zip_path

    return options


def run_import_export_test(import_path: str | list[str], export_fname: str, boundary_zip_path: str):
    """

    :param import_path:
    :param export_fname:
    :param boundary_zip_path:
    :return:
    """
    logger = Logger()
    # CGMES model import to MultiCircuit
    circuit_1 = gc.open_file(import_path)
    # circuit_1.buses.sort(key=lambda obj: obj.name)      # SORTING
    nc_1 = gc.compile_numerical_circuit_at(circuit_1)
    # run power flow
    pf_options = PowerFlowOptions()
    pf_results = gc.power_flow(circuit_1, pf_options)

    pf_session_data = DriverToSave(name="powerflow results",
                                   tpe=SimulationTypes.PowerFlow_run,
                                   results=pf_results,
                                   logger=logger)
    # Export
    # export_dir = os.path.join(os.path.curdir, "/export_result")
    # export_name = os.path.join(export_dir, export_name)
    options = create_file_save_options(boundary_zip_path)
    options.sessions_data.append(pf_session_data)

    cgmes_export = FileSave(circuit=circuit_1,
                            file_name=export_fname,
                            options=options)
    cgmes_export.save_cgmes()

    circuit_2 = gc.open_file([export_fname, boundary_zip_path])
    # circuit_2.buses.sort(key=lambda obj: obj.name)      # SORTING
    nc_2 = gc.compile_numerical_circuit_at(circuit_2)

    # COMPARING
    ok, logger = circuit_1.compare_circuits(circuit_2)

    if not ok:
        logger.print()

    ok, logger = nc_1.compare(nc_2=nc_2, tol=1e-6)

    if ok:
        print("OK!")
    else:
        logger.print()

    S_diff = nc_2.Sbus - nc_1.Sbus
    print(S_diff)
    Y_diff = nc_2.Ybus.A - nc_1.Ybus.A
    print(Y_diff)

    assert ok


def test_cgmes_roundtrip():
    """

    :return:
    """
    script_path = os.path.abspath(__file__)

    cgmes_files_relative_path = os.path.join('..', 'data', 'grids', 'CGMES_2_4_15', 'micro_grid_NL_T1.zip')
    cgmes_path = os.path.abspath(os.path.join(os.path.dirname(script_path), cgmes_files_relative_path))

    boundary_relative_path = os.path.join('..', 'data', 'grids', 'CGMES_2_4_15', 'ENTSOe_boundary_set.zip')
    boundary_path = os.path.abspath(os.path.join(os.path.dirname(script_path), boundary_relative_path))

    export_relative_path = os.path.join('export_result', 'micro_grid_NL_T1.zip')
    export_name = os.path.abspath(os.path.join(os.path.dirname(script_path), export_relative_path))
    if not os.path.exists(os.path.dirname(export_name)):
        os.makedirs(os.path.dirname(export_name))

    run_import_export_test(cgmes_path, export_name, boundary_path)
    # nc_o = gc.compile_numerical_circuit_at(circuit_o)

    # export to CGMES
    # crate FileSave

    # boundary: micro grid Boundary
    # gc.save_file() from FileHandler

    # import the exported CGMES

    # Compare with the original
