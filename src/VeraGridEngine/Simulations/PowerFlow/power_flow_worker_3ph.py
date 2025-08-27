# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
from typing import Union, Dict, Tuple, TYPE_CHECKING

from VeraGridEngine.enumerations import SolverType
from VeraGridEngine.basic_structures import Logger, ConvergenceReport
from VeraGridEngine.Simulations.PowerFlow.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation_3ph import (PfBasicFormulation3Ph,
                                                                                        expand3ph,
                                                                                        expandVoltage3ph)
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.powell_fx import powell_fx
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.levenberg_marquadt_fx import levenberg_marquardt_fx
from VeraGridEngine.Topology.simulation_indices import SimulationIndices
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Aggregation.area import Area
from VeraGridEngine.basic_structures import CxVec, Vec

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGridEngine.Compilers.circuit_to_data import VALID_OPF_RESULTS


def __solve_island_limited_support_3ph(island: NumericalCircuit,
                                       indices: SimulationIndices,
                                       options: PowerFlowOptions,
                                       V0: CxVec,
                                       S_base: CxVec,
                                       Shvdc: Vec,
                                       logger=Logger()) -> Tuple[NumericPowerFlowResults, ConvergenceReport]:
    """
    Run a power flow simulation using the selected method (no outer loop controls).
    This routine supports delete voltage controls,and Hvdc links through external injections (Shvdc)
    Also requires grids to be split by HvdcLines
    :param island: SnapshotData circuit, this ensures on-demand admittances computation
    :param indices: SimulationIndices
    :param options: PowerFlow options
    :param V0: Array of initial voltages
    :param S_base: Array of power Injections
    :param Shvdc: Array of power injections due t the HVDC lines (only used in some algorithms)
    :param logger: Logger
    :return: NumericPowerFlowResults
    """

    logger.add_info('Using the complete support power flow method')

    report = ConvergenceReport()
    if options.retry_with_other_methods:
        solver_list = [SolverType.NR,
                       SolverType.PowellDogLeg,
                       SolverType.LM]

        if options.solver_type in solver_list:
            solver_list.remove(options.solver_type)

        solvers = [options.solver_type] + solver_list
    else:
        # No retry selected
        solvers = [options.solver_type]

    # set worked = false to enter the loop
    solver_idx = 0

    # set the initial value
    Qmax, Qmin = island.get_reactive_power_limits()
    S0: CxVec = Shvdc + S_base  # already for 3-phase

    if len(indices.vd) == 0:
        solution = NumericPowerFlowResults(V=np.zeros(len(S0) * 3, dtype=complex),
                                           Scalc=S0,
                                           m=expand3ph(island.active_branch_data.tap_module),
                                           tau=expand3ph(island.active_branch_data.tap_angle),
                                           Sf=np.zeros(island.nbr * 3, dtype=complex),
                                           St=np.zeros(island.nbr * 3, dtype=complex),
                                           If=np.zeros(island.nbr * 3, dtype=complex),
                                           It=np.zeros(island.nbr * 3, dtype=complex),
                                           loading=np.zeros(island.nbr * 3, dtype=complex),
                                           losses=np.zeros(island.nbr * 3, dtype=complex),
                                           Pf_vsc=np.zeros(island.nvsc, dtype=float),
                                           St_vsc=np.zeros(island.nvsc * 3, dtype=complex),
                                           If_vsc=np.zeros(island.nvsc, dtype=float),
                                           It_vsc=np.zeros(island.nvsc, dtype=complex),
                                           losses_vsc=np.zeros(island.nvsc, dtype=float),
                                           loading_vsc=np.zeros(island.nvsc, dtype=float),
                                           Sf_hvdc=np.zeros(island.nhvdc, dtype=complex),
                                           St_hvdc=np.zeros(island.nhvdc, dtype=complex),
                                           losses_hvdc=np.zeros(island.nhvdc, dtype=complex),
                                           loading_hvdc=np.zeros(island.nhvdc, dtype=complex),
                                           converged=False,
                                           norm_f=1e200,
                                           iterations=0,
                                           elapsed=0)

        # method, converged: bool, error: float, elapsed: float, iterations: int
        report.add(method=SolverType.NoSolver, converged=True, error=0.0, elapsed=0.0, iterations=0)
        logger.add_error('Not solving power flow because there is no slack bus')
        return solution, report

    else:

        final_solution = NumericPowerFlowResults(V=V0,
                                                 converged=False,
                                                 norm_f=1e200,
                                                 Scalc=S0,
                                                 m=expand3ph(island.active_branch_data.tap_module),
                                                 tau=expand3ph(island.active_branch_data.tap_angle),
                                                 Sf=np.zeros(island.nbr * 3, dtype=complex),
                                                 St=np.zeros(island.nbr * 3, dtype=complex),
                                                 If=np.zeros(island.nbr * 3, dtype=complex),
                                                 It=np.zeros(island.nbr * 3, dtype=complex),
                                                 loading=np.zeros(island.nbr * 3, dtype=complex),
                                                 losses=np.zeros(island.nbr * 3, dtype=complex),
                                                 Pf_vsc=np.zeros(island.nvsc, dtype=float),
                                                 St_vsc=np.zeros(island.nvsc * 3, dtype=complex),
                                                 If_vsc=np.zeros(island.nvsc, dtype=float),
                                                 It_vsc=np.zeros(island.nvsc * 3, dtype=complex),
                                                 losses_vsc=np.zeros(island.nvsc, dtype=float),
                                                 loading_vsc=np.zeros(island.nvsc, dtype=float),
                                                 Sf_hvdc=np.zeros(island.nhvdc, dtype=complex),
                                                 St_hvdc=np.zeros(island.nhvdc, dtype=complex),
                                                 losses_hvdc=np.zeros(island.nhvdc, dtype=complex),
                                                 loading_hvdc=np.zeros(island.nhvdc, dtype=complex),
                                                 iterations=0,
                                                 elapsed=0)

        while solver_idx < len(solvers) and not final_solution.converged:
            # get the solver
            solver_type = solvers[solver_idx]

            if solver_type == SolverType.LM:

                problem = PfBasicFormulation3Ph(V0=final_solution.V,
                                                S0=S0,
                                                Qmin=Qmin,
                                                Qmax=Qmax,
                                                nc=island,
                                                options=options,
                                                logger=logger)

                solution = levenberg_marquardt_fx(problem=problem,
                                                  tol=options.tolerance,
                                                  max_iter=options.max_iter,
                                                  verbose=options.verbose,
                                                  logger=logger)

            elif solver_type == SolverType.NR:

                problem = PfBasicFormulation3Ph(V0=final_solution.V,
                                                S0=S0,
                                                Qmin=Qmin,
                                                Qmax=Qmax,
                                                nc=island,
                                                options=options,
                                                logger=logger)

                solution = newton_raphson_fx(problem=problem,
                                             tol=options.tolerance,
                                             max_iter=options.max_iter,
                                             trust=options.trust_radius,
                                             verbose=options.verbose,
                                             logger=logger)

            elif solver_type == SolverType.PowellDogLeg:

                problem = PfBasicFormulation3Ph(V0=final_solution.V,
                                                S0=S0,
                                                Qmin=Qmin,
                                                Qmax=Qmax,
                                                nc=island,
                                                options=options,
                                                logger=logger)

                solution = powell_fx(problem=problem,
                                     tol=options.tolerance,
                                     max_iter=options.max_iter,
                                     trust=options.trust_radius,
                                     verbose=options.verbose,
                                     logger=logger)

            else:
                # for any other method, raise exception
                raise Exception(solver_type.value + ' Not supported in power flow mode')

            # record the solution type
            solution.method = solver_type

            # record the method used, if it improved the solution
            if abs(solution.norm_f) < abs(final_solution.norm_f):
                report.add(method=solver_type,
                           converged=solution.converged,
                           error=solution.norm_f,
                           elapsed=solution.elapsed,
                           iterations=solution.iterations)

                if solution.method in [SolverType.Linear, SolverType.LACPF]:
                    # if the method is linear, we do not check the solution quality
                    final_solution = solution
                else:
                    # if the method is supposed to be exact, we check the solution quality
                    if abs(solution.norm_f) < 0.1:
                        final_solution = solution
                    else:
                        logger.add_info('Tried solution is garbage',
                                        solver_type.value,
                                        value="{:.4e}".format(solution.norm_f),
                                        expected_value=0.1)
            else:
                logger.add_info('Tried solver but it did not improve the solution',
                                solver_type.value,
                                value="{:.4e}".format(solution.norm_f),
                                expected_value=final_solution.norm_f)

            # next solver
            solver_idx += 1

        if not final_solution.converged:
            logger.add_error('Did not converge, even after retry!',
                             device='Error',
                             value="{:.4e}".format(final_solution.norm_f),
                             expected_value=f"<{options.tolerance}")

        if final_solution.tap_module is None:
            final_solution.tap_module = island.active_branch_data.tap_module

        if final_solution.tap_angle is None:
            final_solution.tap_angle = island.active_branch_data.tap_angle

        return final_solution, report


