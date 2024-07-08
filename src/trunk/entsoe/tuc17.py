# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import os
import numpy as np
import GridCalEngine.api as gce


def tuc_17() -> None:
    """
    This test load two supposedly equivalent grids and compared their internal structures and their power flow
    """

    # path to the boundary set
    bd_set = os.path.join("..", "..", "tests", "data", "grids", "CGMES_2_4_15",
                          "TestConfigurations_packageCASv2.0", 'MicroGrid', 'BaseCase_BC',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_BD_v2.zip')

    # load any model, IEEE14 in this case
    grid1 = gce.open_file(filename=os.path.join("..", "..", "tests", "data", "grids", "RAW", "IEEE 14 bus.raw"))
    nc1 = gce.compile_numerical_circuit_at(grid1)
    pf_res1 = gce.power_flow(grid1)

    # we need to hack it a bit: add substations and voltage levels
    gce.detect_substations(grid=grid1)

    # save the model in CGMES
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
        logger_nc.print()
        logger_nc.to_xlsx("tuc_17_1_ieee14.xlsx")
    else:
        print("TUC 17.1 ok")

    # TUC 17.2 compare power flows
    df1 = pf_res1.get_bus_df()
    df2 = pf_res2.get_bus_df()

    diff = df1 - df2

    print("Grid 1")
    print(pf_res1.get_bus_df())

    print("Grid 2")
    print(pf_res2.get_bus_df())

    print("Difference")
    print(diff)


if __name__ == '__main__':
    tuc_17()
