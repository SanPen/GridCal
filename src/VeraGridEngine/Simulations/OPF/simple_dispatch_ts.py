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
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.basic_structures import Vec, Mat, IntVec, Logger


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
def greedy_dispatch(
        load_profile: Mat,

        gen_profile: Mat,
        gen_p_max: Mat,
        gen_p_min: Mat,
        gen_dispatchable: Mat,
        gen_active: Mat,
        gen_cost: Mat,

        batt_active: Mat,
        batt_p_max_charge: Mat,
        batt_p_max_discharge: Mat,
        batt_energy_max: Mat,
        batt_eff_charge: Mat,
        batt_eff_discharge: Mat,
        batt_cost: Mat,
        batt_soc0: Vec,
        batt_soc_min: Vec,

        dt: Vec,
        force_charge_if_low: bool,
        tol=1e-6):
    """
    Greedy dispatch algorithm with dispatchable and non-dispatchable (e.g., renewable) generators.
    :param load_profile: ndarray (T, L) - Load time series per timestep and load element.
    :param gen_profile: ndarray (T, G) - Precomputed generator output (for renewables or constraints).
    :param gen_p_max: ndarray (T, G) - array of generators maximum power
    :param gen_p_min: ndarray (T, G) - array of generators minimum power
    :param gen_dispatchable: ndarray (G,) - Boolean flag per generator (True if dispatchable).
    :param gen_active: ndarray (T, G) - Boolean array indicating whether each generator is active.
    :param gen_cost: ndarray (T, G) - Generator cost profile per timestep.
    :param batt_active: ndarray (T, B) - Battery active states.
    :param batt_p_max_charge: ndarray (T, B) - Battery charge limits.
    :param batt_p_max_discharge: ndarray (T, B) - Battery discharge limits.
    :param batt_energy_max: ndarray (T, B) - Battery energy capacity.
    :param batt_eff_charge: ndarray (T, B) - Battery efficiencies.
    :param batt_eff_discharge: ndarray (T, B) - Battery efficiencies.
    :param batt_cost (T, B) - Battery costs of discharge
    :param batt_soc0: ndarray (B,) - Initial SOC.
    :param batt_soc_min: ndarray (B) - Battery minimum state of charge
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
    batt_energy = np.zeros((T + 1, B))
    total_cost = 0.0

    load_not_supplied = np.zeros(T)
    load_total = np.zeros(T)

    # initialize the SoC
    batt_energy[0, :] = batt_soc0

    for t in range(T):

        # Step 0: Initialize the remaining load to the total load
        remaining_load = np.sum(load_profile[t, :])
        load_total[t] = remaining_load

        # Step 1: Apply fixed (non-dispatchable) generation
        gen_order = list()
        for g in range(G):
            if gen_active[t, g]:
                if gen_dispatchable[g]:
                    # store the dispatchable generation for later
                    gen_order.append((gen_cost[t, g], g))
                else:
                    # remove the generation that is fixed
                    dispatch = min(gen_profile[t, g], remaining_load)
                    dispatch_gen[t, g] = dispatch
                    remaining_load -= dispatch
                    total_cost += dispatch * gen_cost[t, g] * dt[t]
                    # No cost for renewables assumed

        # Step 2: Dispatchable generation (sorted by cost)
        # Generate list of (cost, g) for active+dispatchable generators
        gen_order.sort()
        for cost, g in gen_order:
            p_max = min(gen_p_max[t, g], gen_profile[t, g])
            p_min = min(gen_p_min[t, g], p_max)  # don't allow p_min > p_max
            p = min(p_max, remaining_load)
            p = max(p, p_min) if remaining_load >= p_min else 0.0
            dispatch_gen[t, g] = p
            total_cost += p * gen_cost[t, g] * dt[t]
            remaining_load -= p
            if remaining_load <= tol:
                break

        # Step 3: Battery dispatch
        if remaining_load > tol:
            # Discharge batteries
            for b in range(B):
                if batt_active[t, b]:
                    avail = batt_energy[t, b] / dt[t]
                    p_dis = min(batt_p_max_discharge[t, b], remaining_load / batt_eff_discharge[t, b], avail)
                    dispatched = p_dis * batt_eff_discharge[t, b]
                    dispatch_batt[t, b] = dispatched
                    batt_energy[t + 1, b] = batt_energy[t, b] - p_dis * dt[t]
                    remaining_load -= dispatched
                    total_cost += dispatched * batt_cost[t, b] * dt[t]
                    if remaining_load <= tol:
                        break
        else:
            # Charging section (with optional forced charging if SoC < soc_min)
            excess = -remaining_load if remaining_load < -tol else 0.0

            for b in range(B):
                if batt_active[t, b]:
                    force_charge = force_charge_if_low and batt_energy[t, b] < batt_soc_min[b]
                    room = (batt_energy_max[t, b] - batt_energy[t, b]) / dt[t]
                    p_ch_possible = batt_p_max_charge[t, b]
                    if not force_charge and excess <= 0.0:
                        batt_energy[t + 1, b] = batt_energy[t, b]  # maintain
                        continue

                    p_ch = min(p_ch_possible, room)
                    if not force_charge:
                        p_ch = min(p_ch, excess * batt_eff_charge[t, b])

                    dispatched = -p_ch / batt_eff_charge[t, b]
                    dispatch_batt[t, b] = dispatched
                    batt_energy[t + 1, b] = batt_energy[t, b] + p_ch * dt[t]
                    if not force_charge:
                        excess -= -dispatched

        if remaining_load > 0:
            load_not_supplied[t] = remaining_load

    load_shedding = np.round(load_profile * (load_not_supplied / load_total)[:, np.newaxis], 6)

    return dispatch_gen, dispatch_batt, batt_energy[1::, :], total_cost, load_not_supplied, load_shedding


@nb.njit(cache=True)
def greedy_dispatch2(
        load_profile: Mat,

        gen_profile: Mat,
        gen_p_max: Mat,
        gen_p_min: Mat,
        gen_dispatchable: Mat,
        gen_active: Mat,
        gen_cost: Mat,

        batt_active: Mat,
        batt_p_max_charge: Mat,
        batt_p_max_discharge: Mat,
        batt_energy_max: Mat,
        batt_eff_charge: Mat,
        batt_eff_discharge: Mat,
        batt_cost: Mat,
        batt_soc0: Vec,
        batt_soc_min: Vec,

        dt: Vec,
        force_charge_if_low: bool,
        tol=1e-6):
    """
    Greedy dispatch algorithm with dispatchable and non-dispatchable (e.g., renewable) generators.

    (A) non-dispatchable gens
    → (B) battery discharge
    → (C) dispatchable gens
    → (D) charge batteries from NDG excess
         (and, if force_charge_if_low=True,
         allow charging even with no excess for depleted batteries).

    :param load_profile: ndarray (T, L) - Load time series per timestep and load element.
    :param gen_profile: ndarray (T, G) - Precomputed generator output (for renewables or constraints).
    :param gen_p_max: ndarray (T, G) - array of generators maximum power
    :param gen_p_min: ndarray (T, G) - array of generators minimum power
    :param gen_dispatchable: ndarray (G,) - Boolean flag per generator (True if dispatchable).
    :param gen_active: ndarray (T, G) - Boolean array indicating whether each generator is active.
    :param gen_cost: ndarray (T, G) - Generator cost profile per timestep.
    :param batt_active: ndarray (T, B) - Battery active states.
    :param batt_p_max_charge: ndarray (T, B) - Battery charge limits.
    :param batt_p_max_discharge: ndarray (T, B) - Battery discharge limits.
    :param batt_energy_max: ndarray (T, B) - Battery energy capacity.
    :param batt_eff_charge: ndarray (T, B) - Battery efficiencies.
    :param batt_eff_discharge: ndarray (T, B) - Battery efficiencies.
    :param batt_cost (T, B) - Battery costs of discharge
    :param batt_soc0: ndarray (B,) - Initial SOC.
    :param batt_soc_min: ndarray (B) - Battery minimum state of charge
    :param dt: float - Timestep duration [h].
    :param force_charge_if_low: Force to charge if low?
    :param tol: Tolerance (numerical zero)
    :return:
            dispatch_gen : ndarray (T, G)
            dispatch_batt : ndarray (T, B)
            soc : ndarray (T, B)
            total_cost : float
            load_not_supplied:
            load_shedding:
            ndg_surplus_after_batt,
            ndg_curtailment_per_gen (T, G)
    """

    T, L = load_profile.shape
    _, G = gen_profile.shape
    _, B = batt_p_max_charge.shape

    dispatch_gen = np.zeros((T, G))
    dispatch_batt = np.zeros((T, B))  # + = discharge to grid, - = charging
    batt_energy = np.zeros((T + 1, B))
    total_cost = 0.0

    load_not_supplied = np.zeros(T)
    load_total = np.zeros(T)

    # Non-dispatchable generation (NDG) accounting
    ndg_surplus_after_batt = np.zeros(T)  # total curtailed NDG after attempting to charge
    ndg_curtailment_per_gen = np.zeros((T, G))
    ndg_unused = np.zeros((T, G))  # NDG not used to serve load at (A)

    # init SoC
    batt_energy[0, :] = batt_soc0

    for t in range(T):
        # carry SoC forward by default
        batt_energy[t + 1, :] = batt_energy[t, :]

        # total load this step
        remaining_load = np.sum(load_profile[t, :])
        load_total[t] = remaining_load

        # ------------------------------------------------------------
        # (A) NON-DISPATCHABLE GENERATION
        # ------------------------------------------------------------
        ndg_excess = 0.0
        gen_order = list()

        for g in range(G):
            if gen_active[t, g]:
                if gen_dispatchable[g]:
                    gen_order.append((gen_cost[t, g], g))
                else:
                    # available NDG this step (keep original behaviour)
                    avail = gen_profile[t, g]
                    if gen_p_max[t, g] < avail:
                        avail = gen_p_max[t, g]  # cap the dispatch to the maximum value (error in the model)

                    # dispatch = min(avail, remaining_load)
                    if avail <= remaining_load:
                        dispatch = avail
                    else:
                        dispatch = remaining_load

                    dispatch_gen[t, g] = dispatch
                    remaining_load = remaining_load - dispatch
                    total_cost = total_cost + dispatch * gen_cost[t, g] * dt[t]

                    # NDG not used to serve load -> potential surplus
                    unused = avail - dispatch
                    ndg_unused[t, g] = unused
                    ndg_excess = ndg_excess + unused
            else:
                # inactive generator
                pass

        # ------------------------------------------------------------
        # (B) BATTERY DISCHARGE (cover remaining deficit)
        # ------------------------------------------------------------
        # track batteries that discharged to avoid charging them later in (D)
        batt_discharged_flag = np.zeros(B, dtype=np.int64)

        if remaining_load > tol:
            for b in range(B):
                if batt_active[t, b]:
                    # available discharge power; do not go below soc_min
                    if batt_energy[t, b] > batt_soc_min[b]:
                        if dt[t] != 0.0:
                            avail_pow = (batt_energy[t, b] - batt_soc_min[b]) / dt[t]
                        else:
                            avail_pow = 0.0
                        if avail_pow < 0.0:
                            avail_pow = 0.0
                    else:
                        avail_pow = 0.0

                    # remaining/eta_d (guard η)
                    if batt_eff_discharge[t, b] > tol:
                        limit_by_eff = remaining_load / batt_eff_discharge[t, b]
                    else:
                        limit_by_eff = 0.0

                    # p_dis = min(p_max_discharge, limit_by_eff, avail_pow)
                    p_dis = batt_p_max_discharge[t, b]
                    if limit_by_eff < p_dis:
                        p_dis = limit_by_eff
                    if avail_pow < p_dis:
                        p_dis = avail_pow

                    if p_dis > tol:
                        delivered = p_dis * batt_eff_discharge[t, b]
                        dispatch_batt[t, b] = delivered
                        batt_energy[t + 1, b] = batt_energy[t, b] - p_dis * dt[t]

                        # clamp SoC to [soc_min, Emax]
                        if batt_energy[t + 1, b] < batt_soc_min[b]:
                            batt_energy[t + 1, b] = batt_soc_min[b]
                        if batt_energy[t + 1, b] > batt_energy_max[t, b]:
                            batt_energy[t + 1, b] = batt_energy_max[t, b]

                        remaining_load = remaining_load - delivered
                        total_cost = total_cost + delivered * batt_cost[t, b] * dt[t]
                        batt_discharged_flag[b] = 1

                        if remaining_load <= tol:
                            break
                else:
                    # inactive battery
                    pass

        # ------------------------------------------------------------
        # (C) DISPATCHABLE GENERATION (ascending cost)
        # ------------------------------------------------------------
        gen_order.sort()
        for cost, g in gen_order:
            # p_max = min(gen_p_max, gen_profile)
            if gen_p_max[t, g] <= gen_profile[t, g]:
                p_max = gen_p_max[t, g]
            else:
                p_max = gen_profile[t, g]

            # p_min = min(gen_p_min, p_max)
            if gen_p_min[t, g] <= p_max:
                p_min = gen_p_min[t, g]
            else:
                p_min = p_max

            # if remaining >= p_min: p = min(p_max, remaining) else 0
            if remaining_load >= p_min:
                if p_max <= remaining_load:
                    p = p_max
                else:
                    p = remaining_load
            else:
                p = 0.0

            dispatch_gen[t, g] = dispatch_gen[t, g] + p  # in case unit had NDG earlier (it didn't, but explicit)
            total_cost = total_cost + p * gen_cost[t, g] * dt[t]
            remaining_load = remaining_load - p

            if remaining_load <= tol:
                break

        # ------------------------------------------------------------
        # (D) BATTERY CHARGE from Non-Dispatchable Generation EXCESS
        #     If depleted and force flag, allow charging even without NDG excess.
        # ------------------------------------------------------------
        excess = ndg_excess  # pool available for regular charging

        for b in range(B):
            if batt_active[t, b]:
                # skip if it discharged earlier this step (avoid ping-pong)
                if batt_discharged_flag[b] == 1:
                    # keep carried SoC
                    pass
                else:
                    # force-charge if depleted and flag is on
                    if force_charge_if_low and (batt_energy[t, b] < batt_soc_min[b]):
                        force_charge = True
                    else:
                        force_charge = False

                    # headroom (kW) this step
                    if dt[t] != 0.0:
                        room_kw = (batt_energy_max[t, b] - batt_energy[t, b]) / dt[t]
                    else:
                        room_kw = 0.0
                    if room_kw < 0.0:
                        room_kw = 0.0

                    p_ch_possible = batt_p_max_charge[t, b]

                    # p_ch starts at possible and is capped by room
                    p_ch = p_ch_possible
                    if room_kw < p_ch:
                        p_ch = room_kw

                    if not force_charge:
                        # limit by NDG excess via efficiency
                        if batt_eff_charge[t, b] > tol:
                            max_by_excess = excess * batt_eff_charge[t, b]
                        else:
                            max_by_excess = 0.0
                        if max_by_excess < p_ch:
                            p_ch = max_by_excess
                    else:
                        # allowed even if excess == 0
                        pass

                    # apply if feasible
                    if batt_eff_charge[t, b] > tol and p_ch > 0.0:
                        grid_draw = p_ch / batt_eff_charge[t, b]  # taken from excess when not forced
                        dispatch_batt[t, b] = dispatch_batt[t, b] - grid_draw
                        batt_energy[t + 1, b] = batt_energy[t, b] + p_ch * dt[t]

                        # clamp SoC to [0, Emax]
                        if batt_energy[t + 1, b] < 0.0:
                            batt_energy[t + 1, b] = 0.0
                        if batt_energy[t + 1, b] > batt_energy_max[t, b]:
                            batt_energy[t + 1, b] = batt_energy_max[t, b]

                        if not force_charge:
                            # reduce NDG excess by the grid draw (positive)
                            excess = excess - grid_draw
                            if excess < 0.0:
                                excess = 0.0
                    else:
                        # no feasible charge; keep carried SoC
                        pass
            else:
                # inactive battery
                pass

        # leftover NDG after charging is curtailment
        if excess > tol:
            ndg_surplus_after_batt[t] = excess
        else:
            ndg_surplus_after_batt[t] = 0.0

        # proportional per-NDG curtailment
        if ndg_excess > tol and ndg_surplus_after_batt[t] > tol:
            for g in range(G):
                if gen_active[t, g]:
                    if gen_dispatchable[g]:
                        ndg_curtailment_per_gen[t, g] = 0.0
                    else:
                        w = ndg_unused[t, g] / ndg_excess
                        ndg_curtailment_per_gen[t, g] = ndg_surplus_after_batt[t] * w
                else:
                    ndg_curtailment_per_gen[t, g] = 0.0
        else:
            ndg_curtailment_per_gen[t, :] = 0.0

        # unmet load
        if remaining_load > 0.0:
            load_not_supplied[t] = remaining_load
        else:
            load_not_supplied[t] = 0.0

    # proportional shedding split
    load_shedding = np.round(load_profile * (load_not_supplied / load_total)[:, np.newaxis], 6)

    return (dispatch_gen,
            dispatch_batt,
            batt_energy[1:, :],
            total_cost,
            load_not_supplied,
            load_shedding,
            ndg_surplus_after_batt,
            ndg_curtailment_per_gen)


class GreedyDispatchInputs:

    def __init__(self, grid: MultiCircuit, time_indices: IntVec | None = None, logger: Logger = Logger()):
        """

        :param grid:
        :param time_indices:
        :param logger:
        """

        if time_indices is None:
            time_indices = grid.get_all_time_indices()

        nt = len(time_indices)
        nl = grid.get_loads_number()
        ng = grid.get_generators_number()
        nbatt = grid.get_batteries_number()

        self.dt = grid.get_time_deltas_in_hours()[time_indices]

        # loads
        self.load_profile = np.zeros((nt, nl), dtype=float)
        for i, elm in enumerate(grid.loads):
            self.load_profile[:, i] = elm.P_prof.toarray()[time_indices]

        # generators
        self.gen_profile = np.zeros((nt, ng), dtype=float)
        self.gen_dispatchable = np.zeros(ng, dtype=int)
        self.gen_active = np.zeros((nt, ng), dtype=int)
        self.gen_cost = np.zeros((nt, ng), dtype=float)
        self.gen_p_max = np.zeros((nt, ng), dtype=float)
        self.gen_p_min = np.zeros((nt, ng), dtype=float)
        for i, elm in enumerate(grid.generators):
            self.gen_profile[:, i] = elm.P_prof.toarray()[time_indices]
            self.gen_active[:, i] = elm.active_prof.toarray()[time_indices]
            self.gen_cost[:, i] = elm.Cost_prof.toarray()[time_indices] + elm.opex
            self.gen_p_max[:, i] = elm.Pmax_prof.toarray()[time_indices]
            self.gen_p_min[:, i] = elm.Pmin_prof.toarray()[time_indices]
            self.gen_dispatchable[i] = elm.enabled_dispatch

        self.gen_profile = np.nan_to_num(self.gen_profile)

        # batteries
        self.batt_active = np.zeros((nt, nbatt), dtype=int)
        self.batt_p_max_charge = np.zeros((nt, nbatt), dtype=float)
        self.batt_p_max_discharge = np.zeros((nt, nbatt), dtype=float)
        self.batt_energy_max = np.zeros((nt, nbatt), dtype=float)
        self.batt_eff_charge = np.ones((nt, nbatt), dtype=float)
        self.batt_eff_discharge = np.ones((nt, nbatt), dtype=float)
        self.batt_cost = np.ones((nt, nbatt), dtype=float)
        self.batt_soc0 = np.zeros(nbatt, dtype=float) + 0.5
        self.batt_soc_min = np.zeros(nbatt, dtype=float) + 0.1
        for i, elm in enumerate(grid.batteries):
            self.batt_active[:, i] = elm.active_prof.toarray()[time_indices]
            self.batt_p_max_charge[:, i] = elm.Pmax
            self.batt_p_max_discharge[:, i] = elm.Pmax
            self.batt_energy_max[:, i] = elm.Enom
            self.batt_cost[:, i] = elm.Cost_prof.toarray()[time_indices] + elm.opex

            if elm.charge_efficiency > 0.0:
                self.batt_eff_charge[:, i] = elm.charge_efficiency
            else:
                self.batt_eff_charge[:, i] = 1.0
                logger.add_warning("Charge efficiency is zero", device_class="Battery", device=elm.idtag)

            if elm.discharge_efficiency > 0.0:
                self.batt_eff_discharge[:, i] = elm.discharge_efficiency
            else:
                self.batt_eff_discharge[:, i] = 1.0
                logger.add_warning("Discharge efficiency is zero", device_class="Battery", device=elm.idtag)

            self.batt_soc0[i] = elm.Enom * 0.5
            self.batt_soc_min[i] = elm.Enom * elm.min_soc


class GreedyDispatchInputsSnapshot:

    def __init__(self, grid: MultiCircuit, logger: Logger = Logger()):
        """

        :param grid:
        :param logger:
        """

        nt = 1
        nl = grid.get_loads_number()
        ng = grid.get_generators_number()
        nbatt = grid.get_batteries_number()

        self.dt = np.ones(1)

        # loads
        self.load_profile = np.zeros((nt, nl), dtype=float)
        for i, elm in enumerate(grid.loads):
            self.load_profile[:, i] = elm.P

        # generators
        self.gen_profile = np.zeros((nt, ng), dtype=float)
        self.gen_dispatchable = np.zeros(ng, dtype=int)
        self.gen_active = np.zeros((nt, ng), dtype=int)
        self.gen_cost = np.zeros((nt, ng), dtype=float)
        self.gen_p_max = np.zeros((nt, ng), dtype=float)
        self.gen_p_min = np.zeros((nt, ng), dtype=float)
        for i, elm in enumerate(grid.generators):
            self.gen_profile[:, i] = elm.P
            self.gen_active[:, i] = elm.active
            self.gen_cost[:, i] = elm.Cost
            self.gen_p_max[:, i] = elm.Pmax
            self.gen_p_min[:, i] = elm.Pmin
            self.gen_dispatchable[i] = elm.enabled_dispatch

        self.gen_profile = np.nan_to_num(self.gen_profile)

        # batteries
        self.batt_active = np.zeros((nt, nbatt), dtype=int)
        self.batt_p_max_charge = np.zeros((nt, nbatt), dtype=float)
        self.batt_p_max_discharge = np.zeros((nt, nbatt), dtype=float)
        self.batt_energy_max = np.zeros((nt, nbatt), dtype=float)
        self.batt_eff_charge = np.ones((nt, nbatt), dtype=float)
        self.batt_eff_discharge = np.ones((nt, nbatt), dtype=float)
        self.batt_cost = np.ones((nt, nbatt), dtype=float)
        self.batt_soc0 = np.zeros(nbatt, dtype=float) + 0.5
        self.batt_soc_min = np.zeros(nbatt, dtype=float) + 0.1
        for i, elm in enumerate(grid.batteries):
            self.batt_active[:, i] = elm.active
            self.batt_p_max_charge[:, i] = elm.Pmax
            self.batt_p_max_discharge[:, i] = elm.Pmax
            self.batt_energy_max[:, i] = elm.Enom
            self.batt_cost[:, i] = elm.Cost + elm.opex

            if elm.charge_efficiency > 0.0:
                self.batt_eff_charge[:, i] = elm.charge_efficiency
            else:
                self.batt_eff_charge[:, i] = 1.0
                logger.add_warning("Charge efficiency is zero", device_class="Battery", device=elm.idtag)

            if elm.discharge_efficiency > 0.0:
                self.batt_eff_discharge[:, i] = elm.discharge_efficiency
            else:
                self.batt_eff_discharge[:, i] = 1.0
                logger.add_warning("Discharge efficiency is zero", device_class="Battery", device=elm.idtag)

            self.batt_soc0[i] = elm.Enom * 0.5
            self.batt_soc_min[i] = elm.Enom * elm.min_soc


def run_greedy_dispatch_ts(grid: MultiCircuit,
                           time_indices: IntVec | None,
                           logger: Logger,
                           text_prog=None,
                           prog_func=None) -> Tuple[Mat, Mat, Mat, Mat, Mat, Mat]:
    """
    Run a simple (greedy) dispatch
    :param grid: MultiCircuit
    :param time_indices: array of time indices (optional)
    :param logger: Logger
    :param text_prog: text report function (optional)
    :param prog_func: progress report function (optional)
    :return:
    """
    if prog_func is not None:
        prog_func(0.0)

    if text_prog is not None:
        text_prog("Running greedy dispatch...")

    inpts = GreedyDispatchInputs(grid=grid, time_indices=time_indices, logger=logger)

    # === Run dispatch ===
    (gen_dispatch, batt_dispatch,
     batt_energy, total_cost,
     load_not_supplied, load_shedding,
     ndg_surplus_after_batt,
     ndg_curtailment_per_gen) = greedy_dispatch2(
        load_profile=inpts.load_profile,
        gen_profile=inpts.gen_profile,
        gen_p_max=inpts.gen_p_max,
        gen_p_min=inpts.gen_p_min,
        gen_dispatchable=inpts.gen_dispatchable,
        gen_active=inpts.gen_active,
        gen_cost=inpts.gen_cost,
        batt_active=inpts.batt_active,
        batt_p_max_charge=inpts.batt_p_max_charge,
        batt_p_max_discharge=inpts.batt_p_max_discharge,
        batt_energy_max=inpts.batt_energy_max,
        batt_eff_charge=inpts.batt_eff_charge,
        batt_eff_discharge=inpts.batt_eff_discharge,
        batt_cost=inpts.batt_cost,
        batt_soc0=inpts.batt_soc0,
        batt_soc_min=inpts.batt_soc_min,
        dt=inpts.dt,
        force_charge_if_low=True
    )

    if prog_func is not None:
        prog_func(100.0)

    if text_prog is not None:
        text_prog("Done!")

    return inpts.load_profile, gen_dispatch, batt_dispatch, batt_energy, load_shedding, ndg_curtailment_per_gen


if __name__ == '__main__':
    import VeraGridEngine.api as gce
    from matplotlib import pyplot as plt

    fname = "/home/santi/Documentos/Git/eRoots/tonga_planning/model_conversion_and_validation/Tongatapu/models/Tongatapu_v4_2024_ts.veragrid"

    grid_ = gce.open_file(fname)

    (load_profile_,
     gen_dispatch_,
     batt_dispatch_,
     batt_energy_,
     load_shedding_) = run_greedy_dispatch_ts(grid=grid_, time_indices=None, logger=Logger())

    print()
