# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
from typing import Union, Dict, Tuple, TYPE_CHECKING

import GridCalEngine.Simulations.PowerFlow as pflw
from GridCalEngine.enumerations import SolverType
from GridCalEngine.basic_structures import Logger, ConvergenceReport
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation import PfBasicFormulation
# from GridCalEngine.Simulations.PowerFlow.Formulations.pf_advanced_formulation import PfAdvancedFormulation
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_generalized_formulation import PfGeneralizedFormulation
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.powell_fx import powell_fx
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.levenberg_marquadt_fx import levenberg_marquardt_fx
from GridCalEngine.Topology.simulation_indices import SimulationIndices
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import compute_slack_distribution
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Aggregation.area import Area
from GridCalEngine.basic_structures import CxVec, Vec

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCalEngine.Compilers.circuit_to_data import VALID_OPF_RESULTS


def __split_reactive_power_into_devices(nc: NumericalCircuit, Qbus: Vec, results: PowerFlowResults) -> None:
    """
    This function splits the reactive power of the power flow solution (nbus) into reactive power per device that
    is able to control reactive power as an injection (generators, batteries, shunts)
    :param nc: NumericalCircuit
    :param Qbus: Array of nodal reactive power (nbus)
    :param results: PowerFlowResults (values are written to it)
    :return: Nothing, the results are set in the results object
    """

    # generation
    bus_idx_gen = nc.generator_data.get_bus_indices()
    gen_q_share = nc.generator_data.q_share / (nc.bus_data.q_shared_total[bus_idx_gen] + 1e-20)

    # batteries
    bus_idx_bat = nc.battery_data.get_bus_indices()
    batt_q_share = nc.battery_data.q_share / (nc.bus_data.q_shared_total[bus_idx_bat] + 1e-20)

    # shunts
    bus_idx_sh = nc.shunt_data.get_bus_indices()
    sh_q_share = nc.shunt_data.q_share / (nc.bus_data.q_shared_total[bus_idx_sh] + 1e-20)

    # Fixed injection of reactive power
    # Zip formula: S0 + np.conj(I0 + Y0 * Vm) * Vm
    Vm = np.abs(results.voltage)
    Qfix = nc.bus_data.q_fixed - (nc.bus_data.ii_fixed + nc.bus_data.b_fixed * Vm) * Vm

    # the remaining Q to share is the total Q computed (Qbus) minus the part that we know is fixed
    Qvar = Qbus - Qfix

    # set the results
    results.gen_q = Qvar[bus_idx_gen] * gen_q_share
    results.battery_q = Qvar[bus_idx_bat] * batt_q_share
    results.shunt_q = Qvar[bus_idx_sh] * sh_q_share


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

    if len(indices.vd) == 0:
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
                                           Pf_vsc=np.zeros(nc.nvsc, dtype=float),
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
                                                 Pf_vsc=np.zeros(nc.nvsc, dtype=float),
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

                problem = PfGeneralizedFormulation(V0=final_solution.V,
                                                   S0=S0,
                                                   I0=I0,
                                                   Y0=Y0,
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

                problem = PfGeneralizedFormulation(V0=final_solution.V,
                                                   S0=S0,
                                                   I0=I0,
                                                   Y0=Y0,
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

                problem = PfGeneralizedFormulation(V0=final_solution.V,
                                                   S0=S0,
                                                   I0=I0,
                                                   Y0=Y0,
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

                if solution.method in [SolverType.DC, SolverType.LACPF]:
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
    This routine supports remove voltage controls,and Hvdc links through external injections (Shvdc)
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

    if len(indices.vd) == 0:
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
                                           Pf_vsc=np.zeros(island.nvsc, dtype=float),
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
                                                 Pf_vsc=np.zeros(island.nvsc, dtype=float),
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

                solution = pflw.helm_josep(nc=island,
                                           Ybus=adm.Ybus,
                                           Yf=adm.Yf,
                                           Yt=adm.Yt,
                                           Yshunt_bus=adm.Yshunt_bus,
                                           Yseries=adms.Yseries,
                                           V0=V0,  # take V0 instead of V
                                           S0=Sbase_plus_hvdc,
                                           Ysh0=adms.Yshunt,
                                           pq=indices.pq,
                                           pv=indices.pv,
                                           vd=indices.vd,
                                           no_slack=indices.no_slack,
                                           tolerance=options.tolerance,
                                           max_coefficients=options.max_iter,
                                           use_pade=False,
                                           verbose=options.verbose,
                                           logger=logger)

                if options.distributed_slack:
                    ok, delta = compute_slack_distribution(Scalc=solution.Scalc,
                                                           vd=indices.vd,
                                                           bus_installed_power=island.bus_data.installed_power)
                    if ok:
                        solution = pflw.helm_josep(nc=island,
                                                   Ybus=adm.Ybus,
                                                   Yf=adm.Yf,
                                                   Yt=adm.Yt,
                                                   Yshunt_bus=adm.Yshunt_bus,
                                                   Yseries=adms.Yseries,
                                                   V0=V0,  # take V0 instead of V
                                                   S0=Sbase_plus_hvdc + delta,
                                                   Ysh0=adms.Yshunt,
                                                   pq=indices.pq,
                                                   pv=indices.pv,
                                                   vd=indices.vd,
                                                   no_slack=indices.no_slack,
                                                   tolerance=options.tolerance,
                                                   max_coefficients=options.max_iter,
                                                   use_pade=False,
                                                   verbose=options.verbose,
                                                   logger=logger)

            # type DC
            elif solver_type == SolverType.DC:

                lin_adm = island.get_linear_admittance_matrices(indices=indices)
                Bpqpv = lin_adm.get_Bred(pqpv=indices.no_slack)
                Bref = lin_adm.get_Bslack(pqpv=indices.no_slack, vd=indices.vd)

                solution = pflw.dcpf(nc=island,
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
                        solution = pflw.dcpf(nc=island,
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
                                      vd=indices.vd)
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
                                              vd=indices.vd)

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

            # record the method used, if it improved the solution
            if abs(solution.norm_f) < abs(final_solution.norm_f):
                report.add(method=solver_type,
                           converged=solution.converged,
                           error=solution.norm_f,
                           elapsed=solution.elapsed,
                           iterations=solution.iterations)

                if solution.method in [SolverType.DC, SolverType.LACPF]:
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

    if nc.active_branch_data.any_pf_control:

        results = __multi_island_pf_nc_complete_support(
            nc=nc,
            options=options,
            logger=logger,
            V_guess=V_guess,
            Sbus_input=Sbus_input,
        )

        if not results.converged:
            results = __multi_island_pf_nc_limited_support(
                nc=nc,
                options=options,
                logger=logger,
                V_guess=V_guess,
                Sbus_input=Sbus_input,
            )

    else:
        results = __multi_island_pf_nc_limited_support(
            nc=nc,
            options=options,
            logger=logger,
            V_guess=V_guess,
            Sbus_input=Sbus_input,
        )

    # expand voltages if there was a bus topology reduction
    if nc.topology_performed:
        results.voltage = nc.propagate_bus_result(results.voltage)

    # do the reactive power partition and store the values
    __split_reactive_power_into_devices(nc=nc, Qbus=results.Sbus.imag, results=results)

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
    )

    res = multi_island_pf_nc(nc=nc, options=options, logger=logger)

    return res
