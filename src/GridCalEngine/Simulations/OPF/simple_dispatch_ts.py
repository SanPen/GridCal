# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
This file implements a DC-OPF for time series
That means that solves the OPF problem for a complete time series at once
"""
import numpy as np
import numba as nb
from typing import Tuple
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.basic_structures import Vec, IntVec, Logger


def run_simple_dispatch(grid: MultiCircuit,
                        text_prog=None,
                        prog_func=None) -> Tuple[Vec, Vec]:
    """
    Simple generation dispatch for the snapshot
    :param grid: MultiCircuit instance
    :param text_prog: text report function
    :param prog_func: progress report function
    :return Pl, Pg
    """
    if text_prog is not None:
        text_prog('Simple dispatch...')

    if prog_func is not None:
        prog_func(0.0)

    ng = grid.get_generators_number()
    nl = grid.get_load_like_device_number()
    Sbase = grid.Sbase

    Pl = np.zeros(nl)
    Pavail = np.zeros(ng)

    # gather generation info
    for i, gen in enumerate(grid.get_generators()):
        Pavail[i] = gen.Pmax / Sbase * gen.active

    # gather load info
    for i, load in enumerate(grid.get_loads()):
        Pl[:, i] = load.P / Sbase * load.active

    # generator share:
    generation_share = Pavail / Pavail.sum()

    Pg = Pl.sum() * generation_share

    if prog_func is not None:
        prog_func(100.0)

    return Pl, Pg


def run_simple_dispatch_ts(grid: MultiCircuit,
                           time_indices: IntVec,
                           logger: Logger,
                           text_prog=None,
                           prog_func=None) -> Tuple[Vec, Vec]:
    """
    Simple generation dispatch for the time series
    :param grid: MultiCircuit instance
    :param time_indices: grid time indices where to simulate
    :param logger: logger
    :param text_prog: text report function
    :param prog_func: progress report function
    :return Pl, Pg
    """
    if text_prog is not None:
        text_prog('Simple dispatch...')

    nt = len(time_indices)
    ng = grid.get_generators_number()
    nl = grid.get_load_like_device_number()

    Pg = np.zeros((nt, ng))  # dispatched generation (to be filled)
    dispatchable_indices = list()  # generator indices that are available for beign dispatched
    Pg_sta = np.zeros((nt, ng))  # non dispatchable Pg
    Pl = np.zeros((nt, nl))  # load (non dispatchable)
    P_avail = np.zeros((nt, ng))  # generation available power

    # gather generation info
    for i, gen in enumerate(grid.get_generators()):

        # Gather the profiles as arrays
        elm_p = gen.P_prof.toarray()

        elm_active = gen.active_prof.toarray()

        Pg[:, i] = elm_p[time_indices] * elm_active[time_indices]  # copy at first ...

        if gen.enabled_dispatch:
            elm_p_max = gen.Pmax_prof.toarray()
            bad_p_max_idx = np.where(elm_p_max <= 0)[0]
            if len(bad_p_max_idx) > 0:

                for tt in bad_p_max_idx:
                    logger.add_error("Generator Pmax <= 0", device=gen.name,
                                     value=elm_p_max[tt], expected_value=">0")

                elm_p_max[bad_p_max_idx] = 9999.0

            P_avail[:, i] = elm_p_max * elm_active[time_indices]
            dispatchable_indices.append(i)
        else:
            Pg_sta[:, i] = Pg[:, i].copy()

    # gather load info
    for i, load in enumerate(grid.get_loads()):
        elm_p = load.P_prof.toarray()
        elm_active = load.active_prof.toarray()

        Pl[:, i] = elm_p[time_indices] * elm_active[time_indices]

    # for every time step...
    for t_idx, t in enumerate(time_indices):
        # generator share that is available
        generation_share_at_t = P_avail[t_idx, :] / P_avail[t_idx, :].sum()

        # total power that is needed at the time step, scaled to the generation available
        required_power = (Pl[t_idx, :].sum() - Pg_sta[t_idx, :].sum()) * generation_share_at_t

        # set the values
        Pg[t_idx, dispatchable_indices] = required_power[dispatchable_indices]

        if prog_func is not None:
            prog_func((t_idx + 1) / nt * 100.0)

    return Pl, Pg


from numba import njit
import numpy as np


@njit
def fast_dispatch_with_renewables(load, gen_profile, dispatchable, active, cost_gen,
                                  p_max_charge, p_max_discharge, energy_max,
                                  eff_charge, eff_discharge, soc0, soc_min,
                                  dt, force_charge_if_low):
    """
    Greedy dispatch algorithm with dispatchable and non-dispatchable (e.g., renewable) generators.

    Parameters
    ----------
    load : ndarray (T, L)
        Load time series per timestep and load point.
    gen_profile : ndarray (T, G)
        Precomputed generator output (for renewables or constraints).
    dispatchable : ndarray (G,)
        Boolean flag per generator (True if dispatchable).
    active : ndarray (T, G)
        Boolean array indicating whether each generator is active.
    cost_gen : ndarray (T, G)
        Generator cost profile per timestep.
    p_max_charge, p_max_discharge : ndarray (T, B)
        Battery charge/discharge limits.
    energy_max : ndarray (T, B)
        Battery energy capacity.
    eff_charge, eff_discharge : ndarray (T, B)
        Battery efficiencies.
    soc0 : ndarray (B,)
        Initial SOC.
    dt : float
        Timestep duration [h].

    Returns
    -------
    dispatch_gen : ndarray (T, G)
    dispatch_batt : ndarray (T, B)
    soc : ndarray (T, B)
    total_cost : float
    """
    T, L = load.shape
    _, G = gen_profile.shape
    _, B = p_max_charge.shape

    dispatch_gen = np.zeros((T, G))
    dispatch_batt = np.zeros((T, B))
    soc = np.zeros((T + 1, B))
    total_cost = 0.0

    for b in range(B):
        soc[0, b] = soc0[b]

    for t in range(T):
        total_load = 0.0
        for l in range(L):
            total_load += load[t, l]

        remaining = total_load

        # Step 1: Apply fixed (non-dispatchable) generation
        for g in range(G):
            if active[t, g] and not dispatchable[g]:
                dispatch = min(gen_profile[t, g], remaining)
                dispatch_gen[t, g] = dispatch
                remaining -= dispatch
                # No cost for renewables assumed

        # Step 2: Dispatchable generation (sorted by cost)
        # Generate list of (cost, g) for active+dispatchable generators
        gen_order = []
        for g in range(G):
            if active[t, g] and dispatchable[g]:
                gen_order.append((cost_gen[t, g], g))

        gen_order.sort()

        for i in range(len(gen_order)):
            g = gen_order[i][1]
            p_max = gen_profile[t, g]  # cap for dispatchable generator
            p = min(p_max, remaining)
            dispatch_gen[t, g] = p
            total_cost += p * cost_gen[t, g] * dt
            remaining -= p
            if remaining <= 1e-6:
                break

        # Step 3: Battery dispatch
        if remaining > 1e-6:
            # Discharge batteries
            for b in range(B):
                avail = soc[t, b] / dt
                p_dis = min(p_max_discharge[t, b], remaining / eff_discharge[t, b], avail)
                dispatched = p_dis * eff_discharge[t, b]
                dispatch_batt[t, b] = dispatched
                soc[t + 1, b] = soc[t, b] - p_dis * dt
                remaining -= dispatched
                if remaining <= 1e-6:
                    break
        else:
            # Charging section (with optional forced charging if SoC < soc_min)
            excess = -remaining if remaining < -1e-6 else 0.0

            for b in range(B):
                force_charge = force_charge_if_low and soc[t, b] < soc_min[b]
                room = (energy_max[t, b] - soc[t, b]) / dt
                p_ch_possible = p_max_charge[t, b]
                if not force_charge and excess <= 0:
                    soc[t + 1, b] = soc[t, b]  # maintain
                    continue

                p_ch = min(p_ch_possible, room)
                if not force_charge:
                    p_ch = min(p_ch, excess * eff_charge[t, b])

                dispatched = -p_ch / eff_charge[t, b]
                dispatch_batt[t, b] = dispatched
                soc[t + 1, b] = soc[t, b] + p_ch * dt
                if not force_charge:
                    excess -= -dispatched

    return dispatch_gen, dispatch_batt, soc[:-1], total_cost
