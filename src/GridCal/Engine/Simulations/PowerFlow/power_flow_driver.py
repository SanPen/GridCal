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

from PySide2.QtCore import QThread, Signal

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import multi_island_pf
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCal.Engine.Simulations.OPF.opf_results import OptimalPowerFlowResults
from GridCal.Engine.Core.multi_circuit import MultiCircuit


class PowerFlowDriver(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    name = 'Power Flow'

    """
    Power flow wrapper to use with Qt
    """

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, opf_results: OptimalPowerFlowResults = None):
        """
        PowerFlowDriver class constructor
        :param grid: MultiCircuit instance
        :param options: PowerFlowOptions instance
        :param opf_results: OptimalPowerFlowResults instance
        """

        QThread.__init__(self)

        # Grid to run a power flow in
        self.grid = grid

        # Options to use
        self.options = options

        self.opf_results = opf_results

        self.results = PowerFlowResults(n=0, m=0, n_tr=0, n_hvdc=0,
                                        bus_names=(), branch_names=(), transformer_names=(),
                                        hvdc_names=(), bus_types=())

        self.logger = Logger()

        self.convergence_reports = list()

        self.__cancel__ = False

    @staticmethod
    def get_steps():
        """

        :return:
        """
        return list()

    def run(self):
        """
        Pack run_pf for the QThread
        :return:
        """
        self.results = multi_island_pf(multi_circuit=self.grid,
                                       options=self.options,
                                       opf_results=self.opf_results,
                                       logger=self.logger)
        self.convergence_reports = self.results.convergence_reports
        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True

