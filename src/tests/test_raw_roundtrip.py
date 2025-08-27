# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os

from VeraGridEngine.enumerations import SimulationTypes
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Simulations.results_template import DriverToSave
from VeraGridEngine.IO.file_handler import FileSavingOptions, FileOpenOptions, FileSave
import VeraGridEngine.api as gc


def run_import_export_test(import_path: str, export_fname: str, version=33):
    """

    :param import_path:
    :param export_fname:
    :return:
    """
    logger = Logger()

    # RAW model import to MultiCircuit
    circuit_1 = gc.FileOpen(file_name=import_path, options=FileOpenOptions()).open()
    nc_1 = gc.compile_numerical_circuit_at(circuit_1)

    # pf_options = PowerFlowOptions()
    pf_results = gc.power_flow(circuit_1)

    pf_session_data = DriverToSave(name="powerflow results",
                                   tpe=SimulationTypes.PowerFlow_run,
                                   results=pf_results,
                                   logger=logger)
    options = FileSavingOptions()
    options.raw_version = version
    options.sessions_data.append(pf_session_data)

    raw_export = FileSave(circuit=circuit_1,
                          file_name=export_fname,
                          options=options)

    file_name, file_extension = os.path.splitext(export_fname)

    if file_extension == '.raw':
        raw_export.save_raw()
    elif file_extension == '.rawx':
        raw_export.save_rawx()
    else:
        raise NotImplementedError(f"Not supported file extension: {file_extension}")

    circuit_2 = gc.FileOpen(file_name=import_path, options=FileOpenOptions()).open()
    nc_2 = gc.compile_numerical_circuit_at(circuit_2)

    ok, logger = circuit_1.compare_circuits(circuit_2)

    if not ok:
        logger.print()

    ok, logger = nc_1.compare(nc_2=nc_2, tol=1e-6)

    if ok:
        print("\nNumerical circuits are identical")
    else:
        logger.print()

    assert ok


def get_path(script_path: str, test_grid_name: str):
    raw_relative_path = os.path.join('data', 'grids', 'RAW', test_grid_name)
    raw_path = os.path.abspath(os.path.join(os.path.dirname(script_path), raw_relative_path))

    export_relative_path = os.path.join('data/output/raw_export_result', test_grid_name)
    export_name = os.path.abspath(os.path.join(os.path.dirname(script_path), export_relative_path))

    if not os.path.exists(os.path.dirname(export_name)):
        os.makedirs(os.path.dirname(export_name))

    return raw_path, export_name


def test_raw_ieee_14_roundtrip():
    """

    :return:
    """
    script_path = os.path.abspath(__file__)
    test_grid_name = 'IEEE 14 bus.raw'
    raw_path, export_name = get_path(script_path, test_grid_name)
    run_import_export_test(import_path=raw_path, export_fname=export_name, version=33)


def test_raw_ieee_30_roundtrip():
    """

    :return:
    """
    script_path = os.path.abspath(__file__)
    test_grid_name = 'IEEE 30 bus.raw'
    raw_path, export_name = get_path(script_path, test_grid_name)
    run_import_export_test(import_path=raw_path, export_fname=export_name, version=33)


def test_raw_ieee_14_fs_ss_roundtrip():
    """

    :return:
    """
    script_path = os.path.abspath(__file__)
    test_grid_name = 'IEEE_14_v35_3_nudox_1_hvdc_desf_rates_fs_ss.raw'
    raw_path, export_name = get_path(script_path, test_grid_name)
    run_import_export_test(import_path=raw_path, export_fname=export_name, version=35)


# def test_raw_ieee_14_fs_ss_wo_pst_roundtrip():
#     """
#
#     :return:
#     """
#     script_path = os.path.abspath(__file__)
#     test_grid_name = 'IEEE_14_v35_3_nudox_1_hvdc_desf_rates_fs_ss_wo_pst.raw'
#     raw_path, export_name = get_path(script_path, test_grid_name)
#     run_import_export_test(import_path=raw_path, export_fname=export_name, version=35)
#
#
# def test_raw_ieee_14_fs_ss_wo_pst_sws_roundtrip():
#     """
#
#     :return:
#     """
#     script_path = os.path.abspath(__file__)
#     test_grid_name = 'IEEE_14_v35_3_nudox_1_hvdc_desf_rates_fs_ss_wo_pst_SWS.raw'
#     raw_path, export_name = get_path(script_path, test_grid_name)
#     run_import_export_test(import_path=raw_path, export_fname=export_name, version=35)


def test_rawx_roundtrip():
    script_path = os.path.abspath(__file__)
    test_grid_name = 'IEEE 14 bus.rawx'
    raw_path, export_name = get_path(script_path, test_grid_name)
    run_import_export_test(import_path=raw_path, export_fname=export_name)
