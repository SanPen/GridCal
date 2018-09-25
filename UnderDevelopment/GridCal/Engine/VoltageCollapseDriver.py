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

import pandas as pd
import numpy as np
from matplotlib import pyplot as plt

from PyQt5.QtCore import QThread, QRunnable, pyqtSignal

from GridCal.Engine.IoStructures import PowerFlowResults
from GridCal.Engine.Numerical.ContinuationPowerFlow import continuation_nr
from GridCal.Engine.CalculationEngine import MultiCircuit
from GridCal.Engine.PlotConfig import LINEWIDTH


########################################################################################################################
# Voltage collapse classes
########################################################################################################################


class VoltageCollapseOptions:

    def __init__(self, step=0.01, approximation_order=1, adapt_step=True, step_min=0.0001, step_max=0.2,
                 error_tol=1e-3, tol=1e-6, max_it=20, stop_at='NOSE', verbose=False):
        """
        Voltage collapse options
        @param step: Step length
        @param approximation_order: Order of the approximation: 1, 2, 3, etc...
        @param adapt_step: Use adaptive step length?
        @param step_min: Minimum step length
        @param step_max: Maximum step length
        @param error_tol: Error tolerance
        @param tol: tolerance
        @param max_it: Maximum number of iterations
        @param stop_at: Value of lambda to stop at, it can be specified by a concept namely NOSE to sto at the edge or
        FULL tp draw the full curve
        """

        self.step = step

        self.approximation_order = approximation_order

        self.adapt_step = adapt_step

        self.step_min = step_min

        self.step_max = step_max

        self.error_tol = error_tol

        self.tol = tol

        self.max_it = max_it

        self.stop_at = stop_at

        self.verbose = verbose


class VoltageCollapseInput:

    def __init__(self, Sbase, Vbase, Starget):
        """
        VoltageCollapseInput constructor
        @param Sbase: Initial power array
        @param Vbase: Initial voltage array
        @param Starget: Final power array
        """
        self.Sbase = Sbase

        self.Starget = Starget

        self.Vbase = Vbase


class VoltageCollapseResults:

    def __init__(self, nbus, nbr):
        """
        VoltageCollapseResults instance
        @param voltages: Resulting voltages
        @param lambdas: Continuation factor
        """

        self.voltages = None

        self.lambdas = None

        self.error = None

        self.converged = False

        self.Sbranch = np.zeros(nbr, dtype=complex)

        self.Ibranch = np.zeros(nbr, dtype=complex)

        self.loading = np.zeros(nbr, dtype=complex)

        self.losses = np.zeros(nbr, dtype=complex)

        self.Sbus = np.zeros(nbus, dtype=complex)

        self.available_results = ['Bus voltage']

    def apply_from_island(self, voltage_collapse_res, pf_res: PowerFlowResults, bus_original_idx, branch_original_idx, nbus_full):
        """
        Apply the results of an island to this VoltageCollapseResults instance
        :param voltage_collapse_res: VoltageCollapseResults instance of the island
        :param bus_original_idx: indices of the buses in the complete grid
        :param nbus_full: total number of buses in the complete grid
        :return:
        """

        if len(voltage_collapse_res.voltages) > 0:
            l, n = voltage_collapse_res.voltages.shape

            if self.voltages is None:
                self.voltages = np.zeros((l, nbus_full), dtype=complex)
                self.voltages[:, bus_original_idx] = voltage_collapse_res.voltages
                self.lambdas = voltage_collapse_res.lambdas
            else:
                lprev = self.voltages.shape[0]
                if l > lprev:
                    vv = self.voltages.copy()
                    self.voltages = np.zeros((l, nbus_full), dtype=complex)
                    self.voltages[0:l, :] = vv

                self.voltages[0:l, bus_original_idx] = voltage_collapse_res.voltages

            # set the branch values
            self.Sbranch[branch_original_idx] = pf_res.Sbranch
            self.Ibranch[branch_original_idx] = pf_res.Ibranch
            self.loading[branch_original_idx] = pf_res.loading
            self.losses[branch_original_idx] = pf_res.losses
            self.Sbus[bus_original_idx] = pf_res.Sbus

    def plot(self, result_type='Bus voltage', ax=None, indices=None, names=None):
        """
        Plot the results
        :param result_type:
        :param ax:
        :param indices:
        :param names:
        :return:
        """

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        if names is None:
            names = np.array(['bus ' + str(i + 1) for i in range(self.voltages.shape[1])])

        if indices is None:
            indices = np.array(range(len(names)))

        if len(indices) > 0:
            labels = names[indices]
            ylabel = ''
            if result_type == 'Bus voltage':
                y = abs(np.array(self.voltages)[:, indices])
                x = self.lambdas
                title = 'Bus voltage'
                ylabel = '(p.u.)'
            else:
                pass

            df = pd.DataFrame(data=y, index=x, columns=indices)
            df.columns = labels
            if len(df.columns) > 10:
                df.abs().plot(ax=ax, linewidth=LINEWIDTH, legend=False)
            else:
                df.abs().plot(ax=ax, linewidth=LINEWIDTH, legend=True)

            ax.set_title(title)
            ax.set_ylabel(ylabel)
            ax.set_xlabel('Loading from the base situation ($\lambda$)')

            return df


