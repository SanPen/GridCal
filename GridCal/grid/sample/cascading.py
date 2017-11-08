import pandas as pd
from numpy import r_, where

from GridCal.grid.sample.cascade_type import CascadeType
from GridCal.grid.calculate.power_flow.power_flow import PowerFlowOptions, \
    PowerFlow
from GridCal.grid.model.circuit import MultiCircuit, Circuit
from GridCal.grid.sample.latin_hypercube.latin_hypercube import \
    LatinHypercubeSampling


class CascadingReportElement:

    def __init__(self, removed_idx, pf_results):

        self.removed_idx = removed_idx
        self.pf_results = pf_results

class Cascading(QThread):

    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, triggering_idx=None, max_additional_islands=1,
                 cascade_type_: CascadeType=CascadeType.LatinHypercube, n_lhs_samples_=1000):
        """
        Constructor
        Args:
            grid: Grid to cascade
            options: Power flow Options
            triggering_idx: branch indices to trigger first
        """

        QThread.__init__(self)

        self.grid = grid

        self.options = options

        self.triggering_idx = triggering_idx

        self.__cancel__ = False

        self.report = list()

        self.current_step = 0

        self.max_additional_islands = max_additional_islands

        self.cascade_type = cascade_type_

        self.n_lhs_samples = n_lhs_samples_

    @staticmethod
    def remove_elements(circuit: Circuit, idx=None):
        """
        Remove branches based on loading
        Returns:
            Nothing
        """

        if idx is None:
            load = abs(circuit.power_flow_results.loading)
            idx = where(load > 1.0)[0]

            if len(idx) == 0:
                idx = where(load >= load.max())[0]

        # disable the selected branches
        print('Removing:', idx, load[idx])

        for i in idx:
            circuit.branches[i].active = False

        return idx

    def perform_step_run(self):
        """
        Perform only one step cascading
        Returns:
            Nothing
        """

        # recompile the grid
        self.grid.compile()

        # initialize the simulator
        if self.cascade_type is CascadeType.PowerFlow:
            model_simulator = PowerFlow(self.grid, self.options)

        elif self.cascade_type is CascadeType.LatinHypercube:
            model_simulator = LatinHypercubeSampling(self.grid, self.options, sampling_points=self.n_lhs_samples)

        else:
            model_simulator = PowerFlow(self.grid, self.options)

        # For every circuit, run a power flow
        # for c in self.grid.circuits:
        model_simulator.run()

        if self.current_step == 0:
            # the first iteration try to trigger the selected indices, if any
            idx = self.remove_elements(self.grid, idx=self.triggering_idx)
        else:
            # cascade normally
            idx = self.remove_elements(self.grid)

        # store the removed indices and the results
        entry = CascadingReportElement(idx, model_simulator.results)
        self.report.append(entry)

        # increase the step number
        self.current_step += 1

        print(model_simulator.results.get_convergence_report())

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def run(self):
        """
        Run the monte carlo simulation
        @return:
        """

        self.__cancel__ = False

        self.report = list()

        if len(self.grid.circuits) == 0:
            self.grid.compile()

        # initialize the simulator
        if self.cascade_type is CascadeType.PowerFlow:
            model_simulator = PowerFlow(self.grid, self.options)

        elif self.cascade_type is CascadeType.LatinHypercube:
            model_simulator = LatinHypercubeSampling(self.grid, self.options, sampling_points=1000)

        else:
            model_simulator = PowerFlow(self.grid, self.options)

        self.progress_signal.emit(0.0)
        self.progress_text.emit('Running cascading failure...')

        n_grids = len(self.grid.circuits) + self.max_additional_islands
        if n_grids > len(self.grid.buses):  # safety check
            n_grids = len(self.grid.buses) - 1

        print('n grids: ', n_grids)

        it = 0
        while len(self.grid.circuits) <= n_grids and it <= n_grids:

            # For every circuit, run a power flow
            # for c in self.grid.circuits:
            model_simulator.run()
            # print(model_simulator.results.get_convergence_report())

            if it == 0:
                # the first iteration try to trigger the selected indices, if any
                idx = self.remove_elements(self.grid, idx=self.triggering_idx)
            else:
                # for the next indices, just cascade normally
                idx = self.remove_elements(self.grid)

            # store the removed indices and the results
            entry = CascadingReportElement(idx, model_simulator.results)
            self.report.append(entry)

            # recompile grid
            self.grid.compile()

            it += 1

            if self.__cancel__:
                break

        print('Grid split into ', len(self.grid.circuits), ' islands after', it, ' steps')

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def get_failed_idx(self):
        """
        Return the array of all failed branches
        Returns:
            array of all failed branches
        """
        res = None
        for i in range(len(self.report)):
            if i == 0:
                res = self.report[i][0]
            else:
                res = r_[res, self.report[i][0]]

        return res

    def get_table(self):

        dta = list()
        for i in range(len(self.report)):
            dta.append(['Step ' + str(i+1), len(self.report[i].removed_idx)])

        return pd.DataFrame(data=dta, columns=['Cascade step', 'Elements failed'])

    def cancel(self):
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled')
        self.done_signal.emit()
