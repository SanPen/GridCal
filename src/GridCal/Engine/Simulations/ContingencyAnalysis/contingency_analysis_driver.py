# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

import time
import numpy as np
from typing import Union
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.numerical_circuit import compile_numerical_circuit_at
import GridCal.Engine.basic_structures as bs
from GridCal.Engine.basic_structures import Vec
from GridCal.Engine.Simulations.ContingencyAnalysis.contingency_analysis_results import ContingencyAnalysisResults
from GridCal.Engine.Simulations.ContingencyAnalysis.helm_contingencies import HelmVariations
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.driver_template import DriverTemplate
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions, SolverType
from GridCal.Engine.Simulations.LinearFactors.linear_analysis import LinearAnalysis
from GridCal.Engine.Simulations.ContingencyAnalysis.contingency_analysis_options import ContingencyAnalysisOptions


class ContingencyAnalysisDriver(DriverTemplate):
    """
    Contingency analysis driver
    """
    name = 'Contingency Analysis'
    tpe = SimulationTypes.ContingencyAnalysis_run

    def __init__(self, grid: MultiCircuit,
                 options: ContingencyAnalysisOptions,
                 engine: bs.EngineType = bs.EngineType.GridCal):
        """
        ContingencyAnalysisDriver constructor
        :param grid: MultiCircuit Object
        :param options: N-k options
        :param engine Calculation engine to use
        """
        DriverTemplate.__init__(self, grid=grid, engine=engine)

        # Options to use
        self.options = options

        # N-K results
        self.results = ContingencyAnalysisResults(
            ncon=0,
            nbus=0,
            nbr=0,
            bus_names=(),
            branch_names=(),
            bus_types=(),
            con_names=()
        )

    def get_steps(self):
        """
        Get variations list of strings
        """
        if self.results is not None:
            return ['#' + v for v in self.results.branch_names]
        else:
            return list()

    def n_minus_k(self, t=None):
        """
        Run N-1 simulation in series
        :param t: time index, if None the snapshot is used
        :return: returns the results
        """
        # set the numerical circuit
        numerical_circuit = compile_numerical_circuit_at(self.grid, t_idx=t)

        if self.options.pf_options is None:
            pf_opts = PowerFlowOptions(
                solver_type=SolverType.DC,
                ignore_single_node_islands=True
            )

        else:
            pf_opts = self.options.pf_options

        # declare the results
        results = ContingencyAnalysisResults(ncon=len(self.grid.contingency_groups),
                                             nbr=numerical_circuit.nbr,
                                             nbus=numerical_circuit.nbus,
                                             branch_names=numerical_circuit.branch_names,
                                             bus_names=numerical_circuit.bus_names,
                                             bus_types=numerical_circuit.bus_types,
                                             con_names=self.grid.get_contingency_group_names())

        # get contingency groups dictionary
        cg_dict = self.grid.get_contingency_group_dict()

        branches_dict = self.grid.get_branches_wo_hvdc_dict()
        calc_branches = self.grid.get_branches_wo_hvdc()
        mon_idx = numerical_circuit.branch_data.get_monitor_enabled_indices()

        # keep the original states
        original_br_active = numerical_circuit.branch_data.active.copy()
        original_gen_active = numerical_circuit.generator_data.active.copy()
        original_gen_p = numerical_circuit.generator_data.p.copy()

        # run 0
        pf_res_0 = multi_island_pf_nc(nc=numerical_circuit,
                                      options=pf_opts)

        # for each contingency group
        for ic, contingency_group in enumerate(self.grid.contingency_groups):

            # get the group's contingencies
            contingencies = cg_dict[contingency_group.idtag]

            # apply the contingencies
            for cnt in contingencies:

                # search for the contingency in the Branches
                if cnt.device_idtag in branches_dict:
                    br_idx = branches_dict[cnt.device_idtag]

                    if cnt.prop == 'active':
                        numerical_circuit.branch_data.active[br_idx] = int(cnt.value)
                    else:
                        print(f'Unknown contingency property {cnt.prop} at {cnt.name} {cnt.idtag}')
                else:
                    pass

            # report progress
            if t is None:
                self.progress_text.emit(f'Contingency group: {contingency_group.name}')
                self.progress_signal.emit((ic + 1) / len(self.grid.contingency_groups) * 100)

            # run
            pf_res = multi_island_pf_nc(nc=numerical_circuit,
                                        options=pf_opts,
                                        V_guess=pf_res_0.voltage)

            results.Sf[ic, :] = pf_res.Sf
            results.S[ic, :] = pf_res.Sbus
            results.loading[ic, :] = pf_res.loading
            results.report.analyze(t=t,
                                   mon_idx=mon_idx,
                                   calc_branches=calc_branches,
                                   numerical_circuit=numerical_circuit,
                                   flows=np.abs(pf_res_0.Sf),
                                   loading=np.abs(pf_res_0.loading),
                                   contingency_flows=np.abs(pf_res.Sf),
                                   contingency_loadings=np.abs(pf_res.loading),
                                   contingency_idx=ic,
                                   contingency_group=contingency_group)

            # revert the states for the next run
            numerical_circuit.branch_data.active = original_br_active.copy()
            numerical_circuit.generator_data.active = original_gen_active.copy()
            numerical_circuit.generator_data.p = original_gen_p.copy()

            if self.__cancel__:
                return results

        return results

    def n_minus_k_helm(self, t: Union[int, None] = None):
        """
        Run N-1 simulation in series with HELM, non-linear solution
        :param t: time index, if None the snapshot is used
        :return: returns the results
        """

        # set the numerical circuit
        numerical_circuit = compile_numerical_circuit_at(self.grid, t_idx=t)

        if self.options.pf_options is None:
            pf_opts = PowerFlowOptions(solver_type=SolverType.DC,
                                       ignore_single_node_islands=True)

        else:
            pf_opts = self.options.pf_options

        # declare the results
        results = ContingencyAnalysisResults(ncon=len(self.grid.contingency_groups),
                                             nbr=numerical_circuit.nbr,
                                             nbus=numerical_circuit.nbus,
                                             branch_names=numerical_circuit.branch_names,
                                             bus_names=numerical_circuit.bus_names,
                                             bus_types=numerical_circuit.bus_types,
                                             con_names=self.grid.get_contingency_group_names())

        # get contingency groups dictionary
        cg_dict = self.grid.get_contingency_group_dict()

        branches_dict = self.grid.get_branches_wo_hvdc_dict()
        calc_branches = self.grid.get_branches_wo_hvdc()
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
        for ic, contingency_group in enumerate(self.grid.contingency_groups):

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
                self.progress_text.emit(f'Contingency group: {contingency_group.name}')
                self.progress_signal.emit((ic + 1) / len(self.grid.contingency_groups) * 100)

            # run
            V, Sf, loading = helm_variations.compute_variations(contingency_br_indices=contingency_br_indices)

            results.Sf[ic, :] = Sf
            results.S[ic, :] = numerical_circuit.Sbus
            results.loading[ic, :] = loading
            results.report.analyze(t=t,
                                   mon_idx=mon_idx,
                                   calc_branches=calc_branches,
                                   numerical_circuit=numerical_circuit,
                                   flows=np.abs(pf_res_0.Sf),
                                   loading=np.abs(pf_res_0.loading),
                                   contingency_flows=np.abs(Sf),
                                   contingency_loadings=np.abs(loading),
                                   contingency_idx=ic,
                                   contingency_group=contingency_group)

            # revert the states for the next run
            numerical_circuit.branch_data.active = original_br_active.copy()
            numerical_circuit.generator_data.active = original_gen_active.copy()
            numerical_circuit.generator_data.p = original_gen_p.copy()

            if self.__cancel__:
                return results

        return results

    def n_minus_k_ptdf(self, t: Union[int, None] = None):
        """
        Run N-1 simulation in series with HELM, non-linear solution
        :param t: time index, if None the snapshot is used
        :return: returns the results
        """

        self.progress_text.emit('Analyzing outage distribution factors in a non-linear fashion...')

        # set the numerical circuit
        numerical_circuit = compile_numerical_circuit_at(self.grid, t_idx=t)

        calc_branches = self.grid.get_branches_wo_hvdc()

        # declare the results
        results = ContingencyAnalysisResults(ncon=len(self.grid.contingency_groups),
                                             nbr=numerical_circuit.nbr,
                                             nbus=numerical_circuit.nbus,
                                             branch_names=numerical_circuit.branch_names,
                                             bus_names=numerical_circuit.bus_names,
                                             bus_types=numerical_circuit.bus_types,
                                             con_names=self.grid.get_contingency_group_names())

        linear_analysis = LinearAnalysis(numerical_circuit=numerical_circuit,
                                         distributed_slack=False,
                                         correct_values=True)
        linear_analysis.run()

        # get the contingency branch indices
        mon_idx = numerical_circuit.branch_data.get_monitor_enabled_indices()
        Pbus = numerical_circuit.get_injections(False).real

        # compute the branch Sf in "n"
        if self.options.use_provided_flows:
            flows_n = self.options.Pf

            if self.options.Pf is None:
                msg = 'The option to use the provided flows is enabled, but no flows are available'
                self.logger.add_error(msg)
                raise Exception(msg)
        else:
            flows_n = linear_analysis.get_flows(numerical_circuit.Sbus) * numerical_circuit.Sbase

        loadings_n = flows_n / (numerical_circuit.rates + 1e-9)

        self.progress_text.emit('Computing loading...')

        # get contingency groups dictionary
        cg_dict = self.grid.get_contingency_group_dict()
        branches_dict = self.grid.get_branches_wo_hvdc_dict()

        # for each contingency group
        for ic, contingency_group in enumerate(self.grid.contingency_groups):

            # get the group's contingencies
            contingencies = cg_dict[contingency_group.idtag]

            # report progress
            if t is None:
                self.progress_text.emit(f'Contingency group: {contingency_group.name}')
                self.progress_signal.emit((ic + 1) / len(self.grid.contingency_groups) * 100)

            # apply the contingencies
            if len(contingencies) == 1:  # can only handle single contingencies ...

                # apply the contingencies
                for cnt in contingencies:

                    # search for the contingency in the Branches
                    if cnt.device_idtag in branches_dict:
                        br_idx = branches_dict[cnt.device_idtag]

                        if cnt.prop == 'active':
                            c_flow = flows_n[mon_idx] + linear_analysis.LODF[mon_idx, br_idx] * flows_n[br_idx]
                            c_loading = c_flow / (numerical_circuit.ContingencyRates[mon_idx] + 1e-9)

                            results.Sf[ic, :] = c_flow  # already in MW
                            results.S[ic, :] = Pbus
                            results.loading[ic, :] = c_loading
                            results.report.analyze(t=t,
                                                   mon_idx=mon_idx,
                                                   calc_branches=calc_branches,
                                                   numerical_circuit=numerical_circuit,
                                                   flows=flows_n,
                                                   loading=loadings_n,
                                                   contingency_flows=c_flow,
                                                   contingency_loadings=c_loading,
                                                   contingency_idx=ic,
                                                   contingency_group=contingency_group)

                        else:
                            print(f'Unknown contingency property {cnt.prop} at {cnt.name} {cnt.idtag}')
                    else:
                        pass
            else:
                print("Cannot handle multiple contingencies with the PTDF method")

        results.lodf = linear_analysis.LODF

        return results

    def run(self) -> None:
        """

        :return:
        """
        start = time.time()

        if self.options.engine == bs.ContingencyEngine.PowerFlow:
            self.results = self.n_minus_k()

        elif self.options.engine == bs.ContingencyEngine.PTDF:
            self.results = self.n_minus_k_ptdf()

        elif self.options.engine == bs.ContingencyEngine.HELM:
            self.results = self.n_minus_k_helm()

        else:
            self.results = self.n_minus_k()

        end = time.time()
        self.elapsed = end - start