class VoltageCollapse(QThread):
    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, circuit: MultiCircuit,
                 options: VoltageCollapseOptions, inputs: VoltageCollapseInput):
        """
        VoltageCollapse constructor
        @param circuit: NumericalCircuit instance
        @param options:
        """
        QThread.__init__(self)

        # MultiCircuit instance
        self.circuit = circuit

        # voltage stability options
        self.options = options

        self.inputs = inputs

        self.results = list()

        self.__cancel__ = False

    def progress_callback(self, l):
        """
        Send progress report
        :param l: lambda value
        :return: None
        """
        self.progress_text.emit('Running voltage collapse lambda:' + "{0:.2f}".format(l) + '...')

    def run(self):
        """
        run the voltage collapse simulation
        @return:
        """
        print('Running voltage collapse...')
        nbus = len(self.circuit.buses)
        nbr = len(self.circuit.branches)
        self.results = VoltageCollapseResults(nbus=nbus, nbr=nbr)

        # compile the numerical circuit
        numerical_circuit = self.circuit.compile()
        numerical_input_islands = numerical_circuit.compute()

        for nc, numerical_island in enumerate(numerical_input_islands):

            self.progress_text.emit('Running voltage collapse at circuit ' + str(nc) + '...')

            if len(numerical_island.ref) > 0:
                Voltage_series, Lambda_series, \
                normF, success = continuation_nr(Ybus=numerical_island.Ybus,
                                                 Ibus_base=numerical_island.Ibus,
                                                 Ibus_target=numerical_island.Ibus,
                                                 Sbus_base=self.inputs.Sbase[numerical_island.original_bus_idx],
                                                 Sbus_target=self.inputs.Starget[numerical_island.original_bus_idx],
                                                 V=self.inputs.Vbase[numerical_island.original_bus_idx],
                                                 pv=numerical_island.pv,
                                                 pq=numerical_island.pq,
                                                 step=self.options.step,
                                                 approximation_order=self.options.approximation_order,
                                                 adapt_step=self.options.adapt_step,
                                                 step_min=self.options.step_min,
                                                 step_max=self.options.step_max,
                                                 error_tol=1e-3,
                                                 tol=1e-6,
                                                 max_it=20,
                                                 stop_at='NOSE',
                                                 verbose=False,
                                                 call_back_fx=self.progress_callback)

                # nbus can be zero, because all the arrays are going to be overwritten
                res = VoltageCollapseResults(nbus=numerical_island.nbus, nbr=numerical_island.nbr)
                res.voltages = np.array(Voltage_series)
                res.lambdas = np.array(Lambda_series)
                res.error = normF
                res.converged = bool(success)
            else:
                res = VoltageCollapseResults(nbus=numerical_island.nbus, nbr=numerical_island.nbr)
                res.voltages = np.array([[0] * numerical_island.nbus])
                res.lambdas = np.array([[0] * numerical_island.nbus])
                res.error = [0]
                res.converged = True

            if len(res.voltages) > 0:
                # compute the island branch results
                branch_res = numerical_island.compute_branch_results(res.voltages[-1])

                self.results.apply_from_island(res, branch_res, numerical_island.original_bus_idx,
                                               numerical_island.original_branch_idx, nbus)
            else:
                print('No voltage values!')
        print('done!')
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True

