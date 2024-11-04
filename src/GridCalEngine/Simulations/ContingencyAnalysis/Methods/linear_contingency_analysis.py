# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_results import ContingencyAnalysisResults
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis, LinearMultiContingencies
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_options import ContingencyAnalysisOptions
from GridCalEngine.basic_structures import Logger

if TYPE_CHECKING:
    from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import ContingencyAnalysisDriver


def linear_contingency_analysis(grid: MultiCircuit,
                                options: ContingencyAnalysisOptions,
                                linear_multiple_contingencies: LinearMultiContingencies,
                                calling_class: ContingencyAnalysisDriver,
                                t=None,
                                t_prob=1.0,
                                logger: Logger | None = None, ) -> ContingencyAnalysisResults:
    """
    Run N-1 simulation in series with HELM, non-linear solution
    :param grid: MultiCircuit
    :param options: ContingencyAnalysisOptions
    :param linear_multiple_contingencies: LinearMultiContingencies
    :param calling_class: ContingencyAnalysisDriver
    :param t: time index, if None the snapshot is used
    :param t_prob: probability of te time
    :param logger: logger instance
    :return: returns the results
    """

    if calling_class is not None:
        calling_class.report_text('Analyzing outage distribution factors in a non-linear fashion...')

    # set the numerical circuit
    numerical_circuit = compile_numerical_circuit_at(grid, t_idx=t)

    # get areas info
    area_names, bus_area_indices, F, T, hvdc_F, hvdc_T = grid.get_branch_areas_info()

    # declare the results
    results = ContingencyAnalysisResults(ncon=len(linear_multiple_contingencies.contingency_groups_used),
                                         nbr=numerical_circuit.nbr,
                                         nbus=numerical_circuit.nbus,
                                         branch_names=numerical_circuit.branch_names,
                                         bus_names=numerical_circuit.bus_names,
                                         bus_types=numerical_circuit.bus_types,
                                         con_names=linear_multiple_contingencies.get_contingency_group_names())

    linear_analysis = LinearAnalysis(numerical_circuit=numerical_circuit,
                                     distributed_slack=options.lin_options.distribute_slack,
                                     correct_values=options.lin_options.correct_values)
    linear_analysis.run()

    linear_multiple_contingencies.compute(lodf=linear_analysis.LODF,
                                          ptdf=linear_analysis.PTDF,
                                          ptdf_threshold=options.lin_options.ptdf_threshold,
                                          lodf_threshold=options.lin_options.lodf_threshold,
                                          prepare_for_srap=options.use_srap)

    # get the contingency branch indices
    mon_idx = numerical_circuit.branch_data.get_monitor_enabled_indices()
    Pbus = numerical_circuit.get_injections(normalize=False).real

    # compute the branch Sf in "n"
    if options.use_provided_flows:
        flows_n = options.Pf

        if options.Pf is None:
            msg = 'The option to use the provided flows is enabled, but no flows are available'
            calling_class.logger.add_error(msg)
            raise Exception(msg)
    else:
        flows_n = linear_analysis.get_flows(numerical_circuit.Sbus) * numerical_circuit.Sbase

    loadings_n = flows_n / (numerical_circuit.rates + 1e-9)

    if calling_class is not None:
        calling_class.report_text('Computing loading...')

    # for each contingency group
    for ic, multi_contingency in enumerate(linear_multiple_contingencies.multi_contingencies):

        if multi_contingency.has_injection_contingencies():
            cnt = grid.contingencies
            injections = numerical_circuit.set_linear_con_or_ra_status(event_list=cnt)
        else:
            injections = None

        c_flow = multi_contingency.get_contingency_flows(base_flow=flows_n, injections=injections)
        c_loading = c_flow / (numerical_circuit.rates + 1e-9)

        results.Sf[ic, :] = c_flow  # already in MW
        results.Sbus[ic, :] = Pbus
        results.loading[ic, :] = c_loading
        results.report.analyze(t=t,
                               t_prob=t_prob,
                               mon_idx=mon_idx,
                               numerical_circuit=numerical_circuit,
                               base_flow=flows_n,
                               base_loading=loadings_n,
                               contingency_flows=c_flow,
                               contingency_loadings=c_loading,
                               contingency_idx=ic,
                               contingency_group=linear_multiple_contingencies.contingency_groups_used[ic],
                               using_srap=options.use_srap,
                               srap_ratings=numerical_circuit.branch_data.protection_rates,
                               srap_max_power=options.srap_max_power,
                               srap_deadband=options.srap_deadband,
                               contingency_deadband=options.contingency_deadband,
                               srap_rever_to_nominal_rating=options.srap_rever_to_nominal_rating,
                               multi_contingency=multi_contingency,
                               PTDF=linear_analysis.PTDF,
                               available_power=numerical_circuit.bus_data.srap_availbale_power,
                               srap_used_power=results.srap_used_power,
                               F=F,
                               T=T,
                               bus_area_indices=bus_area_indices,
                               area_names=area_names,
                               top_n=options.srap_top_n)

        # report progress
        if t is None:
            if calling_class is not None:
                calling_class.report_text(
                    f'Contingency group: {linear_multiple_contingencies.contingency_groups_used[ic].name}')
                calling_class.report_progress2(ic, len(linear_multiple_contingencies.multi_contingencies))

    results.lodf = linear_analysis.LODF

    return results
