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

from GridCal.Engine.PowerFlowDriver import PowerFlowOptions
from GridCal.Engine.CalculationEngine import MultiCircuit, NumericalCircuit
from GridCal.Engine.Devices import DeviceType


def get_failure_time(mttf):
    """
    Get an array of possible failure times
    :param mttf: mean time to failure
    """
    n_samples = len(mttf)
    return -1.0 * mttf * np.log(np.random.rand(n_samples))


def get_repair_time(mttr):
    """
    Get an array of possible repair times
    :param mttr: mean time to recovery
    """
    n_samples = len(mttr)
    return -1.0 * mttr * np.log(np.random.rand(n_samples))


def get_reliability_events(horizon, mttf, mttr, tpe: DeviceType):
    """
    Get random fail-repair events until a given time horizon in hours
    :param horizon: maximum horizon in hours
    :return: list of events,
    Each event tuple has: (time in hours, element index, activation state (True/False))
    """
    n_samples = len(mttf)
    t = np.zeros(n_samples)
    done = np.zeros(n_samples, dtype=bool)
    events = list()

    if mttf.all() == 0.0:
        return events

    not_done = np.where(done == False)[0]
    not_done_s = set(not_done)
    while len(not_done) > 0:  # if all event get to the horizon, finnish the sampling

        # simulate failure
        t[not_done] += get_failure_time(mttf[not_done])
        idx = np.where(t >= horizon)[0]
        done[idx] = True

        # store failure events
        events += [(t[i], tpe, i, False) for i in (not_done_s - set(idx))]

        # simulate repair
        t[not_done] += get_repair_time(mttr[not_done])
        idx = np.where(t >= horizon)[0]
        done[idx] = True

        # store recovery events
        events += [(t[i], tpe, i, True) for i in (not_done_s - set(idx))]

        # update not done
        not_done = np.where(done == False)[0]
        not_done_s = set(not_done)

    # sort in place
    # events.sort(key=lambda tup: tup[0])
    return events


def get_reliability_scenario(nc: NumericalCircuit, horizon=10000):
    """
    Get reliability events
    Args:
        nc: numerical circuit instance
        horizon: time horizon in hours

    Returns: dictionary of events
    Each event tuple has: (time in hours, element index, activation state (True/False))
    """
    all_events = list()

    # branches
    all_events += get_reliability_events(horizon, nc.br_mttf, nc.br_mttr, DeviceType.BranchDevice)

    all_events += get_reliability_events(horizon, nc.controlled_gen_mttf, nc.controlled_gen_mttr, DeviceType.ControlledGeneratorDevice)

    all_events += get_reliability_events(horizon, nc.battery_mttf, nc.battery_mttr, DeviceType.BatteryDevice)

    all_events += get_reliability_events(horizon, nc.static_gen_mttf, nc.static_gen_mttr, DeviceType.StaticGeneratorDevice)

    all_events += get_reliability_events(horizon, nc.load_mttf, nc.load_mttr, DeviceType.LoadDevice)

    all_events += get_reliability_events(horizon, nc.shunt_mttf, nc.shunt_mttr, DeviceType.ShuntDevice)

    # sort all
    all_events.sort(key=lambda tup: tup[0])

    return all_events


def run_events(nc: NumericalCircuit, events_list: list):

    for t, tpe, i, state in events_list:

        # Set the state of the event
        if tpe == DeviceType.BusDevice:
            pass

        elif tpe == DeviceType.BranchDevice:
            nc.branch_states[i] = state

        elif tpe == DeviceType.ControlledGeneratorDevice:
            nc.controlled_gen_enabled[i] = state

        elif tpe == DeviceType.StaticGeneratorDevice:
            nc.static_gen_enabled[i] = state

        elif tpe == DeviceType.BatteryDevice:
            nc.battery_enabled[i] = state

        elif tpe == DeviceType.ShuntDevice:
            nc.shunt_enabled[i] = state

        elif tpe == DeviceType.LoadDevice:
            nc.load_enabled[i] = state

        else:
            pass

        # compile the grid information
        calculation_islands = nc.compute()


class ReliabilityStudy(QThread):
    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, circuit: MultiCircuit, pf_options: PowerFlowOptions):
        """
        VoltageCollapse constructor
        @param circuit: NumericalCircuit instance
        @param pf_options: power flow options instance
        """
        QThread.__init__(self)

        # MultiCircuit instance
        self.circuit = circuit

        # voltage stability options
        self.pf_options = pf_options

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

        # compile the numerical circuit
        numerical_circuit = self.circuit.compile()

        evt = get_reliability_scenario(numerical_circuit)

        run_events(nc=numerical_circuit, events_list=evt)

        print('done!')
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True


if __name__ == '__main__':
    from GridCal.Engine.All import MultiCircuit

    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 30 Bus with storage.xlsx'

    circuit_ = MultiCircuit()
    circuit_.load_file(fname)

    study = ReliabilityStudy(circuit=circuit_, pf_options=PowerFlowOptions())

    study.run()