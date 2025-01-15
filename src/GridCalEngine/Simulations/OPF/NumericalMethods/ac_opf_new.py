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
from GridCalEngine.basic_structures import CxVec, IntVec, Logger


def run_nonlinear_opf(grid: MultiCircuit,
                      opf_options: OptimalPowerFlowOptions,
                      pf_options: PowerFlowOptions,
                      t_idx: Union[None, int] = None,
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

        problem = NonLinearOptimalPfProblem(nc=island,
                                            options=opf_options,
                                            pf_init=pf_init,
                                            Sbus_pf=Sbus_pf[island.bus_data.original_idx],
                                            voltage_pf=voltage_pf[island.bus_data.original_idx],
                                            optimize_nodal_capacity=optimize_nodal_capacity,
                                            nodal_capacity_sign=nodal_capacity_sign,
                                            capacity_nodes_idx=capacity_nodes_idx_isl,
                                            logger=logger
                                            )

        # the solver changes the internal state of the problem
        ips_results = interior_point_solver(problem=problem,
                                            max_iter=opf_options.ips_iterations,
                                            tol=opf_options.ips_tolerance,
                                            pf_init=opf_options.ips_init_with_pf,
                                            trust=opf_options.ips_trust_radius,
                                            verbose=opf_options.verbose,
                                            step_control=False)

        # once solved, we just gather the internal state
        island_res = problem.get_solution(ips_results=ips_results, verbose=opf_options.verbose, plot_error=plot_error)

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
