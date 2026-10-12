# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
from typing import Union, Dict, Tuple, TYPE_CHECKING

import VeraGridEngine.Simulations.PowerFlow as pflw
from VeraGridEngine.enumerations import SolverType, GeneratorControlMode, BusMode, GeneratorType, ShuntControlMode
from VeraGridEngine.basic_structures import Logger, ConvergenceReport
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation import PfBasicFormulation
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_full_acdc_with_negative_poles import PfAcDcWithNegativePoles
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (
    compute_asynchronous_generator_q,
    split_bus_quantity,
    split_reactive_power_between_generators_and_batteries,
    split_slack_bus_quantity_between_generators_and_batteries
)
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.powell_fx import powell_fx
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.levenberg_marquadt_fx import levenberg_marquardt_fx
from VeraGridEngine.Topology.simulation_indices import SimulationIndices
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import compute_slack_distribution
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.static_generator_droop import StaticGeneratorDroop
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Aggregation.area import Area
from VeraGridEngine.basic_structures import CxVec, Vec

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGridEngine.Compilers.circuit_to_data import VALID_OPF_RESULTS


def _get_generator_q_for_split(nc: NumericalCircuit, V: CxVec) -> Vec:
    """
    Return generator Q setpoints for result splitting, including voltage-dependent asynchronous machines.
    """
    q0_gen = nc.generator_data.q.copy()
    q_async = compute_asynchronous_generator_q(V=V,
                                               gen_bus_idx=nc.generator_data.bus_idx,
                                               gen_active=nc.generator_data.active,
                                               gen_types=nc.generator_data.tpe_int,
                                               Rs=nc.generator_data.Rs,
                                               Xs=nc.generator_data.Xs,
                                               Xm=nc.generator_data.Xm,
                                               Rr=nc.generator_data.Rr,
                                               Xr=nc.generator_data.Xr,
                                               P=nc.generator_data.p,
                                               Snom=nc.generator_data.snom)

    for gen_idx in range(nc.generator_data.nelm):
        if (nc.generator_data.active[gen_idx]
                and nc.generator_data.tpe_int[gen_idx] == GeneratorType.Asynchronous.idx()):
            q0_gen[gen_idx] = q_async[gen_idx]

    return q0_gen


def voltage_guess_is_usable(V: CxVec) -> bool:
    """
    Check whether a voltage guess can safely seed nonlinear sparse solvers.

    :param V: Voltage vector.
    :return: True if the voltage vector is finite and numerically bounded.
    """

    usable: bool = bool(np.all(np.isfinite(V)) and np.all(np.abs(V) < 1.0e6))

    return usable


