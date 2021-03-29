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

from typing import List, Dict
import numpy as np
import numba as nb
from GridCal.Engine.basic_structures import BusMode, Logger


def compile_types(Sbus, types, logger=Logger()):
    """
    Compile the types.
    :param Sbus: array of power injections per node
    :param types: array of tentative node types
    :param logger: logger where to store the errors
    :return: ref, pq, pv, pqpv
    """

    # check that Sbus is a 1D array
    assert (len(Sbus.shape) == 1)

    pq = np.where(types == BusMode.PQ.value)[0]
    pv = np.where(types == BusMode.PV.value)[0]
    ref = np.where(types == BusMode.Slack.value)[0]

    if len(ref) == 0:  # there is no slack!

        if len(pv) == 0:  # there are no pv neither -> blackout grid

            logger.add('There are no slack nodes selected')

        else:  # select the first PV generator as the slack

            mx = max(Sbus[pv])
            if mx > 0:
                # find the generator that is injecting the most
                i = np.where(Sbus == mx)[0][0]

            else:
                # all the generators are injecting zero, pick the first pv
                i = pv[0]

            # delete the selected pv bus from the pv list and put it in the slack list
            pv = np.delete(pv, np.where(pv == i)[0])
            ref = [i]
            # print('Setting bus', i, 'as slack')

        ref = np.ndarray.flatten(np.array(ref))
        types[ref] = BusMode.Slack.value
    else:
        pass  # no problem :)

    pqpv = np.r_[pq, pv]
    pqpv.sort()

    return ref, pq, pv, pqpv


def find_different_states(branch_active_prof) -> Dict[int, List[int]]:
    """
    Find the different branch states in time that may lead to different islands
    :param branch_active_prof:
    :return:
    """
    ntime = branch_active_prof.shape[0]

    # initialize
    states = dict()  # type: Dict[int, List[int]]
    k = 1
    for t in range(ntime):

        # search this state in the already existing states
        keys = list(states.keys())
        nn = len(keys)
        found = False
        i = 0
        while i < nn and not found:
            t2 = keys[i]

            # compare state at t2 with the state at t
            if np.array_equal(branch_active_prof[t, :], branch_active_prof[t2, :]):
                states[t2].append(t)
                found = True

            i += 1

        if not found:
            # new state found (append itself)
            states[t] = [t]

        k += 1

    return states
