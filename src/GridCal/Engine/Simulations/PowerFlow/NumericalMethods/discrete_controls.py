import numpy as np
import numba as nb
from GridCal.Engine.basic_structures import BusMode


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


def control_q_iterative(V, Vset, Q, Qmax, Qmin, types, original_types, verbose, k):
    """
    Change the buses type in order to control the generators reactive power using
    iterative changes in Q to reach Vset.

    Arguments:

        **V** (list): array of voltages (all buses)

        **Vset** (list): Array of set points (all buses)

        **Q** (list): Array of reactive power (all buses)

        **Qmin** (list): Array of minimal reactive power (all buses)

        **Qmax** (list): Array of maximal reactive power (all buses)

        **types** (list): Array of types (all buses)

        **original_types** (list): Types as originally intended (all buses)

        **verbose** (list): output messages via the console

        **k** (float, 30): Steepness factor

    Return:

        **Qnew** (list): New reactive power values

        **types_new** (list): Modified types array

        **any_control_issue** (bool): Was there any control issue?
    """

    if verbose:
        print('Q control logic (iterative)')

    n = len(V)
    Vm = np.abs(V)
    Qnew = Q.copy()
    types_new = types.copy()
    any_control_issue = False
    precision = 4
    inc_prec = int(1.5 * precision)

    for i in range(n):

        if types[i] == BusMode.Slack.value:
            pass

        elif types[i] == BusMode.PQ.value and original_types[i] == BusMode.PV.value:

            gain = get_q_increment(Vm[i], abs(Vset[i]), k)

            if round(Vm[i], precision) < round(abs(Vset[i]), precision):
                increment = round(abs(Qmax[i] - Q[i]) * gain, inc_prec)

                if increment > 0 and Q[i] + increment < Qmax[i]:
                    # I can push more VAr, so let's do so
                    Qnew[i] = Q[i] + increment
                    if verbose:
                        print("Bus {} gain = {} (V = {}, Vset = {})".format(i,
                                                                            round(gain, precision),
                                                                            round(Vm[i], precision),
                                                                            abs(Vset[i])))
                        print("Bus {} increment = {} (Q = {}, Qmax = {})".format(i,
                                                                                 round(increment, inc_prec),
                                                                                 round(Q[i], precision),
                                                                                 round(abs(Qmax[i]), precision),
                                                                                 ))
                        print("Bus {} raising its Q from {} to {} (V = {}, Vset = {})".format(i,
                                                                                              round(Q[i], precision),
                                                                                              round(Qnew[i], precision),
                                                                                              round(Vm[i], precision),
                                                                                              abs(Vset[i]),
                                                                                              ))
                    any_control_issue = True

                else:
                    if verbose:
                        print("Bus {} stable enough (inc = {}, Q = {}, Qmax = {}, V = {}, Vset = {})".format(i,
                                                                                                             round(
                                                                                                                 increment,
                                                                                                                 inc_prec),
                                                                                                             round(Q[i],
                                                                                                                   precision),
                                                                                                             round(abs(
                                                                                                                 Qmax[
                                                                                                                     i]),
                                                                                                                   precision),
                                                                                                             round(
                                                                                                                 Vm[i],
                                                                                                                 precision),
                                                                                                             abs(Vset[
                                                                                                                     i]),
                                                                                                             )
                              )

            elif round(Vm[i], precision) > round(abs(Vset[i]), precision):
                increment = round(abs(Qmin[i] - Q[i]) * gain, inc_prec)

                if increment > 0 and Q[i] - increment > Qmin[i]:
                    # I can pull more VAr, so let's do so
                    Qnew[i] = Q[i] - increment
                    if verbose:
                        print("Bus {} increment = {} (Q = {}, Qmin = {})".format(i,
                                                                                 round(increment, inc_prec),
                                                                                 round(Q[i], precision),
                                                                                 round(abs(Qmin[i]), precision),
                                                                                 )
                              )
                        print("Bus {} gain = {} (V = {}, Vset = {})".format(i,
                                                                            round(gain, precision),
                                                                            round(Vm[i], precision),
                                                                            abs(Vset[i]),
                                                                            )
                              )
                        print("Bus {} lowering its Q from {} to {} (V = {}, Vset = {})".format(i,
                                                                                               round(Q[i], precision),
                                                                                               round(Qnew[i],
                                                                                                     precision),
                                                                                               round(Vm[i], precision),
                                                                                               abs(Vset[i]),
                                                                                               )
                              )
                    any_control_issue = True

                else:
                    if verbose:
                        print("Bus {} stable enough (inc = {}, Q = {}, Qmin = {}, V = {}, Vset = {})".format(i,
                                                                                                             round(
                                                                                                                 increment,
                                                                                                                 inc_prec),
                                                                                                             round(Q[i],
                                                                                                                   precision),
                                                                                                             round(abs(
                                                                                                                 Qmin[
                                                                                                                     i]),
                                                                                                                   precision),
                                                                                                             round(
                                                                                                                 Vm[i],
                                                                                                                 precision),
                                                                                                             abs(Vset[
                                                                                                                     i]),
                                                                                                             )
                              )

            else:
                if verbose:
                    print("Bus {} stable (V = {}, Vset = {})".format(i,
                                                                     round(Vm[i], precision),
                                                                     abs(Vset[i]),
                                                                     )
                          )

        elif types[i] == BusMode.PV.value:
            # If it's still in PV mode (first run), change it to PQ mode
            types_new[i] = BusMode.PQ.value
            Qnew[i] = 0
            if verbose:
                print("Bus {} switching to PQ control, with a Q of 0".format(i))
            any_control_issue = True

    return Qnew, types_new, any_control_issue


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

        if types[i] == BusMode.Slack.value:
            pass

        elif types[i] == BusMode.PQ.value and original_types[i] == BusMode.PV.value:

            if Vm[i] != Vset[i]:

                if Q[i] >= Qmax[i]:  # it is still a PQ bus but set Q = Qmax .
                    Qnew[i] = Qmax[i]

                elif Q[i] <= Qmin[i]:  # it is still a PQ bus and set Q = Qmin .
                    Qnew[i] = Qmin[i]

                else:  # switch back to PV, set Vnew = Vset.

                    types_new[i] = BusMode.PV.value
                    Vnew[i] = complex(Vset[i], 0)

                    if verbose:
                        print('Bus', i, 'switched back to PV')

                any_control_issue = True

            else:
                pass  # The voltages are equal

        elif types[i] == BusMode.PV.value:

            if Q[i] >= Qmax[i]:  # it is switched to PQ and set Q = Qmax .

                types_new[i] = BusMode.PQ.value
                Qnew[i] = Qmax[i]
                any_control_issue = True

                if verbose:
                    print('Bus', i, 'switched to PQ: Q', Q[i], ' Qmax:', Qmax[i])

            elif Q[i] <= Qmin[i]:  # it is switched to PQ and set Q = Qmin .

                types_new[i] = BusMode.PQ.value
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
def control_q_inside_method(Scalc, Sbus, pv, pq, pvpq, Qmin, Qmax):
    """
    Control of reactive power within the numerical method
    :param Scalc: Calculated power array (changed inside)
    :param Sbus: Specified power array (changed inside)
    :param pv: array of pv bus indices (changed inside)
    :param pq: array of pq bus indices (changed inside)
    :param pvpq: array of pv|pq bus indices (changed inside)
    :param Qmin: Array of lower reactive power limits per bus in p.u.
    :param Qmax: Array of upper reactive power limits per bus in p.u.
    :return: any change?, Scalc, Sbus, pv, pq, pvpq
    """
    messages = list()
    changed = list()
    for k, i in enumerate(pv):
        Q = Scalc[i].imag
        if Q > Qmax[i]:
            Sbus[i] = np.complex128(complex(Sbus[i].real, Qmax[i]))
            changed.append(k)
            messages.append((1, i, Qmax[i]))
        elif Q < Qmin[i]:
            Sbus[i] = np.complex128(complex(Sbus[i].real, Qmin[i]))
            changed.append(k)
            messages.append((1, i, Qmin[i]))

    if len(changed) > 0:
        # convert PV nodes to PQ
        pv_new = pv[np.array(changed)]
        pq = np.concatenate((pq, pv_new))
        pv = np.delete(pv, changed)
        pq.sort()
        pvpq = np.concatenate((pv, pq))

    return len(changed), Scalc, Sbus, pv, pq, pvpq, messages


