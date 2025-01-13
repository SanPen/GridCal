# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import timeit
import pandas as pd
from typing import Union
from GridCalEngine.Utils.NumericalMethods.ips import interior_point_solver
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from GridCalEngine.enumerations import AcOpfMode
from GridCalEngine.Simulations.OPF.Formulations.ac_opf_problem import NonLinearOptimalPfProblem, NonlinearOPFResults
from GridCalEngine.Simulations.OPF.NumericalMethods.newton_raphson_ips_fx import interior_point_solver, IpsSolution
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import remap_original_bus_indices
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, Logger


def solve(problem: NonLinearOptimalPfProblem,
          verbose: int = 0,
          step_control: bool = False,
          plot_error: bool = False) -> NonlinearOPFResults:
    """

    :param problem:
    :param verbose:
    :param step_control:
    :param plot_error:
    :return:
    """
    tstart = timeit.default_timer()
    result: IpsSolution = interior_point_solver(problem=problem,
                                   max_iter=problem.options.ips_iterations,
                                   tol=problem.options.ips_tolerance,
                                   pf_init=problem.options.ips_init_with_pf,
                                   trust=problem.options.ips_trust_radius,
                                   verbose=verbose,
                                   step_control=step_control)

    problem.x2var(result.x)

    # Save Results DataFrame for tests
    # pd.DataFrame(Va).transpose().to_csv('REEresth.csv')
    # pd.DataFrame(Vm).transpose().to_csv('REEresV.csv')
    # pd.DataFrame(Pg_dis).transpose().to_csv('REEresP.csv')
    # pd.DataFrame(Qg_dis).transpose().to_csv('REEresQ.csv')

    Pg = np.zeros(problem.n_gen_disp)
    Qg = np.zeros(problem.n_gen_disp)

    Pg[problem.gen_disp_idx] = problem.Pg
    Qg[problem.gen_disp_idx] = problem.Qg
    Pg[problem.gen_nondisp_idx] = np.real(problem.Sg_undis)
    Qg[problem.gen_nondisp_idx] = np.imag(problem.Sg_undis)

    # convert the lagrange multipliers to significant ones
    lam_p, lam_q = result.lam[:problem.nbus], result.lam[problem.nbus: 2 * problem.nbus]

    loading = np.abs(problem.Sftot) / (problem.rates + 1e-9)

    if problem.options.acopf_mode == AcOpfMode.ACOPFslacks:
        overloads_sf = (np.power(np.power(problem.rates[problem.br_mon_idx], 2) + problem.sl_sf, 0.5)
                        - problem.rates[problem.br_mon_idx]) * problem.Sbase
        overloads_st = (np.power(np.power(problem.rates[problem.br_mon_idx], 2) + problem.sl_st, 0.5)
                        - problem.rates[problem.br_mon_idx]) * problem.Sbase

    else:
        overloads_sf = np.zeros_like(problem.rates)
        overloads_st = np.zeros_like(problem.rates)

    hvdc_power = problem.nc.hvdc_data.Pset.copy()
    hvdc_power[problem.hvdc_disp_idx] = problem.Pfdc
    hvdc_loading = hvdc_power / (problem.nc.hvdc_data.rates + 1e-9)
    tap_module = np.zeros(problem.nc.nbr)
    tap_phase = np.zeros(problem.nc.nbr)
    tap_module[problem.k_m] = problem.tapm
    tap_phase[problem.k_tau] = problem.tapt
    Pcost = np.zeros(problem.ngen + problem.nsh)
    Pcost[problem.gen_disp_idx] = problem.c0 + problem.c1 * Pg[problem.gen_disp_idx] + problem.c2 * np.power(Pg[problem.gen_disp_idx],
                                                                                                             2.0)
    Pcost[problem.gen_nondisp_idx] = (problem.c0n + problem.c1n * np.real(problem.Sg_undis)
                                      + problem.c2n * np.power(np.real(problem.Sg_undis), 2.0))
    nodal_capacity = problem.slcap * problem.Sbase

    tend = timeit.default_timer()

    if problem.options.verbose > 0:
        df_bus = pd.DataFrame(data={'Va (rad)': problem.Va, 'Vm (p.u.)': problem.Vm,
                                    'dual price (€/MW)': lam_p, 'dual price (€/MVAr)': lam_q})
        df_gen = pd.DataFrame(data={'P (MW)': Pg * problem.Sbase, 'Q (MVAr)': Qg * problem.Sbase})
        df_linkdc = pd.DataFrame(data={'P_dc (MW)': problem.Pfdc * problem.Sbase})

        df_slsf = pd.DataFrame(data={'Slacks Sf': problem.sl_sf})
        df_slst = pd.DataFrame(data={'Slacks St': problem.sl_st})
        df_slvmax = pd.DataFrame(data={'Slacks Vmax': problem.sl_vmax})
        df_slvmin = pd.DataFrame(data={'Slacks Vmin': problem.sl_vmin})
        df_trafo_m = pd.DataFrame(data={'V (p.u.)': problem.tapm}, index=problem.k_m)
        df_trafo_tau = pd.DataFrame(data={'Tau (rad)': problem.tapt}, index=problem.k_tau)
        # df_times = pd.DataFrame(data=times[1:], index=list(range(result.iterations)),
        #                         columns=['t_modadm', 't_f', 't_g', 't_h', 't_fx', 't_gx',
        #                                  't_hx', 't_fxx', 't_gxx', 't_hxx', 't_nrstep',
        #                                  't_mult', 't_steps', 't_cond', 't_iter'])

        print("Time elapsed (s):\n", tend - tstart)

        print("Bus:\n", df_bus)
        print("V-Trafos:\n", df_trafo_m)
        print("Tau-Trafos:\n", df_trafo_tau)
        print("Gen:\n", df_gen)
        print("Link DC:\n", df_linkdc)

        print('Qshunt min: ' + str(problem.Qsh_min))

        if problem.options.acopf_mode == AcOpfMode.ACOPFslacks:
            print("Slacks:\n", df_slsf)
            print("Slacks:\n", df_slst)
            print("Slacks:\n", df_slvmax)
            print("Slacks:\n", df_slvmin)

        if problem.optimize_nodal_capacity:
            df_nodal_cap = pd.DataFrame(data={'Nodal capacity (MW)': problem.slcap * problem.Sbase},
                                        index=problem.capacity_nodes_idx)
            print("Nodal Capacity:\n", df_nodal_cap)
        print("Error", result.error)
        print("Gamma", result.gamma)
        print("Sf", problem.Sf)

        # if self.options.verbose > 1:
        #     print('Times:\n', df_times)
        #     print('Relative times:\n', 100 * df_times[['t_modadm', 't_f', 't_g', 't_h', 't_fx', 't_gx',
        #                                                't_hx', 't_fxx', 't_gxx', 't_hxx', 't_nrstep',
        #                                                't_mult', 't_steps', 't_cond', 't_iter']].div(
        #         df_times['t_iter'],
        #         axis=0))

    if plot_error:
        result.plot_error()

    if not result.converged or result.converged:

        for i in range(problem.nbus):
            if abs(result.dlam[i]) >= 1e-3:
                problem.logger.add_warning('Nodal Power Balance convergence tolerance not achieved',
                                           device_property="dlam",
                                           device=str(i),
                                           value=str(result.dlam[i]),
                                           expected_value='< 1e-3')

            if abs(result.dlam[problem.nbus + i]) >= 1e-3:  # TODO: What is the difference with the previous?
                problem.logger.add_warning('Nodal Power Balance convergence tolerance not achieved',
                                           device_property="dlam",
                                           device=str(i),
                                           value=str(result.dlam[i + problem.nbus]),
                                           expected_value='< 1e-3')

        for pvbus in range(problem.npv):
            if abs(result.dlam[2 * problem.nbus + 1 + pvbus]) >= 1e-3:
                problem.logger.add_warning('PV voltage module convergence tolerance not achieved',
                                           device_property="dlam",
                                           device=str(problem.pv[pvbus]),
                                           value=str((result.dlam[2 * problem.nbus + 1 + pvbus])),
                                           expected_value='< 1e-3')

        for k in range(problem.n_br_mon):
            muz_f = abs(result.z[k] * result.mu[k])
            muz_t = abs(result.z[k + problem.n_br_mon] * result.mu[k + problem.n_br_mon])
            if muz_f >= 1e-3:
                problem.logger.add_warning('Branch rating "from" multipliers did not reach the tolerance',
                                           device_property="mu · z",
                                           device=str(problem.br_mon_idx[k]),
                                           value=str(muz_f),
                                           expected_value='< 1e-3')
            if muz_t >= 1e-3:
                problem.logger.add_warning('Branch rating "to" multipliers did not reach the tolerance',
                                           device_property="mu · z",
                                           device=str(problem.br_mon_idx[k]),
                                           value=str(muz_t),
                                           expected_value='< 1e-3')

        for link in range(problem.n_disp_hvdc):
            muz_f = abs(result.z[problem.nineq - 2 * problem.n_disp_hvdc + link] * result.mu[
                problem.nineq - 2 * problem.n_disp_hvdc + link])
            muz_t = abs(
                result.z[problem.nineq - problem.n_disp_hvdc + link] * result.mu[problem.nineq - problem.n_disp_hvdc + link])
            if muz_f >= 1e-3:
                problem.logger.add_warning('HVDC rating "from" multipliers did not reach the tolerance',
                                           device_property="mu · z",
                                           device=str(link),
                                           value=str(muz_f),
                                           expected_value='< 1e-3')
            if muz_t >= 1e-3:
                problem.logger.add_warning('HVDC rating "to" multipliers did not reach the tolerance',
                                           device_property="mu · z",
                                           device=str(link),
                                           value=str(muz_t),
                                           expected_value='< 1e-3')

        if problem.options.acopf_mode == AcOpfMode.ACOPFslacks:
            for k in range(problem.n_br_mon):
                if overloads_sf[k] > problem.options.ips_tolerance * problem.Sbase:
                    problem.logger.add_warning('Branch overload in the from sense (MVA)',
                                               device=str(problem.br_mon_idx[k]),
                                               device_property="Slack",
                                               value=str(overloads_sf[k]),
                                               expected_value=f'< {problem.options.ips_tolerance * problem.Sbase}')

                if overloads_st[k] > problem.options.ips_tolerance * problem.Sbase:
                    problem.logger.add_warning('Branch overload in the to sense (MVA)',
                                               device=str(problem.br_mon_idx[k]),
                                               device_property="Slack",
                                               value=str(overloads_st[k]),
                                               expected_value=f'< {problem.options.ips_tolerance * problem.Sbase}')

            for i in range(problem.npq):
                if problem.sl_vmax[i] > problem.options.ips_tolerance:
                    problem.logger.add_warning('Overvoltage',
                                               device_property="Slack",
                                               device=str(problem.pq[i]),
                                               value=str(problem.sl_vmax[i]),
                                               expected_value=f'>{problem.options.ips_tolerance}')
                if problem.sl_vmin[i] > problem.options.ips_tolerance:
                    problem.logger.add_warning('Undervoltage',
                                               device_property="Slack",
                                               device=str(problem.pq[i]),
                                               value=str(problem.sl_vmin[i]),
                                               expected_value=f'> {problem.options.ips_tolerance}')

    if verbose > 0:
        if len(problem.logger):
            problem.logger.print()

    return NonlinearOPFResults(Va=problem.Va, Vm=problem.Vm, S=problem.Scalc,
                               Sf=problem.Sftot, St=problem.Sttot, loading=loading,
                               Pg=Pg[:problem.ngen], Qg=Qg[:problem.ngen], Qsh=Qg[problem.ngen:], Pcost=Pcost[:problem.ngen],
                               tap_module=tap_module, tap_phase=tap_phase,
                               hvdc_Pf=hvdc_power, hvdc_loading=hvdc_loading,
                               lam_p=lam_p, lam_q=lam_q,
                               sl_sf=problem.sl_sf, sl_st=problem.sl_st, sl_vmax=problem.sl_vmax, sl_vmin=problem.sl_vmin,
                               nodal_capacity=nodal_capacity,
                               error=result.error,
                               converged=result.converged,
                               iterations=result.iterations)


