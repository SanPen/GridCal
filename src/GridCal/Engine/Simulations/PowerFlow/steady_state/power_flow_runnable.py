from PySide2.QtCore import QRunnable

from GridCal.Engine.Core.calculation_inputs import CalculationInputs
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.PowerFlow.steady_state.power_flow_mp import \
    PowerFlowMP
from GridCal.Engine.Simulations.PowerFlow.steady_state.power_flow_options \
    import PowerFlowOptions


def get_steps():
    return list()


class PowerFlow(QRunnable):
    """
    Power flow wrapper to use with Qt
    """

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions):
        """
        PowerFlow class constructor
        **grid: MultiCircuit Object
        """
        QRunnable.__init__(self)

        # Grid to run a power flow in
        self.grid = grid

        # Options to use
        self.options = options

        self.results = None

        self.pf = PowerFlowMP(grid, options)

        self.__cancel__ = False

    def run(self):
        """
        Pack run_pf for the QThread
        :return:
        """

        results = self.pf.run()
        self.results = results

    def run_pf(self, circuit: CalculationInputs, Vbus, Sbus, Ibus):
        """
        Run a power flow for every circuit
        @return:
        """

        return self.pf.run_pf(circuit, Vbus, Sbus, Ibus)

    def cancel(self):
        self.__cancel__ = True