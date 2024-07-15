# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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

import numpy as np

from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit, compile_numerical_circuit_at
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Simulations.driver_template import DriverTemplate


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
    :param mttf: Mean time to failure (h)
    :param mttr: Mean time to repair (h)
    :param tpe: device type (DeviceType)
    :return: list of events, each event tuple has: (time in hours, element index, activation state (True/False))
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
    :param nc: numerical circuit instance
    :param horizon: time horizon in hours
    :return: dictionary of events, each event tuple has:
    (time in hours, DataType, element index, activation state (True/False))
    """
    all_events = list()

    # TODO: Add MTTF and MTTR to data devices

    # Branches
    all_events += get_reliability_events(horizon,
                                         nc.branch_data.mttf,
                                         nc.branch_data.mttr,
                                         DeviceType.BranchDevice)

    all_events += get_reliability_events(horizon,
                                         nc.generator_data.mttf,
                                         nc.generator_data.mttr,
                                         DeviceType.GeneratorDevice)

    all_events += get_reliability_events(horizon,
                                         nc.battery_data.mttf,
                                         nc.battery_data.mttr,
                                         DeviceType.BatteryDevice)

    all_events += get_reliability_events(horizon,
                                         nc.load_data.mttf,
                                         nc.load_data.mttr,
                                         DeviceType.LoadDevice)

    all_events += get_reliability_events(horizon,
                                         nc.shunt_data.mttf,
                                         nc.shunt_data.mttr,
                                         DeviceType.ShuntDevice)

    # sort all
    all_events.sort(key=lambda tup: tup[0])

    return all_events


def run_events(nc: NumericalCircuit, events_list: list):
    """

    :param nc:
    :param events_list:
    """
    for t, tpe, i, state in events_list:

        # Set the state of the event
        if tpe == DeviceType.BusDevice:
            pass

        elif tpe == DeviceType.BranchDevice:
            nc.branch_data.active[i] = state

        elif tpe == DeviceType.GeneratorDevice:
            nc.generator_data.active[i] = state

        elif tpe == DeviceType.BatteryDevice:
            nc.battery_data.active[i] = state

        elif tpe == DeviceType.ShuntDevice:
            nc.shunt_data.active[i] = state

        elif tpe == DeviceType.LoadDevice:
            nc.load_data.active[i] = state

        else:
            pass

        # compile the grid information
        calculation_islands = nc.split_into_islands()


class ReliabilityStudy(DriverTemplate):

    def __init__(self, circuit: MultiCircuit, pf_options: PowerFlowOptions):
        """
        ContinuationPowerFlowDriver constructor
        @param circuit: NumericalCircuit instance
        @param pf_options: power flow options instance
        """
        DriverTemplate.__init__(self, grid=circuit)

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
        self.report_text('Running voltage collapse lambda:' + "{0:.2f}".format(l) + '...')

    def run(self):
        """
        run the voltage collapse simulation
        @return:
        """
        self.tic()

        # compile the numerical circuit
        numerical_circuit = compile_numerical_circuit_at(self.grid, t_idx=None, logger=self.logger)

        evt = get_reliability_scenario(numerical_circuit,
                                       horizon=1)

        run_events(nc=numerical_circuit, events_list=evt)

        self.toc()

    def cancel(self):
        self.__cancel__ = True


