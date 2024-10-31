# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import numpy as np
import pandas as pd
import GridCalEngine.api as gce

pd.set_option('display.max_colwidth', None)


def tuc_17() -> None:
    """
    This test load two supposedly equivalent grids and compared their internal structures and their power flow
    """

    test_folder = os.path.join("..", "..", "tests")

    # load IEEE14 ------------------------------------------------------------------------------------------------------
    grid1 = gce.open_file(filename=os.path.join("..", "..", "tests", "data", "grids", "RAW", "IEEE 14 bus.raw"))
    nc1 = gce.compile_numerical_circuit_at(grid1)
    pf_res1 = gce.power_flow(grid1)

    # we need to hack it a bit: add substations and voltage levels
    gce.detect_substations(grid=grid1)

    # save the model in CGMES ------------------------------------------------------------------------------------------

    # path to the boundary set
    bd_set = os.path.join(test_folder, "data", "grids", "CGMES_2_4_15",
                          "TestConfigurations_packageCASv2.0", 'MicroGrid', 'BaseCase_BC',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_BD_v2.zip')

    gce.save_cgmes_file(grid=grid1,
                        filename="IEEE14.zip",
                        cgmes_boundary_set_path=bd_set,
                        cgmes_version=gce.CGMESVersions.v3_0_0,
                        pf_results=pf_res1)

    # load again from CGMES into a new grid object
    grid2 = gce.open_file(filename=["IEEE14.zip", bd_set])
    nc2 = gce.compile_numerical_circuit_at(grid2)
    pf_res2 = gce.power_flow(grid2)

    # TUC 17.1 compare structures (Ybus, Sbus, etc...)
    ok_nc, logger_nc = nc1.compare(nc2)

    if not ok_nc:
        logger_nc.print("CGMES roundtrip comparison with the original")
        logger_nc.to_xlsx("tuc_17_1_ieee14.xlsx")
    else:
        print("TUC 17.1 ok")

    # load a CGMES grid made with CImConverter -------------------------------------------------------------------------
    grid3 = gce.open_file(filename=[os.path.join(test_folder, "data", "grids", "CGMES_2_4_15", "IEEE 14 bus.zip"),
                                    bd_set])
    nc3 = gce.compile_numerical_circuit_at(grid3)
    pf_res3 = gce.power_flow(grid3)

    # TUC 17.1 compare structures (Ybus, Sbus, etc...)
    ok_nc3, logger_nc3 = nc1.compare(nc3)

    if not ok_nc3:
        logger_nc3.print("CGMES cim-converter comparison with the original")
        logger_nc3.to_xlsx("tuc_17_1_ieee14_cim_converter.xlsx")
    else:
        print("TUC Cimconverter 17.1 ok")

    # ------------------------------------------------------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------------------------------------------------------
    # load the associated results file
    results_file = os.path.join(test_folder, 'data', 'results', 'IEEE 14 bus.sav.xlsx')
    df_v = pd.read_excel(results_file, sheet_name='Vabs', index_col=0)

    # TUC 17.2 compare power flows
    df1 = pf_res1.get_bus_df()
    df2 = pf_res2.get_bus_df()
    df3 = pf_res3.get_bus_df()
    diff12 = df1 - df2
    diff13 = df1 - df3

    print("\nGrid 1 (PSSe raw)",
          "Vm ok:", np.allclose(df1['Vm'].values, df_v.values[:, 0]))
    print(pf_res1.get_bus_df())

    print("\nGrid 2 (CGMES - round-tripped)",
          "Vm ok:", np.allclose(df2['Vm'].values, df_v.values[:, 0]))
    print(pf_res2.get_bus_df())

    print("\nGrid 3 (CGMES - from Cim-converter)",
          "Vm ok:", np.allclose(df3['Vm'].values, df_v.values[:, 0]))
    print(pf_res3.get_bus_df())

    print("\nDifference raw to GridCal CGMES")
    print(diff12)
    print("max err:", np.max(np.abs(diff12.values)))

    print("\nDifference raw to Cim-converter CGMES")
    print(diff13)
    print("max err:", np.max(np.abs(diff13.values)))


if __name__ == '__main__':
    tuc_17()
