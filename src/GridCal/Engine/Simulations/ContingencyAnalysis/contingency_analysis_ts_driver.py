# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
import datetime
import numpy as np
import pandas as pd
from numba import jit, prange
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.time_series_pf_data import compile_time_circuit
from GridCal.Engine.Simulations.LinearFactors.linear_analysis import LinearAnalysis
from GridCal.Engine.Simulations.ContingencyAnalysis.contingency_analysis_driver import ContingencyAnalysisOptions, ContingencyAnalysisDriver
from GridCal.Engine.Simulations.ContingencyAnalysis.contingency_analysis_ts_results import ContingencyAnalysisTimeSeriesResults
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.driver_template import TimeSeriesDriverTemplate


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
            compute_flows_numba_t(e, c, nt, LODF, Flows, rates, overload_count, max_overload, worst_flows)
    else:
        for ic in prange(nc):
            c = contingency_branch_idx[ic]
            compute_flows_numba_t(e, c, nt, LODF, Flows, rates, overload_count, max_overload, worst_flows)


class ContingencyAnalysisTimeSeries(TimeSeriesDriverTemplate):
    name = 'Contingency analysis time series'
    tpe = SimulationTypes.ContingencyAnalysisTS_run

    def __init__(self, grid: MultiCircuit, options: ContingencyAnalysisOptions, start_=0, end_=None):
        """
        N - k class constructor
        @param grid: MultiCircuit Object
        @param options: N-k options
        @:param pf_options: power flow options
        """
        TimeSeriesDriverTemplate.__init__(self,
                                          grid=grid,
                                          start_=start_,
                                          end_=end_)

        # Options to use
        self.options = options

        # N-K results
        self.results = ContingencyAnalysisTimeSeriesResults(n=0, ne=0, nc=0,
                                                            time_array=(),
                                                            bus_names=(),
                                                            branch_names=(),
                                                            bus_types=(),
                                                            con_names=())

        self.branch_names = list()

        self.start_ = start_

        self.end_ = end_

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return [l.strftime('%d-%m-%Y %H:%M') for l in pd.to_datetime(self.grid.time_profile[self.start_: self.end_])]

    def n_minus_k(self):
        """
        Run N-1 simulation in series
        :return: returns the results
        """

        self.progress_text.emit("Analyzing...")

        ts_numeric_circuit = compile_time_circuit(self.grid)
        ne = ts_numeric_circuit.nbr
        nc = ts_numeric_circuit.nbr
        nt = len(ts_numeric_circuit.time_array)

        results = ContingencyAnalysisTimeSeriesResults(ne=ne,
                                                       nc=nc,
                                                       time_array=ts_numeric_circuit.time_array,
                                                       n=ts_numeric_circuit.nbus,
                                                       branch_names=ts_numeric_circuit.branch_names,
                                                       bus_names=ts_numeric_circuit.bus_names,
                                                       bus_types=ts_numeric_circuit.bus_types,
                                                       con_names=self.grid.get_contingency_group_names())

        if self.end_ is None:
            self.end_ = len(self.grid.time_profile)

        time_indices = np.arange(self.start_, self.end_)

        cdriver = ContingencyAnalysisDriver(self.grid, self.options)

        contingency_count = None

        for it, t in enumerate(time_indices):

            self.progress_text.emit('Contingency at ' + str(self.grid.time_profile[t]))
            self.progress_signal.emit((it + 1) / len(time_indices) * 100)

            # run contingency at t
            res_t = cdriver.n_minus_k(t=t)

            l_abs = np.abs(res_t.loading)
            contingency = l_abs > 1
            if contingency_count is None:
                contingency_count = contingency.sum(axis=0)
            else:
                contingency_count += contingency.sum(axis=0)

            results.worst_flows[t, :] = res_t.Sf.real.max(axis=0)
            results.worst_loading[t, :] = np.abs(res_t.loading).max(axis=0)
            results.max_overload = np.maximum(results.max_overload, results.worst_loading[t, :])

            if self.__cancel__:
                return results

        results.overload_count = contingency_count
        results.relative_frequency = contingency_count / len(time_indices)

        return results

    def run(self):
        """

        :return:
        """
        start = time.time()
        self.results = self.n_minus_k()

        end = time.time()
        self.elapsed = end - start


if __name__ == '__main__':
    import os
    import pandas as pd
    from GridCal.Engine import FileOpen, SolverType, PowerFlowOptions

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/2869 Pegase.gridcal'
    # fname = os.path.join('..', '..', '..', '..', '..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')
    # fname = os.path.join('..', '..', '..', '..', '..', 'Grids_and_profiles', 'grids', '2869 Pegase.gridcal')

    main_circuit = FileOpen(fname).open()

    options_ = ContingencyAnalysisOptions()
    simulation = ContingencyAnalysisTimeSeries(grid=main_circuit, options=options_)
    simulation.run()

    print()
