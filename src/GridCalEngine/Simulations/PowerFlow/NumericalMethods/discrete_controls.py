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
import numba as nb
from typing import Tuple
from GridCalEngine.enumerations import BusMode
from GridCalEngine.basic_structures import Vec, IntVec, CxVec


def get_q_increment(V1, V2, k):
    """
    Logistic function to get the Q increment gain using the difference
    between the current voltage (V1) and the target voltage (V2).

    The gain varies between 0 (at V1 = V2) and inf (at V2 - V1 = inf).

    The default steepness factor k was set through trial an error. Other values may
    be specified as a :ref:`PowerFlowOptions<pf_options>`.

    Arguments:

        **V1** (float): Current voltage

        **V2** (float): Target voltage

        **k** (float, 30): Steepness factor

    Returns:

        Q increment gain
    """

    return 2 * (1 / (1 + np.exp(-k * np.abs(V2 - V1))) - 0.5)


def control_q_direct(V, Vm, Vset, Q, Qmax, Qmin, types, original_types, verbose=False):
    """
    Change the buses type in order to control the generators reactive power.
    :param V: Array of complex voltages
    :param Vm: Array of voltage modules (for speed)
    :param Vset: array of voltage Set points
    :param Q: Array of reactive power values per bus
    :param Qmax: Array of Qmax per bus
    :param Qmin: Array of Qmin per bus
    :param types: Array of bus types
    :param original_types: Array of original bus types
    :param verbose: More info?
    :return:
            **Vnew** (list): New voltage values

            **Qnew** (list): New reactive power values

            **types_new** (list): Modified types array

            **any_control_issue** (bool): Was there any control issue?
    """

    """
    Logic:

    ON PV-PQ BUS TYPE SWITCHING LOGIC IN POWER FLOW COMPUTATION
    Jinquan Zhao

    1) Bus i is a PQ bus in the previous iteration and its
       reactive power was fixed at its lower limit:

        If its voltage magnitude Vi ≥ Viset, then

            it is still a PQ bus at current iteration and set Qi = Qimin .

            If Vi < Viset , then

                compare Qi with the upper and lower limits.

                If Qi ≥ Qimax , then
                    it is still a PQ bus but set Qi = Qimax .
                If Qi ≤ Qimin , then
                    it is still a PQ bus and set Qi = Qimin .
                If Qimin < Qi < Qi max , then
                    it is switched to PV bus, set Vinew = Viset.

    2) Bus i is a PQ bus in the previous iteration and
       its reactive power was fixed at its upper limit:

        If its voltage magnitude Vi ≤ Viset , then:
            bus i still a PQ bus and set Q i = Q i max.

            If Vi > Viset , then

                Compare between Qi and its upper/lower limits

                If Qi ≥ Qimax , then
                    it is still a PQ bus and set Q i = Qimax .
                If Qi ≤ Qimin , then
                    it is still a PQ bus but let Qi = Qimin in current iteration.
                If Qimin < Qi < Qimax , then
                    it is switched to PV bus and set Vinew = Viset

    3) Bus i is a PV bus in the previous iteration.

        Compare Q i with its upper and lower limits.

        If Qi ≥ Qimax , then
            it is switched to PQ and set Qi = Qimax .
        If Qi ≤ Qimin , then
            it is switched to PQ and set Qi = Qimin .
        If Qi min < Qi < Qimax , then
            it is still a PV bus.
    """

    if verbose:
        print('Q control logic (fast)')

    n = len(V)
    Qnew = Q.copy()
    Vnew = V.copy()
    types_new = types.copy()
    any_control_issue = False

    for i in range(n):

        if types[i] == BusMode.Slack_tpe.value:
            pass

        elif types[i] == BusMode.PQ_tpe.value and original_types[i] == BusMode.PV_tpe.value:

            if Vm[i] != Vset[i]:

                if Q[i] >= Qmax[i]:  # it is still a PQ bus but set Q = Qmax .
                    Qnew[i] = Qmax[i]

                elif Q[i] <= Qmin[i]:  # it is still a PQ bus and set Q = Qmin .
                    Qnew[i] = Qmin[i]

                else:  # switch back to PV, set Vnew = Vset.

                    types_new[i] = BusMode.PV_tpe.value
                    Vnew[i] = complex(Vset[i], 0)

                    if verbose:
                        print('Bus', i, 'switched back to PV')

                any_control_issue = True

            else:
                pass  # The voltages are equal

        elif types[i] == BusMode.PV_tpe.value:

            if Q[i] >= Qmax[i]:  # it is switched to PQ and set Q = Qmax .

                types_new[i] = BusMode.PQ_tpe.value
                Qnew[i] = Qmax[i]
                any_control_issue = True

                if verbose:
                    print('Bus', i, 'switched to PQ: Q', Q[i], ' Qmax:', Qmax[i])

            elif Q[i] <= Qmin[i]:  # it is switched to PQ and set Q = Qmin .

                types_new[i] = BusMode.PQ_tpe.value
                Qnew[i] = Qmin[i]
                any_control_issue = True

                if verbose:
                    print('Bus', i, 'switched to PQ: Q', Q[i], ' Qmin:', Qmin[i])

            else:  # it is still a PV bus.
                pass

        else:
            pass

    return Vnew, Qnew, types_new, any_control_issue


@nb.njit(cache=True)
def control_q_inside_method(Scalc: CxVec, S0: CxVec,
                            pv: IntVec, pq: IntVec, pqv: IntVec, p: IntVec,
                            Qmin: Vec, Qmax: Vec):
    """
    Control of reactive power within the numerical method
    :param Scalc: Calculated power array (changed inside)
    :param S0: Specified power array (changed inside)
    :param pv: array of pv bus indices (changed inside)
    :param pq: array of pq bus indices (changed inside)
    :param pqv: array of pqv bus indices (changed inside)
    :param p: array of p bus indices (changed inside)
    :param Qmin: Array of lower reactive power limits per bus in p.u.
    :param Qmax: Array of upper reactive power limits per bus in p.u.
    :return: any change?, Scalc, Sbus, pv, pq, pqv, p
    """
    pv_indices = list()
    changed = list()
    for k, i in enumerate(pv):
        Q = Scalc[i].imag
        if Q > Qmax[i]:
            S0[i] = np.complex128(complex(S0[i].real, Qmax[i]))
            changed.append(i)
            pv_indices.append(k)
        elif Q < Qmin[i]:
            S0[i] = np.complex128(complex(S0[i].real, Qmin[i]))
            changed.append(i)
            pv_indices.append(k)

    if len(changed) > 0:
        # convert PV nodes to PQ
        pq_new = np.array(changed)
        pq = np.concatenate((pq, pq_new))
        pv = np.delete(pv, pv_indices)
        pq.sort()

    return changed, pv, pq, pqv, p


def compute_slack_distribution(Scalc: CxVec, vd: IntVec, bus_installed_power: Vec) -> Tuple[bool, Vec]:
    """
    Slack distribution logic
    :param Scalc: Computed power array
    :param vd: slack indices
    :param bus_installed_power: Amount of installed power
    :return: is slack division possible?
    """
    # Distribute the slack power
    slack_power = Scalc[vd].real.sum()
    total_installed_power = bus_installed_power.sum()

    if total_installed_power > 0.0:
        delta = slack_power * bus_installed_power / total_installed_power
        ok = True
    else:
        delta = np.zeros(len(Scalc))
        ok = False

    return ok, delta
