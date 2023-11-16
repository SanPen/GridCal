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
from numba import jit, prange
from typing import Union

import GridCalEngine.basic_structures as bs
from GridCalEngine.basic_structures import IntVec, StrVec
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearMultiContingencies
from GridCalEngine.Simulations.LinearFactors.linear_analysis_options import LinearAnalysisOptions
from GridCalEngine.Simulations.LinearFactors.linear_analysis_ts_driver import LinearAnalysisTimeSeriesDriver
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import ContingencyAnalysisOptions, \
    ContingencyAnalysisDriver
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_ts_results import \
    ContingencyAnalysisTimeSeriesResults
from GridCalEngine.Simulations.driver_types import SimulationTypes
from GridCalEngine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCalEngine.Simulations.Clustering.clustering_results import ClusteringResults
from GridCalEngine.Core.Compilers.circuit_to_newton_pa import newton_pa_contingencies


@jit(nopython=True, parallel=False, cache=True)
def compute_flows_numba_t(e, c, nt, LODF, Flows, rates, overload_count, max_overload, worst_flows):
    """
    Compute LODF based flows (Sf)
    :param e: element index
    :param c: contingency element index
    :param nt: number of time steps
    :param LODF: LODF matrix (element, failed element)
    :param Flows: base Sf matrix (time, element)
    :param rates: Matrix of rates (time, element)
    :param overload_count: [out] number of overloads per element (element, contingency element)
    :param max_overload: [out] maximum overload per element (element, contingency element)
    :param worst_flows: [out] worst flows per element (time, element)
    :return: Cube of N-1 Flows (time, elements, contingencies)
    """

    for t in range(nt):
        # the formula is: Fn-1(i) = Fbase(i) + LODF(i,j) * Fbase(j) here i->line, j->failed line
        flow_n_1 = LODF[e, c] * Flows[t, c] + Flows[t, e]
        flow_n_1_abs = abs(flow_n_1)

        if rates[t, e] > 0:
            rate = flow_n_1_abs / rates[t, e]

            if rate > 1:
                overload_count[e, c] += 1
                if flow_n_1_abs > max_overload[e, c]:
                    max_overload[e, c] = flow_n_1_abs

        if flow_n_1_abs > abs(worst_flows[t, e]):
            worst_flows[t, e] = flow_n_1


@jit(nopython=True, parallel=True, cache=True)
def compute_flows_numba(e, nt, contingency_branch_idx, LODF, Flows, rates, overload_count,
                        max_overload, worst_flows, parallelize_from=500):
    """
    Compute LODF based Sf
    :param e: element index
    :param nt: number of time steps
    :param contingency_branch_idx: list of branch indices to fail
    :param LODF: LODF matrix (element, failed element)
    :param Flows: base Sf matrix (time, element)
    :param rates:
    :param overload_count:
    :param max_overload:
    :param worst_flows:
    :param parallelize_from:
    :return:  Cube of N-1 Flows (time, elements, contingencies)
    """
    nc = len(contingency_branch_idx)
    if nc < parallelize_from:
        for ic in range(nc):
            c = contingency_branch_idx[ic]
            compute_flows_numba_t(
                e=e,
                c=c,
                nt=nt,
                LODF=LODF,
                Flows=Flows,
                rates=rates,
                overload_count=overload_count,
                max_overload=max_overload,
                worst_flows=worst_flows,
            )
    else:
        for ic in prange(nc):
            c = contingency_branch_idx[ic]
            compute_flows_numba_t(
                e=e,
                c=c,
                nt=nt,
                LODF=LODF,
                Flows=Flows,
                rates=rates,
                overload_count=overload_count,
                max_overload=max_overload,
                worst_flows=worst_flows,
            )


