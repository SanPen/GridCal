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
from __future__ import annotations
import numpy as np
from typing import Union, Dict, Tuple, TYPE_CHECKING

import GridCalEngine.Simulations.PowerFlow as pflw
from GridCalEngine.enumerations import SolverType
from GridCalEngine.basic_structures import Logger, ConvergenceReport
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Core.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.Core.Devices.Substation.bus import Bus
from GridCalEngine.Core.Devices.Aggregation.area import Area
from GridCalEngine.basic_structures import CxVec, Vec, IntVec

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCalEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults


def solve(circuit: NumericalCircuit,
          options: PowerFlowOptions,
          report: ConvergenceReport,
          V0: CxVec, 
          S0: CxVec, 
          I0: CxVec, 
          Y0: CxVec,
          tap_modules: Vec, 
          tap_angles: Vec, 
          Beq: Vec,
          pq: IntVec, 
          pv: IntVec, 
          ref: IntVec, 
          pqpv: IntVec,
          Qmin: Vec, 
          Qmax: Vec, 
          logger=Logger()) -> NumericPowerFlowResults:
    """
    Run a power flow simulation using the selected method (no outer loop controls).
    :param circuit: SnapshotData circuit, this ensures on-demand admittances computation
    :param options: PowerFlow options
    :param report: Convergence report to fill in
    :param V0: Array of initial voltages
    :param S0: Array of power Injections
    :param I0: Array of current Injections
    :param Y0: Array of admittance injections
    :param tap_modules: Array of branch tap modules
    :param tap_angles: Array of branch tap angles
    :param Beq: Array of branch equivalent susceptances
    :param pq: Array of pq nodes
    :param pv: Array of pv nodes
    :param ref: Array of slack nodes
    :param pqpv: Array of (sorted) pq and pv nodes
    :param Qmin: Array of minimum reactive power capability per bus
    :param Qmax: Array of maximum reactive power capability per bus
    :param logger: Logger
    :return: NumericPowerFlowResults 
    """

    if options.retry_with_other_methods:
        if circuit.any_control:
            solver_list = [SolverType.NR,
                           SolverType.LM,
                           SolverType.HELM,
                           SolverType.IWAMOTO,
                           SolverType.LACPF]
        else:
            solver_list = [SolverType.NR,
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

    final_solution = NumericPowerFlowResults(V=V0,
                                             converged=False,
                                             norm_f=1e200,
                                             Scalc=S0,
                                             ma=tap_modules,
                                             theta=circuit.branch_data.tap_angle,
                                             Beq=Beq,
                                             Ybus=circuit.Ybus,
                                             Yf=circuit.Yf,
                                             Yt=circuit.Yt,
                                             iterations=0,
                                             elapsed=0)

    while solver_idx < len(solvers) and not final_solution.converged:
        # get the solver
        solver_type = solvers[solver_idx]

        # type HELM
        if solver_type == SolverType.HELM:
            solution = pflw.helm_josep(Ybus=circuit.Ybus,
                                       Yseries=circuit.Yseries,
                                       V0=V0,  # take V0 instead of V
                                       S0=S0,
                                       Ysh0=circuit.Yshunt,
                                       pq=pq,
                                       pv=pv,
                                       sl=ref,
                                       pqpv=pqpv,
                                       tolerance=options.tolerance,
                                       max_coefficients=options.max_iter,
                                       use_pade=False,
                                       verbose=options.verbose,
                                       logger=logger)

        # type DC
        elif solver_type == SolverType.DC:
            solution = pflw.dcpf(Ybus=circuit.Ybus,
                                 Bpqpv=circuit.Bpqpv,
                                 Bref=circuit.Bref,
                                 Bf=circuit.Bf,
                                 S0=S0,
                                 I0=I0,
                                 Y0=Y0,
                                 V0=V0,
                                 tau=tap_angles,
                                 vd=ref,
                                 pvpq=pqpv,
                                 pq=pq,
                                 pv=pv)

        # LAC PF
        elif solver_type == SolverType.LACPF:
            solution = pflw.lacpf(Ybus=circuit.Ybus,
                                  Ys=circuit.Yseries,
                                  S0=S0,
                                  I0=I0,
                                  V0=V0,
                                  pq=pq,
                                  pv=pv)

        # Gauss-Seidel
        elif solver_type == SolverType.GAUSS:
            solution = pflw.gausspf(Ybus=circuit.Ybus,
                                    S0=S0,
                                    I0=I0,
                                    Y0=Y0,
                                    V0=V0,
                                    pv=pv,
                                    pq=pq,
                                    tol=options.tolerance,
                                    max_it=options.max_iter,
                                    verbose=options.verbose,
                                    logger=logger)

        # Levenberg-Marquardt
        elif solver_type == SolverType.LM:
            if circuit.any_control:
                solution = pflw.LM_ACDC(nc=circuit,
                                        Vbus=V0,
                                        S0=S0,
                                        I0=I0,
                                        Y0=Y0,
                                        tolerance=options.tolerance,
                                        max_iter=options.max_iter)
            else:
                solution = pflw.levenberg_marquardt_pf(Ybus=circuit.Ybus,
                                                       S0=S0,
                                                       V0=final_solution.V,
                                                       I0=I0,
                                                       Y0=Y0,
                                                       pv_=pv,
                                                       pq_=pq,
                                                       Qmin=Qmin,
                                                       Qmax=Qmax,
                                                       tol=options.tolerance,
                                                       max_it=options.max_iter,
                                                       control_q=options.control_Q,
                                                       verbose=options.verbose,
                                                       logger=logger)

        # Fast decoupled
        elif solver_type == SolverType.FASTDECOUPLED:
            solution = pflw.FDPF(Vbus=V0,
                                 S0=S0,
                                 I0=I0,
                                 Y0=Y0,
                                 Ybus=circuit.Ybus,
                                 B1=circuit.B1,
                                 B2=circuit.B2,
                                 pq=pq,
                                 pv=pv,
                                 pqpv=pqpv,
                                 tol=options.tolerance,
                                 max_it=options.max_iter)

        # Newton-Raphson (full)
        elif solver_type == SolverType.NR:

            if circuit.any_control:
                # Solve NR with the AC/DC algorithm
                solution = pflw.NR_LS_ACDC(nc=circuit,
                                           V0=V0,
                                           S0=S0,
                                           I0=I0,
                                           Y0=Y0,
                                           tolerance=options.tolerance,
                                           max_iter=options.max_iter,
                                           acceleration_parameter=options.backtracking_parameter,
                                           mu_0=options.trust_radius,
                                           control_q=options.control_Q)
            else:
                # Solve NR with the AC algorithm
                solution = pflw.NR_LS(Ybus=circuit.Ybus,
                                      S0=S0,
                                      V0=final_solution.V,
                                      I0=I0,
                                      Y0=Y0,
                                      pv_=pv,
                                      pq_=pq,
                                      Qmin=Qmin,
                                      Qmax=Qmax,
                                      tol=options.tolerance,
                                      max_it=options.max_iter,
                                      mu_0=options.trust_radius,
                                      acceleration_parameter=options.backtracking_parameter,
                                      control_q=options.control_Q,
                                      verbose=options.verbose,
                                      logger=logger)

        # Newton-Raphson-Decpupled
        elif solver_type == SolverType.NRD:
            # Solve NR with the linear AC solution
            solution = pflw.NRD_LS(Ybus=circuit.Ybus,
                                   S0=S0,
                                   V0=final_solution.V,
                                   I0=I0,
                                   Y0=Y0,
                                   pv=pv,
                                   pq=pq,
                                   tol=options.tolerance,
                                   max_it=options.max_iter,
                                   acceleration_parameter=options.backtracking_parameter)

        # Newton-Raphson-Iwamoto
        elif solver_type == SolverType.IWAMOTO:
            solution = pflw.IwamotoNR(Ybus=circuit.Ybus,
                                      S0=S0,
                                      V0=final_solution.V,
                                      I0=I0,
                                      Y0=Y0,
                                      pv_=pv,
                                      pq_=pq,
                                      Qmin=Qmin,
                                      Qmax=Qmax,
                                      tol=options.tolerance,
                                      max_it=options.max_iter,
                                      control_q=options.control_Q,
                                      robust=True)

        # Newton-Raphson in current equations
        elif solver_type == SolverType.NRI:
            solution = pflw.NR_I_LS(Ybus=circuit.Ybus,
                                    Sbus_sp=S0,
                                    V0=final_solution.V,
                                    Ibus_sp=I0,
                                    pv=pv,
                                    pq=pq,
                                    tol=options.tolerance,
                                    max_it=options.max_iter)

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
            final_solution = solution
        else:
            logger.add_info('Tried solver but it did not improve the solution',
                            solver_type.value, value=solution.norm_f,
                            expected_value=final_solution.norm_f)

        # record the solver steps
        solver_idx += 1

    if not final_solution.converged:
        logger.add_error('Did not converge, even after retry!', 'Error', str(final_solution.norm_f), options.tolerance)

    if final_solution.ma is None:
        final_solution.ma = tap_modules

    if final_solution.theta is None:
        final_solution.theta = tap_angles

    if final_solution.Beq is None:
        final_solution.Beq = Beq

    return final_solution


def single_island_pf(circuit: NumericalCircuit, options: PowerFlowOptions,
                     voltage_solution, S0, I0, Y0, tap_modules, tap_angles, Beq, branch_rates,
                     pq, pv, vd, pqpv, Qmin, Qmax, logger=Logger()) -> "PowerFlowResults":
    """
    Run a power flow simulation for a single circuit using the
    selected outer loop controls.
    This method shouldn't be called directly.
    :param circuit: CalculationInputs instance
    :param options: PowerFlowOptions
    :param voltage_solution: vector of initial voltages
    :param S0: Array of power Injections
    :param I0: Array of current Injections
    :param Y0: Array of admittance injections
    :param tap_modules: Array of branch tap modules
    :param tap_angles: Array of branch tap angles
    :param Beq: Array of branch equivalent susceptances
    :param branch_rates: Array of branch rates
    :param pq: Array of pq nodes
    :param pv: Array of pv nodes
    :param vd: Array of slack nodes
    :param pqpv: Array of (sorted) pq and pv nodes
    :param Qmin: Array of minimum reactive power capability per bus
    :param Qmax: Array of maximum reactive power capability per bus
    :param logger: Logger object
    :return: PowerFlowResults instance
    """

    # get the original types and compile this class' own lists of node types for thread independence
    bus_types = circuit.bus_types.copy()

    report = ConvergenceReport()
    solution = NumericPowerFlowResults(V=voltage_solution,
                                       converged=False,
                                       norm_f=1e200,
                                       Scalc=S0,
                                       ma=tap_modules,
                                       theta=tap_angles,
                                       Beq=Beq,
                                       Ybus=circuit.Ybus,
                                       Yf=circuit.Yf,
                                       Yt=circuit.Yt,
                                       iterations=0,
                                       elapsed=0)

    # this the "outer-loop"
    if len(vd) == 0:
        solution.V = np.zeros(len(S0), dtype=complex)
        report.add(SolverType.NoSolver, True, 0, 0.0, 0.0)
        logger.add_error('Not solving power flow because there is no slack bus')
    else:

        # run the power flow method that shall be run
        solution = solve(circuit=circuit,
                         options=options,
                         report=report,  # is modified here
                         V0=voltage_solution,
                         S0=S0,
                         I0=I0,
                         Y0=Y0,
                         tap_modules=tap_modules,
                         tap_angles=tap_angles,
                         Beq=Beq,
                         pq=pq,
                         pv=pv,
                         ref=vd,
                         pqpv=pqpv,
                         Qmin=Qmin,
                         Qmax=Qmax,
                         logger=logger)

        if options.distributed_slack:
            # Distribute the slack power
            slack_power = S0[circuit.vd].real.sum()
            total_installed_power = circuit.bus_installed_power.sum()

            if total_installed_power > 0.0:
                delta = slack_power * circuit.bus_installed_power / total_installed_power

                # repeat power flow with the redistributed power
                solution = solve(circuit=circuit,
                                 options=options,
                                 report=report,  # is modified here
                                 V0=solution.V,
                                 S0=S0 + delta,
                                 I0=I0,
                                 Y0=Y0,
                                 tap_modules=tap_modules,
                                 tap_angles=tap_angles,
                                 Beq=Beq,
                                 pq=pq,
                                 pv=pv,
                                 ref=vd,
                                 pqpv=pqpv,
                                 Qmin=Qmin,
                                 Qmax=Qmax,
                                 logger=logger)

    # Compute the Branches power and the slack buses power
    Sfb, Stb, If, It, Vbranch, loading, losses, S0 = power_flow_post_process(calculation_inputs=circuit,
                                                                             Sbus=solution.Scalc,
                                                                             V=solution.V,
                                                                             branch_rates=branch_rates,
                                                                             Yf=solution.Yf,
                                                                             Yt=solution.Yt,
                                                                             method=solution.method)

    # voltage, Sf, loading, losses, error, converged, Qpv
    results = PowerFlowResults(n=circuit.nbus,
                               m=circuit.nbr,
                               n_hvdc=circuit.nhvdc,
                               bus_names=circuit.bus_names,
                               branch_names=circuit.branch_names,
                               hvdc_names=circuit.hvdc_names,
                               bus_types=bus_types)

    results.Sbus = solution.Scalc * circuit.Sbase  # MVA
    results.voltage = solution.V
    results.Sf = Sfb  # in MVA already
    results.St = Stb  # in MVA already
    results.If = If  # in p.u.
    results.It = It  # in p.u.
    results.tap_module = solution.ma
    results.tap_angle = solution.theta
    results.Beq = solution.Beq
    results.Vbranch = Vbranch
    results.loading = loading
    results.losses = losses
    results.convergence_reports.append(report)
    results.Qpv = S0.imag[circuit.pv]

    # HVDC results are gathered in the multi island power flow function due to their nature

    return results


def power_flow_post_process(calculation_inputs: NumericalCircuit,
                            Sbus: CxVec,
                            V: CxVec,
                            branch_rates: CxVec,
                            Yf=None, Yt=None,
                            method: SolverType = None) -> Tuple[CxVec, CxVec, CxVec, CxVec, CxVec, CxVec, CxVec, CxVec]:
    """
    Compute the power Sf trough the Branches.
    :param calculation_inputs: NumericalCircuit
    :param Sbus: Array of computed nodal injections
    :param V: Array of computed nodal voltages
    :param branch_rates: Array of branch rates
    :param Yf: Admittance-from matrix
    :param Yt: Admittance-to matrix
    :param method: SolverType (the non-linear and Linear flow calculations differ)
    :return: Sf (MVA), St (MVA), If (p.u.), It (p.u.), Vbranch (p.u.), loading (p.u.), losses (MVA), Sbus(MVA)
    """
    # Compute the slack and pv buses power
    vd = calculation_inputs.vd
    pv = calculation_inputs.pv

    if method not in [SolverType.DC]:
        # power at the slack nodes
        Sbus[vd] = V[vd] * np.conj(calculation_inputs.Ybus[vd, :].dot(V))

        # Reactive power at the pv nodes
        P = Sbus[pv].real
        Q = (V[pv] * np.conj(calculation_inputs.Ybus[pv, :].dot(V))).imag
        Sbus[pv] = P + 1j * Q  # keep the original P injection and set the calculated reactive power

        if Yf is None:
            Yf = calculation_inputs.Yf
        if Yt is None:
            Yt = calculation_inputs.Yt

        # Branches current, loading, etc
        Vf = V[calculation_inputs.branch_data.F]
        Vt = V[calculation_inputs.branch_data.T]
        If = Yf * V
        It = Yt * V
        Sf = Vf * np.conj(If)
        St = Vt * np.conj(It)

        # Branch losses in MVA
        losses = (Sf + St) * calculation_inputs.Sbase

        # branch voltage increment
        Vbranch = Vf - Vt

        # Branch power in MVA
        Sfb = Sf * calculation_inputs.Sbase
        Stb = St * calculation_inputs.Sbase

    else:
        # DC power flow
        theta = np.angle(V, deg=False)
        theta_f = theta[calculation_inputs.F]
        theta_t = theta[calculation_inputs.T]

        b = 1.0 / (calculation_inputs.branch_data.X * calculation_inputs.branch_data.tap_module)
        # Pf = calculation_inputs.Bf @ theta - b * calculation_inputs.branch_data.tap_angle

        Pf = b * (theta_f - theta_t - calculation_inputs.branch_data.tap_angle)

        Sfb = Pf * calculation_inputs.Sbase
        Stb = -Pf * calculation_inputs.Sbase

        Vf = V[calculation_inputs.branch_data.F]
        Vt = V[calculation_inputs.branch_data.T]
        Vbranch = Vf - Vt
        If = Pf / (Vf + 1e-20)
        It = -If
        # losses are not considered in the power flow computation
        losses = np.zeros(calculation_inputs.nbr)

    # Branch loading in p.u.
    loading = Sfb / (branch_rates + 1e-9)

    return Sfb, Stb, If, It, Vbranch, loading, losses, Sbus


def multi_island_pf_nc(nc: NumericalCircuit,
                       options: PowerFlowOptions,
                       logger=Logger(),
                       V_guess: Union[CxVec, None] = None,
                       Sbus_input: Union[CxVec, None] = None) -> "PowerFlowResults":
    """
    Multiple islands power flow (this is the most generic power flow function)
    :param nc: SnapshotData instance
    :param options: PowerFlowOptions instance
    :param logger: logger
    :param V_guess: voltage guess
    :param Sbus_input: Use this power injections if provided
    :return: PowerFlowResults instance
    """

    # declare results
    results = PowerFlowResults(
        n=nc.nbus,
        m=nc.nbr,
        n_hvdc=nc.nhvdc,
        bus_names=nc.bus_data.names,
        branch_names=nc.branch_data.names,
        hvdc_names=nc.hvdc_data.names,
        bus_types=nc.bus_data.bus_types,
    )

    # compose the HVDC power Injections
    Shvdc, Losses_hvdc, Pf_hvdc, Pt_hvdc, loading_hvdc, n_free = nc.hvdc_data.get_power(
        Sbase=nc.Sbase,
        theta=np.zeros(nc.nbus),
    )

    # remember the initial hvdc control values
    Losses_hvdc_prev = Losses_hvdc.copy()
    Pf_hvdc_prev = Pf_hvdc.copy()
    Pt_hvdc_prev = Pt_hvdc.copy()
    loading_hvdc_prev = loading_hvdc.copy()
    Shvdc_prev = Shvdc.copy()

    # compute islands
    islands = nc.split_into_islands(ignore_single_node_islands=options.ignore_single_node_islands)
    results.island_number = len(islands)

    # initialize the all controls var
    all_controls_ok = False  # to run the first time
    control_iter = 0
    max_control_iter = 1  # only one Pmode3 iteration...
    oscillations_number = 0
    hvdc_error_threshold = 0.01

    while not all_controls_ok:

        # simulate each island and merge the results (doesn't matter if there is only a single island) -----------------
        for i, island in enumerate(islands):

            if len(island.vd) > 0:

                if Sbus_input is None:
                    Sbus = island.Sbus + Shvdc[island.original_bus_idx]
                else:
                    Sbus = Sbus_input + Shvdc[island.original_bus_idx]

                res = single_island_pf(
                    circuit=island,
                    options=options,
                    voltage_solution=island.Vbus if V_guess is None else V_guess[island.original_bus_idx],
                    S0=Sbus,
                    I0=island.Ibus,
                    Y0=island.YLoadBus,
                    tap_modules=island.branch_data.tap_module,
                    tap_angles=island.branch_data.tap_angle,
                    Beq=island.branch_data.Beq,
                    branch_rates=island.Rates,
                    pq=island.pq,
                    pv=island.pv,
                    vd=island.vd,
                    pqpv=island.pqpv,
                    Qmin=island.Qmin_bus,
                    Qmax=island.Qmax_bus,
                    logger=logger)

                # merge the results from this island
                results.apply_from_island(
                    results=res,
                    b_idx=island.original_bus_idx,
                    br_idx=island.original_branch_idx,
                )

            else:
                logger.add_info('No slack nodes in the island', str(i))
        # --------------------------------------------------------------------------------------------------------------

        if n_free and control_iter < max_control_iter:

            Shvdc, Losses_hvdc, Pf_hvdc, Pt_hvdc, loading_hvdc, n_free = nc.hvdc_data.get_power(
                Sbase=nc.Sbase,
                theta=np.angle(results.voltage),
            )

            # hvdc_control_err = np.max(np.abs(Pf_hvdc_prev - Pf_hvdc))
            hvdc_control_err = np.max(np.abs(Shvdc - Shvdc_prev))

            Shvdc = Shvdc_prev + (Shvdc - Shvdc_prev)

            # check for oscillations
            oscillating = False

            # check oscillations: if Pf changes sign from prev to current, the previous prevails and we end the control
            logger.add_debug('HVDC angle droop control err:', hvdc_control_err, '', Pf_hvdc)
            if oscillating:
                oscillations_number += 1

                if oscillations_number > 1:
                    all_controls_ok = True
                    # revert the data
                    Losses_hvdc = Losses_hvdc_prev
                    Pf_hvdc = Pf_hvdc_prev
                    Pt_hvdc = Pt_hvdc_prev
                    loading_hvdc = loading_hvdc_prev

                # update
                Losses_hvdc_prev = Losses_hvdc.copy()
                Pf_hvdc_prev = Pf_hvdc.copy()
                Pt_hvdc_prev = Pt_hvdc.copy()
                loading_hvdc_prev = loading_hvdc.copy()
                Shvdc_prev = Shvdc.copy()

            else:
                if hvdc_control_err < hvdc_error_threshold:
                    # finalize
                    all_controls_ok = True
                else:
                    # update
                    Losses_hvdc_prev = Losses_hvdc.copy()
                    Pf_hvdc_prev = Pf_hvdc.copy()
                    Pt_hvdc_prev = Pt_hvdc.copy()
                    loading_hvdc_prev = loading_hvdc.copy()
                    Shvdc_prev = Shvdc.copy()
        else:
            all_controls_ok = True

        control_iter += 1

    # Compile HVDC results (available for the complete grid since HVDC line as
    # formulated are split objects
    # Pt is the "generation" at the sending point
    # Shvdc, Losses_hvdc, Pf_hvdc, Pt_hvdc
    results.hvdc_Pf = - Pf_hvdc * nc.Sbase  # we change the sign to keep the sign convention with AC lines
    results.hvdc_Pt = - Pt_hvdc * nc.Sbase  # we change the sign to keep the sign convention with AC lines
    results.hvdc_loading = loading_hvdc
    results.hvdc_losses = Losses_hvdc * nc.Sbase

    return results


def multi_island_pf(multi_circuit: MultiCircuit,
                    options: PowerFlowOptions,
                    opf_results: Union[OptimalPowerFlowResults, None] = None,
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
        areas_dict=areas_dict
    )

    res = multi_island_pf_nc(nc=nc, options=options, logger=logger)

    return res
