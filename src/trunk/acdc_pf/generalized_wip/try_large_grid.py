# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from typing import Tuple
import os
import pandas as pd
import numpy as np
from GridCalEngine.basic_structures import Logger
from GridCalEngine.IO.file_handler import FileOpen
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_options import SolverType
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
import GridCalEngine.api as gce
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_generalized_formulation import PfGeneralizedFormulation
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_advanced_formulation import PfAdvancedFormulation
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_FOLDER = os.path.join(SCRIPT_DIR, "..", "..", "..", "tests")


def solve_generalized(grid: gce.MultiCircuit,
                      options: PowerFlowOptions,
                      generalized: bool=True) -> Tuple[PfGeneralizedFormulation, NumericPowerFlowResults]:
    """

    :param grid:
    :param options:
    :param generalized:
    :return:
    """
    nc = gce.compile_numerical_circuit_at(
        grid,
        t_idx=None,
        apply_temperature=False,
        branch_tolerance_mode=gce.BranchImpedanceMode.Specified,
        opf_results=None,
        use_stored_guess=False,
        bus_dict=None,
        areas_dict=None,
        control_taps_modules=options.control_taps_modules,
        control_taps_phase=options.control_taps_phase,
        control_remote_voltage=options.control_remote_voltage,
    )

    islands = nc.split_into_islands(consider_hvdc_as_island_links=True)
    logger = Logger()

    island = islands[0]

    Vbus = island.bus_data.Vbus
    S0 = island.get_power_injections_pu()
    I0 = island.get_current_injections_pu()
    Y0 = island.get_admittance_injections_pu()
    Qmax_bus, Qmin_bus = island.get_reactive_power_limits()

    if generalized:
        problem = PfGeneralizedFormulation(V0=Vbus,
                                       S0=S0,
                                       I0=I0,
                                       Y0=Y0,
                                       Qmin=Qmin_bus,
                                       Qmax=Qmax_bus,
                                       nc=island,
                                       options=options,
                                       logger=logger)
    else:
        problem = PfAdvancedFormulation(V0=Vbus,
                                    S0=S0,
                                    I0=I0,
                                    Y0=Y0,
                                    Qmin=Qmin_bus,
                                    Qmax=Qmax_bus,
                                    nc=island,
                                    options=options,
                                    logger=logger)

    solution = newton_raphson_fx(problem=problem,
                                 tol=options.tolerance,
                                 max_iter=options.max_iter,
                                 trust=options.trust_radius,
                                 verbose=options.verbose,
                                 logger=logger)

    logger.print("Logger")

    return problem, solution


def try_power_flow() -> None:
    """
    Check that a transformer can regulate the voltage at a bus
    """
    # fname = os.path.join('/Users', 'josep', 'Documents', 'Grids', '202206011015_vsc.gridcal')
    fname = os.path.join('/Users', 'josep', 'Documents', 'Grids', '202206011015_original.gridcal')
    # fname = os.path.join('/Users', 'josep', 'Documents', 'Grids', '202206011015_off_shunts.gridcal')
    # fname = os.path.join('/Users', 'josep', 'Documents', 'Grids', '202206011015_on_shunts.gridcal')
    # fname = os.path.join('/Users', 'josep', 'Documents', 'Grids', '202206011015_no_shunts.gridcal')
    # fname = os.path.join('/Users', 'josep', 'Documents', 'Grids', '202206011015_vsc_v2.gridcal')

    grid = gce.open_file(fname)

    options = PowerFlowOptions(solver_type=gce.SolverType.NR,
                               verbose=1,
                               control_q=False,
                               retry_with_other_methods=False,
                               initialize_with_existing_solution=False,
                               control_taps_phase=True,
                               control_taps_modules=False,
                               tolerance=1e-5,
                               max_iter=80)

    problem, solution = solve_generalized(grid=grid, options=options, generalized=True)
    # problem, solution = solve_generalized(grid=grid, options=options, generalized=False)

    print(solution.elapsed)

    n_act = 0
    n_inact = 0
    for bus in grid.buses:
        if bus.active:
            n_act += 1
        else:
            n_inact += 1

    print(n_act, n_inact)
    print(solution.norm_f)

    assert solution.converged


if __name__ == "__main__":
    try_power_flow()