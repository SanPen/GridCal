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

from GridCalEngine.basic_structures import IntVec, StrVec
from GridCalEngine.enumerations import EngineType, ContingencyMethod
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearMultiContingencies
from GridCalEngine.Simulations.LinearFactors.linear_analysis_options import LinearAnalysisOptions
from GridCalEngine.Simulations.LinearFactors.linear_analysis_ts_driver import LinearAnalysisTimeSeriesDriver
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import (ContingencyAnalysisOptions,
                                                                                       ContingencyAnalysisDriver)
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_ts_results import (
    ContingencyAnalysisTimeSeriesResults)
from GridCalEngine.enumerations import SimulationTypes
from GridCalEngine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCalEngine.Simulations.Clustering.clustering_results import ClusteringResults
from GridCalEngine.Compilers.circuit_to_newton_pa import newton_pa_contingencies, translate_contingency_report
from GridCalEngine.Utils.NumericalMethods.weldorf_online_stddev import WeldorfOnlineStdDevMat


class ContingencyAnalysisTimeSeriesDriver(TimeSeriesDriverTemplate):
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
                 engine: EngineType = EngineType.GridCal):
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

        self.report_text("Analyzing...")

        nb = self.grid.get_bus_number()

        time_array = self.grid.time_profile[self.time_indices]

        if self.options.contingency_groups is None:
            con_names = self.grid.get_contingency_group_names()
        else:
            con_names = [con.name for con in self.options.contingency_groups]

        results = ContingencyAnalysisTimeSeriesResults(
            n=nb,
            nbr=self.grid.get_branch_number_wo_hvdc(),
            time_array=time_array,
            branch_names=self.grid.get_branch_names_wo_hvdc(),
            bus_names=self.grid.get_bus_names(),
            bus_types=np.ones(nb, dtype=int),
            con_names=con_names,
            clustering_results=self.clustering_results
        )

        # linear_multiple_contingencies = LinearMultiContingencies(grid=self.grid)

        cdriver = ContingencyAnalysisDriver(grid=self.grid,
                                            options=self.options,
                                            linear_multiple_contingencies=None  # it is computed inside
                                            )

        if self.options.contingency_method == ContingencyMethod.PTDF:
            linear = LinearAnalysisTimeSeriesDriver(
                grid=self.grid,
                options=self.options,
                time_indices=self.time_indices
            )
            linear.run()

        std_dev_counter = WeldorfOnlineStdDevMat(nrow=results.nt, ncol=results.nbranch)

        for it, t in enumerate(self.time_indices):

            self.report_text('Contingency at ' + str(self.grid.time_profile[t]))
            self.report_progress2(it, len(self.time_indices))

            if self.clustering_results is not None:
                t_prob = self.clustering_results.sampled_probabilities[it]
            else:
                t_prob = 1.0/len(self.time_indices)

            res_t = cdriver.run_at(t=t, t_prob=t_prob)

            results.S[it, :] = res_t.Sbus.real.max(axis=0)

            results.max_flows[it, :] = np.abs(res_t.Sf).max(axis=0)

            # Note: Loading is (ncon, nbranch)

            loading_abs = np.abs(res_t.loading)
            overloading = loading_abs.copy()
            overloading[overloading <= 1.0] = 0

            for k in range(results.ncon):
                std_dev_counter.update(it, overloading[k, :])

            results.max_loading[it, :] = loading_abs.max(axis=0)
            results.overload_count[it, :] = np.count_nonzero(overloading > 1.0)
            results.sum_overload[it, :] = overloading.sum(axis=0)

            results.std_dev_overload[it, :] = np.abs(res_t.loading).max(axis=0)

            results.srap_used_power += res_t.srap_used_power
            results.report += res_t.report

            # TODO: think what to do about this
            # results.report.merge(res_t.report)

            if self.__cancel__:
                return results

        # compute the mean
        std_dev_counter.finalize()
        results.mean_overload = std_dev_counter.mean
        results.std_dev_overload = std_dev_counter.std_dev

        return results

    def run_newton_pa(self) -> ContingencyAnalysisTimeSeriesResults:
        """
        Run with Newton Power Analytics
        :return:
        """
        res = newton_pa_contingencies(circuit=self.grid,
                                      con_opt=self.options,
                                      time_series=True,
                                      time_indices=self.time_indices)

        time_array = self.grid.time_profile[self.time_indices]

        nb = self.grid.get_bus_number()
        results = ContingencyAnalysisTimeSeriesResults(
            n=nb,
            nbr=self.grid.get_branch_number_wo_hvdc(),
            time_array=time_array,
            branch_names=self.grid.get_branch_names_wo_hvdc(),
            bus_names=self.grid.get_bus_names(),
            bus_types=np.ones(nb, dtype=int),
            con_names=self.grid.get_contingency_group_names(),
            clustering_results=self.clustering_results
        )

        # results.S[t, :] = res_t.S.real.max(axis=0)
        results.max_flows = np.abs(res.contingency_flows)
        results.max_loading = res.contingency_loading

        translate_contingency_report(newton_report=res.report, gridcal_report=results.report)

        return results

    def run(self) -> None:
        """
        Run contingency analysis time series
        """
        self.tic()

        if self.engine == EngineType.GridCal:
            self.results = self.run_contingency_analysis()

        elif self.engine == EngineType.NewtonPA:
            self.report_text('Running Newton power analytics... ')
            self.results = self.run_newton_pa()

        else:
            # default to GridCal mode
            self.results = self.run_contingency_analysis()

        self.toc()
