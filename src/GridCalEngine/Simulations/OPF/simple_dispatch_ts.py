# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
This file implements a DC-OPF for time series
That means that solves the OPF problem for a complete time series at once
"""
from functools import cache

import numpy as np
import numba as nb
from typing import Tuple
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.basic_structures import Vec, Mat, IntMat, IntVec, Logger


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


def run_simple_dispatch_ts_old(grid: MultiCircuit,
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


@nb.njit(cache=True)
def fast_dispatch_with_renewables(
        load_profile: Mat,

        gen_profile: Mat,
        gen_dispatchable: Mat,
        gen_active: Mat,
        gen_cost: Mat,

        batt_p_max_charge: Mat,
        batt_p_max_discharge: Mat,
        batt_energy_max: Mat,
        batt_eff_charge: Mat,
        batt_eff_discharge: Mat,
        soc0: Vec,
        soc_min: Vec,

        dt: Vec,
        force_charge_if_low: bool,
        tol=1e-6):
    """
    Greedy dispatch algorithm with dispatchable and non-dispatchable (e.g., renewable) generators.
    :param load_profile: ndarray (T, L) - Load time series per timestep and load element.
    :param gen_profile: ndarray (T, G) - Precomputed generator output (for renewables or constraints).
    :param gen_dispatchable: ndarray (G,) - Boolean flag per generator (True if dispatchable).
    :param gen_active: ndarray (T, G) - Boolean array indicating whether each generator is active.
    :param gen_cost: ndarray (T, G) - Generator cost profile per timestep.
    :param batt_p_max_charge: ndarray (T, B) - Battery charge limits.
    :param batt_p_max_discharge: ndarray (T, B) - Battery discharge limits.
    :param batt_energy_max: ndarray (T, B) - Battery energy capacity.
    :param batt_eff_charge: ndarray (T, B) - Battery efficiencies.
    :param batt_eff_discharge: ndarray (T, B) - Battery efficiencies.
    :param soc0: ndarray (B,) - Initial SOC.
    :param soc_min: ndarray (B) - Battery minimum state of charge
    :param dt: float - Timestep duration [h].
    :param force_charge_if_low: Force to charge if low?
    :param tol: Tolerance (numerical zero)
    :return:
            dispatch_gen : ndarray (T, G)
            dispatch_batt : ndarray (T, B)
            soc : ndarray (T, B)
            total_cost : float
    """

    T, L = load_profile.shape
    _, G = gen_profile.shape
    _, B = batt_p_max_charge.shape

    dispatch_gen = np.zeros((T, G))
    dispatch_batt = np.zeros((T, B))
    soc = np.zeros((T + 1, B))
    total_cost = 0.0

    # initialize the SoC
    soc[0, :] = soc0

    for t in range(T):

        # Step 0: Initialize the remaining load to the total load
        remaining = np.sum(load_profile[t, :])

        # Step 1: Apply fixed (non-dispatchable) generation

        gen_order = list()
        for g in range(G):
            if gen_active[t, g] and not gen_dispatchable[g]:
                dispatch = min(gen_profile[t, g], remaining)
                dispatch_gen[t, g] = dispatch
                remaining -= dispatch
                # No cost for renewables assumed

        # Step 2: Dispatchable generation (sorted by cost)
        # Generate list of (cost, g) for active+dispatchable generators
        for g in range(G):
            if gen_active[t, g] and gen_dispatchable[g]:
                gen_order.append((gen_cost[t, g], g))

        gen_order.sort()
        for cost, g in gen_order:
            p_max = gen_profile[t, g]  # cap for dispatchable generator
            p = min(p_max, remaining)
            dispatch_gen[t, g] = p
            total_cost += p * gen_cost[t, g] * dt[t]
            remaining -= p
            if remaining <= tol:
                break

        # Step 3: Battery dispatch
        if remaining > tol:
            # Discharge batteries
            for b in range(B):
                avail = soc[t, b] / dt[t]
                p_dis = min(batt_p_max_discharge[t, b], remaining / batt_eff_discharge[t, b], avail)
                dispatched = p_dis * batt_eff_discharge[t, b]
                dispatch_batt[t, b] = dispatched
                soc[t + 1, b] = soc[t, b] - p_dis * dt[t]
                remaining -= dispatched
                if remaining <= tol:
                    break
        else:
            # Charging section (with optional forced charging if SoC < soc_min)
            excess = -remaining if remaining < -tol else 0.0

            for b in range(B):
                force_charge = force_charge_if_low and soc[t, b] < soc_min[b]
                room = (batt_energy_max[t, b] - soc[t, b]) / dt[t]
                p_ch_possible = batt_p_max_charge[t, b]
                if not force_charge and excess <= 0.0:
                    soc[t + 1, b] = soc[t, b]  # maintain
                    continue

                p_ch = min(p_ch_possible, room)
                if not force_charge:
                    p_ch = min(p_ch, excess * batt_eff_charge[t, b])

                dispatched = -p_ch / batt_eff_charge[t, b]
                dispatch_batt[t, b] = dispatched
                soc[t + 1, b] = soc[t, b] + p_ch * dt[t]
                if not force_charge:
                    excess -= -dispatched

    return dispatch_gen, dispatch_batt, soc[1::, :], total_cost


def run_simple_dispatch_ts(grid: MultiCircuit,
                           time_indices: IntVec,
                           logger: Logger,
                           text_prog=None,
                           prog_func=None) -> Tuple[Mat, Mat, Mat, Mat, Mat]:
    """

    :param grid:
    :param time_indices:
    :param logger:
    :param text_prog:
    :param prog_func:
    :return:
    """

    if time_indices is None:
        time_indices = grid.get_all_time_indices()

    nt = len(time_indices)
    nl = grid.get_loads_number()
    ng = grid.get_generators_number()
    nb = grid.get_batteries_number()

    # loads
    load_profile = np.zeros((nt, nl))
    for i, elm in enumerate(grid.loads):
        load_profile[:, i] = elm.P_prof.toarray()[time_indices]

    # generators
    gen_profile = np.zeros((nt, ng))
    dispatchable = np.zeros(ng, dtype=int)
    gen_active = np.zeros((nt, ng), dtype=int)
    gen_cost = np.zeros((nt, ng))
    for i, elm in enumerate(grid.generators):
        gen_profile[:, i] = elm.P_prof.toarray()[time_indices]
        gen_active[:, i] = elm.active_prof.toarray()[time_indices]
        gen_cost[:, i] = elm.Cost_prof.toarray()[time_indices]
        dispatchable[i] = elm.enabled_dispatch

    # batteries
    p_max_charge = np.zeros((nt, nb), dtype=int)
    p_max_discharge = np.zeros((nt, nb), dtype=int)
    energy_max = np.zeros((nt, nb), dtype=int)
    eff_charge = np.zeros((nt, nb), dtype=int)
    eff_discharge = np.zeros((nt, nb), dtype=int)
    soc0 = np.zeros(nb, dtype=int) + 0.5
    soc_min = np.zeros(nb, dtype=int) + 0.1
    for i, elm in enumerate(grid.batteries):
        p_max_charge[:, i] = elm.Pmax * 0.5
        p_max_discharge[:, i] = elm.Pmax * 0.5
        energy_max[:, i] = elm.Enom
        eff_charge[:, i] = elm.charge_efficiency if elm.charge_efficiency > 0.0 else 1.0
        eff_discharge[:, i] = elm.discharge_efficiency if elm.discharge_efficiency > 0.0 else 1.0
        soc0[i] = elm.Enom * 0.5
        soc_min[i] = elm.Enom * elm.min_soc

    # === Run dispatch ===
    gen_dispatch, batt_dispatch, soc, total_cost = fast_dispatch_with_renewables(
        load_profile=load_profile,
        gen_profile=gen_profile,
        gen_dispatchable=dispatchable,
        gen_active=gen_active,
        gen_cost=gen_cost,
        batt_p_max_charge=p_max_charge,
        batt_p_max_discharge=p_max_discharge,
        batt_energy_max=energy_max,
        batt_eff_charge=eff_charge,
        batt_eff_discharge=eff_discharge,
        soc0=soc0,
        soc_min=soc_min,
        dt=grid.get_time_deltas_in_hours()[time_indices],
        force_charge_if_low=True
    )

    load_total = np.sum(load_profile, axis=1)
    gen_total = np.sum(gen_dispatch, axis=1)
    batt_total = np.sum(batt_dispatch, axis=1)
    supply_total = gen_total + batt_total
    load_not_supplied = load_total - supply_total

    load_shedding = np.round(load_profile * (load_not_supplied / load_total)[:, np.newaxis], 6)

    return load_profile, gen_dispatch, batt_dispatch, soc, load_shedding
