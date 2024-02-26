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

from warnings import warn
import numpy as np
from typing import Tuple, Dict, List
import json
import pandas as pd
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import SolverType
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_ts_results import PowerFlowTimeSeriesResults
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.DataStructures.bus_data import BusData
from GridCalEngine.DataStructures.load_data import LoadData
from GridCalEngine.DataStructures.generator_data import GeneratorData
from GridCalEngine.DataStructures.battery_data import BatteryData
from GridCalEngine.DataStructures.branch_data import BranchData
from GridCalEngine.DataStructures.hvdc_data import HvdcData
from GridCalEngine.DataStructures.shunt_data import ShuntData
import GridCalEngine.Devices as dev

try:
    # to be installed with <pip install gurobi-optimods>
    # https://gurobi-optimization-gurobi-optimods.readthedocs-hosted.com/en/stable/mods/opf/opf.html
    from gurobi_optimods import datasets
    from gurobi_optimods import opf

    GUROBI_OPTIMODS_AVAILABLE = True
except ImportError as e:
    GUROBI_OPTIMODS_AVAILABLE = False


def solve_acopf(case: Dict) -> Dict:
    """
    Solve ACOPF
    :param case:
    :return:
    """
    res = opf.solve_opf(case, opftype="AC")
    return res


if __name__ == '__main__':
    import GridCalEngine as gce
    fname = r'/home/santi/matpower8.0b1/data/case9_gurobi_test.m'

    # Gurobi
    case_ = gce.get_matpower_case_data(fname, force_linear_cost=True)
    result_optimods = solve_acopf(case_)

    print("Bus res optimod\n", pd.DataFrame(data=result_optimods['bus']))
    print("Branch res optimod\n", pd.DataFrame(data=result_optimods['branch']))
    print("Gen res optimod\n", pd.DataFrame(data=result_optimods['gen']))

    # GridCal + Newton
    # grid = gce.FileOpen(fname).open()
    # pf_options = gce.PowerFlowOptions(tolerance=1e-6)
    # options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.AC_OPF,
    #                                       power_flow_options=pf_options)
    # acopf_driver = gce.OptimalPowerFlowDriver(grid=grid, options=options, engine=gce.EngineType.NewtonPA)
    # acopf_driver.run()
    # gc_res = acopf_driver.results

    print()