def run_nonlinear_opf(grid: MultiCircuit,
                      opf_options: OptimalPowerFlowOptions,
                      pf_options: PowerFlowOptions,
                      t_idx: Union[None, int] = None,
                      debug: bool = False,
                      use_autodiff: bool = False,
                      pf_init=False,
                      Sbus_pf0: Union[CxVec, None] = None,
                      voltage_pf0: Union[CxVec, None] = None,
                      plot_error: bool = False,
                      optimize_nodal_capacity: bool = False,
                      nodal_capacity_sign: float = 1.0,
                      capacity_nodes_idx: Union[IntVec, None] = None,
                      logger: Logger = Logger()) -> NonlinearOPFResults:
    """
    Run optimal power flow for a MultiCircuit
    :param grid: MultiCircuit
    :param opf_options: OptimalPowerFlowOptions
    :param pf_options: PowerFlowOptions
    :param t_idx: Time index
    :param debug: debug? when active the autodiff is activated
    :param use_autodiff: Use autodiff?
    :param pf_init: Initialize with a power flow?
    :param Sbus_pf0: Sbus initial solution
    :param voltage_pf0: Voltage initial solution
    :param plot_error: Plot the error evolution
    :param optimize_nodal_capacity:
    :param nodal_capacity_sign:
    :param capacity_nodes_idx:
    :param logger: Logger object
    :return: NonlinearOPFResults
    """

    # compile the system
    nc = compile_numerical_circuit_at(circuit=grid, t_idx=t_idx, logger=logger)

    if pf_init:
        if Sbus_pf0 is None:
            # run power flow to initialize
            pf_results = multi_island_pf_nc(nc=nc, options=pf_options)
            Sbus_pf = pf_results.Sbus
            voltage_pf = pf_results.voltage
        else:
            # pick the passed values
            Sbus_pf = Sbus_pf0
            voltage_pf = voltage_pf0
    else:
        # initialize with sensible values
        Sbus_pf = nc.bus_data.installed_power
        voltage_pf = nc.bus_data.Vbus

    # split into islands, but considering the HVDC lines as actual links
    islands = nc.split_into_islands(ignore_single_node_islands=True,
                                    consider_hvdc_as_island_links=True)

    # create and initialize results
    results = NonlinearOPFResults()
    results.initialize(nbus=nc.nbus, nbr=nc.nbr, nsh=nc.nshunt, ng=nc.ngen,
                       nhvdc=nc.nhvdc, ncap=len(capacity_nodes_idx) if capacity_nodes_idx is not None else 0)

    for i, island in enumerate(islands):

        if capacity_nodes_idx is not None:
            # get the
            (capacity_nodes_idx_org,
             capacity_nodes_idx_isl) = remap_original_bus_indices(nbus=nc.nbus, orginal_bus_idx=capacity_nodes_idx)
        else:
            capacity_nodes_idx_org = None
            capacity_nodes_idx_isl = None

        # run the island ACOPF
        # island_res = ac_optimal_power_flow(nc=island,
        #                                    opf_options=opf_options,
        #                                    pf_options=pf_options,
        #                                    debug=debug,
        #                                    use_autodiff=use_autodiff,
        #                                    pf_init=pf_init,
        #                                    Sbus_pf=Sbus_pf[island.bus_data.original_idx],
        #                                    voltage_pf=voltage_pf[island.bus_data.original_idx],
        #                                    plot_error=plot_error,
        #                                    optimize_nodal_capacity=optimize_nodal_capacity,
        #                                    nodal_capacity_sign=nodal_capacity_sign,
        #                                    capacity_nodes_idx=capacity_nodes_idx_isl,
        #                                    logger=logger)

        problem = NonLinearOptimalPfProblem(nc=island,
                                            options=opf_options,
                                            pf_init=pf_init,
                                            Sbus_pf=Sbus_pf[island.bus_data.original_idx],
                                            voltage_pf=voltage_pf[island.bus_data.original_idx],
                                            optimize_nodal_capacity=optimize_nodal_capacity,
                                            nodal_capacity_sign=nodal_capacity_sign,
                                            capacity_nodes_idx=capacity_nodes_idx,
                                            logger=logger
                                            )

        island_res = solve(problem)

        results.merge(other=island_res,
                      bus_idx=island.bus_data.original_idx,
                      br_idx=island.passive_branch_data.original_idx,
                      il_idx=island.passive_branch_data.get_monitor_enabled_indices(),
                      gen_idx=island.generator_data.original_idx,
                      hvdc_idx=island.hvdc_data.original_idx,
                      ncap_idx=capacity_nodes_idx_org,
                      contshunt_idx=np.where(island.shunt_data.controllable == True)[0],
                      acopf_mode=opf_options.acopf_mode)
        if i > 0:
            results.error = max(results.error, island_res.error)
            results.iterations = max(results.iterations, island_res.iterations)
            results.converged = results.converged and island_res.converged if i > 0 else island_res.converged
        else:
            results.error = island_res.error
            results.iterations = island_res.iterations
            results.converged = island_res.converged

    # expand voltages if there was a bus topology reduction
    if nc.topology_performed:
        results.voltage = nc.propagate_bus_result(results.voltage)

    return results
