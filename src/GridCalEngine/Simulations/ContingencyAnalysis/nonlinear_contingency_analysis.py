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

import numpy as np
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_results import ContingencyAnalysisResults
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions, SolverType
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_options import ContingencyAnalysisOptions
from GridCalEngine.Simulations.LinearFactors.srap import get_buses_for_srap_list


def nonlinear_contingency_analysis(grid: MultiCircuit,
                                   options: ContingencyAnalysisOptions,
                                   calling_class, t=None) -> ContingencyAnalysisResults:
    """
    Run N-1 simulation in series
    :param grid:
    :param options:
    :param calling_class:
    :param t: time index, if None the snapshot is used
    :return: returns the results
    """
    # set the numerical circuit
    numerical_circuit = compile_numerical_circuit_at(grid, t_idx=t)

    if options.pf_options is None:
        pf_opts = PowerFlowOptions(solver_type=SolverType.DC,
                                   ignore_single_node_islands=True)

    else:
        pf_opts = options.pf_options

    # declare the results
    results = ContingencyAnalysisResults(ncon=len(grid.contingency_groups),
                                         nbr=numerical_circuit.nbr,
                                         nbus=numerical_circuit.nbus,
                                         branch_names=numerical_circuit.branch_names,
                                         bus_names=numerical_circuit.bus_names,
                                         bus_types=numerical_circuit.bus_types,
                                         con_names=grid.get_contingency_group_names())

    # get contingency groups dictionary
    cg_dict = grid.get_contingency_group_dict()
    calc_branches = grid.get_branches_wo_hvdc()
    mon_idx = numerical_circuit.branch_data.get_monitor_enabled_indices()

    # run 0
    pf_res_0 = multi_island_pf_nc(nc=numerical_circuit,
                                  options=pf_opts)

    if options.use_srap:

        # we need the PTDF for this
        linear_analysis = LinearAnalysis(numerical_circuit=numerical_circuit,
                                         distributed_slack=options.lin_options.distribute_slack,
                                         correct_values=options.lin_options.correct_values)
        linear_analysis.run()

        # construct a list of information structures about how to deal with SRAP
        buses_for_srap_list = get_buses_for_srap_list(PTDF=linear_analysis.PTDF,
                                                      threshold=0.01  # self.options.lin_options.ptdf_threshold
                                                      )
    else:
        buses_for_srap_list = list()

    # for each contingency group
    for ic, contingency_group in enumerate(grid.contingency_groups):

        # get the group's contingencies
        contingencies = cg_dict[contingency_group.idtag]

        # set the status
        numerical_circuit.set_contingency_status(contingencies)

        # report progress
        if t is None and calling_class is not None:
            calling_class.report_text(f'Contingency group: {contingency_group.name}')
            calling_class.report_progress2(ic, len(grid.contingency_groups) * 100)

        # run
        pf_res = multi_island_pf_nc(nc=numerical_circuit,
                                    options=pf_opts,
                                    V_guess=pf_res_0.voltage)

        results.Sf[ic, :] = pf_res.Sf
        results.Sbus[ic, :] = pf_res.Sbus
        results.loading[ic, :] = pf_res.loading
        results.voltage[ic, :] = pf_res.voltage
        results.report.analyze(t=t,
                               mon_idx=mon_idx,
                               calc_branches=calc_branches,
                               numerical_circuit=numerical_circuit,
                               flows=np.abs(pf_res_0.Sf),
                               loading=np.abs(pf_res_0.loading),
                               contingency_flows=np.abs(pf_res.Sf),
                               contingency_loadings=np.abs(pf_res.loading),
                               contingency_idx=ic,
                               contingency_group=contingency_group,
                               using_srap=options.use_srap,
                               srap_max_loading=options.srap_max_loading,
                               srap_max_power=options.srap_max_power,
                               buses_for_srap_list=buses_for_srap_list)

        # set the status
        numerical_circuit.set_contingency_status(contingencies, revert=True)

        if calling_class is not None:
            if calling_class.is_cancel():
                return results

    return results
