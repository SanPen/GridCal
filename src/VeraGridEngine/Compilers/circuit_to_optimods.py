# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from warnings import warn
import numpy as np
from typing import Tuple, Dict, List
import json
import pandas as pd
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import SolverType
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.PowerFlow.power_flow_ts_results import PowerFlowTimeSeriesResults
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.DataStructures.bus_data import BusData
from VeraGridEngine.DataStructures.load_data import LoadData
from VeraGridEngine.DataStructures.generator_data import GeneratorData
from VeraGridEngine.DataStructures.battery_data import BatteryData
from VeraGridEngine.DataStructures.passive_branch_data import PassiveBranchData
from VeraGridEngine.DataStructures.hvdc_data import HvdcData
from VeraGridEngine.DataStructures.shunt_data import ShuntData
import VeraGridEngine.Devices as dev

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
    if GUROBI_OPTIMODS_AVAILABLE:
        res = opf.solve_opf(case, opftype="AC")
        return res
    else:
        raise ImportError("No gurobi optimization available")




if __name__ == '__main__':
    import VeraGridEngine as gce
    fname = r'/home/santi/matpower8.0b1/data/case9_gurobi_test.m'

    # Gurobi
    # case_ = gce.to_matpower(grid)
    case_ = gce.get_matpower_case_data(fname, force_linear_cost=True)
    result_optimods = solve_acopf(case_)

    print("Bus res optimod\n", pd.DataFrame(data=result_optimods['bus']))
    print("Branch res optimod\n", pd.DataFrame(data=result_optimods['branch']))
    print("Gen res optimod\n", pd.DataFrame(data=result_optimods['gen']))

    # VeraGrid + Newton
    # grid = gce.FileOpen(fname).open()
    # pf_options = gce.PowerFlowOptions(tolerance=1e-6)
    # options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.AC_OPF,
    #                                       power_flow_options=pf_options)
    # acopf_driver = gce.OptimalPowerFlowDriver(grid=grid, options=options, engine=gce.EngineType.NewtonPA)
    # acopf_driver.run()
    # gc_res = acopf_driver.results

