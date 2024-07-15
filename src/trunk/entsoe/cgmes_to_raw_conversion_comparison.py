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


def tuc_17_1() -> None:
    """
    This test load two supposedly equivalent grids and compared their internal structures
    """
    base_folder = os.path.join("..", "..", "tests", "data", "grids", "CGMES_2_4_15",
                               "TestConfigurations_packageCASv2.0")

    logger = gce.Logger()

    lst = [
        os.path.join(base_folder, 'MicroGrid', 'BaseCase_BC', 'CGMES_v2.4.15_MicroGridTestConfiguration_BD_v2.zip'),
        os.path.join(base_folder, 'MicroGrid', 'BaseCase_BC', 'CGMES_v2.4.15_MicroGridTestConfiguration_BC_BE_v2.zip'),
    ]

    grid1 = gce.open_file(filename=lst)

    grid2 = gce.open_file(filename=os.path.join(base_folder, 'MicroGrid', 'BaseCase_BC', 'BE_psse33_cimconverter.raw'))

    # does not make sense because ID?s are not respected
    # ok, logger = grid1.compare_circuits(grid2)
    #
    # if not ok:
    #     logger.print()

    nc1 = gce.compile_numerical_circuit_at(grid1)
    nc2 = gce.compile_numerical_circuit_at(grid2)

    ok_nc, logger_nc = nc1.compare(nc2)

    if not ok_nc:
        logger_nc.print()
        # logger_nc.to_xlsx("tuc_17_1.xlsx")
    else:
        print("TUC 17.1 ok")


def tuc_17_2() -> None:
    """
    This test load two supposedly equivalent grids and compared their internal structures
    """
    base_folder = os.path.join("..", "..", "tests", "data", "grids", "CGMES_2_4_15",
                               "TestConfigurations_packageCASv2.0")

    logger = gce.Logger()

    lst = [
        os.path.join(base_folder, 'MicroGrid', 'BaseCase_BC', 'CGMES_v2.4.15_MicroGridTestConfiguration_BD_v2.zip'),
        os.path.join(base_folder, 'MicroGrid', 'BaseCase_BC', 'CGMES_v2.4.15_MicroGridTestConfiguration_BC_BE_v2.zip'),
    ]

    grid1 = gce.open_file(filename=lst)

    grid2 = gce.open_file(filename=os.path.join(base_folder, 'MicroGrid', 'BaseCase_BC', 'BE_psse33_cimconverter.raw'))

    # does not make sense because ID?s are not respected
    # ok, logger = grid1.compare_circuits(grid2)
    #
    # if not ok:
    #     logger.print()

    res1 = gce.power_flow(grid1)
    res2 = gce.power_flow(grid2)

    df1 = res1.get_bus_df()
    df2 = res2.get_bus_df()

    diff = df1 - df2

    print("Grid 1")
    print(res1.get_bus_df())

    print("Grid 2")
    print(res2.get_bus_df())

    print("Difference")
    print(diff)

    # if not ok:
    #     print("Grid 1")
    #     print(res1.get_bus_df())
    #     print("Grid 2")
    #     print(res2.get_bus_df())
    # else:
    #     print("TUC 17.2 ok")


if __name__ == '__main__':
    tuc_17_1()
    tuc_17_2()
