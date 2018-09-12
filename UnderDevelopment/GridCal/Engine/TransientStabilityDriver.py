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


from PyQt5.QtCore import QThread, QRunnable, pyqtSignal

from GridCal.Engine.CalculationEngine import MultiCircuit
from GridCal.Engine.PowerFlowDriver import PowerFlowResults
from GridCal.Engine.Numerical.DynamicModels import DynamicModels, dynamic_simulation

########################################################################################################################
# Transient stability
########################################################################################################################


class TransientStabilityOptions:

    def __init__(self, h=0.001, t_sim=15, max_err=0.0001, max_iter=25):

        # step length (s)
        self.h = h

        # simulation time (s)
        self.t_sim = t_sim

        # Maximum error in network iteration (voltage mismatches)
        self.max_err = max_err

        # Maximum number of network iterations
        self.max_iter = max_iter


class TransientStability(QThread):
    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: TransientStabilityOptions, pf_res: PowerFlowResults):
        """
        TimeSeries constructor
        @param grid: MultiCircuit instance
        @param options: PowerFlowOptions instance
        """
        QThread.__init__(self)

        self.grid = grid

        self.options = options

        self.pf_res = pf_res

        self.results = None

    def status(self, txt, progress):
        """
        Emit status
        :param txt: text to display
        :param progress: progress 0-100
        """
        self.progress_signal.emit(progress)
        self.progress_text.emit(txt)

    def run(self):
        """
        Run transient stability
        """
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Running transient stability...')

        for circuit in self.grid.circuits:
            dynamic_devices = circuit.get_controlled_generators()
            bus_indices = [circuit.buses_dict[elm.bus] for elm in dynamic_devices]

            res = dynamic_simulation(n=len(circuit.buses),
                                     Vbus=self.pf_res.voltage[circuit.bus_original_idx],
                                     Sbus=self.pf_res.Sbus[circuit.bus_original_idx],
                                     Ybus=circuit.power_flow_input.Ybus,
                                     Sbase=circuit.Sbase,
                                     fBase=circuit.fBase,
                                     t_sim=self.options.t_sim,
                                     h=self.options.h,
                                     dynamic_devices=dynamic_devices,
                                     bus_indices=bus_indices,
                                     callback=self.status)

        self.results = res

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()