def __multi_island_pf_nc_limited_support_3ph(nc: NumericalCircuit,
                                             options: PowerFlowOptions,
                                             logger: Logger | None = None,
                                             V_guess: Union[CxVec, None] = None,
                                             Sbus_input: Union[CxVec, None] = None) -> PowerFlowResults3Ph:
    """
    Multiple islands power flow (this is the most generic power flow function)

    multi_island_pf
      |-> multi_island_pf_nc
                |-> split_into_islands  (Deals with HvdcLine injections)
                        |-> for each island:
                                |-> single_island_pf
                                        |-> solve

    :param nc: SnapshotData instance
    :param options: PowerFlowOptions instance
    :param logger: logger
    :param V_guess: voltage guess
    :param Sbus_input: Use this power injections if provided
    :return: PowerFlowResults instance
    """
    if logger is None:
        logger = Logger()

    # declare results
    results = PowerFlowResults3Ph(
        n=nc.nbus * 3,
        m=nc.nbr * 3,
        n_hvdc=nc.nhvdc,
        n_vsc=nc.nvsc,
        n_gen=nc.ngen,
        n_batt=nc.nbatt,
        n_sh=nc.nshunt,
        bus_names=nc.bus_data.get_3ph_names(),
        branch_names=nc.passive_branch_data.get_3ph_names(),
        hvdc_names=nc.hvdc_data.names,
        vsc_names=nc.vsc_data.names,
        gen_names=nc.generator_data.names,
        batt_names=nc.battery_data.names,
        sh_names=nc.shunt_data.names,
        bus_types=nc.bus_data.bus_types,
    )

    # compose the HVDC power Injections
    # since the power flow methods don't support HVDC directly, we need this step
    Shvdc, Losses_hvdc, Pf_hvdc, Pt_hvdc, loading_hvdc, n_free = nc.hvdc_data.get_power(
        Sbase=nc.Sbase,
        theta=np.zeros(nc.nbus),
    )

    # compute islands
    islands = nc.split_into_islands(ignore_single_node_islands=options.ignore_single_node_islands,
                                    consider_hvdc_as_island_links=False,
                                    logger=logger)

    for i, island in enumerate(islands):

        Sbus_base = island.get_power_injections_pu()
        indices = island.get_simulation_indices(Sbus=Sbus_base)

        if len(indices.vd) > 0:

            V0 = island.bus_data.Vbus if V_guess is None else V_guess[island.bus_data.original_idx]
            S_base = Sbus_base if Sbus_input is None else Sbus_input[island.bus_data.original_idx]
            Shvdc = Shvdc[island.bus_data.original_idx]

            # call the numerical methods
            solution, report = __solve_island_limited_support_3ph(
                island=island,
                indices=indices,
                options=options,
                V0=expandVoltage3ph(V0),
                S_base=expand3ph(S_base),
                Shvdc=expand3ph(Shvdc),
                logger=logger
            )

            # merge the results from this island
            results.apply_from_island(
                results=solution,
                b_idx=island.bus_data.original_idx,
                br_idx=island.passive_branch_data.original_idx,
                hvdc_idx=island.hvdc_data.original_idx,
                vsc_idx=island.vsc_data.original_idx
            )
            results.convergence_reports.append(report)

        else:
            logger.add_info('No slack nodes in the island', str(i))

    # Compile HVDC results (available for the complete grid since HVDC line as
    # formulated are split objects
    # Pt is the "generation" at the sending point
    results.Pf_hvdc = - Pf_hvdc * nc.Sbase  # we change the sign to keep the sign convention with AC lines
    results.Pt_hvdc = - Pt_hvdc * nc.Sbase  # we change the sign to keep the sign convention with AC lines
    results.loading_hvdc = loading_hvdc
    results.losses_hvdc = Losses_hvdc * nc.Sbase

    return results


