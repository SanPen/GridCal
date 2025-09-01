# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from typing import Union, Tuple, Sequence
from VeraGridEngine.Utils.NumericalMethods.ips import interior_point_solver
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from VeraGridEngine.Simulations.OPF.Formulations.ac_opf_problem import NonLinearOptimalPfProblem, NonlinearOPFResults
from VeraGridEngine.Simulations.OPF.NumericalMethods.newton_raphson_ips_fx import interior_point_solver
from VeraGridEngine.basic_structures import CxVec, IntVec, Logger


def remap_original_bus_indices(n_bus, original_bus_idx: Sequence[int]) -> Tuple[IntVec, IntVec]:
    """
    Get arrays of bus mappings
    :param n_bus: number of buses
    :param original_bus_idx: array of bus indices in the multi-island scheme
    :return: original_indices: array of bus indices in the multi-island that apply for this island,
             island_indices: array of island indices that apply for this island
    """
    original_idx = np.arange(n_bus, dtype=int)
    mapping = {o: i for i, o in enumerate(original_idx)}
    island_indices = list()
    original_indices = list()
    for a, o in enumerate(original_bus_idx):
        i = mapping.get(o, None)
        if i is not None:
            island_indices.append(i)
            original_indices.append(a)

    return np.array(original_indices, dtype=int), np.array(island_indices, dtype=int)


def run_nonlinear_opf(grid: MultiCircuit,
                      opf_options: OptimalPowerFlowOptions,
                      t_idx: Union[None, int] = None,
                      plot_error: bool = False,
                      optimize_nodal_capacity: bool = False,
                      nodal_capacity_sign: float = 1.0,
                      capacity_nodes_idx: Union[IntVec, None] = None,
                      logger: Logger = Logger()) -> NonlinearOPFResults:
    """
    Run optimal power flow for a MultiCircuit
    :param grid: MultiCircuit
    :param opf_options: OptimalPowerFlowOptions
    :param t_idx: Time index
    :param plot_error: Plot the error evolution
    :param optimize_nodal_capacity:
    :param nodal_capacity_sign:
    :param capacity_nodes_idx:
    :param logger: Logger object
    :return: NonlinearOPFResults
    """

    # compile the system
    nc = compile_numerical_circuit_at(circuit=grid, t_idx=t_idx, logger=logger)

    if opf_options.ips_init_with_pf and opf_options.acopf_S0 is not None and opf_options.acopf_v0 is not None:
        # pick the passed values
        Sbus_pf = opf_options.acopf_S0
        voltage_pf = opf_options.acopf_v0
    else:
        # pick the default values
        Sbus_pf = nc.bus_data.installed_power
        voltage_pf = nc.bus_data.Vbus
        logger.add_error("Initialized with PF, but no PF values were passed")

    # split into islands, but considering the HVDC lines as actual links
    islands = nc.split_into_islands(ignore_single_node_islands=True,
                                    consider_hvdc_as_island_links=True)

    # create and initialize results
    results = NonlinearOPFResults()
    results.initialize(nbus=nc.nbus, nbr=nc.nbr, nsh=nc.nshunt, ng=nc.ngen, nil=len(nc.passive_branch_data.get_monitor_enabled_indices()),
                       nhvdc=nc.nhvdc, ncap=len(capacity_nodes_idx) if capacity_nodes_idx is not None else 0)

    for i, island in enumerate(islands):

        if capacity_nodes_idx is not None:
            # get the
            (capacity_nodes_idx_org,
             capacity_nodes_idx_isl) = remap_original_bus_indices(n_bus=nc.nbus, original_bus_idx=capacity_nodes_idx)
        else:
            capacity_nodes_idx_org = None
            capacity_nodes_idx_isl = None

        problem = NonLinearOptimalPfProblem(nc=island,
                                            options=opf_options,
                                            pf_init=opf_options.ips_init_with_pf,
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

        results.Va = nc.propagate_bus_result(results.Va)
        results.Vm = nc.propagate_bus_result(results.Vm)
        results.voltage = nc.propagate_bus_result(results.voltage)

    return results
