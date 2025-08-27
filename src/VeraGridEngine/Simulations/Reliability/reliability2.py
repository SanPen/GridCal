# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Tuple
import numba as nb
import numpy as np
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.basic_structures import IntMat, Vec, Mat

"""
Common reliability indicators:


(System Average Interruption Frequency Index)
SAIFI = total number of customer interruptions / total number of customers

(System Average Interruption Duration Index)
SAIDI = Total number of customer hours of interruption / Total number of customers

(Customer Average Interruption Duration Index)
CAIDI = Total number of customer hours of interruption / total number of customer interruptions 

(Average System Availability Index)
ASAI = (8760 - SAIDI) / 8760

"""


def get_transition_probabilities(lbda: Vec, mu: Vec) -> Tuple[Vec, Vec]:
    """
    Probability of the component being unavailable
    See: Power distribution system reliability p.67
    :param lbda: failure rate ( 1 / mttf)
    :param mu: repair rate (1 / mttr)
    :return: availability probability, unavailability probability
    """
    lbda2 = lbda * lbda
    mu2 = mu * mu
    p_unavailability = lbda2 / (lbda2 + 2.0 * lbda * mu + 2.0 * mu2)
    p_availability = 1.0 - p_unavailability

    return p_availability, p_unavailability


def compute_transition_probabilities(mttf: Vec, mttr: Vec,
                                     forced_mttf: None | float, forced_mttr: None | float) -> Tuple[Vec, Vec]:
    """
    Compute the transition probabilities
    :param mttf: Vector of mean-time-to-failures
    :param mttr: Vector of mean-time-to-recoveries
    :param forced_mttf: forced mttf value (used if not None)
    :param forced_mttr: forced mttr value (used if not None)
    :return: Probability of being up, Probability of being down
    """
    # compute the transition probabilities
    if forced_mttf is None:
        lbda = 1.0 / mttf
    else:
        lbda = 1.0 / np.full(len(mttf), forced_mttf)

    if forced_mttr is None:
        mu = 1.0 / mttr
    else:
        mu = 1.0 / np.full(len(mttr), forced_mttr)

    p_up, p_dwn = get_transition_probabilities(lbda=lbda, mu=mu)

    return p_up, p_dwn


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
                                         nc.passive_branch_data.mttf,
                                         nc.passive_branch_data.mttr,
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
            nc.passive_branch_data.active[i] = state

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
