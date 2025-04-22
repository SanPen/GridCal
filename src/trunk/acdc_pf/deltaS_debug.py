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
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx


def solve_generalized(grid: gce.MultiCircuit,
                      options: PowerFlowOptions) -> Tuple[PfGeneralizedFormulation, NumericPowerFlowResults]:
    """

    :param grid:
    :param options:
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
    problem = PfGeneralizedFormulation(V0=Vbus,
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

def test_power_flow_12bus_acdc() -> None:
    """
    Check that a transformer can regulate the voltage at a bus
    """
    fname = os.path.join('src', 'tests', 'data', 'grids', 'AC-DC with all and DCload.gridcal')

    grid = gce.open_file(fname)

    expected_v = np.array([1.+0.j,
                           0.99993477-0.01142182j,
                           0.981475 -0.02798462j,
                           0.99961098-0.02789078j,
                           0.9970314 +0.j, 
                           0.9921219 +0.j, 
                           1.+0.j,
                           0.9967762 +0.j,
                           0.99174229-0.02349737j,
                           0.99263056-0.02449658j,
                           1.+0.j,
                           0.99972273-0.0235469j,
                           0.99752297-0.01554718j,
                           0.99999114-0.00421027j,
                           0.99937536-0.03533967j,
                           0.99964957-0.02647153j,
                           0.99799207+0.j])

    # ------------------------------------------------------------------------------------------------------------------
    # for solver_type in [SolverType.NR, SolverType.LM, SolverType.PowellDogLeg]:
    # run power flow

    options = PowerFlowOptions(solver_type=gce.SolverType.NR,
                               verbose=1,
                               control_q=False,
                               retry_with_other_methods=False,
                               control_taps_phase=True,
                               max_iter=80)

    problem, solution = solve_generalized(grid=grid, options=options)

    assert np.allclose(expected_v, solution.V, atol=1e-6)

    assert grid.vsc_devices[0].control1_val == solution.Pf_vsc[0]
    assert grid.vsc_devices[0].control2_val == solution.St_vsc[0].imag

    assert grid.vsc_devices[1].control1_val == abs(solution.V[3])
    assert grid.vsc_devices[1].control2_val == solution.St_vsc[1].real

    assert grid.vsc_devices[2].control1_val == abs(solution.V[6])
    assert grid.vsc_devices[2].control2_val == solution.St_vsc[2].imag

    assert grid.vsc_devices[3].control1_val == solution.Pf_vsc[3] 
    assert grid.vsc_devices[3].control2_val == solution.St_vsc[3].imag

    assert grid.transformers2w[2].vset == abs(solution.V[13])

    assert grid.hvdc_lines[0].Pset == solution.Sf_hvdc[0].real

    assert solution.converged

def test_voltage_control_with_ltc() -> None:
    """
    Check that a transformer can regulate the voltage at a bus
    """
    fname = os.path.join('src', 'tests', 'data', 'grids', '5Bus_LTC_FACTS_Fig4.7.gridcal')

    grid = gce.open_file(fname)
    bus_dict = grid.get_bus_index_dict()
    ctrl_idx = bus_dict[grid.transformers2w[0].regulation_bus]

    for control_taps_modules in [True, False]:
        options = PowerFlowOptions(gce.SolverType.NR,
                                   verbose=1,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_modules=control_taps_modules,
                                   control_taps_phase=False,
                                   control_remote_voltage=False,
                                   apply_temperature_correction=False)

        problem, solution = solve_generalized(grid=grid, options=options)

        vm = np.abs(solution.V)

        print('LTC test case iterations: ', solution.iterations)

        assert solution.converged

        # check that the bus voltage module is the transformer voltage set point
        ok = np.isclose(vm[ctrl_idx], grid.transformers2w[0].vset, atol=options.tolerance)

        if control_taps_modules:
            assert ok
        else:
            assert not ok

def test_generator_Q_lims() -> None:
    """
    Check that we can shift the controls well when hitting Q limits
    """
    fname = os.path.join('src', 'tests', 'data', 'grids', '5Bus_LTC_FACTS_Fig4.7_Qlim.gridcal')

    grid = gce.open_file(fname)

    for control_q in [True]:
        options = PowerFlowOptions(gce.SolverType.NR,
                                   verbose=1,
                                   control_q=control_q,
                                   retry_with_other_methods=False,
                                   control_taps_modules=False,
                                   control_taps_phase=False,
                                   control_remote_voltage=False,
                                   apply_temperature_correction=False,
                                   distributed_slack=False)

        problem, solution = solve_generalized(grid=grid, options=options)

        # check that the bus Q is at the limit
        qbus = solution.Scalc[3].imag
        ok = np.isclose(qbus, grid.generators[1].Qmin, atol=options.tolerance)
        print(qbus, grid.generators[1].Qmin, options.tolerance)
        if control_q:
            assert ok
        else:
            assert not ok

        assert solution.converged

if __name__ == "__main__":
    # test_voltage_control_with_ltc()
    # test_generator_Q_lims()
    test_power_flow_12bus_acdc()