class ContingencyAnalysisTimeSeries(TimeSeriesDriverTemplate):
    """
    Contingency Analysis Time Series
    """
    name = 'Contingency analysis time series'
    tpe = SimulationTypes.ContingencyAnalysisTS_run

    def __init__(self,
                 grid: MultiCircuit,
                 options: Union[ContingencyAnalysisOptions, LinearAnalysisOptions],
                 time_indices: IntVec,
                 clustering_results: Union["ClusteringResults", None] = None,
                 engine: bs.EngineType = bs.EngineType.GridCal):
        """
        Contingecny analysis constructor
        :param grid: Multicircuit instance
        :param options: ContingencyAnalysisOptions instance
        :param time_indices: array of time indices to simulate
        :param clustering_results: ClusteringResults instance (optional)
        :param engine: Calculation engine to use
        """
        TimeSeriesDriverTemplate.__init__(self,
                                          grid=grid,
                                          time_indices=time_indices,
                                          clustering_results=clustering_results,
                                          engine=engine)

        # Options to use
        self.options: Union[ContingencyAnalysisOptions, LinearAnalysisOptions] = options

        # N-K results
        self.results: ContingencyAnalysisTimeSeriesResults = ContingencyAnalysisTimeSeriesResults(
            n=0,
            nbr=0,
            nc=0,
            time_array=(),
            bus_names=(),
            branch_names=(),
            bus_types=(),
            con_names=(),
            clustering_results=clustering_results
        )

        self.branch_names: StrVec = np.empty(shape=grid.get_branch_number_wo_hvdc(), dtype=str)

    def run_contingency_analysis(self) -> ContingencyAnalysisTimeSeriesResults:
        """
        Run a contngency analysis in series
        :return: returns the results
        """

        self.progress_text.emit("Analyzing...")

        nb = self.grid.get_bus_number()

        time_array = self.grid.time_profile[self.time_indices]

        results = ContingencyAnalysisTimeSeriesResults(
            n=nb,
            nbr=self.grid.get_branch_number_wo_hvdc(),
            nc=self.grid.get_contingency_number(),
            time_array=time_array,
            branch_names=self.grid.get_branch_names_wo_hvdc(),
            bus_names=self.grid.get_bus_names(),
            bus_types=np.ones(nb, dtype=int),
            con_names=self.grid.get_contingency_group_names(),
            clustering_results=self.clustering_results
        )

        linear_multiple_contingencies = LinearMultiContingencies(grid=self.grid)

        cdriver = ContingencyAnalysisDriver(grid=self.grid,
                                            options=self.options,
                                            linear_multiple_contingencies=linear_multiple_contingencies)

        contingency_count = None

        if self.options.engine == bs.ContingencyEngine.PTDF:
            linear = LinearAnalysisTimeSeriesDriver(
                grid=self.grid,
                options=self.options,
                time_indices=self.time_indices
            )
            linear.run()

        for it, t in enumerate(self.time_indices):

            self.progress_text.emit('Contingency at ' + str(self.grid.time_profile[t]))
            self.progress_signal.emit((it + 1) / len(self.time_indices) * 100)

            # run contingency at t using the specified method
            if self.options.engine == bs.ContingencyEngine.PowerFlow:
                res_t = cdriver.n_minus_k(t=t)

            elif self.options.engine == bs.ContingencyEngine.PTDF:
                res_t = cdriver.n_minus_k_ptdf(t=t)

            elif self.options.engine == bs.ContingencyEngine.HELM:
                res_t = cdriver.n_minus_k_helm(t=t)

            else:
                res_t = cdriver.n_minus_k(t=t)

            l_abs = np.abs(res_t.loading)
            contingency = l_abs > 1
            if contingency_count is None:
                contingency_count = contingency.sum(axis=0)
            else:
                contingency_count += contingency.sum(axis=0)

            results.S[it, :] = res_t.Sbus.real.max(axis=0)
            results.worst_flows[it, :] = np.abs(res_t.Sf).max(axis=0)
            results.worst_loading[it, :] = np.abs(res_t.loading).max(axis=0)
            results.max_overload = np.maximum(results.max_overload, results.worst_loading[it, :])
            results.report.merge(res_t.report)

            if self.__cancel__:
                results.overload_count = contingency_count
                results.relative_frequency = contingency_count / len(self.time_indices)
                return results

        results.overload_count = contingency_count
        results.relative_frequency = contingency_count / len(self.time_indices)

        return results

    def run_newton_pa(self) -> ContingencyAnalysisTimeSeriesResults:
        """
        Run with Newton Power Analytics
        :return:
        """
        res = newton_pa_contingencies(circuit=self.grid,
                                      pf_opt=self.options.pf_options,
                                      con_opt=self.options,
                                      time_series=True,
                                      time_indices=self.time_indices)

        time_array = self.grid.time_profile[self.time_indices]

        nb = self.grid.get_bus_number()
        results = ContingencyAnalysisTimeSeriesResults(
            n=nb,
            nbr=self.grid.get_branch_number_wo_hvdc(),
            nc=self.grid.get_contingency_number(),
            time_array=time_array,
            branch_names=self.grid.get_branch_names_wo_hvdc(),
            bus_names=self.grid.get_bus_names(),
            bus_types=np.ones(nb, dtype=int),
            con_names=self.grid.get_contingency_group_names(),
            clustering_results=self.clustering_results
        )

        # results.S[t, :] = res_t.S.real.max(axis=0)
        results.worst_flows = np.abs(res.contingency_flows)
        results.worst_loading = res.contingency_loading

        for entry in res.report.entries:
            results.report.add(time_index=entry.time_index,
                               base_name=entry.base_name,
                               base_uuid=entry.base_uuid,
                               base_flow=np.abs(entry.base_flow),
                               base_rating=entry.base_rating,
                               base_loading=entry.base_loading,
                               contingency_idx=entry.contingency_idx,
                               contingency_name=entry.contingency_name,
                               contingency_uuid=entry.contingency_uuid,
                               post_contingency_flow=entry.post_contingency_flow,
                               contingency_rating=entry.contingency_rating,
                               post_contingency_loading=entry.post_contingency_loading)

        return results

    def run(self) -> None:
        """
        Run contingency analysis time series
        """
        self.tic()

        if self.engine == bs.EngineType.GridCal:
            self.results = self.run_contingency_analysis()

        elif self.engine == bs.EngineType.NewtonPA:
            self.progress_text.emit('Running Newton power analytics... ')
            self.results = self.run_newton_pa()

        else:
            # default to GridCal mode
            self.results = self.run_contingency_analysis()

        self.toc()
