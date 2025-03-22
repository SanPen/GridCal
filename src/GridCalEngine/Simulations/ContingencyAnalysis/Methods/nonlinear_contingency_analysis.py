# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING, Union
import numpy as np
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_results import ContingencyAnalysisResults
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions, SolverType
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis, LinearMultiContingencies
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_options import ContingencyAnalysisOptions
from GridCalEngine.basic_structures import Logger

if TYPE_CHECKING:
    from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import ContingencyAnalysisDriver


def nonlinear_contingency_analysis(grid: MultiCircuit,
                                   options: ContingencyAnalysisOptions,
                                   linear_multiple_contingencies: LinearMultiContingencies,
                                   calling_class: ContingencyAnalysisDriver,
                                   t_idx: Union[None, int] = None,
                                   t_prob: float = 1.0,
                                   logger: Logger | None = None, ) -> ContingencyAnalysisResults:
    """
    Run a contingency analysis using the power flow options
    :param grid: MultiCircuit
    :param options: ContingencyAnalysisOptions
    :param linear_multiple_contingencies: LinearMultiContingencies
    :param calling_class: ContingencyAnalysisDriver
    :param t_idx: time index, if None the snapshot is used
    :param t_prob: probability of te time
    :param logger: logging object
    :return: returns the results (ContingencyAnalysisResults)
    """
    if logger is None:
        logger = Logger()

    # set the numerical circuit
    nc = compile_numerical_circuit_at(grid, t_idx=t_idx)

    if options.pf_options is None:
        pf_opts = PowerFlowOptions(solver_type=SolverType.DC,
                                   ignore_single_node_islands=True)

    else:
        pf_opts = options.pf_options

    area_names, bus_area_indices, F, T, hvdc_F, hvdc_T = grid.get_branch_areas_info()

    # declare the results
    results = ContingencyAnalysisResults(ncon=len(linear_multiple_contingencies.contingency_groups_used),
                                         nbr=nc.nbr,
                                         nbus=nc.nbus,
                                         branch_names=nc.passive_branch_data.names,
                                         bus_names=nc.bus_data.names,
                                         bus_types=nc.bus_data.bus_types,
                                         con_names=linear_multiple_contingencies.get_contingency_group_names())

    # get contingency groups dictionary
    mon_idx = nc.passive_branch_data.get_monitor_enabled_indices()

    # run 0
    pf_res_0 = multi_island_pf_nc(nc=nc,
                                  options=pf_opts)

    if options.use_srap:

        # we need the PTDF for this
        linear_analysis = LinearAnalysis(numerical_circuit=nc,
                                         distributed_slack=options.lin_options.distribute_slack,
                                         correct_values=options.lin_options.correct_values)

        linear_multiple_contingencies.compute(lodf=linear_analysis.LODF,
                                              ptdf=linear_analysis.PTDF,
                                              ptdf_threshold=options.lin_options.ptdf_threshold,
                                              lodf_threshold=options.lin_options.lodf_threshold)

        PTDF = linear_analysis.PTDF

    else:
        PTDF = None

    available_power = nc.generator_data.get_injections_per_bus().real

    # for each contingency group
    for ic, contingency_group in enumerate(linear_multiple_contingencies.contingency_groups_used):

        # get the group's contingencies
        contingencies = linear_multiple_contingencies.contingency_group_dict[contingency_group.idtag]

        # set the status
        nc.set_con_or_ra_status(contingencies)

        # report progress
        if t_idx is None and calling_class is not None:
            calling_class.report_text(f'Contingency group: {contingency_group.name}')
            calling_class.report_progress2(ic, len(linear_multiple_contingencies.contingency_groups_used) * 100)

        # run
        pf_res = multi_island_pf_nc(nc=nc,
                                    options=pf_opts,
                                    V_guess=pf_res_0.voltage,
                                    logger=logger)

        results.Sf[ic, :] = pf_res.Sf
        results.Sbus[ic, :] = pf_res.Sbus
        results.loading[ic, :] = pf_res.loading
        results.voltage[ic, :] = pf_res.voltage
        multi_contingency = linear_multiple_contingencies.multi_contingencies[ic] if options.use_srap else None

        results.report.analyze(t=t_idx,
                               t_prob=t_prob,
                               mon_idx=mon_idx,
                               nc=nc,
                               base_flow=np.abs(pf_res_0.Sf),
                               base_loading=np.abs(pf_res_0.loading),
                               contingency_flows=np.abs(pf_res.Sf),
                               contingency_loadings=np.abs(pf_res.loading),
                               contingency_idx=ic,
                               contingency_group=contingency_group,
                               using_srap=options.use_srap,
                               srap_ratings=nc.passive_branch_data.protection_rates,
                               srap_max_power=options.srap_max_power,
                               srap_deadband=options.srap_deadband,
                               contingency_deadband=options.contingency_deadband,
                               multi_contingency=multi_contingency,
                               PTDF=PTDF,
                               available_power=available_power,
                               srap_used_power=results.srap_used_power,
                               F=F,
                               T=T,
                               bus_area_indices=bus_area_indices,
                               area_names=area_names,
                               top_n=options.srap_top_n)

        # set the status
        nc.set_con_or_ra_status(contingencies, revert=True)

        if calling_class is not None:
            if calling_class.is_cancel():
                return results

    return results
