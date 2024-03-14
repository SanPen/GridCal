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
from typing import Union
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_results import ContingencyAnalysisResults
from GridCalEngine.Simulations.ContingencyAnalysis.Methods.helm_contingencies import HelmVariations
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions, SolverType
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_options import ContingencyAnalysisOptions


def helm_contingency_analysis(grid: MultiCircuit,
                              options: ContingencyAnalysisOptions,
                              calling_class,
                              t: Union[int, None] = None,
                              t_prob: float = 1.0) -> ContingencyAnalysisResults:
    """
    Run N-1 simulation in series with HELM, non-linear solution
    :param grid:
    :param options:
    :param calling_class:
    :param t: time index, if None the snapshot is used
    :param t_prob: probability of te time
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

    branches_dict = grid.get_branches_wo_hvdc_dict()
    calc_branches = grid.get_branches_wo_hvdc()
    mon_idx = numerical_circuit.branch_data.get_monitor_enabled_indices()

    # keep the original states
    original_br_active = numerical_circuit.branch_data.active.copy()
    original_gen_active = numerical_circuit.generator_data.active.copy()
    original_gen_p = numerical_circuit.generator_data.p.copy()

    # run 0
    pf_res_0 = multi_island_pf_nc(nc=numerical_circuit,
                                  options=pf_opts)

    helm_variations = HelmVariations(numerical_circuit=numerical_circuit)

    # for each contingency group
    for ic, contingency_group in enumerate(grid.contingency_groups):

        # get the group's contingencies
        contingencies = cg_dict[contingency_group.idtag]

        # apply the contingencies
        contingency_br_indices = list()
        for cnt in contingencies:

            # search for the contingency in the Branches
            if cnt.device_idtag in branches_dict:
                br_idx = branches_dict[cnt.device_idtag]

                if cnt.prop == 'active':
                    contingency_br_indices.append(br_idx)
                else:
                    print(f'Unknown contingency property {cnt.prop} at {cnt.name} {cnt.idtag}')
            else:
                pass

        # report progress
        if t is None:
            if calling_class is not None:
                calling_class.report_text(f'Contingency group: {contingency_group.name}')
                calling_class.report_progress2(ic, len(grid.contingency_groups) * 100)

        # run
        V, Sf, loading = helm_variations.compute_variations(contingency_br_indices=contingency_br_indices)

        results.Sf[ic, :] = Sf
        results.Sbus[ic, :] = numerical_circuit.Sbus
        results.loading[ic, :] = loading
        results.report.analyze(t=t,
                               t_prob=t_prob,
                               mon_idx=mon_idx,
                               numerical_circuit=numerical_circuit,
                               base_flow=np.abs(pf_res_0.Sf),
                               base_loading=np.abs(pf_res_0.loading),
                               contingency_flows=np.abs(Sf),
                               contingency_loadings=np.abs(loading),
                               contingency_idx=ic,
                               contingency_group=contingency_group)

        # revert the states for the next run
        numerical_circuit.branch_data.active = original_br_active.copy()
        numerical_circuit.generator_data.active = original_gen_active.copy()
        numerical_circuit.generator_data.p = original_gen_p.copy()

        if calling_class is not None:
            if calling_class.is_cancelled():
                return results

    return results
