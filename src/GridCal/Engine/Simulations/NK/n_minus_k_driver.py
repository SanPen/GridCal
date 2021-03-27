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
from itertools import combinations
from PySide2.QtCore import QThread, Signal

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit
from GridCal.Engine.Simulations.NK.n_minus_k_results import NMinusKResults
from GridCal.Engine.Simulations.LinearFactors.analytic_ptdf import LinearAnalysis


def enumerate_states_n_k(m, k=1):
    """
    Enumerates the states to produce the so called N-k failures
    :param m: number of branches
    :param k: failure level
    :return: binary array (number of states, m)
    """

    # num = int(math.factorial(k) / math.factorial(m-k))
    states = list()
    indices = list()
    arr = np.ones(m, dtype=int).tolist()

    idx = list(range(m))
    for k1 in range(k + 1):
        for failed in combinations(idx, k1):
            indices.append(failed)
            arr2 = arr.copy()
            for j in failed:
                arr2[j] = 0
            states.append(arr2)

    return np.array(states), indices


class NMinusKOptions:

    def __init__(self, distributed_slack=True, correct_values=True):

        self.distributed_slack = distributed_slack

        self.correct_values = correct_values


class NMinusK(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    name = 'N-1/OTDF'

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
        self.results = NMinusKResults(n=0, m=0,
                                      bus_names=(),
                                      branch_names=(),
                                      bus_types=())

        self.numerical_circuit = None

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

        self.numerical_circuit = compile_snapshot_circuit(self.grid)

        results = NMinusKResults(m=self.numerical_circuit.nbr,
                                 n=self.numerical_circuit.nbus,
                                 branch_names=self.numerical_circuit.branch_names,
                                 bus_names=self.numerical_circuit.bus_names,
                                 bus_types=self.numerical_circuit.bus_types)

        self.progress_text.emit('Analyzing outage distribution factors...')
        linear_analysis = LinearAnalysis(grid=self.grid,
                                         distributed_slack=self.options.distributed_slack,
                                         correct_values=self.options.correct_values)
        linear_analysis.run()

        Pbus = self.numerical_circuit.get_injections(False).real[:, 0]
        PTDF = linear_analysis.results.PTDF
        LODF = linear_analysis.results.LODF

        # compute the branch flows in "n"
        flows_n = np.dot(PTDF, Pbus)

        self.progress_text.emit('Computing flows...')
        nl = self.numerical_circuit.nbr
        for c in range(nl):  # branch that fails (contingency)

            results.Sf[:, c] = flows_n[:] + LODF[:, c] * flows_n[c]
            results.loading[:, c] = results.Sf[:, c] / (self.numerical_circuit.branch_rates + 1e-9)

            results.S[c, :] = Pbus

            self.progress_signal.emit((c+1) / nl * 100)

        results.otdf = LODF

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
    from GridCal.Engine import FileOpen, SolverType,PowerFlowOptions

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/2869 Pegase.gridcal'
    fname = os.path.join('..', '..', '..', '..', '..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')
    # fname = os.path.join('..', '..', '..', '..', '..', 'Grids_and_profiles', 'grids', '2869 Pegase.gridcal')

    main_circuit = FileOpen(fname).open()

    options_ = NMinusKOptions()
    simulation = NMinusK(grid=main_circuit, options=options_)
    simulation.run()

    otdf_ = simulation.get_otdf()

    # save the result
    br_names = [b.name for b in main_circuit.branches]
    br_names2 = ['#' + b.name for b in main_circuit.branches]
    w = pd.ExcelWriter('OTDF IEEE30.xlsx')
    pd.DataFrame(data=simulation.results.Sf.real,
                 columns=br_names,
                 index=['base'] + br_names2).to_excel(w, sheet_name='branch power')
    pd.DataFrame(data=otdf_,
                 columns=br_names,
                 index=br_names2).to_excel(w, sheet_name='OTDF')
    w.save()