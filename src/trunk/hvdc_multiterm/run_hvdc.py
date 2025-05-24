import os
from typing import Tuple
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_generalized_formulation import PfGeneralizedFormulation
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
import GridCalEngine.api as gce
import numpy as np


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
        use_stored_guess=True,
        bus_dict=None,
        areas_dict=None,
        control_taps_modules=options.control_taps_modules,
        control_taps_phase=options.control_taps_phase,
        control_remote_voltage=options.control_remote_voltage,
    )

    islands = nc.split_into_islands(consider_hvdc_as_island_links=False)
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


def run_hvdc_multiterminal() -> None:
    """
    Try the HVDC multiterminal case through scripting
    """

    # grid = gce.open_file("src/trunk/hvdc_multiterm/8bus_v1.gridcal")
    # fname = os.path.join('src', 'trunk', 'hvdc_multiterm', '8bus_v1.gridcal')
    # fname = os.path.join('src', 'trunk', 'hvdc_multiterm', 'vsc1.gridcal')
    # fname = os.path.join('src', 'trunk', 'hvdc_multiterm', 'simple_v1.gridcal')
    # fname = os.path.join('src', 'trunk', 'hvdc_multiterm', 'simple_v2.gridcal')
    fname = os.path.join('src', 'trunk', 'hvdc_multiterm', 'vsc_debug2.gridcal')
    # fname = os.path.join('src', 'trunk', 'hvdc_multiterm', 'debug_controls.gridcal')
    grid = gce.FileOpen(fname).open()

    options = PowerFlowOptions(control_q=False, use_stored_guess=True, max_iter=25)
    problem, solution = solve_generalized(grid=grid, options=options)

    print(f"Converged: {solution.converged}")
    print(f"Iterations: {solution.iterations}")
    print(f"Vm: {np.abs(solution.V)}")
    print(f"Va: {np.angle(solution.V, deg=False)}")

    return None


if __name__ == "__main__":
    run_hvdc_multiterminal()
