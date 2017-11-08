from numpy.core.multiarray import array

from GridCal.grid.calculate.voltage_collapse.input import VoltageCollapseInput
from GridCal.grid.calculate.voltage_collapse.options import \
    VoltageCollapseOptions
from GridCal.grid.calculate.voltage_collapse.results import \
    VoltageCollapseResults


class VoltageCollapseThread(QThread):

    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: VoltageCollapseOptions, inputs: VoltageCollapseInput):
        """
        VoltageCollapse constructor
        @param grid:
        @param options:
        """
        QThread.__init__(self)

        # MultiCircuit instance
        self.grid = grid

        # voltage stability options
        self.options = options

        self.inputs = inputs

        self.results = list()

        self.__cancel__ = False

    def run(self):
        """
        run the voltage collapse simulation
        @return:
        """
        print('Running voltage collapse...')
        nbus = len(self.grid.buses)
        self.results = VoltageCollapseResults(nbus=nbus)

        for nc, c in enumerate(self.grid.circuits):
            self.progress_text.emit('Running voltage collapse at circuit ' + str(nc) + '...')

            Voltage_series, Lambda_series, \
            normF, success = continuation_nr(Ybus=c.power_flow_input.Ybus,
                                             Ibus_base=c.power_flow_input.Ibus[c.bus_original_idx],
                                             Ibus_target=c.power_flow_input.Ibus[c.bus_original_idx],
                                             Sbus_base=self.inputs.Sbase[c.bus_original_idx],
                                             Sbus_target=self.inputs.Starget[c.bus_original_idx],
                                             V=self.inputs.Vbase[c.bus_original_idx],
                                             pv=c.power_flow_input.pv,
                                             pq=c.power_flow_input.pq,
                                             step=self.options.step,
                                             approximation_order=self.options.approximation_order,
                                             adapt_step=self.options.adapt_step,
                                             step_min=self.options.step_min,
                                             step_max=self.options.step_max,
                                             error_tol=1e-3,
                                             tol=1e-6,
                                             max_it=20,
                                             stop_at='NOSE',
                                             verbose=False)

            res = VoltageCollapseResults(nbus=0)  # nbus can be zero, because all the arrays are going to be overwritten
            res.voltages = array(Voltage_series)
            res.lambdas = array(Lambda_series)
            res.error = normF
            res.converged = bool(success)

            self.results.apply_from_island(res, c.bus_original_idx, nbus)
        print('done!')
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True