def tap_up(tap, max_tap):
    """
    Go to the next upper tap position
    """
    if tap + 1 <= max_tap:
        return tap + 1
    else:
        return tap


def tap_down(tap, min_tap):
    """
    Go to the next upper tap position
    """
    if tap - 1 >= min_tap:
        return tap - 1
    else:
        return tap


def control_taps_iterative(voltage, T, bus_to_regulated_idx, tap_position, tap_module, min_tap, max_tap,
                           tap_inc_reg_up, tap_inc_reg_down, vset, verbose=False):
    """
    Change the taps and compute the continuous tap magnitude.

    Arguments:

        **voltage** (list): array of bus voltages solution

        **T** (list): array of indices of the "to" buses of each branch

        **bus_to_regulated_idx** (list): array with the indices of the branches that regulate the bus "to"

        **tap_position** (list): array of branch tap positions

        **tap_module** (list): array of branch tap modules

        **min_tap** (list): array of minimum tap positions

        **max_tap** (list): array of maximum tap positions

        **tap_inc_reg_up** (list): array of tap increment when regulating up

        **tap_inc_reg_down** (list): array of tap increment when regulating down

        **vset** (list): array of set voltages to control

    Returns:

        **stable** (bool): Is the system stable (i.e.: are controllers stable)?

        **tap_magnitude** (list): Tap module at each bus in per unit

        **tap_position** (list): Tap position at each bus
    """

    stable = True
    for i in bus_to_regulated_idx:  # traverse the indices of the branches that are regulated at the "to" bus

        j = T[i]  # get the index of the "to" bus of the branch "i"
        v = np.abs(voltage[j])
        if verbose:
            print("Bus", j, "regulated by branch", i, ": U =", round(v, 4), "pu, U_set =", vset[i])

        if tap_position[i] > 0:

            if vset[i] > v + tap_inc_reg_up[i] / 2:
                if tap_position[i] == min_tap[i]:
                    if verbose:
                        print("Branch", i, ": Already at lowest tap (", tap_position[i], "), skipping")
                else:
                    tap_position[i] = tap_down(tap_position[i], min_tap[i])
                    tap_module[i] = 1.0 + tap_position[i] * tap_inc_reg_up[i]
                    if verbose:
                        print("Branch", i, ": Lowering from tap ", tap_position[i])
                    stable = False

            elif vset[i] < v - tap_inc_reg_up[i] / 2:
                if tap_position[i] == max_tap[i]:
                    if verbose:
                        print("Branch", i, ": Already at highest tap (", tap_position[i], "), skipping")
                else:
                    tap_position[i] = tap_up(tap_position[i], max_tap[i])
                    tap_module[i] = 1.0 + tap_position[i] * tap_inc_reg_up[i]
                    if verbose:
                        print("Branch", i, ": Raising from tap ", tap_position[i])
                    stable = False

        elif tap_position[i] < 0:
            if vset[i] > v + tap_inc_reg_down[i] / 2:
                if tap_position[i] == min_tap[i]:
                    if verbose:
                        print("Branch", i, ": Already at lowest tap (", tap_position[i], "), skipping")
                else:
                    tap_position[i] = tap_down(tap_position[i], min_tap[i])
                    tap_module[i] = 1.0 + tap_position[i] * tap_inc_reg_down[i]
                    if verbose:
                        print("Branch", i, ": Lowering from tap", tap_position[i])
                    stable = False

            elif vset[i] < v - tap_inc_reg_down[i] / 2:
                if tap_position[i] == max_tap[i]:
                    print("Branch", i, ": Already at highest tap (", tap_position[i], "), skipping")
                else:
                    tap_position[i] = tap_up(tap_position[i], max_tap[i])
                    tap_module[i] = 1.0 + tap_position[i] * tap_inc_reg_down[i]
                    if verbose:
                        print("Branch", i, ": Raising from tap", tap_position[i])
                    stable = False

        else:
            if vset[i] > v + tap_inc_reg_up[i] / 2:
                if tap_position[i] == min_tap[i]:
                    if verbose:
                        print("Branch", i, ": Already at lowest tap (", tap_position[i], "), skipping")
                else:
                    tap_position[i] = tap_down(tap_position[i], min_tap[i])
                    tap_module[i] = 1.0 + tap_position[i] * tap_inc_reg_down[i]
                    if verbose:
                        print("Branch", i, ": Lowering from tap ", tap_position[i])
                    stable = False

            elif vset[i] < v - tap_inc_reg_down[i] / 2:
                if tap_position[i] == max_tap[i]:
                    if verbose:
                        print("Branch", i, ": Already at highest tap (", tap_position[i], "), skipping")
                else:
                    tap_position[i] = tap_up(tap_position[i], max_tap[i])
                    tap_module[i] = 1.0 + tap_position[i] * tap_inc_reg_up[i]
                    if verbose:
                        print("Branch", i, ": Raising from tap ", tap_position[i])
                    stable = False

    return stable, tap_module, tap_position