def multi_island_pf_nc_3ph(nc: NumericalCircuit,
                           options: PowerFlowOptions,
                           logger: Logger | None = None,
                           V_guess: Union[CxVec, None] = None,
                           Sbus_input: Union[CxVec, None] = None) -> PowerFlowResults3Ph:
    """
    Multiple islands power flow (this is the most generic power flow function)
    :param nc: SnapshotData instance
    :param options: PowerFlowOptions instance
    :param logger: logger
    :param V_guess: voltage guess
    :param Sbus_input: Use this power injections if provided (in p.u.)
    :return: PowerFlowResults instance
    """
    if logger is None:
        logger = Logger()

    results = __multi_island_pf_nc_limited_support_3ph(
        nc=nc,
        options=options,
        logger=logger,
        V_guess=V_guess,
        Sbus_input=Sbus_input,
    )

    # expand voltages if there was a bus topology reduction
    # if nc.topology_performed:
    #     results.voltage = nc.propagate_bus_result(results.voltage)

    # do the reactive power partition and store the values
    # __split_reactive_power_into_devices(nc=nc, Qbus=results.Sbus.imag, results=results)

    results.three_phase = True
    return results


def multi_island_pf_3ph(multi_circuit: MultiCircuit,
                        options: PowerFlowOptions,
                        opf_results: VALID_OPF_RESULTS | None = None,
                        t: Union[int, None] = None,
                        logger: Logger = Logger(),
                        bus_dict: Union[Dict[Bus, int], None] = None,
                        areas_dict: Union[Dict[Area, int], None] = None) -> PowerFlowResults3Ph:
    """
    Multiple islands power flow (this is the most generic power flow function)
    :param multi_circuit: MultiCircuit instance
    :param options: PowerFlowOptions instance
    :param opf_results: OPF results, to be used if not None
    :param t: time step, if None, the snapshot is compiled
    :param logger: list of events to add to
    :param bus_dict: Dus object to index dictionary
    :param areas_dict: Area to area index dictionary
    :return: PowerFlowResults instance
    """

    nc = compile_numerical_circuit_at(
        circuit=multi_circuit,
        t_idx=t,
        apply_temperature=options.apply_temperature_correction,
        branch_tolerance_mode=options.branch_impedance_tolerance_mode,
        opf_results=opf_results,
        use_stored_guess=options.use_stored_guess,
        bus_dict=bus_dict,
        areas_dict=areas_dict,
        control_taps_modules=options.control_taps_modules,
        control_taps_phase=options.control_taps_phase,
        control_remote_voltage=options.control_remote_voltage,
        logger=logger,
        fill_three_phase=True
    )

    res = multi_island_pf_nc_3ph(nc=nc, options=options, logger=logger)

    return res
