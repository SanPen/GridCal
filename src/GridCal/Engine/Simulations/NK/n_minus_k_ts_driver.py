# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.
import time
import datetime
import numpy as np
from numba import jit, prange
from itertools import combinations
from PySide2.QtCore import QThread, Signal

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.time_series_pf_data import compile_time_circuit
from GridCal.Engine.Simulations.NK.n_minus_k_driver import NMinusKOptions
from GridCal.Engine.Simulations.NK.n_minus_k_ts_results import NMinusKTimeSeriesResults
from GridCal.Engine.Simulations.LinearFactors.analytic_ptdf import LinearAnalysis


@jit(nopython=True, parallel=False)
def compute_flows_numba_t(e, c, nt, OTDF, Flows, rates, overload_count, max_overload, worst_flows):
    """
    Compute OTDF based flows
    :param nt: number of time steps
    :param ne: number of elements
    :param nc: number of failed elements
    :param OTDF: OTDF matrix (element, failed element)
    :param Flows: base flows matrix (time, element)
    :return: Cube of N-1 Flows (time, elements, contingencies)
    """

    for t in range(nt):
        # the formula is: Fn-1(i) = Fbase(i) + OTDF(i,j) * Fbase(j) here i->line, j->failed line
        flow_n_1 = OTDF[e, c] * Flows[t, c] + Flows[t, e]
        flow_n_1_abs = abs(flow_n_1)

        if rates[t, e] > 0:
            rate = flow_n_1_abs / rates[t, e]

            if rate > 1:
                overload_count[e, c] += 1
                if flow_n_1_abs > max_overload[e, c]:
                    max_overload[e, c] = flow_n_1_abs

        if flow_n_1_abs > abs(worst_flows[t, e]):
            worst_flows[t, e] = flow_n_1


@jit(nopython=True, parallel=True)
def compute_flows_numba(e, nt, nc, OTDF, Flows, rates, overload_count, max_overload, worst_flows, paralelize_from=500):
    """
    Compute OTDF based flows
    :param nt: number of time steps
    :param ne: number of elements
    :param nc: number of failed elements
    :param OTDF: OTDF matrix (element, failed element)
    :param Flows: base flows matrix (time, element)
    :return: Cube of N-1 Flows (time, elements, contingencies)
    """

    if nc < paralelize_from:
        for c in range(nc):
            compute_flows_numba_t(e, c, nt, OTDF, Flows, rates, overload_count, max_overload, worst_flows)
    else:
        for c in prange(nc):
            compute_flows_numba_t(e, c, nt, OTDF, Flows, rates, overload_count, max_overload, worst_flows)


class NMinusKTimeSeries(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    name = 'N-1 time series'

    def __init__(self, grid: MultiCircuit, options: NMinusKOptions):
        """
        N - k class constructor
        @param grid: MultiCircuit Object
        @param options: N-k options
        @:param pf_options: power flow options
        """
        QThread.__init__(self)

        # Grid to run
        self.grid = grid

        # Options to use
        self.options = options

        # N-K results
        self.results = NMinusKTimeSeriesResults(n=0, ne=0, nc=0,
                                                time_array=(),
                                                bus_names=(),
                                                branch_names=(),
                                                bus_types=())

        # set cancel state
        self.__cancel__ = False

        self.logger = Logger()

        self.elapsed = 0.0

        self.branch_names = list()

    def get_steps(self):
        """
        Get variations list of strings
        """
        if self.results is not None:
            return [v for v in self.branch_names]
        else:
            return list()

    def n_minus_k(self):
        """
        Run N-1 simulation in series
        :return: returns the results
        """

        self.progress_text.emit("Filtering elements by voltage")

        ts_numeric_circuit = compile_time_circuit(self.grid)
        ne = ts_numeric_circuit.nbr
        nc = ts_numeric_circuit.nbr
        nt = len(ts_numeric_circuit.time_array)

        results = NMinusKTimeSeriesResults(ne=ne, nc=nc,
                                           time_array=ts_numeric_circuit.time_array,
                                           n=ts_numeric_circuit.nbus,
                                           branch_names=ts_numeric_circuit.branch_names,
                                           bus_names=ts_numeric_circuit.bus_names,
                                           bus_types=ts_numeric_circuit.bus_types)

        self.progress_text.emit('Analyzing outage distribution factors...')
        linear_analysis = LinearAnalysis(grid=self.grid,
                                         distributed_slack=self.options.distributed_slack,
                                         correct_values=self.options.correct_values)
        linear_analysis.run()

        self.progress_text.emit('Computing branch base flows...')
        Pbus = ts_numeric_circuit.Sbus.real
        flows = linear_analysis.get_branch_time_series(Pbus)
        rates = ts_numeric_circuit.Rates.T

        self.progress_text.emit('Computing N-1 flows...')

        for e in range(ne):
            compute_flows_numba(e=e,
                                nt=nt,
                                nc=nc,
                                OTDF=linear_analysis.results.LODF,
                                Flows=flows,
                                rates=rates,
                                overload_count=results.overload_count,
                                max_overload=results.max_overload,
                                worst_flows=results.worst_flows)

            self.progress_signal.emit((e + 1) / ne * 100)

        results.relative_frequency = results.overload_count / nt
        results.worst_loading = results.worst_flows / (rates + 1e-9)

        return results

    def run(self):
        """

        :return:
        """
        start = time.time()
        self.results = self.n_minus_k()

        end = time.time()
        self.elapsed = end - start
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True


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

    options_ = NMinusKOptions()
    simulation = NMinusKTimeSeries(grid=main_circuit, options=options_)
    simulation.run()

    print()
