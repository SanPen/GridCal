# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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

import pandas as pd
import numpy as np
import GridCal.Engine.basic_structures as bs

import GridCal.Engine.Simulations.PowerFlow.linearized_power_flow as aclin
import GridCal.Engine.Simulations.PowerFlow.jacobian_based_power_flow as acjb
import GridCal.Engine.Simulations.PowerFlow.jacobian_based_acdc_power_flow as acdcjb
import GridCal.Engine.Simulations.PowerFlow.fast_decoupled_power_flow as acfd
import GridCal.Engine.Simulations.PowerFlow.helm_power_flow as hl
import GridCal.Engine.Simulations.PowerFlow.gausspf as gs

from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCal.Engine.Core.snapshot_pf_data import SnapshotData
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit
from GridCal.Engine.Devices.enumerations import HvdcControlType


def solve(circuit: SnapshotData, options: PowerFlowOptions, report: bs.ConvergenceReport, V0, Sbus, Ibus,
          ma, theta, Beq,
          pq, pv, ref, pqpv, logger=bs.Logger()) -> NumericPowerFlowResults:
    """
    Run a power flow simulation using the selected method (no outer loop controls).
    :param circuit: SnapshotData circuit, this ensures on-demand admittances computation
    :param options: PowerFlow options
    :param report: Convergence report to fill in
    :param V0: Array of initial voltages
    :param Sbus: Array of power injections
    :param Ibus: Array of current injections
    :param pq: Array of pq nodes
    :param pv: Array of pv nodes
    :param ref: Array of slack nodes
    :param pqpv: Array of (sorted) pq and pv nodes
    :param logger: Logger
    :return: NumericPowerFlowResults 
    """

    if options.retry_with_other_methods:
        if circuit.any_control:
            solver_list = [bs.SolverType.NR,
                           bs.SolverType.LM,
                           bs.SolverType.HELM,
                           bs.SolverType.IWAMOTO,
                           bs.SolverType.LACPF]
        else:
            solver_list = [bs.SolverType.NR,
                           bs.SolverType.HELM,
                           bs.SolverType.IWAMOTO,
                           bs.SolverType.LM,
                           bs.SolverType.LACPF]

        if options.solver_type in solver_list:
            solver_list.remove(options.solver_type)

        solvers = [options.solver_type] + solver_list
    else:
        # No retry selected
        solvers = [options.solver_type]

    # set worked to false to enter in the loop
    solver_idx = 0

    # set the initial value

    final_solution = NumericPowerFlowResults(V=V0,
                                             converged=False,
                                             norm_f=1e200,
                                             Scalc=Sbus,
                                             ma=circuit.branch_data.m[:, 0],
                                             theta=circuit.branch_data.theta[:, 0],
                                             Beq=circuit.branch_data.Beq[:, 0],
                                             Ybus=circuit.Ybus,
                                             Yf=circuit.Yf,
                                             Yt=circuit.Yt,
                                             iterations=0,
                                             elapsed=0)

    while solver_idx < len(solvers) and not final_solution.converged:
        # get the solver
        solver_type = solvers[solver_idx]

        # type HELM
        if solver_type == bs.SolverType.HELM:
            solution = hl.helm_josep(Ybus=circuit.Ybus,
                                     Yseries=circuit.Yseries,
                                     V0=V0,  # take V0 instead of V
                                     S0=Sbus,
                                     Ysh0=circuit.Yshunt,
                                     pq=pq,
                                     pv=pv,
                                     sl=ref,
                                     pqpv=pqpv,
                                     tolerance=options.tolerance,
                                     max_coeff=options.max_iter,
                                     use_pade=True,
                                     verbose=False)

        # type DC
        elif solver_type == bs.SolverType.DC:
            solution = aclin.dcpf(Ybus=circuit.Ybus,
                                  Bpqpv=circuit.Bpqpv,
                                  Bref=circuit.Bref,
                                  Btheta=circuit.Btheta,
                                  Sbus=Sbus,
                                  Ibus=Ibus,
                                  V0=V0,
                                  theta=theta,
                                  ref=ref,
                                  pvpq=pqpv,
                                  pq=pq,
                                  pv=pv)

        # LAC PF
        elif solver_type == bs.SolverType.LACPF:
            solution = aclin.lacpf(Y=circuit.Ybus,
                                   Ys=circuit.Yseries,
                                   S=Sbus,
                                   I=Ibus,
                                   Vset=V0,
                                   pq=pq,
                                   pv=pv)

        elif solver_type == bs.SolverType.GAUSS:
            solution = gs.gausspf(Ybus=circuit.Ybus,
                                  Sbus=Sbus,
                                  V0=V0,
                                  pv=pv,
                                  pq=pq,
                                  tol=options.tolerance,
                                  max_it=options.max_iter,
                                  verbose=False)

        # Levenberg-Marquardt
        elif solver_type == bs.SolverType.LM:
            if circuit.any_control:
                solution = acdcjb.LM_ACDC(nc=circuit,
                                          Vbus=V0,
                                          Sbus=Sbus,
                                          tolerance=options.tolerance,
                                          max_iter=options.max_iter)
            else:
                solution = acjb.levenberg_marquardt_pf(Ybus=circuit.Ybus,
                                                       Sbus_=Sbus,
                                                       V0=final_solution.V,
                                                       Ibus=Ibus,
                                                       pv_=pv,
                                                       pq_=pq,
                                                       Qmin=circuit.Qmin_bus[0, :],
                                                       Qmax=circuit.Qmax_bus[0, :],
                                                       tol=options.tolerance,
                                                       max_it=options.max_iter,
                                                       control_q=options.control_Q)

        # Fast decoupled
        elif solver_type == bs.SolverType.FASTDECOUPLED:
            solution = acfd.FDPF(Vbus=V0,
                                 Sbus=Sbus,
                                 Ibus=Ibus,
                                 Ybus=circuit.Ybus,
                                 B1=circuit.B1,
                                 B2=circuit.B2,
                                 pq=pq,
                                 pv=pv,
                                 pqpv=pqpv,
                                 tol=options.tolerance,
                                 max_it=options.max_iter)

        # Newton-Raphson (full)
        elif solver_type == bs.SolverType.NR:

            if circuit.any_control:
                # Solve NR with the AC/DC algorithm
                solution = acdcjb.NR_LS_ACDC(nc=circuit,
                                             Vbus=V0,
                                             Sbus=Sbus,
                                             tolerance=options.tolerance,
                                             max_iter=options.max_iter,
                                             acceleration_parameter=options.backtracking_parameter,
                                             mu_0=options.mu,
                                             control_q=options.control_Q)
            else:
                # Solve NR with the AC algorithm
                solution = acjb.NR_LS(Ybus=circuit.Ybus,
                                      Sbus_=Sbus,
                                      V0=final_solution.V,
                                      Ibus=Ibus,
                                      pv_=pv,
                                      pq_=pq,
                                      Qmin=circuit.Qmin_bus[0, :],
                                      Qmax=circuit.Qmax_bus[0, :],
                                      tol=options.tolerance,
                                      max_it=options.max_iter,
                                      mu_0=options.mu,
                                      acceleration_parameter=options.backtracking_parameter,
                                      control_q=options.control_Q)

        # Newton-Raphson-Decpupled
        elif solver_type == bs.SolverType.NRD:
            # Solve NR with the linear AC solution
            solution = acjb.NRD_LS(Ybus=circuit.Ybus,
                                   Sbus=Sbus,
                                   V0=final_solution.V,
                                   Ibus=Ibus,
                                   pv=pv,
                                   pq=pq,
                                   tol=options.tolerance,
                                   max_it=options.max_iter,
                                   acceleration_parameter=options.backtracking_parameter)

        # Newton-Raphson-Iwamoto
        elif solver_type == bs.SolverType.IWAMOTO:
            solution = acjb.IwamotoNR(Ybus=circuit.Ybus,
                                      Sbus_=Sbus,
                                      V0=final_solution.V,
                                      Ibus=Ibus,
                                      pv_=pv,
                                      pq_=pq,
                                      Qmin=circuit.Qmin_bus[0, :],
                                      Qmax=circuit.Qmax_bus[0, :],
                                      tol=options.tolerance,
                                      max_it=options.max_iter,
                                      control_q=options.control_Q,
                                      robust=True)

        # Newton-Raphson in current equations
        elif solver_type == bs.SolverType.NRI:
            solution = acjb.NR_I_LS(Ybus=circuit.Ybus,
                                    Sbus_sp=Sbus,
                                    V0=final_solution.V,
                                    Ibus_sp=Ibus,
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
        if solution.norm_f < final_solution.norm_f:
            report.add(method=solver_type,
                       converged=solution.converged,
                       error=solution.norm_f,
                       elapsed=solution.elapsed,
                       iterations=solution.iterations)
            final_solution = solution

        # record the solver steps
        solver_idx += 1

    if not final_solution.converged:
        logger.add_error('Did not converge, even after retry!', 'Error', str(final_solution.norm_f), options.tolerance)

    if final_solution.ma is None:
        final_solution.ma = circuit.branch_data.m[:, 0]

    if final_solution.theta is None:
        final_solution.theta = circuit.branch_data.theta[:, 0]

    if final_solution.Beq is None:
        final_solution.Beq = circuit.branch_data.Beq[:, 0]

    return final_solution


def outer_loop_power_flow(circuit: SnapshotData, options: PowerFlowOptions,
                          voltage_solution, Sbus, Ibus, ma, theta, Beq, branch_rates,
                          pq, pv, vd, pqpv, logger=bs.Logger()) -> "PowerFlowResults":
    """
    Run a power flow simulation for a single circuit using the selected outer loop
    controls. This method shouldn't be called directly.
    :param circuit: CalculationInputs instance
    :param options:
    :param voltage_solution: vector of initial voltages
    :param Sbus: vector of power injections
    :param Ibus: vector of current injections
    :param branch_rates:
    :param pq: Array of pq nodes
    :param pv: Array of pv nodes
    :param vd: Array of slack nodes
    :param pqpv: Array of (sorted) pq and pv nodes
    :param logger:
    :return: PowerFlowResults instance
    """

    # get the original types and compile this class' own lists of node types for thread independence
    bus_types = circuit.bus_types.copy()

    report = bs.ConvergenceReport()
    solution = NumericPowerFlowResults(V=voltage_solution,
                                       converged=False,
                                       norm_f=1e200,
                                       Scalc=Sbus,
                                       ma=ma,
                                       theta=theta,
                                       Beq=Beq,
                                       Ybus=circuit.Ybus,
                                       Yf=circuit.Yf,
                                       Yt=circuit.Yt,
                                       iterations=0,
                                       elapsed=0)

    # this the "outer-loop"
    if len(circuit.vd) == 0:
        voltage_solution = np.zeros(len(Sbus), dtype=complex)
        normF = 0
        Scalc = Sbus.copy()
        any_q_control_issue = False
        converged = True
        logger.add_error('Not solving power flow because there is no slack bus')
    else:

        # run the power flow method that shall be run
        solution = solve(circuit=circuit,
                         options=options,
                         report=report,  # is modified here
                         V0=voltage_solution,
                         Sbus=Sbus,
                         Ibus=Ibus,
                         ma=ma,
                         theta=theta,
                         Beq=Beq,
                         pq=pq,
                         pv=pv,
                         ref=vd,
                         pqpv=pqpv,
                         logger=logger)

        if options.distributed_slack:
            # Distribute the slack power
            slack_power = Sbus[circuit.vd].real.sum()
            total_installed_power = circuit.bus_installed_power.sum()

            if total_installed_power > 0.0:
                delta = slack_power * circuit.bus_installed_power / total_installed_power

                # repeat power flow with the redistributed power
                solution = solve(circuit=circuit,
                                 options=options,
                                 report=report,  # is modified here
                                 V0=solution.V,
                                 Sbus=Sbus + delta,
                                 Ibus=Ibus,
                                 ma=ma,
                                 theta=theta,
                                 Beq=Beq,
                                 pq=pq,
                                 pv=pv,
                                 ref=vd,
                                 pqpv=pqpv,
                                 logger=logger)

    # Compute the branches power and the slack buses power
    Sfb, Stb, If, It, Vbranch, loading, losses, Sbus = power_flow_post_process(calculation_inputs=circuit,
                                                                               Sbus=solution.Scalc,
                                                                               V=solution.V,
                                                                               branch_rates=branch_rates,
                                                                               Yf=solution.Yf,
                                                                               Yt=solution.Yt,
                                                                               method=solution.method)

    # voltage, Sf, loading, losses, error, converged, Qpv
    results = PowerFlowResults(n=circuit.nbus,
                               m=circuit.nbr,
                               n_tr=circuit.ntr,
                               n_hvdc=circuit.nhvdc,
                               bus_names=circuit.bus_names,
                               branch_names=circuit.branch_names,
                               transformer_names=circuit.tr_names,
                               hvdc_names=circuit.hvdc_names,
                               bus_types=bus_types)

    results.Sbus = solution.Scalc * circuit.Sbase  # MVA
    results.voltage = solution.V
    results.Sf = Sfb  # in MVA already
    results.St = Stb  # in MVA already
    results.If = If  # in p.u.
    results.It = It  # in p.u.
    results.ma = solution.ma
    results.theta = solution.theta
    results.Beq = solution.Beq
    results.Vbranch = Vbranch
    results.loading = loading
    results.losses = losses
    results.transformer_tap_module = solution.ma[circuit.transformer_idx]
    results.convergence_reports.append(report)
    results.Qpv = Sbus.imag[circuit.pv]

    # HVDC results are gathered in the multi island power flow function due to their nature

    return results


def power_flow_post_process(calculation_inputs: SnapshotData, Sbus, V, branch_rates, Yf=None, Yt=None,
                            method: bs.SolverType = None):
    """
    Compute the power Sf trough the branches.

    Arguments:

        **calculation_inputs**: instance of Circuit

        **V**: Voltage solution array for the circuit buses

        **only_power**: compute only the power injection

    Returns:

        Sf (MVA), If (p.u.), loading (p.u.), losses (MVA), Sbus(MVA)
    """
    # Compute the slack and pv buses power
    vd = calculation_inputs.vd
    pv = calculation_inputs.pv

    Vf = calculation_inputs.Cf * V
    Vt = calculation_inputs.Ct * V

    if method not in [bs.SolverType.DC]:
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
        theta_f = np.angle(Vf, deg=False)
        theta_t = np.angle(Vt, deg=False)
        Vbranch = theta_f - theta_t
        Sf = (1.0 / calculation_inputs.branch_data.X) * Vbranch
        Sfb = Sf * calculation_inputs.Sbase
        Stb = Sf * calculation_inputs.Sbase
        If = Sfb
        It = Stb
        losses = np.zeros(calculation_inputs.nbr)

    # Branch loading in p.u.
    loading = Sfb / (branch_rates + 1e-9)

    return Sfb, Stb, If, It, Vbranch, loading, losses, Sbus


def single_island_pf(circuit: SnapshotData, Vbus, Sbus, Ibus, ma, theta, Beq, branch_rates,
                     pq, pv, vd, pqpv,
                     options: PowerFlowOptions, logger: bs.Logger) -> "PowerFlowResults":
    """
    Run a power flow for a circuit. In most cases, the **run** method should be used instead.
    :param circuit: SnapshotData instance
    :param Vbus: Initial voltage at each bus in complex per unit
    :param Sbus: Power injection at each bus in complex MVA
    :param Ibus: Current injection at each bus in complex MVA
    :param branch_rates: array of branch rates
    :param pq: Array of pq nodes
    :param pv: Array of pv nodes
    :param vd: Array of slack nodes
    :param pqpv: Array of (sorted) pq and pv nodes
    :param options: PowerFlowOptions instance
    :param logger: Logger instance
    :return: PowerFlowResults instance
    """

    # solve the power flow
    results = outer_loop_power_flow(circuit=circuit,
                                    options=options,
                                    voltage_solution=Vbus,
                                    Sbus=Sbus,
                                    Ibus=Ibus,
                                    ma=ma, theta=theta, Beq=Beq,
                                    branch_rates=branch_rates,
                                    pq=pq,
                                    pv=pv,
                                    vd=vd,
                                    pqpv=pqpv,
                                    logger=logger)

    # did it worked?
    worked = np.all(results.converged)

    # if not worked:
    #     logger.add_error('Did not converge, even after retry!', 'Error', str(results.error), options.tolerance)

    return results


def get_hvdc_power(multi_circuit: MultiCircuit, bus_dict, theta, t=None):

    Shvdc = np.zeros(len(multi_circuit.buses))
    Losses_hvdc = np.zeros(len(multi_circuit.hvdc_lines))
    Pf_hvdc = np.zeros(len(multi_circuit.hvdc_lines))
    Pt_hvdc = np.zeros(len(multi_circuit.hvdc_lines))
    loading_hvdc = np.zeros(len(multi_circuit.hvdc_lines))
    n_free = 0  # number of free hvdc lines that nee PF recalculation

    for k, elm in enumerate(multi_circuit.hvdc_lines):

        _from = bus_dict[elm.bus_from]
        _to = bus_dict[elm.bus_to]

        if t is None:
            if elm.active:
                if elm.control_mode == HvdcControlType.type_0_free:
                    n_free += int(elm.active)  # count only if active

                Pf, Pt, losses = elm.get_from_and_to_power(theta_f=theta[_from], theta_t=theta[_to],
                                                           Sbase=multi_circuit.Sbase, in_pu=True)
                loading_hvdc[k] = Pf / elm.rate
            else:
                Pf = 0
                Pt = 0
                losses = 0
        else:
            if elm.active_prof[t]:
                if elm.control_mode == HvdcControlType.type_0_free:
                    n_free += int(elm.active_prof[t])  # count only if active

                Pf, Pt, losses = elm.get_from_and_to_power_at(t=t, theta_f=theta[_from], theta_t=theta[_to],
                                                              Sbase=multi_circuit.Sbase, in_pu=True)
                loading_hvdc[k] = Pf / elm.rate_prof[t]
            else:
                Pf = 0
                Pt = 0
                losses = 0

        Shvdc[_from] += Pf
        Shvdc[_to] += Pt
        Losses_hvdc[k] = losses
        Pf_hvdc[k] = Pf
        Pt_hvdc[k] = Pt

    return Shvdc, Losses_hvdc, Pf_hvdc, Pt_hvdc, loading_hvdc, n_free


def multi_island_pf(multi_circuit: MultiCircuit, options: PowerFlowOptions, opf_results=None,
                    logger=bs.Logger()) -> "PowerFlowResults":
    """
    Multiple islands power flow (this is the most generic power flow function)
    :param multi_circuit: MultiCircuit instance
    :param options: PowerFlowOptions instance
    :param opf_results: OPF results, to be used if not None
    :param logger: list of events to add to
    :return: PowerFlowResults instance
    """

    nc = compile_snapshot_circuit(circuit=multi_circuit,
                                  apply_temperature=options.apply_temperature_correction,
                                  branch_tolerance_mode=options.branch_impedance_tolerance_mode,
                                  opf_results=opf_results)

    # compose the HVDC power injections
    bus_dict = multi_circuit.get_bus_index_dict()
    Shvdc, Losses_hvdc, Pf_hvdc, Pt_hvdc, loading_hvdc, n_free = get_hvdc_power(multi_circuit,
                                                                                bus_dict,
                                                                                theta=np.zeros(nc.nbus))
    Pf_hvdc_prev = Pf_hvdc.copy()
    calculation_inputs = nc.split_into_islands(ignore_single_node_islands=options.ignore_single_node_islands)

    results = PowerFlowResults(n=nc.nbus,
                               m=nc.nbr,
                               n_tr=nc.ntr,
                               n_hvdc=nc.nhvdc,
                               bus_names=nc.bus_data.bus_names,
                               branch_names=nc.branch_data.branch_names,
                               transformer_names=nc.transformer_data.tr_names,
                               hvdc_names=nc.hvdc_data.names,
                               bus_types=nc.bus_data.bus_types)

    # initialize the all controls var
    all_controls_ok = False  # to run the first time

    control_iter = 0
    max_control_iter = 10
    while not all_controls_ok:

        # simulate each island and merge the results (doesn't matter if there is only a single island) -----------------
        for i, calculation_input in enumerate(calculation_inputs):

            if len(calculation_input.vd) > 0:

                # run circuit power flow
                res = single_island_pf(circuit=calculation_input,
                                       Vbus=calculation_input.Vbus,
                                       Sbus=calculation_input.Sbus + Shvdc[calculation_input.original_bus_idx],
                                       Ibus=calculation_input.Ibus,
                                       ma=calculation_input.branch_data.m[:, 0],
                                       theta=calculation_input.branch_data.theta[:, 0],
                                       Beq=calculation_input.branch_data.Beq[:, 0],
                                       branch_rates=calculation_input.Rates,
                                       pq=calculation_input.pq,
                                       pv=calculation_input.pv,
                                       vd=calculation_input.vd,
                                       pqpv=calculation_input.pqpv,
                                       options=options,
                                       logger=logger)

                # merge the results from this island
                results.apply_from_island(res,
                                          calculation_input.original_bus_idx,
                                          calculation_input.original_branch_idx,
                                          calculation_input.original_tr_idx)

            else:
                logger.add_info('No slack nodes in the island', str(i))
        # --------------------------------------------------------------------------------------------------------------

        if n_free and control_iter < max_control_iter:
            Shvdc, Losses_hvdc, Pf_hvdc, Pt_hvdc, loading_hvdc, n_free = get_hvdc_power(multi_circuit,
                                                                                        bus_dict,
                                                                                        theta=np.angle(results.voltage))
            hvdc_control_err = np.max(np.abs(Pf_hvdc_prev - Pf_hvdc))

            print('control err:', hvdc_control_err, '', Pf_hvdc)

            if hvdc_control_err < 0.1:
                # finalize
                all_controls_ok = True
            else:
                # update
                Pf_hvdc_prev = Pf_hvdc.copy()
        else:
            all_controls_ok = True

        control_iter += 1

    # compile HVDC results (available for the complete grid since HVDC line as formulated are split objects
    # Pt is the "generation" at the sending point
    # Shvdc, Losses_hvdc, Pf_hvdc, Pt_hvdc
    results.hvdc_Pf = Pf_hvdc * nc.Sbase
    results.hvdc_Pt = Pt_hvdc * nc.Sbase
    results.hvdc_loading = loading_hvdc * 100.0
    results.hvdc_losses = Losses_hvdc * nc.Sbase

    # set the inter-area variables
    results.F = nc.F
    results.T = nc.T
    results.hvdc_F = nc.hvdc_data.get_bus_indices_f()
    results.hvdc_T = nc.hvdc_data.get_bus_indices_t()
    results.bus_area_indices = nc.bus_data.areas
    results.area_names = [a.name for a in multi_circuit.areas]

    return results
