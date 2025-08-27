# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import pytest
import numpy as np
import pandas as pd
import VeraGridEngine.api as gce
from VeraGridEngine.IO.file_handler import FileOpen, FileOpenOptions

pd.set_option('display.max_colwidth', None)


@pytest.mark.skip(reason="Not passing because VeraGrid ConnectivityNodes were removed and this needs rethinking")
def test_ieee14_cgmes() -> None:
    """
    This test load two supposedly equivalent grids and compared their internal structures and their power flow
    """

    # load IEEE14 ------------------------------------------------------------------------------------------------------
    file_open_options = FileOpenOptions(
        cgmes_map_areas_like_raw=True,
        try_to_map_dc_to_hvdc_line=True,
        # crash_on_errors=True,
        adjust_taps_to_discrete_positions=True,
    )
    # RAW model import to MultiCircuit
    file_open1 = FileOpen(file_name=os.path.join("data", "grids", "RAW", "IEEE 14 bus.raw"),
                          options=file_open_options)
    grid1 = file_open1.open()
    nc1 = gce.compile_numerical_circuit_at(grid1)
    pf_res1 = gce.power_flow(grid1)

    # we need to hack it a bit: add substations and voltage levels
    gce.detect_substations(grid=grid1)

    # save the model in CGMES ------------------------------------------------------------------------------------------

    # path to the boundary set
    bd_set = os.path.join("data", "grids", "CGMES_2_4_15",
                          "TestConfigurations_packageCASv2.0", 'MicroGrid', 'BaseCase_BC',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_BD_v2.zip')

    output_cgmes_path = os.path.join("data", "output", "IEEE14_test_ieee_export.zip")

    gce.save_cgmes_file(grid=grid1,
                        filename=output_cgmes_path,
                        cgmes_boundary_set_path=bd_set,
                        cgmes_version=gce.CGMESVersions.v2_4_15,
                        # cgmes_version=gce.CGMESVersions.v3_0_0,
                        pf_results=pf_res1)

    # load again from CGMES into a new grid object
    # grid2 = gce.open_file(filename=[output_cgmes_path, bd_set])
    file_open2 = FileOpen(file_name=[output_cgmes_path, bd_set],
                          options=file_open_options)
    grid2 = file_open2.open()
    nc2 = gce.compile_numerical_circuit_at(grid2)
    pf_res2 = gce.power_flow(grid2)

    # TUC 17.1 compare structures (Ybus, Sbus, etc...)
    ok_nc, logger_nc = nc1.compare(nc2)

    if not ok_nc:
        print("\n\tTUC 17.1 is NOT OK\n")
        logger_nc.print("CGMES roundtrip comparison with the original")
        logger_nc.to_xlsx(os.path.join("data", "output", "tuc_17_1_ieee14.xlsx"))
    else:
        print("TUC 17.1 is OK")

    # load a CGMES grid made with CImConverter -------------------------------------------------------------------------
    file_open3 = FileOpen(file_name=[os.path.join("data", "grids", "CGMES_2_4_15", "IEEE 14 bus.zip"),
                                    bd_set],
                          options=file_open_options)
    grid3 = file_open3.open()
    nc3 = gce.compile_numerical_circuit_at(grid3)
    pf_res3 = gce.power_flow(grid3)

    # TUC 17.1 compare structures (Ybus, Sbus, etc...)
    ok_nc3, logger_nc3 = nc1.compare(nc3)

    # Scal = V * conj(Y @ V)
    # error = max(abs(Scalc - S0)) < 1e-3
    # pf_res3.error

    if not ok_nc3:
        logger_nc3.print("CGMES cim-converter comparison with the original")
        logger_nc3.to_xlsx(os.path.join("data", "output", "tuc_17_1_ieee14_cim_converter.xlsx"))
    else:
        print("TUC Cimconverter 17.1 ok")

    # load the associated results file  --------------------------------------
    results_folder = os.path.join('data', 'results')
    results_file = 'IEEE 14 bus.sav.xlsx'
    df_v = pd.read_excel(os.path.join(results_folder, results_file),
                         sheet_name='Vabs', index_col=0)
    v_psse = df_v.values[:, 0]
    v_gc = np.abs(pf_res1.voltage)
    v_gc = v_gc[0:len(v_psse)]  # for debug
    v_ok = np.allclose(v_gc, v_psse, atol=1e-6)

    assert v_ok

    # ------------------------------------------------------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------------------------------------------------------
    # load the associated results file
    results_file = os.path.join('data', 'results', 'IEEE 14 bus.sav.xlsx')
    df_v = pd.read_excel(results_file, sheet_name='Vabs', index_col=0)

    # TUC 17.2 compare power flows
    df1 = pf_res1.get_bus_df()
    df2 = pf_res2.get_bus_df()
    df3 = pf_res3.get_bus_df()
    diff12 = df1 - df2
    diff13 = df1 - df3

    grid1_ok = np.allclose(df1['Vm'].values, df_v.values[:, 0])
    print("\nGrid 1 (PSSe raw)",
          "Vm ok:", grid1_ok)
    print(pf_res1.get_bus_df())

    grid2_ok = np.allclose(df2['Vm'].values, df_v.values[:, 0])
    print("\nGrid 2 (CGMES - round-tripped)",
          "Vm ok:", grid2_ok)
    print(pf_res2.get_bus_df())

    # grid3_ok = np.allclose(df3['Vm'].values[:14], df_v.values[:, 0])
    # print("\nGrid 3 (CGMES - from Cim-converter)",
    #       "Vm ok:", grid3_ok)
    # print(pf_res3.get_bus_df())

    print("\nDifference raw to VeraGrid CGMES")
    print(diff12)
    print("max err:", np.max(np.abs(diff12.values)))

    print("\nDifference raw to Cim-converter CGMES")
    print(diff13)
    print("max err:", np.max(np.abs(diff13.values)))

    assert grid1_ok
    assert grid2_ok
    # assert grid3_ok


# def test_ieee_grids() -> None:
#     """
#     Checks the CGMES files made with cim converter are loaded
#     This test checks that VeraGrid loads these CGMEs models correctly, via power flow
#     :return: Nothing if ok, fails if not
#     """
#
#     results_folder = os.path.join('data', 'results')
#     cgmes_folder = os.path.join('data', 'grids', 'CGMES_2_4_15')
#
#     bd_set = os.path.join(cgmes_folder, 'BD_IEEE_Grids.zip')
#
#     files = [
#         ('IEEE 14 bus.zip', 'IEEE 14 bus.sav.xlsx'),
#         ('IEEE 118 Bus v2.zip', 'IEEE 118 Bus.sav.xlsx'),
#         ('IEEE 30 bus_33.zip', 'IEEE 30 bus.sav.xlsx'),
#     ]
#
#     file_open_options = FileOpenOptions(
#         cgmes_map_areas_like_raw=True,
#         try_to_map_dc_to_hvdc_line=True,
#         # crash_on_errors=True,
#         adjust_taps_to_discrete_positions=True,
#     )
#
#     options = gce.PowerFlowOptions(gce.SolverType.NR,
#                                    verbose=0,
#                                    control_q=False,
#                                    retry_with_other_methods=False)
#
#     for grid_file, results_file in files:
#         print(grid_file, end=' ')
#
#         # load the grid
#         file_open = FileOpen(file_name=[bd_set, os.path.join(cgmes_folder, grid_file)],
#                              options=file_open_options)
#         main_circuit = file_open.open()
#         power_flow_res = gce.power_flow(grid=main_circuit, options=options)
#         pf_df = power_flow_res.get_bus_df()
#
#         # load the associated results file
#         df_v = pd.read_excel(os.path.join(results_folder, results_file), sheet_name='Vabs', index_col=0)
#
#         v_psse = df_v.values[:, 0]
#
#         v_gc = np.abs(power_flow_res.voltage)
#         v_gc = v_gc[0:len(v_psse)]       # for debug
#
#         v_ok = np.allclose(v_gc, v_psse, atol=1e-6)
#
#         if not v_ok:
#             print(f'power flow voltages test for {grid_file} failed')
#             print(v_gc)
#             print(v_psse)
#             print(pf_df)
#         else:
#             print(f'power flow voltages test for {grid_file} ok')
#
#         assert v_ok