def control_taps_direct(voltage, T, bus_to_regulated_idx, tap_position, tap_module, min_tap, max_tap,
                        tap_inc_reg_up, tap_inc_reg_down, vset, tap_index_offset, verbose=False):
    """
    Change the taps and compute the continuous tap magnitude.

    Arguments:

        **voltage** (list): array of bus voltages solution

        **T** (list): array of indices of the "to" buses of each branch

        **bus_to_regulated_idx** (list): array with the indices of the branches
        that regulate the bus "to"

        **tap_position** (list): array of branch tap positions

        **tap_module** (list): array of branch tap modules

        **min_tap** (list): array of minimum tap positions

        **max_tap** (list): array of maximum tap positions

        **tap_inc_reg_up** (list): array of tap increment when regulating up

        **tap_inc_reg_down** (list): array of tap increment when regulating down

        **vset** (list): array of set voltages to control

    Returns:

        **stable** (bool): Is the system stable (i.e.: are controllers stable)?

        **tap_magnitude** (list): Tap module at each bus in per unit

        **tap_position** (list): Tap position at each bus
    """
    stable = True

    # traverse the indices of the branches that are regulated at the "to" bus
    for k, bus_idx in enumerate(bus_to_regulated_idx):

        j = T[bus_idx]  # get the index of the "to" bus of the branch "i"
        v = np.abs(voltage[j])  # voltage at to "to" bus
        if verbose:
            print("Bus", j, "regulated by branch", bus_idx, ": U=", round(v, 4), "pu, U_set=", vset[k])

        tap_inc = tap_inc_reg_up
        if tap_inc_reg_up.all() != tap_inc_reg_down.all():
            print("Error: tap_inc_reg_up and down are not equal for branch {}".format(bus_idx))

        desired_module = v / vset[k] * tap_module[tap_index_offset + k]
        desired_pos = round((desired_module - 1) / tap_inc[k])

        if desired_pos == tap_position[k]:
            continue

        elif desired_pos > 0 and desired_pos > max_tap[k]:
            if verbose:
                print("Branch {}: Changing from tap {} to {} (module {} to {})".format(bus_idx,
                                                                                       tap_position[k],
                                                                                       max_tap[k],
                                                                                       tap_module[tap_index_offset + k],
                                                                                       1 + max_tap[k] * tap_inc[k]))
            tap_position[k] = max_tap[k]

        elif desired_pos < 0 and desired_pos < min_tap[k]:
            if verbose:
                print("Branch {}: Changing from tap {} to {} (module {} to {})".format(bus_idx,
                                                                                       tap_position[k],
                                                                                       min_tap[k],
                                                                                       tap_module[tap_index_offset + k],
                                                                                       1 + min_tap[k] * tap_inc[k]))
            tap_position[k] = min_tap[k]

        else:
            if verbose:
                print("Branch {}: Changing from tap {} to {} (module {} to {})".format(bus_idx,
                                                                                       tap_position[k],
                                                                                       desired_pos,
                                                                                       tap_module[tap_index_offset + k],
                                                                                       1 + desired_pos * tap_inc[k]))
            tap_position[k] = desired_pos

        tap_module[tap_index_offset + k] = 1 + tap_position[k] * tap_inc[k]
        stable = False

    return stable, tap_module, tap_position