def __solve_island_complete_support(nc: NumericalCircuit,
                                    indices: SimulationIndices,
                                    options: PowerFlowOptions,
                                    V0: CxVec,
                                    S0: CxVec,
                                    logger=Logger()) -> Tuple[NumericPowerFlowResults, ConvergenceReport]:
    """
    Run a power flow simulation using the selected method (no outer loop controls).
    This routine supports all controls, VSC's and Hvdc links
    Does not require grids to be split by HvdcLines
    :param nc: SnapshotData circuit, this ensures on-demand admittances computation
    :param indices: SimulationIndices
    :param options: PowerFlow options
    :param V0: Array of initial voltages
    :param S0: Array of power Injections
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
    Qmax, Qmin = nc.get_reactive_power_limits()
    I0 = nc.get_current_injections_pu()
    Y0 = nc.get_admittance_injections_pu()

    if len(indices.vd) == 0 or len(indices.no_slack) == 0:
        solution = NumericPowerFlowResults(V=np.zeros(len(S0), dtype=complex),
                                           Scalc=S0,
                                           m=nc.active_branch_data.tap_module,
                                           tau=nc.active_branch_data.tap_angle,
                                           Sf=np.zeros(nc.nbr, dtype=complex),
                                           St=np.zeros(nc.nbr, dtype=complex),
                                           If=np.zeros(nc.nbr, dtype=complex),
                                           It=np.zeros(nc.nbr, dtype=complex),
                                           loading=np.zeros(nc.nbr, dtype=complex),
                                           losses=np.zeros(nc.nbr, dtype=complex),
                                           Pfp_vsc=np.zeros(nc.nvsc, dtype=float),
                                           Pfn_vsc=np.zeros(nc.nvsc, dtype=float),
                                           St_vsc=np.zeros(nc.nvsc, dtype=complex),
                                           If_vsc=np.zeros(nc.nvsc, dtype=float),
                                           It_vsc=np.zeros(nc.nvsc, dtype=complex),
                                           losses_vsc=np.zeros(nc.nvsc, dtype=float),
                                           loading_vsc=np.zeros(nc.nvsc, dtype=float),
                                           Sf_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                           St_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                           losses_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                           loading_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                           converged=False,
                                           norm_f=1e200,
                                           iterations=0,
                                           elapsed=0)

        # method, converged: bool, error: float, elapsed: float, iterations: int
        report.add(method=SolverType.NoSolver, converged=True, error=0.0, elapsed=0.0, iterations=0)
        logger.add_error('Not solving power flow because there is no slack bus')
        return solution, report

    else:
        if voltage_guess_is_usable(V=V0):
            V0 = V0
        else:
            logger.add_warning("Ignoring unusable power flow voltage guess")
            V0 = nc.bus_data.Vbus

        final_solution = NumericPowerFlowResults(V=V0,
                                                 converged=False,
                                                 norm_f=1e200,
                                                 Scalc=S0,
                                                 m=nc.active_branch_data.tap_module,
                                                 tau=nc.active_branch_data.tap_angle,
                                                 Sf=np.zeros(nc.nbr, dtype=complex),
                                                 St=np.zeros(nc.nbr, dtype=complex),
                                                 If=np.zeros(nc.nbr, dtype=complex),
                                                 It=np.zeros(nc.nbr, dtype=complex),
                                                 loading=np.zeros(nc.nbr, dtype=complex),
                                                 losses=np.zeros(nc.nbr, dtype=complex),
                                                 Pfp_vsc=np.zeros(nc.nvsc, dtype=float),
                                                 Pfn_vsc=np.zeros(nc.nvsc, dtype=float),
                                                 St_vsc=np.zeros(nc.nvsc, dtype=complex),
                                                 If_vsc=np.zeros(nc.nvsc, dtype=float),
                                                 It_vsc=np.zeros(nc.nvsc, dtype=complex),
                                                 losses_vsc=np.zeros(nc.nvsc, dtype=float),
                                                 loading_vsc=np.zeros(nc.nvsc, dtype=float),
                                                 Sf_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                                 St_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                                 losses_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                                 loading_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                                 iterations=0,
                                                 elapsed=0)

        while solver_idx < len(solvers) and not final_solution.converged:
            # get the solver
            solver_type = solvers[solver_idx]

            if solver_type == SolverType.LM:

                problem = PfAcDcWithNegativePoles(V0=final_solution.V,
                                                  S0=S0,
                                                  I0=I0,
                                                  Y0=-Y0,
                                                  Qmin=Qmin,
                                                  Qmax=Qmax,
                                                  nc=nc,
                                                  options=options,
                                                  logger=logger)

                solution = levenberg_marquardt_fx(problem=problem,
                                                  tol=options.tolerance,
                                                  max_iter=options.max_iter,
                                                  verbose=options.verbose,
                                                  logger=logger)

            elif solver_type == SolverType.NR:

                problem = PfAcDcWithNegativePoles(V0=final_solution.V,
                                                  S0=S0,
                                                  I0=I0,
                                                  Y0=-Y0,
                                                  Qmin=Qmin,
                                                  Qmax=Qmax,
                                                  nc=nc,
                                                  options=options,
                                                  logger=logger)

                solution = newton_raphson_fx(problem=problem,
                                             tol=options.tolerance,
                                             max_iter=options.max_iter,
                                             trust=options.trust_radius,
                                             verbose=options.verbose,
                                             logger=logger)

            elif solver_type == SolverType.PowellDogLeg:

                problem = PfAcDcWithNegativePoles(V0=final_solution.V,
                                                  S0=S0,
                                                  I0=I0,
                                                  Y0=-Y0,
                                                  Qmin=Qmin,
                                                  Qmax=Qmax,
                                                  nc=nc,
                                                  options=options,
                                                  logger=logger)

                solution = powell_fx(problem=problem,
                                     tol=options.tolerance,
                                     max_iter=options.max_iter,
                                     trust=options.trust_radius,
                                     verbose=options.verbose,
                                     logger=logger)

            elif solver_type == SolverType.Linear:

                indices = nc.get_simulation_indices(Sbus=S0)
                lin_adm = nc.get_linear_admittance_matrices(indices=indices)

                # The HVDC devices have to enter as bus injections externally
                s_hvdc, losses_hvdc, pf_hvdc, pt_hvdc, load_hvdc, n_free_hvdc = nc.hvdc_data.get_power(
                    Sbase=nc.Sbase,
                    theta=np.zeros(nc.nbus)
                )

                solution = pflw.acdc_lin_pf(
                    nc=nc,
                    Bbus=lin_adm.Bbus,
                    Bf=lin_adm.Bf,
                    Gbus=lin_adm.Gbus,
                    Gf=lin_adm.Gf,
                    ac=indices.ac,
                    dc=indices.dc,
                    vd=indices.vd,
                    pv=indices.pv,
                    S0=S0 + s_hvdc,
                    I0=I0,
                    Y0=Y0,
                    V0=V0,
                    tau=nc.active_branch_data.tap_angle
                )

            else:
                # for any other method, raise exception
                logger.add_error('Solver not supported in power flow mode', value=solver_type.value)
                problem = PfAcDcWithNegativePoles(V0=final_solution.V,
                                                  S0=S0,
                                                  I0=I0,
                                                  Y0=-Y0,
                                                  Qmin=Qmin,
                                                  Qmax=Qmax,
                                                  nc=nc,
                                                  options=options,
                                                  logger=logger)

                solution = newton_raphson_fx(problem=problem,
                                             tol=options.tolerance,
                                             max_iter=options.max_iter,
                                             trust=options.trust_radius,
                                             verbose=options.verbose,
                                             logger=logger)

            # record the solution type
            solution.method = solver_type
            if np.isfinite(solution.norm_f) and solution.norm_f <= options.tolerance:
                solution.converged = True
            else:
                pass

            solution_is_usable: bool = bool(np.isfinite(solution.norm_f)
                                            and np.all(np.isfinite(solution.V))
                                            and np.all(np.abs(solution.V) < 1.0e6))

            # record the method used, if it improved the solution
            if solution_is_usable and abs(solution.norm_f) < abs(final_solution.norm_f):
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
            final_solution.tap_module = nc.active_branch_data.tap_module

        if final_solution.tap_angle is None:
            final_solution.tap_angle = nc.active_branch_data.tap_angle

        return final_solution, report


def __solve_island_limited_support(island: NumericalCircuit,
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

    logger.add_info('Using the limited support power flow method')

    report = ConvergenceReport()
    if options.retry_with_other_methods:
        solver_list = [SolverType.NR,
                       SolverType.PowellDogLeg,
                       SolverType.HELM,
                       SolverType.IWAMOTO,
                       SolverType.LM,
                       SolverType.LACPF]

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
    I0 = island.get_current_injections_pu()
    Y0 = island.get_admittance_injections_pu()

    Sbase_plus_hvdc: CxVec = S_base + Shvdc

    if len(indices.vd) == 0 or len(indices.no_slack) == 0:
        solution = NumericPowerFlowResults(V=np.zeros(len(S_base), dtype=complex),
                                           Scalc=Sbase_plus_hvdc,
                                           m=island.active_branch_data.tap_module,
                                           tau=island.active_branch_data.tap_angle,
                                           Sf=np.zeros(island.nbr, dtype=complex),
                                           St=np.zeros(island.nbr, dtype=complex),
                                           If=np.zeros(island.nbr, dtype=complex),
                                           It=np.zeros(island.nbr, dtype=complex),
                                           loading=np.zeros(island.nbr, dtype=complex),
                                           losses=np.zeros(island.nbr, dtype=complex),
                                           Pfp_vsc=np.zeros(island.nvsc, dtype=float),
                                           Pfn_vsc=np.zeros(island.nvsc, dtype=float),
                                           St_vsc=np.zeros(island.nvsc, dtype=complex),
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
        if voltage_guess_is_usable(V=V0):
            V0 = V0
        else:
            logger.add_warning("Ignoring unusable power flow voltage guess")
            V0 = island.bus_data.Vbus

        adm = island.get_admittance_matrices()

        final_solution = NumericPowerFlowResults(V=V0,
                                                 converged=False,
                                                 norm_f=1e200,
                                                 Scalc=Sbase_plus_hvdc,
                                                 m=island.active_branch_data.tap_module,
                                                 tau=island.active_branch_data.tap_angle,
                                                 Sf=np.zeros(island.nbr, dtype=complex),
                                                 St=np.zeros(island.nbr, dtype=complex),
                                                 If=np.zeros(island.nbr, dtype=complex),
                                                 It=np.zeros(island.nbr, dtype=complex),
                                                 loading=np.zeros(island.nbr, dtype=complex),
                                                 losses=np.zeros(island.nbr, dtype=complex),
                                                 Pfp_vsc=np.zeros(island.nvsc, dtype=float),
                                                 Pfn_vsc=np.zeros(island.nvsc, dtype=float),
                                                 St_vsc=np.zeros(island.nvsc, dtype=complex),
                                                 If_vsc=np.zeros(island.nvsc, dtype=float),
                                                 It_vsc=np.zeros(island.nvsc, dtype=complex),
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

            # type HELM
            if solver_type == SolverType.HELM:
                adms = island.get_series_admittance_matrices()

                solution = pflw.helm_dpr(
                    nc=island,
                    Ybus=adm.Ybus,
                    Yf=adm.Yf,
                    Yt=adm.Yt,
                    Yshunt_bus=adm.Yshunt_bus,
                    Yseries=adms.Yseries,
                    V0=V0,
                    S0=Sbase_plus_hvdc,
                    Ysh0=adms.Yshunt,
                    pq=indices.pq,
                    pv=indices.pv,
                    vd=indices.vd,
                    pqv=indices.pqv,
                    p=indices.p,
                    no_slack=indices.no_slack,
                    tolerance=options.tolerance,
                    max_coefficients=options.max_iter,
                    use_pade=False,
                    use_classical_germ=not options.use_stored_guess,
                    control_q=options.control_Q,
                    Qmin=Qmin,
                    Qmax=Qmax,
                    control_discrete_shunts=np.any(
                        island.shunt_data.control_mode_int == ShuntControlMode.Discrete.idx()
                    ),
                    control_qv_droop=np.any(
                        island.generator_data.control_mode_int == GeneratorControlMode.QVDroop.idx()
                    ),
                    distributed_slack=options.distributed_slack,
                    bus_installed_power=island.bus_data.installed_power,
                    controls_tol=options.controls_start_tolerance,
                    verbose=options.verbose,
                    logger=logger
                )

            # type DC
            elif solver_type == SolverType.Linear:

                lin_adm = island.get_linear_admittance_matrices(indices=indices)
                Bpqpv = lin_adm.get_Bred(pqpv=indices.no_slack)
                Bref = lin_adm.get_Bslack(pqpv=indices.no_slack, vd=indices.vd)

                solution = pflw.linear_pf(nc=island,
                                          Ybus=adm.Ybus,
                                          Bpqpv=Bpqpv,
                                          Bref=Bref,
                                          Bf=lin_adm.Bf,
                                          S0=Sbase_plus_hvdc,
                                          I0=I0,
                                          Y0=Y0,
                                          V0=V0,
                                          tau=island.active_branch_data.tap_angle,
                                          vd=indices.vd,
                                          no_slack=indices.no_slack,
                                          pq=indices.pq,
                                          pv=indices.pv)

                if options.distributed_slack:
                    ok, delta = compute_slack_distribution(Scalc=solution.Scalc,
                                                           vd=indices.vd,
                                                           bus_installed_power=island.bus_data.installed_power)
                    if ok:
                        solution = pflw.linear_pf(nc=island,
                                                  Ybus=adm.Ybus,
                                                  Bpqpv=Bpqpv,
                                                  Bref=Bref,
                                                  Bf=lin_adm.Bf,
                                                  S0=Sbase_plus_hvdc + delta,
                                                  I0=I0,
                                                  Y0=Y0,
                                                  V0=V0,
                                                  tau=island.active_branch_data.tap_angle,
                                                  vd=indices.vd,
                                                  no_slack=indices.no_slack,
                                                  pq=indices.pq,
                                                  pv=indices.pv)

                if solver_idx > 0:
                    # if we get to this solver, the converged tag should not tell me it worked
                    solution.converged = solution.norm_f <= options.tolerance

            # LAC PF
            elif solver_type == SolverType.LACPF:
                adms = island.get_series_admittance_matrices()
                solution = pflw.lacpf(nc=island,
                                      Ybus=adm.Ybus,
                                      Yf=adm.Yf,
                                      Yt=adm.Yt,
                                      Yshunt_bus=adm.Yshunt_bus,
                                      Ys=adms.Yseries,
                                      S0=Sbase_plus_hvdc,
                                      V0=V0,
                                      pq=indices.pq,
                                      pv=indices.pv,
                                      vd=indices.vd,
                                      logger=logger)
                if options.distributed_slack:
                    ok, delta = compute_slack_distribution(Scalc=solution.Scalc,
                                                           vd=indices.vd,
                                                           bus_installed_power=island.bus_data.installed_power)
                    if ok:
                        solution = pflw.lacpf(nc=island,
                                              Ybus=adm.Ybus,
                                              Yf=adm.Yf,
                                              Yt=adm.Yt,
                                              Ys=adms.Yseries,
                                              Yshunt_bus=adm.Yshunt_bus,
                                              S0=Sbase_plus_hvdc + delta,
                                              V0=V0,
                                              pq=indices.pq,
                                              pv=indices.pv,
                                              vd=indices.vd,
                                              logger=logger)
                if solver_idx > 0:
                    # if we get to this solver, the converged tag should not tell me it worked
                    solution.converged = solution.norm_f <= options.tolerance

            # Gauss-Seidel
            elif solver_type == SolverType.GAUSS:
                solution = pflw.gausspf(nc=island,
                                        Ybus=adm.Ybus,
                                        Yf=adm.Yf,
                                        Yt=adm.Yt,
                                        Yshunt_bus=adm.Yshunt_bus,
                                        S0=Sbase_plus_hvdc,
                                        I0=I0,
                                        Y0=Y0,
                                        V0=V0,
                                        pv=indices.pv,
                                        pq=indices.pq,
                                        p=indices.p,
                                        pqv=indices.pqv,
                                        vd=indices.vd,
                                        bus_installed_power=island.bus_data.installed_power,
                                        Qmin=Qmin,
                                        Qmax=Qmax,
                                        tol=options.tolerance,
                                        max_it=options.max_iter,
                                        control_q=options.control_Q,
                                        distribute_slack=options.distributed_slack,
                                        verbose=options.verbose,
                                        logger=logger)

            # Levenberg-Marquardt
            elif solver_type == SolverType.LM:
                problem = PfBasicFormulation(V0=final_solution.V,
                                             S0=Sbase_plus_hvdc,
                                             I0=I0,
                                             Y0=Y0,
                                             Qmin=Qmin,
                                             Qmax=Qmax,
                                             nc=island,
                                             options=options)

                solution = levenberg_marquardt_fx(problem=problem,
                                                  tol=options.tolerance,
                                                  max_iter=options.max_iter,
                                                  verbose=options.verbose,
                                                  logger=logger)

            # Fast decoupled
            elif solver_type == SolverType.FASTDECOUPLED:
                fd_adm = island.get_fast_decoupled_amittances()

                solution = pflw.FDPF(nc=island,
                                     Vbus=V0,
                                     S0=Sbase_plus_hvdc,
                                     I0=I0,
                                     Y0=Y0,
                                     Ybus=adm.Ybus,
                                     Yf=adm.Yf,
                                     Yt=adm.Yt,
                                     Yshunt_bus=adm.Yshunt_bus,
                                     B1=fd_adm.B1,
                                     B2=fd_adm.B2,
                                     pv_=indices.pv,
                                     pq_=indices.pq,
                                     pqv_=indices.pqv,
                                     p_=indices.p,
                                     vd_=indices.vd,
                                     Qmin=Qmin,
                                     Qmax=Qmax,
                                     bus_installed_power=island.bus_data.installed_power,
                                     tol=options.tolerance,
                                     max_it=options.max_iter,
                                     control_q=options.control_Q,
                                     distribute_slack=options.distributed_slack)

            # Newton-Raphson (full, but non-generalized)
            elif solver_type == SolverType.NR:
                problem = PfBasicFormulation(V0=final_solution.V,
                                             S0=Sbase_plus_hvdc,
                                             I0=I0,
                                             Y0=Y0,
                                             Qmin=Qmin,
                                             Qmax=Qmax,
                                             nc=island,
                                             options=options)

                solution = newton_raphson_fx(problem=problem,
                                             tol=options.tolerance,
                                             max_iter=options.max_iter,
                                             trust=options.trust_radius,
                                             verbose=options.verbose,
                                             logger=logger)

            # Powell's Dog Leg (full)
            elif solver_type == SolverType.PowellDogLeg:
                problem = PfBasicFormulation(V0=final_solution.V,
                                             S0=S_base,
                                             I0=I0,
                                             Y0=Y0,
                                             Qmin=Qmin,
                                             Qmax=Qmax,
                                             nc=island,
                                             options=options)

                solution = powell_fx(problem=problem,
                                     tol=options.tolerance,
                                     max_iter=options.max_iter,
                                     trust=options.trust_radius,
                                     verbose=options.verbose,
                                     logger=logger)

            # Newton-Raphson-Iwamoto
            elif solver_type == SolverType.IWAMOTO:
                solution = pflw.IwamotoNR(nc=island,
                                          Ybus=adm.Ybus,
                                          Yf=adm.Yf,
                                          Yt=adm.Yt,
                                          Yshunt_bus=adm.Yshunt_bus,
                                          S0=Sbase_plus_hvdc,
                                          V0=final_solution.V,
                                          I0=I0,
                                          Y0=Y0,
                                          pv_=indices.pv,
                                          pq_=indices.pq,
                                          pqv_=indices.pqv,
                                          p_=indices.p,
                                          vd_=indices.vd,
                                          Qmin=Qmin,
                                          Qmax=Qmax,
                                          tol=options.tolerance,
                                          max_it=options.max_iter,
                                          control_q=options.control_Q,
                                          robust=True,
                                          logger=logger)

            else:
                # for any other method, raise exception
                raise Exception(solver_type.value + ' Not supported in power flow mode')

            # record the solution type
            solution.method = solver_type
            if np.isfinite(solution.norm_f) and solution.norm_f <= options.tolerance:
                solution.converged = True
            else:
                pass

            solution_is_usable: bool = bool(np.isfinite(solution.norm_f)
                                            and np.all(np.isfinite(solution.V))
                                            and np.all(np.abs(solution.V) < 1.0e6))

            # record the method used, if it improved the solution
            if solution_is_usable and abs(solution.norm_f) < abs(final_solution.norm_f):
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
                    if abs(solution.norm_f) < 0.1 or (options.retry_with_other_methods == False):
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


def __multi_island_pf_nc_complete_support(nc: NumericalCircuit,
                                          options: PowerFlowOptions,
                                          logger: Logger | None = None,
                                          V_guess: Union[CxVec, None] = None,
                                          Sbus_input: Union[CxVec, None] = None) -> PowerFlowResults:
    """
    Multiple islands power flow (this is the most generic power flow function)

    multi_island_pf
      |-> multi_island_pf_nc
                |-> split_into_islands
                        |-> for each island:
                                |-> __solve_island_complete_support
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
    results = PowerFlowResults(
        n=nc.nbus,
        m=nc.nbr,
        n_hvdc=nc.nhvdc,
        n_vsc=nc.nvsc,
        n_gen=nc.ngen,
        n_batt=nc.nbatt,
        n_sh=nc.nshunt,
        bus_names=nc.bus_data.names,
        branch_names=nc.passive_branch_data.names,
        hvdc_names=nc.hvdc_data.names,
        vsc_names=nc.vsc_data.names,
        gen_names=nc.generator_data.names,
        batt_names=nc.battery_data.names,
        sh_names=nc.shunt_data.names,
        bus_types=nc.bus_data.bus_types,
    )

    # compute islands
    islands = nc.split_into_islands(ignore_single_node_islands=options.ignore_single_node_islands,
                                    consider_hvdc_as_island_links=True,
                                    logger=logger)

    for i, island in enumerate(islands):

        indices = island.get_simulation_indices()
        Sbus_base = island.get_power_injections_pu()

        if len(indices.vd) > 0:

            # call the numerical methods
            solution, report = __solve_island_complete_support(
                nc=island,
                indices=indices,
                options=options,
                V0=island.bus_data.Vbus if V_guess is None else V_guess[island.bus_data.original_idx],
                S0=Sbus_base if Sbus_input is None else Sbus_input[island.bus_data.original_idx],
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

            # TODO: SANPEN: This must be inside apply_from_island, looks like fucking AI garbage
            # Preserve the numerical bus modes actually used by this island,
            # including any automatically promoted angular reference.
            results.bus_types[island.bus_data.original_idx] = (
                island.bus_data.bus_types
            )
            results.convergence_reports.append(report)

        else:
            logger.add_info('No slack nodes in the island', str(i))

    return results


def __multi_island_pf_nc_limited_support(nc: NumericalCircuit,
                                         options: PowerFlowOptions,
                                         logger: Logger | None = None,
                                         V_guess: Union[CxVec, None] = None,
                                         Sbus_input: Union[CxVec, None] = None) -> PowerFlowResults:
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
    results = PowerFlowResults(
        n=nc.nbus,
        m=nc.nbr,
        n_hvdc=nc.nhvdc,
        n_vsc=nc.nvsc,
        n_gen=nc.ngen,
        n_batt=nc.nbatt,
        n_sh=nc.nshunt,
        bus_names=nc.bus_data.names,
        branch_names=nc.passive_branch_data.names,
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

            # call the numerical methods
            solution, report = __solve_island_limited_support(
                island=island,
                indices=indices,
                options=options,
                V0=island.bus_data.Vbus if V_guess is None else V_guess[island.bus_data.original_idx],
                S_base=Sbus_base if Sbus_input is None else Sbus_input[island.bus_data.original_idx],
                Shvdc=Shvdc[island.bus_data.original_idx],
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
            # Preserve the numerical bus modes actually used by this island,
            # including any automatically promoted angular reference.
            results.bus_types[island.bus_data.original_idx] = (
                island.bus_data.bus_types
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


def multi_island_pf_nc(nc: NumericalCircuit,
                       options: PowerFlowOptions,
                       logger: Logger | None = None,
                       V_guess: Union[CxVec, None] = None,
                       Sbus_input: Union[CxVec, None] = None) -> PowerFlowResults:
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

    if options.initialize_angles and options.solver_type not in [SolverType.Linear,
                                                                 SolverType.LACPF,
                                                                 SolverType.HELM]:
        # NOTE: This is to initialize power flows with very different angles
        # that may happen if the transformer phase shifts are applied in the power flow
        results_0 = __multi_island_pf_nc_limited_support(
            nc=nc,
            options=PowerFlowOptions(solver_type=SolverType.Linear),
            logger=logger,
            V_guess=V_guess,
            Sbus_input=Sbus_input,
        )
        V0 = results_0.voltage
    else:
        if V_guess is None:
            V0 = nc.bus_data.Vbus
        else:
            V0 = V_guess[nc.bus_data.original_idx]
            if voltage_guess_is_usable(V=V0):
                V0 = V0
            else:
                logger.add_warning("Ignoring unusable power flow voltage guess")
                V0 = nc.bus_data.Vbus

    static_droop: StaticGeneratorDroop = StaticGeneratorDroop(nc)
    has_static_droop: bool = len(static_droop.idx) > 0
    if has_static_droop or (nc.active_branch_data.any_pf_control and options.solver_type != SolverType.HELM):

        results = __multi_island_pf_nc_complete_support(
            nc=nc,
            options=options,
            logger=logger,
            V_guess=V0,
            Sbus_input=Sbus_input,
        )

        if not results.converged and not has_static_droop:
            logger.add_warning(
                msg="Control-aware power flow did not converge; falling back to the "
                    "limited-support solver, which does NOT enforce branch/VSC/HVDC "
                    "controls (tap module, phase shift, converter set-points). "
                    "The returned solution may not honour those control targets.",
                device="PowerFlow",
                value="control-aware solver failed",
                expected_value="converged solution with controls enforced"
            )
            results = __multi_island_pf_nc_limited_support(
                nc=nc,
                options=options,
                logger=logger,
                V_guess=V0,
                Sbus_input=Sbus_input,
            )

        # expand voltages if there was a bus topology reduction
        if nc.topology_performed:
            results.voltage = nc.propagate_bus_result(results.voltage)

        V_for_q = results.voltage[nc.bus_data.original_idx] if nc.topology_performed else results.voltage
        q0_gen = _get_generator_q_for_split(nc=nc, V=V_for_q)
        droop_q: Vec = static_droop.delta_q_bus(V_for_q) * nc.Sbase
        if nc.topology_performed:
            droop_q = nc.propagate_bus_result(droop_q)
        else:
            pass

        vm_abs: Vec = np.abs(results.voltage)
        slack_bus_mask: np.ndarray = (
                results.bus_types == BusMode.Slack_tpe.value
        )
        fixed_load_bus: CxVec = (
                nc.load_data.get_injections_per_bus()
                + results.voltage * np.conj(
            nc.load_data.get_current_injections_per_bus()
            + nc.load_data.get_admittance_injections_per_bus() * results.voltage
        )
        )
        fixed_shunt_bus: CxVec = results.voltage * np.conj(
            nc.shunt_data.get_injections_per_bus() * results.voltage
        )
        fixed_non_generator_bus: CxVec = fixed_load_bus + fixed_shunt_bus
        fixed_non_generator_bus += 1j * droop_q
        qfixed_bus: Vec = (
                nc.bus_data.q_fixed
                - (nc.bus_data.ii_fixed + nc.bus_data.b_fixed * vm_abs) * vm_abs
        )
        qfixed_bus += droop_q

        # Reconstruct the fixed shunt-like device reactive power from the final
        # solved voltage so the reported device values remain in nodal balance.
        results.shunt_q = -(nc.shunt_data.Y.imag * np.power(vm_abs[nc.shunt_data.bus_idx], 2.0)) * nc.shunt_data.active

        # Split only the remaining generator-like reactive power after removing
        # the fixed compiled bus contribution.
        results.gen_q, results.battery_q = split_reactive_power_between_generators_and_batteries(
            Qbus=results.Sbus.imag,
            Qfixed_bus=qfixed_bus,
            gen_bus_idx=nc.generator_data.bus_idx,
            Qmin_gen=nc.generator_data.qmin,
            Qmax_gen=nc.generator_data.qmax,
            gen_status=nc.generator_data.active,
            control_mode_int_gen=nc.generator_data.control_mode_int,
            Q0_gen=q0_gen,
            Vset_gen=nc.generator_data.v,
            k_droop_gen=nc.generator_data.k_droop,
            dead_band_gen=nc.generator_data.dead_band,
            batt_bus_idx=nc.battery_data.bus_idx,
            Qmin_batt=nc.battery_data.qmin,
            Qmax_batt=nc.battery_data.qmax,
            batt_status=nc.battery_data.active,
            control_mode_int_batt=nc.battery_data.control_mode_int,
            Q0_batt=nc.battery_data.q,
            v_ctrl_val_gen=GeneratorControlMode.V.idx(),
            qv_droop_val_gen=GeneratorControlMode.QVDroop.idx(),
            Vm=vm_abs,
            enforce_q_limits=options.control_Q,
            atol=1e-12,
        )

        results.gen_q, results.battery_q = split_slack_bus_quantity_between_generators_and_batteries(
            Qbus=results.Sbus.imag,
            Qfixed_bus=fixed_non_generator_bus.imag,
            slack_bus_mask=slack_bus_mask,
            gen_bus_idx=nc.generator_data.bus_idx,
            Qmin_gen=nc.generator_data.qmin,
            Qmax_gen=nc.generator_data.qmax,
            gen_status=nc.generator_data.active,
            Q0_gen=results.gen_q,
            batt_bus_idx=nc.battery_data.bus_idx,
            Qmin_batt=nc.battery_data.qmin,
            Qmax_batt=nc.battery_data.qmax,
            batt_status=nc.battery_data.active,
            Q0_batt=results.battery_q,
            atol=1e-12,
        )

        if options.distributed_slack:
            results.gen_p, results.battery_p = split_bus_quantity(
                Qbus=results.Sbus.real,
                gen_bus_idx=nc.generator_data.bus_idx,
                Qmin_gen=nc.generator_data.pmin,
                Qmax_gen=nc.generator_data.pmax,
                gen_status=nc.generator_data.active,
                control_mode_int_gen=nc.generator_data.control_mode_int,
                Q0_gen=nc.generator_data.q,
                Vset_gen=nc.generator_data.v,
                k_droop_gen=nc.generator_data.k_droop,
                dead_band_gen=nc.generator_data.dead_band,
                batt_bus_idx=nc.battery_data.bus_idx,
                Qmin_batt=nc.battery_data.pmin,
                Qmax_batt=nc.battery_data.pmax,
                batt_status=nc.battery_data.active,
                control_mode_int_batt=nc.battery_data.control_mode_int,
                Q0_batt=nc.battery_data.p,
                v_ctrl_val_gen=GeneratorControlMode.V.idx(),
                qv_droop_val_gen=GeneratorControlMode.QVDroop.idx(),
                Vm=np.abs(results.voltage),
                atol=1e-12,
            )
        else:
            results.gen_p = nc.generator_data.p
            results.battery_p = nc.battery_data.p

        # Reference generators absorb the final solved residual after all
        # non-reference active-power allocations have been established.
        results.gen_p, results.battery_p = split_slack_bus_quantity_between_generators_and_batteries(
            Qbus=results.Sbus.real,
            Qfixed_bus=fixed_non_generator_bus.real,
            slack_bus_mask=slack_bus_mask,
            gen_bus_idx=nc.generator_data.bus_idx,
            Qmin_gen=nc.generator_data.pmin,
            Qmax_gen=nc.generator_data.pmax,
            gen_status=nc.generator_data.active,
            Q0_gen=results.gen_p,
            batt_bus_idx=nc.battery_data.bus_idx,
            Qmin_batt=nc.battery_data.pmin,
            Qmax_batt=nc.battery_data.pmax,
            batt_status=nc.battery_data.active,
            Q0_batt=results.battery_p,
            atol=1e-12,
        )

        return results

    else:

        results = __multi_island_pf_nc_limited_support(
            nc=nc,
            options=options,
            logger=logger,
            V_guess=V0,
            Sbus_input=Sbus_input,
        )

        # expand voltages if there was a bus topology reduction
        if nc.topology_performed:
            results.voltage = nc.propagate_bus_result(results.voltage)

        V_for_q = results.voltage[nc.bus_data.original_idx] if nc.topology_performed else results.voltage
        q0_gen = _get_generator_q_for_split(nc=nc, V=V_for_q)

        vm_abs: Vec = np.abs(results.voltage)
        slack_bus_mask: np.ndarray = (
                results.bus_types == BusMode.Slack_tpe.value
        )
        fixed_load_bus: CxVec = (
                nc.load_data.get_injections_per_bus()
                + results.voltage * np.conj(
            nc.load_data.get_current_injections_per_bus()
            + nc.load_data.get_admittance_injections_per_bus() * results.voltage
        )
        )
        fixed_shunt_bus: CxVec = results.voltage * np.conj(
            nc.shunt_data.get_injections_per_bus() * results.voltage
        )
        fixed_non_generator_bus: CxVec = fixed_load_bus + fixed_shunt_bus
        qfixed_bus: Vec = (
                nc.bus_data.q_fixed
                - (nc.bus_data.ii_fixed + nc.bus_data.b_fixed * vm_abs) * vm_abs
        )

        results.shunt_q = -(nc.shunt_data.Y.imag * np.power(vm_abs[nc.shunt_data.bus_idx], 2.0)) * nc.shunt_data.active

        # Remove the compiled fixed bus-side Q before allocating the solved
        # residual to generator-like voltage controllers.
        results.gen_q, results.battery_q = split_reactive_power_between_generators_and_batteries(
            Qbus=results.Sbus.imag,
            Qfixed_bus=qfixed_bus,
            gen_bus_idx=nc.generator_data.bus_idx,
            Qmin_gen=nc.generator_data.qmin,
            Qmax_gen=nc.generator_data.qmax,
            gen_status=nc.generator_data.active,
            control_mode_int_gen=nc.generator_data.control_mode_int,
            Q0_gen=q0_gen,
            Vset_gen=nc.generator_data.v,
            k_droop_gen=nc.generator_data.k_droop,
            dead_band_gen=nc.generator_data.dead_band,
            batt_bus_idx=nc.battery_data.bus_idx,
            Qmin_batt=nc.battery_data.qmin,
            Qmax_batt=nc.battery_data.qmax,
            batt_status=nc.battery_data.active,
            control_mode_int_batt=nc.battery_data.control_mode_int,
            Q0_batt=nc.battery_data.q,
            v_ctrl_val_gen=GeneratorControlMode.V.idx(),
            qv_droop_val_gen=GeneratorControlMode.QVDroop.idx(),
            Vm=vm_abs,
            enforce_q_limits=options.control_Q,
            atol=1e-12,
        )

        results.gen_q, results.battery_q = split_slack_bus_quantity_between_generators_and_batteries(
            Qbus=results.Sbus.imag,
            Qfixed_bus=fixed_non_generator_bus.imag,
            slack_bus_mask=slack_bus_mask,
            gen_bus_idx=nc.generator_data.bus_idx,
            Qmin_gen=nc.generator_data.qmin,
            Qmax_gen=nc.generator_data.qmax,
            gen_status=nc.generator_data.active,
            Q0_gen=results.gen_q,
            batt_bus_idx=nc.battery_data.bus_idx,
            Qmin_batt=nc.battery_data.qmin,
            Qmax_batt=nc.battery_data.qmax,
            batt_status=nc.battery_data.active,
            Q0_batt=results.battery_q,
            atol=1e-12,
        )

        if options.distributed_slack:
            results.gen_p, results.battery_p = split_bus_quantity(
                Qbus=results.Sbus.real,
                gen_bus_idx=nc.generator_data.bus_idx,
                Qmin_gen=nc.generator_data.pmin,
                Qmax_gen=nc.generator_data.pmax,
                gen_status=nc.generator_data.active,
                control_mode_int_gen=nc.generator_data.control_mode_int,
                Q0_gen=nc.generator_data.q,
                Vset_gen=nc.generator_data.v,
                k_droop_gen=nc.generator_data.k_droop,
                dead_band_gen=nc.generator_data.dead_band,
                batt_bus_idx=nc.battery_data.bus_idx,
                Qmin_batt=nc.battery_data.pmin,
                Qmax_batt=nc.battery_data.pmax,
                batt_status=nc.battery_data.active,
                control_mode_int_batt=nc.battery_data.control_mode_int,
                Q0_batt=nc.battery_data.p,
                v_ctrl_val_gen=GeneratorControlMode.V.idx(),
                qv_droop_val_gen=GeneratorControlMode.QVDroop.idx(),
                Vm=np.abs(results.voltage),
                atol=1e-12,
            )
        else:
            results.gen_p = nc.generator_data.p
            results.battery_p = nc.battery_data.p

        results.gen_p, results.battery_p = split_slack_bus_quantity_between_generators_and_batteries(
            Qbus=results.Sbus.real,
            Qfixed_bus=fixed_non_generator_bus.real,
            slack_bus_mask=slack_bus_mask,
            gen_bus_idx=nc.generator_data.bus_idx,
            Qmin_gen=nc.generator_data.pmin,
            Qmax_gen=nc.generator_data.pmax,
            gen_status=nc.generator_data.active,
            Q0_gen=results.gen_p,
            batt_bus_idx=nc.battery_data.bus_idx,
            Qmin_batt=nc.battery_data.pmin,
            Qmax_batt=nc.battery_data.pmax,
            batt_status=nc.battery_data.active,
            Q0_batt=results.battery_p,
            atol=1e-12,
        )

        return results


def multi_island_pf(multi_circuit: MultiCircuit,
                    options: PowerFlowOptions,
                    opf_results: VALID_OPF_RESULTS | None = None,
                    t: Union[int, None] = None,
                    logger: Logger = Logger(),
                    bus_dict: Union[Dict[Bus, int], None] = None,
                    areas_dict: Union[Dict[Area, int], None] = None) -> PowerFlowResults:
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
        fill_three_phase=False,  # This worker is only for positive sequence
        consider_grounded_buses=len(multi_circuit.vsc_devices) > 0
    )

    res = multi_island_pf_nc(nc=nc, options=options, logger=logger)

    return res
