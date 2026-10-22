# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
This file implements a DC-OPF for time series
That means that solves the OPF problem for a complete time series at once
"""
from __future__ import annotations
import os
import numpy as np
from typing import List, Union, Tuple, Callable, Dict, Set

from VeraGridEngine.enumerations import MIPSolvers, MIPFramework, ZonalGrouping
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Events.contingency_group import ContingencyGroup
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.DataStructures.generator_data import GeneratorData
from VeraGridEngine.DataStructures.battery_data import BatteryData
from VeraGridEngine.DataStructures.load_data import LoadData
from VeraGridEngine.DataStructures.passive_branch_data import PassiveBranchData
from VeraGridEngine.DataStructures.active_branch_data import ActiveBranchData
from VeraGridEngine.DataStructures.hvdc_data import HvdcData
from VeraGridEngine.DataStructures.vsc_data import VscData
from VeraGridEngine.DataStructures.bus_data import BusData
from VeraGridEngine.basic_structures import Logger, Vec, IntVec, BoolVec, CxMat, Mat, ObjVec
from VeraGridEngine.Utils.MIP.selected_interface import LpExp, LpVar, LpModel, join, get_model_instance, is_infeasible
from VeraGridEngine.enumerations import TapPhaseControl, HvdcControlType, AvailableTransferMode, ConverterControlType
from scipy.sparse import csc_matrix, coo_matrix
from VeraGridEngine.Simulations.LinearFactors.linear_analysis import (LinearAnalysis, LinearMultiContingencies,
                                                                      LinearMultiContingency)
from VeraGridEngine.Simulations.ATC.available_transfer_capacity_driver import compute_alpha, compute_alpha_n1, \
    compute_dP
from VeraGridEngine.IO.file_system import opf_file_path
from VeraGridEngine.Simulations.NTC.ntc_compact import (SolverProgress, CompactContingencies, add_clipped_flow,
                                                        BranchVariables, ConverterVariables)


def formulate_monitorization_logic(monitor_only_sensitive_branches: bool,
                                   monitor_only_ntc_load_rule_branches: bool,
                                   monitor_loading: BoolVec,
                                   alpha: Vec,
                                   alpha_n1: Vec,
                                   branch_sensitivity_threshold: float,
                                   base_flows: Vec,
                                   structural_ntc: float,
                                   ntc_load_rule: float,
                                   rates: Vec) -> Tuple[BoolVec, ObjVec, Vec, Vec]:
    """
    Function to formulate branch monitor status due the given logic
    :param monitor_only_sensitive_branches: boolean to apply sensitivity threshold to the monitorization logic.
    :param monitor_only_ntc_load_rule_branches: boolean to apply ntc load rule to the monitorization logic.
    :param monitor_loading: Array of branch monitor loading status given by the user (True / False)
    :param alpha: Array of branch sensitivity to the exchange in n condition
    :param alpha_n1: Array of branch sensitivity to the exchange in n-1 condition
    :param branch_sensitivity_threshold: branch sensitivity to the exchange threshold
    :param base_flows: branch base flows
    :param structural_ntc: Maximum NTC available by thermal interconnection rates.
    :param ntc_load_rule: percentage of loading reserved to exchange flow (Clean Energy Package rule by ACER).
    :param rates: array of branch rates
    return:
        - monitor: Array of final monitor status per branch after applying the logic
        - monitor_type: monitor type chosen depending on the rules
        - branch_ntc_load_rule: branch minimum ntc to be considered as limiting element
        - branch_zero_exchange_load: branch load for zero exchange situation.
    """

    # NTC min for considering as limiting element by CEP rule
    branch_ntc_load_rule_n = ntc_load_rule * rates / (alpha + 1e-20)
    branch_ntc_load_rule_n1 = ntc_load_rule * rates / (alpha_n1 + 1e-20)

    # Branch load without exchange
    branch_zero_exchange_load_n = base_flows * (1 - alpha) / rates
    branch_zero_exchange_load_n1 = base_flows * (1 - alpha_n1) / rates

    # Exclude branches with not enough sensibility to exchange
    if monitor_only_sensitive_branches:
        monitor_by_sensitivity_n = alpha > branch_sensitivity_threshold
        monitor_by_sensitivity_n1 = alpha_n1 > branch_sensitivity_threshold
    else:
        monitor_by_sensitivity_n = np.ones(len(base_flows), dtype=bool)
        monitor_by_sensitivity_n1 = np.ones(len(base_flows), dtype=bool)

    # N 'and' N-1 criteria
    branch_zero_exchange_load = branch_zero_exchange_load_n * branch_zero_exchange_load_n1
    branch_ntc_load_rule = branch_ntc_load_rule_n * branch_ntc_load_rule_n1
    monitor_by_sensitivity = monitor_by_sensitivity_n * monitor_by_sensitivity_n1

    # Avoid unrealistic ntc && Exclude branches with 'interchange zero' flows over CEP rule limit
    if monitor_only_ntc_load_rule_branches:
        monitor_by_unrealistic_ntc = branch_ntc_load_rule <= structural_ntc
        monitor_by_zero_exchange = branch_zero_exchange_load >= (1 - ntc_load_rule)
    else:
        monitor_by_unrealistic_ntc = np.ones(len(base_flows), dtype=bool)
        monitor_by_zero_exchange = np.ones(len(base_flows), dtype=bool)

    monitor_loading = np.array(monitor_loading, dtype=bool)

    monitor = (monitor_loading *
               monitor_by_sensitivity *
               monitor_by_unrealistic_ntc *
               monitor_by_zero_exchange)

    monitor_type = np.zeros(len(base_flows), dtype=object)

    for i, (a, b, c, d) in enumerate(zip(monitor_loading,
                                         monitor_by_sensitivity,
                                         monitor_by_unrealistic_ntc,
                                         monitor_by_zero_exchange)):
        res = []
        if not a:
            res.append('excluded by model')
        if not b:
            res.append('excluded by sensitivity')
        if not c:
            res.append('excluded by unrealistic ntc')
        if not d:
            res.append('excluded by zero exchange')

        monitor_type[i] = ';'.join(res)

    return monitor, monitor_type, branch_ntc_load_rule, branch_zero_exchange_load


def get_transfer_power_scaling_per_bus(bus_data_t: BusData,
                                       gen_data_t: GeneratorData,
                                       load_data_t: LoadData,
                                       transfer_method: AvailableTransferMode,
                                       skip_generation_limits: bool,
                                       inf_value: float,
                                       Sbase: float) -> Tuple[Vec, Vec, Vec]:
    """
    Get nodal power, nodal pmax and nodal pmin according to the transfer_method.
    :param bus_data_t: BusData structure
    :param gen_data_t: GenData structure
    :param load_data_t: LoadData structure
    :param transfer_method: Exchange transfer method
    :param skip_generation_limits: Skip generation limits?
    :param inf_value: infinity value. Ex 1e-20
    :param Sbase: base power (100 MVA)
    :return: nodal power (p.u.), pmax (p.u.), pmin(p.u.)
    """

    # get values per bus
    # active power only: a complex reference makes complex proportions, whose solved values read as 0
    gen_per_bus: Vec = gen_data_t.get_injections_per_bus().real / Sbase
    load_per_bus: Vec = load_data_t.get_injections_per_bus().real / Sbase
    pinst_per_bus = gen_data_t.get_array_per_bus(gen_data_t.installed_p * gen_data_t.active) / Sbase
    # pinst_per_bus = gen_data_t.get_array_per_bus(gen_data_t.installed_p) / Sbase

    # Evaluate transfer method
    if transfer_method == AvailableTransferMode.InstalledPower:
        p_ref = pinst_per_bus

        if skip_generation_limits:
            p_min = np.full(bus_data_t.nbus, -inf_value)
            p_max = np.full(bus_data_t.nbus, inf_value)

        else:
            p_min = gen_data_t.get_pmin_per_bus() / Sbase
            p_max = gen_data_t.get_pmax_per_bus() / Sbase

        # dispatchable_bus = (gen_data_t.C_bus_elm * gen_data_t.dispatchable).astype(bool).astype(float)
        dispatchable_bus = gen_data_t.get_array_per_bus(
            (gen_data_t.dispatchable * gen_data_t.active).astype(float)).astype(bool).astype(float)

    elif transfer_method == AvailableTransferMode.Generation:
        p_ref = gen_per_bus

        if skip_generation_limits:
            p_min = np.full(bus_data_t.nbus, -inf_value)
            p_max = np.full(bus_data_t.nbus, inf_value)

        else:
            p_min = gen_data_t.get_pmin_per_bus() / Sbase
            p_max = gen_data_t.get_pmax_per_bus() / Sbase

        # dispatchable_bus = (gen_data_t.C_bus_elm * gen_data_t.dispatchable).astype(bool).astype(float)
        dispatchable_bus = gen_data_t.get_array_per_bus(
            (gen_data_t.dispatchable * gen_data_t.active).astype(float)).astype(bool).astype(float)

    elif transfer_method == AvailableTransferMode.Load:
        p_ref = load_per_bus
        p_min = -inf_value
        p_max = inf_value

        # todo check
        # dispatchable_bus = (load_data_t.C_bus_elm * load_data_t.S).astype(bool).astype(float)
        dispatchable_bus = load_data_t.get_array_per_bus(load_data_t.S.real).astype(bool).astype(float)

    elif transfer_method == AvailableTransferMode.GenerationAndLoad:
        p_ref = gen_per_bus - load_per_bus
        if skip_generation_limits:
            p_min = np.full(bus_data_t.nbus, -inf_value)
            p_max = np.full(bus_data_t.nbus, inf_value)
        else:
            p_min = gen_data_t.get_pmin_per_bus() / Sbase
            p_max = gen_data_t.get_pmax_per_bus() / Sbase

        # todo check
        # dispatchable_bus = (load_data_t.C_bus_elm * load_data_t.S).astype(bool).astype(float)
        dispatchable_bus = load_data_t.get_array_per_bus(load_data_t.S.real).astype(bool).astype(float)

    else:
        raise Exception('Undefined available transfer mode')

    return p_ref * dispatchable_bus, p_max, p_min


def get_sensed_proportions(power: Vec,
                           idx: IntVec,
                           logger: Logger) -> Vec:
    """

    :param power:
    :param idx:
    :param logger:
    :return:
    """
    nelem = len(power)

    # bus area mask
    isin_ = np.isin(range(nelem), idx, assume_unique=True)

    p_ref = power * isin_

    # get proportions of contribution by sense (gen or pump) and area
    # the idea is both techs contributes to achieve the power shift goal in the same proportion
    # that in base situation

    # Filter positive and negative generators. Same vectors lenght, set not matched values to zero.
    gen_pos = np.where(p_ref < 0, 0, p_ref)
    gen_neg = np.where(p_ref > 0, 0, p_ref)

    denom = np.sum(np.abs(p_ref))
    if denom != 0.0:
        prop_up = np.sum(gen_pos) / denom
        prop_dw = np.sum(gen_neg) / denom
    else:
        prop_up = np.zeros(len(gen_pos))
        prop_dw = np.zeros(len(gen_neg))

    # get proportion by production (amount of power contributed by generator to his sensed area).
    if np.sum(np.abs(gen_pos)) != 0:
        prop_up_gen = gen_pos / np.sum(np.abs(gen_pos))
    else:
        prop_up_gen = np.zeros_like(gen_pos)

    if np.sum(np.abs(gen_neg)) != 0:
        prop_dw_gen = gen_neg / np.sum(np.abs(gen_neg))
    else:
        prop_dw_gen = np.zeros_like(gen_neg)

    # delta proportion by generator (considering both proportions: sense and production)
    prop_gen_delta_up = prop_up_gen * prop_up
    prop_gen_delta_dw = prop_dw_gen * prop_dw

    # Join generator proportions into one vector
    # Notice this is not a summation, it's just joining like 'or' logical operation
    proportions = prop_gen_delta_up + prop_gen_delta_dw

    # some checks
    if not np.isclose(np.sum(proportions), 1, rtol=1e-6):
        logger.add_warning('Issue computing proportions to scale delta generation in area 1.')

    return proportions


def get_exchange_proportions(power: Vec,
                             bus_a1_idx: IntVec,
                             bus_a2_idx: IntVec,
                             logger: Logger,
                             decimals: int):
    """
    Get generation proportions by transfer method with sign consideration.
    :param power: Vec. Power reference
    :param bus_a1_idx: bus indices within area 1
    :param bus_a2_idx: bus indices within area 2
    :param logger: logger instance
    :param decimals: Number of decimals to round to
    :return: proportions (rounded), summing to exactly 1 in area 1 and -1 in area 2
    """
    proportions_a1: Vec = np.round(get_sensed_proportions(power=power, idx=bus_a1_idx, logger=logger), decimals)
    proportions_a2: Vec = np.round(get_sensed_proportions(power=power, idx=bus_a2_idx, logger=logger), decimals)

    # Rounding drops the smallest shares, so each area's total drifts from 1 by ~1e-5. Kirchhoff then
    # makes the area 1 increase differ from the area 2 decrease by that amount. Correct it.
    sum_a1: float = float(np.sum(proportions_a1))
    if sum_a1 != 0.0:
        proportions_a1 /= sum_a1
    else:
        pass  # no transferable injection in area 1

    sum_a2: float = float(np.sum(proportions_a2))
    if sum_a2 != 0.0:
        proportions_a2 /= sum_a2
    else:
        pass  # no transferable injection in area 2

    return proportions_a1 - proportions_a2


def pmode3_formulation(prob, t_idx, m, rate, P0, droop, theta_f, theta_t,
                       base_name: str = "hvdc", angle_range=(-4 * np.pi, 4 * np.pi)):
    """Exact saturation with bounds on the unclipped physical demand."""
    if rate <= 0.0:
        return 0.0
    elif droop == 0.0:
        return float(np.clip(P0, -rate, rate))
    else:
        name = f"{base_name}_{t_idx}_{m}"
        flow = prob.add_var(lb=-rate, ub=rate, name=name + "_flow")
        # same +-90 degree bound on the angle difference as the corrective states, to keep the big M tight
        bounded_range = (max(angle_range[0], -np.pi / 2), min(angle_range[1], np.pi / 2))
        bounds = [P0 + droop * angle for angle in bounded_range]
        add_clipped_flow(prob, flow, P0 + droop * (theta_f - theta_t), rate,
                         min(bounds), max(bounds), name)
        return flow


class BusNtcVars:
    """
    Struct to store the bus related vars
    """

    __slots__ = (
        "angle_min",
        "angle_max",
        "Va",
        "Vm",
        "kirchhoff",
        "shadow_prices",
        "load_p",
        "load_shedding",
        "Pinj",
        "Pbalance",
        "delta_p",
        "proportions",
    )

    def __init__(self, nt: int, n_elm: int):
        """
        BusVars structure
        :param nt: Number of time steps
        :param n_elm: Number of branches
        """
        self.angle_min = np.full(n_elm, -2 * np.pi)
        self.angle_max = np.full(n_elm, 2 * np.pi)
        self.Va = np.zeros((nt, n_elm), dtype=object)
        self.Vm = np.ones((nt, n_elm), dtype=object)
        self.kirchhoff = np.zeros((nt, n_elm), dtype=object)
        self.shadow_prices = np.zeros((nt, n_elm), dtype=float)

        # nodal load
        self.load_p = np.zeros((nt, n_elm), dtype=float)
        self.load_shedding = np.zeros((nt, n_elm), dtype=object)

        # nodal gen
        self.Pinj = np.zeros((nt, n_elm), dtype=object)
        self.Pbalance = np.zeros((nt, n_elm), dtype=object)
        self.delta_p = np.zeros((nt, n_elm), dtype=object)
        self.proportions = np.zeros((nt, n_elm), dtype=float)

    def get_values(self, Sbase: float, model: LpModel) -> "BusNtcVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: BusVars
        """
        nt, n_elm = self.Va.shape
        data = BusNtcVars(nt=nt, n_elm=n_elm)

        data.shadow_prices = self.shadow_prices
        data.load_p = self.load_p * Sbase
        data.proportions = self.proportions

        for t in range(nt):

            for i in range(n_elm):
                data.Va[t, i] = model.get_value(self.Va[t, i])
                data.Vm[t, i] = model.get_value(self.Vm[t, i])
                data.shadow_prices[t, i] = model.get_dual_value(self.kirchhoff[t, i])
                data.load_shedding[t, i] = model.get_value(self.load_shedding[t, i]) * Sbase
                data.Pbalance[t, i] = model.get_value(self.Pbalance[t, i]) * Sbase
                data.Pinj[t, i] = model.get_value(self.Pinj[t, i]) * Sbase
                data.delta_p[t, i] = model.get_value(self.delta_p[t, i]) * Sbase

        # format the arrays appropriately
        data.Va = data.Va.astype(float, copy=False)
        data.Vm = data.Vm.astype(float, copy=False)

        data.load_shedding = data.load_shedding.astype(float, copy=False)

        data.Pbalance = data.Pbalance.astype(float, copy=False)
        data.delta_p = data.delta_p.astype(float, copy=False)

        return data


class LoadVars:
    """
    Struct to store the load related vars
    """

    __slots__ = ("p",)

    def __init__(self, nt: int, n_elm: int):
        """
        LoadVars structure
        :param nt: Number of time steps
        :param n_elm: Number of branches
        """
        self.p = np.zeros((nt, n_elm), dtype=object)  # to be filled (no vars)

    def get_values(self, Sbase: float, model: LpModel) -> "LoadVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: LoadVars
        """
        nt, n_elm = self.p.shape
        data = LoadVars(nt=nt, n_elm=n_elm)

        for t in range(nt):
            for i in range(n_elm):
                data.p[t, i] = model.get_value(self.p[t, i]) * Sbase

        # format the arrays appropriately
        data.p = data.p.astype(float, copy=False)

        return data


class GenerationVars:
    """
    Struct to store the generation vars
    """

    __slots__ = ("p", "p_inc")

    def __init__(self, nt: int, n_elm: int):
        """
        GenerationVars structure
        :param nt: Number of time steps
        :param n_elm: Number of generators
        """
        self.p = np.zeros((nt, n_elm), dtype=object)
        self.p_inc = np.zeros((nt, n_elm), dtype=object)

    def get_values(self,
                   Sbase: float,
                   model: LpModel) -> "GenerationVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :param Sbase: Base power (100 MVA)
        :param model: LpModel
        :return: GenerationVars
        """
        nt, n_elm = self.p.shape
        data = GenerationVars(nt=nt, n_elm=n_elm)

        for t in range(nt):
            for i in range(n_elm):
                data.p[t, i] = model.get_value(self.p[t, i]) * Sbase
                data.p_inc[t, i] = model.get_value(self.p_inc[t, i]) * Sbase

        # format the arrays appropriately
        data.p = data.p.astype(float, copy=False)
        data.p_inc = data.p_inc.astype(float, copy=False)

        return data


class BatteryVars(GenerationVars):
    """
    struct extending the generation vars to handle the battery vars
    """

    __slots__ = ()

    def __init__(self, nt: int, n_elm: int):
        """
        BatteryVars structure
        :param nt: Number of time steps
        :param n_elm: Number of branches
        """
        GenerationVars.__init__(self, nt=nt, n_elm=n_elm)

    def get_values(self, Sbase: float, model: LpModel) -> "BatteryVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: BatteryVars
        """
        nt, n_elm = self.p.shape
        data = BatteryVars(nt=nt, n_elm=n_elm)

        for t in range(nt):
            for i in range(n_elm):
                data.p[t, i] = model.get_value(self.p[t, i]) * Sbase
                data.p_inc[t, i] = model.get_value(self.p_inc[t, i]) * Sbase

            # format the arrays appropriately
            data.p_inc = data.p_inc.astype(float, copy=False)

        return data


class BranchNtcVars:
    """
    Struct to store the branch related vars
    """

    __slots__ = (
        "flows",
        "flow_slacks_pos",
        "flow_slacks_neg",
        "tap_angles",
        "flow_constraints_ub",
        "flow_constraints_lb",
        "rates",
        "contingency_rates",
        "loading",
        "alpha",
        "monitor",
        "monitor_logic",
        "contingency_flow_data",
        "inter_space_branches",
        "worst_contingency_idx",
        "worst_contingency_flow",
        "worst_contingency_loading",
        "alpha_n1_worst",
        "worst_contingency_ties",
    )

    def __init__(self, nt: int, n_elm: int):
        """
        BranchVars structure
        :param nt: Number of time steps
        :param n_elm: Number of branches
        """
        self.flows = np.zeros((nt, n_elm), dtype=object)
        self.flow_slacks_pos = np.zeros((nt, n_elm), dtype=object)
        self.flow_slacks_neg = np.zeros((nt, n_elm), dtype=object)
        self.tap_angles = np.zeros((nt, n_elm), dtype=object)
        self.flow_constraints_ub = np.zeros((nt, n_elm), dtype=object)
        self.flow_constraints_lb = np.zeros((nt, n_elm), dtype=object)

        self.rates = np.zeros((nt, n_elm), dtype=float)
        self.contingency_rates = np.zeros((nt, n_elm), dtype=float)
        self.loading = np.zeros((nt, n_elm), dtype=float)
        self.alpha = np.zeros((nt, n_elm), dtype=float)

        self.monitor = np.zeros((nt, n_elm), dtype=bool)
        self.monitor_logic = np.zeros((nt, n_elm), dtype=int)

        # t, m, c, contingency, negative_slack, positive_slack
        self.contingency_flow_data: List[Tuple[int, int, int, Union[float, LpVar, LpExp], LpVar, LpVar]] = list()

        self.inter_space_branches: List[Tuple[int, float]] = list()  # index, sense

        # per-hour worst N-1: group index in the grid list, or -1 when N-1 is not worse than N
        self.worst_contingency_idx = np.full((nt, n_elm), -1, dtype=int)
        self.worst_contingency_flow = np.zeros((nt, n_elm), dtype=float)
        self.worst_contingency_loading = np.zeros((nt, n_elm), dtype=float)
        self.alpha_n1_worst = np.zeros((nt, n_elm), dtype=float)

        # branch, group, N-1 flow (MW), N-1 loading (p.u.), alpha N-1 of the groups tied with the worst
        self.worst_contingency_ties: List[Tuple[int, int, float, float, float]] = list()

    def get_values(self, Sbase: float, model: LpModel) -> "BranchNtcVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :param Sbase:
        :param model:
        :return: BranchVars
        """
        nt, n_elm = self.flows.shape
        data = BranchNtcVars(nt=nt, n_elm=n_elm)

        data.rates = self.rates
        data.contingency_rates = self.contingency_rates
        data.alpha = self.alpha
        data.inter_space_branches = self.inter_space_branches
        data.monitor_logic = self.monitor_logic
        data.worst_contingency_idx = self.worst_contingency_idx
        data.worst_contingency_flow = self.worst_contingency_flow
        data.worst_contingency_loading = self.worst_contingency_loading
        data.alpha_n1_worst = self.alpha_n1_worst
        data.worst_contingency_ties = self.worst_contingency_ties

        for t in range(nt):
            for i in range(n_elm):
                data.flows[t, i] = model.get_value(self.flows[t, i]) * Sbase
                data.flow_slacks_pos[t, i] = model.get_value(self.flow_slacks_pos[t, i]) * Sbase
                data.flow_slacks_neg[t, i] = model.get_value(self.flow_slacks_neg[t, i]) * Sbase
                data.tap_angles[t, i] = model.get_value(self.tap_angles[t, i])
                data.flow_constraints_ub[t, i] = model.get_value(self.flow_constraints_ub[t, i])
                data.flow_constraints_lb[t, i] = model.get_value(self.flow_constraints_lb[t, i])

        for i in range(len(self.contingency_flow_data)):
            t, m, c, var, neg_slack, pos_slack = self.contingency_flow_data[i]
            self.contingency_flow_data[i] = (t, m, c,
                                             model.get_value(var) * Sbase,
                                             model.get_value(neg_slack) * Sbase,
                                             model.get_value(pos_slack) * Sbase)

        # format the arrays appropriately
        data.flows = data.flows.astype(float, copy=False)
        data.flow_slacks_pos = data.flow_slacks_pos.astype(float, copy=False)
        data.flow_slacks_neg = data.flow_slacks_neg.astype(float, copy=False)
        data.tap_angles = data.tap_angles.astype(float, copy=False)
        data.contingency_flow_data = self.contingency_flow_data

        # compute loading
        data.loading = data.flows / (data.rates + 1e-20)

        return data

    def add_contingency_flow(self, t: int, m: int, c: int,
                             flow_var: Union[float, LpVar, LpExp],
                             neg_slack: LpVar,
                             pos_slack: LpVar):
        """
        Add contingency flow
        :param t: time index
        :param m: monitored index
        :param c: contingency group index
        :param flow_var: flow var
        :param neg_slack: negative flow slack variable
        :param pos_slack: positive flow slack variable
        """
        self.contingency_flow_data.append((t, m, c, flow_var, neg_slack, pos_slack))

    def get_total_flow_slack(self):
        """
        Get total flow slacks
        :return:
        """
        return self.flow_slacks_pos - self.flow_slacks_neg


class HvdcNtcVars:
    """
    Struct to store the generation vars
    """

    __slots__ = (
        "flows",
        "z",
        "y",
        "rates",
        "loading",
        "inter_space_hvdc",
    )

    def __init__(self, nt: int, n_elm: int):
        """
        GenerationVars structure
        :param nt: Number of time steps
        :param n_elm: Number of branches
        """
        self.flows = np.zeros((nt, n_elm), dtype=object)
        self.z = np.zeros((nt, n_elm), dtype=object)
        self.y = np.zeros((nt, n_elm), dtype=object)

        self.rates = np.zeros((nt, n_elm), dtype=float)
        self.loading = np.zeros((nt, n_elm), dtype=float)

        self.inter_space_hvdc: List[Tuple[int, float]] = list()  # index, sense

    def get_values(self, Sbase: float, model: LpModel) -> "HvdcNtcVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: HvdcVars
        """
        nt, n_elm = self.flows.shape
        data = HvdcNtcVars(nt=nt, n_elm=n_elm)
        data.rates = self.rates
        data.inter_space_hvdc = self.inter_space_hvdc

        for t in range(nt):
            for i in range(n_elm):
                data.flows[t, i] = model.get_value(self.flows[t, i]) * Sbase
                data.y[t, i] = model.get_value(self.y[t, i]) * Sbase
                data.z[t, i] = model.get_value(self.z[t, i])

        # format the arrays appropriately
        data.flows = data.flows.astype(float, copy=False)

        data.loading = data.flows / (data.rates + 1e-20)

        return data


class VscNtcVars:
    """
    Struct to store the VSC vars
    """

    __slots__ = (
        "flows",
        "z",
        "y",
        "rates",
        "loading",
        "inter_space_vsc",
    )

    def __init__(self, nt: int, n_elm: int):
        """
        VscNtcVars structure
        :param nt: Number of time steps
        :param n_elm: Number of VSC
        """
        self.flows = np.zeros((nt, n_elm), dtype=object)
        self.z = np.zeros((nt, n_elm), dtype=object)
        self.y = np.zeros((nt, n_elm), dtype=object)

        self.rates = np.zeros((nt, n_elm), dtype=float)
        self.loading = np.zeros((nt, n_elm), dtype=float)

        self.inter_space_vsc: List[Tuple[int, float]] = list()  # index, sense

    def get_values(self, Sbase: float, model: LpModel) -> "VscNtcVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: VscNtcVars
        """
        nt, n_elm = self.flows.shape
        data = VscNtcVars(nt=nt, n_elm=n_elm)
        data.rates = self.rates
        data.inter_space_vsc = self.inter_space_vsc

        for t in range(nt):
            for i in range(n_elm):
                data.flows[t, i] = model.get_value(self.flows[t, i]) * Sbase
                data.y[t, i] = model.get_value(self.y[t, i]) * Sbase
                data.z[t, i] = model.get_value(self.z[t, i])

        # format the arrays appropriately
        data.flows = data.flows.astype(float, copy=False)

        data.loading = data.flows / (data.rates + 1e-20)

        return data


class NtcVars:
    """
    Structure to host the opf variables
    """

    __slots__ = (
        "nt",
        "nbus",
        "ng",
        "nb",
        "nl",
        "nbr",
        "n_hvdc",
        "n_vsc",
        "model",
        "acceptable_solution",
        "bus_vars",
        "load_vars",
        "gen_vars",
        "batt_vars",
        "branch_vars",
        "hvdc_vars",
        "vsc_vars",
        "delta_1",
        "delta_2",
        "delta_sl_1",
        "delta_sl_2",
        "power_shift",
        "structural_ntc",
        "inter_area_flows",
    )

    def __init__(self, nt: int, nbus: int, ng: int, nb: int, nl: int, nbr: int, n_hvdc: int, n_vsc: int,
                 model: LpModel):
        """
        Constructor
        :param nt: number of time steps
        :param nbus: number of nodes
        :param ng: number of generators
        :param nb: number of batteries
        :param nl: number of loads
        :param nbr: number of branches
        :param n_hvdc: number of HVDC
        :param model: LpModel instance
        """
        self.nt = nt
        self.nbus = nbus
        self.ng = ng
        self.nb = nb
        self.nl = nl
        self.nbr = nbr
        self.n_hvdc = n_hvdc
        self.n_vsc = n_vsc
        self.model = model

        self.acceptable_solution = np.zeros(nt, dtype=bool)

        self.bus_vars = BusNtcVars(nt=nt, n_elm=nbus)

        self.load_vars = LoadVars(nt=nt, n_elm=nl)
        self.gen_vars = GenerationVars(nt=nt, n_elm=ng)
        self.batt_vars = BatteryVars(nt=nt, n_elm=nb)

        self.branch_vars = BranchNtcVars(nt=nt, n_elm=nbr)
        self.hvdc_vars = HvdcNtcVars(nt=nt, n_elm=n_hvdc)
        self.vsc_vars = VscNtcVars(nt=nt, n_elm=n_vsc)

        # power shift
        self.delta_1 = np.zeros(nt, dtype=object)  # array of power increment in area 1
        self.delta_2 = np.zeros(nt, dtype=object)  # array of power increment in area 2
        self.delta_sl_1 = np.zeros(nt, dtype=object)  # array of power increment slack at area 1
        self.delta_sl_2 = np.zeros(nt, dtype=object)  # array of power increment slack at area 2
        self.power_shift = np.zeros(nt, dtype=object)  # array of vars at the beginning

        # structural NTC
        self.structural_ntc = np.zeros(nt, dtype=float)

        self.inter_area_flows = np.zeros(nt, dtype=float)

    def get_values(self, Sbase: float, model: LpModel) -> "NtcVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :param Sbase
        :param model:
        :return: OpfVars instance
        """

        data = NtcVars(nt=self.nt,
                       nbus=self.nbus,
                       ng=self.ng,
                       nb=self.nb,
                       nl=self.nl,
                       nbr=self.nbr,
                       n_hvdc=self.n_hvdc,
                       n_vsc=self.n_vsc,
                       model=self.model)

        data.bus_vars = self.bus_vars.get_values(Sbase, model)
        data.branch_vars = self.branch_vars.get_values(Sbase, model)
        data.hvdc_vars = self.hvdc_vars.get_values(Sbase, model)
        data.vsc_vars = self.vsc_vars.get_values(Sbase, model)

        data.acceptable_solution = self.acceptable_solution
        data.structural_ntc = self.structural_ntc

        for t in range(self.nt):
            data.delta_1[t] = model.get_value(self.delta_1[t])
            data.delta_2[t] = model.get_value(self.delta_2[t])
            data.delta_sl_1[t] = model.get_value(self.delta_sl_1[t])
            data.delta_sl_2[t] = model.get_value(self.delta_sl_2[t])
            data.power_shift[t] = model.get_value(self.power_shift[t])
            # data.inter_area_flows[t] = model.get_value(self.inter_area_flows[t])  # is filled later

        # format the arrays appropriately
        # data.power_shift = data.power_shift.astype(float, copy=False)

        return data

    def get_voltages(self) -> CxMat:
        """

        :return:
        """
        return self.bus_vars.Vm * np.exp(1j * self.bus_vars.Va)

    def check_kirchhoff(self, tol: float = 1e-10):
        """

        :param tol:
        """
        nodal_power = self.bus_vars.Pbalance


def get_base_power(Sbase: float,
                   gen_data_t: GeneratorData,
                   batt_data_t: BatteryData,
                   load_data_t: LoadData,
                   branch_data_t: PassiveBranchData,
                   active_branch_data_t: ActiveBranchData,
                   hvdc_data_t: HvdcData,
                   logger: Logger) -> Vec:
    """
    Get the perfectly balanced base power
    :param Sbase:
    :param gen_data_t:
    :param batt_data_t:
    :param load_data_t:
    :param branch_data_t
    :param active_branch_data_t
    :param logger:
    :return:
    """
    # base power injections
    gen_per_bus = gen_data_t.get_injections_per_bus().real / Sbase
    batt_per_bus = batt_data_t.get_injections_per_bus().real / Sbase
    load_per_bus = load_data_t.get_injections_per_bus().real / Sbase  # this comes with the proper sign already

    # contributions from phase shifters
    # branch_bus_dp = np.zeros(branch_data_t.nbus)
    # for k in range(branch_data_t.nelm):
    #     if (active_branch_data_t.tap_phase_control_mode[k] == TapPhaseControl.fixed and
    #             active_branch_data_t.tap_angle[k] != 0.0):
    #         # this power will not be optimized and needs to be accounted for
    #         ps = active_branch_data_t.tap_angle[k] / (branch_data_t.X[k] + 1e-20)
    #         f = branch_data_t.F[k]
    #         t = branch_data_t.T[k]
    #         branch_bus_dp[f] += -ps
    #         branch_bus_dp[t] += ps

    base_power = gen_per_bus + batt_per_bus + load_per_bus  # + branch_bus_dp

    # Mandatory scaling so that we can do the deltas madness
    diff = base_power.sum()
    if diff != 0.0:
        gen_sum = gen_per_bus.sum()
        if gen_sum != 0:
            share = gen_per_bus / gen_sum
            gen_per_bus += - share * diff  # we make the generators balance the system
        else:
            raise ValueError("Cannot balance the circumstance")

        base_power = gen_per_bus + batt_per_bus + load_per_bus
        new_diff = np.sum(base_power)

        if np.isclose(new_diff, 0, atol=1e-10):
            # only report imbalances that matter (> 1 MW)
            if abs(diff) * Sbase > 1.0:
                logger.add_warning("The base circumstance had to be balanced",
                                   value=diff * Sbase, expected_value=0.0)
            else:
                pass
        else:
            raise ValueError("Cannot balance the circumstance")

    return base_power


def add_linear_injections_formulation(t: Union[int, None],
                                      Sbase: float,
                                      gen_data_t: GeneratorData,
                                      batt_data_t: BatteryData,
                                      load_data_t: LoadData,
                                      bus_data_t: BusData,
                                      branch_data_t: PassiveBranchData,
                                      active_branch_data_t: ActiveBranchData,
                                      hvdc_data_t: HvdcData,
                                      bus_a1_idx: IntVec,
                                      bus_a2_idx: IntVec,
                                      transfer_method: AvailableTransferMode,
                                      skip_generation_limits: bool,
                                      ntc_vars: NtcVars,
                                      prob: LpModel,
                                      logger: Logger):
    """
    Add MIP injections formulation
    :param t: time step
    :param Sbase: base power (100 MVA)
    :param gen_data_t: GeneratorData structure
    :param batt_data_t: BatteryData structure
    :param load_data_t: LoadData structure
    :param bus_data_t: BusData structure
    :param branch_data_t:
    :param active_branch_data_t:
    :param hvdc_data_t:
    :param bus_a1_idx: bus indices within area "from"
    :param bus_a2_idx: bus indices within area "to"
    :param transfer_method: Exchange transfer method
    :param skip_generation_limits: Skip generation limits?
    :param ntc_vars: MIP variables structure
    :param prob: MIP problem
    :param logger: logger instance
    :return objective function
    """

    # base power injections
    base_power = get_base_power(Sbase=Sbase,
                                gen_data_t=gen_data_t,
                                batt_data_t=batt_data_t,
                                load_data_t=load_data_t,
                                branch_data_t=branch_data_t,
                                active_branch_data_t=active_branch_data_t,
                                hvdc_data_t=hvdc_data_t,
                                logger=logger)

    # returns nodal reference power (p.u.), pmax (p.u.), pmin(p.u.)
    bus_pref_t, bus_pmax_t, bus_pmin_t = get_transfer_power_scaling_per_bus(
        bus_data_t=bus_data_t,
        gen_data_t=gen_data_t,
        load_data_t=load_data_t,
        transfer_method=transfer_method,
        skip_generation_limits=skip_generation_limits,
        inf_value=prob.INFINITY,
        Sbase=Sbase
    )

    # compute each area's share with sign (rounded)
    proportions = get_exchange_proportions(
        power=bus_pref_t,
        bus_a1_idx=bus_a1_idx,
        bus_a2_idx=bus_a2_idx,
        logger=logger,
        decimals=6
    )

    # copy the computed proportions
    ntc_vars.bus_vars.proportions[t, :] = proportions

    f_obj = 0.0
    ntc_vars.delta_1[t] = prob.add_var(lb=0, ub=prob.INFINITY, name=join("Delta_up_", [t]))
    ntc_vars.delta_2[t] = prob.add_var(lb=0, ub=prob.INFINITY, name=join("Delta_down_", [t]))

    ntc_vars.delta_sl_1[t] = prob.add_var(lb=0, ub=prob.INFINITY, name=join("DeltaSL_up_", [t]))
    ntc_vars.delta_sl_2[t] = prob.add_var(lb=0, ub=prob.INFINITY, name=join("DeltaSL_down_", [t]))

    for k in bus_a1_idx:
        if bus_data_t.active[k] and proportions[k] != 0:
            ntc_vars.bus_vars.delta_p[t, k] = ntc_vars.delta_1[t] * proportions[k]

            if not skip_generation_limits:
                prob.add_cst(
                    cst=base_power[k] + ntc_vars.bus_vars.delta_p[t, k] <= bus_pmax_t[k],
                    name=join(f'delta_p_up', [t, k], "_")
                )

    for k in bus_a2_idx:
        if bus_data_t.active[k] and proportions[k] != 0:
            # the proportion already has the sign
            ntc_vars.bus_vars.delta_p[t, k] = ntc_vars.delta_2[t] * proportions[k]

            if not skip_generation_limits:
                prob.add_cst(
                    cst=base_power[k] - ntc_vars.bus_vars.delta_p[t, k] >= bus_pmin_t[k],
                    name=join(f'delta_p_dwn', [t, k], "_")
                )

    # the increase in area 1 must be equal to the decrease in area 2, since
    # we have declared the deltas positive for the sending and receiving areas
    prob.add_cst(
        cst=ntc_vars.delta_1[t] - ntc_vars.delta_sl_1[t] == ntc_vars.delta_2[t] - ntc_vars.delta_sl_2[t],
        name=join(f'deltas_equality_', [t], "_")
    )

    # now, formulate the final injections for all buses
    for k in range(bus_data_t.nbus):
        # we compute the injection power: P = Pset + (proportion · ΔP)
        ntc_vars.bus_vars.Pinj[t, k] += base_power[k] + ntc_vars.bus_vars.delta_p[t, k]
        ntc_vars.bus_vars.Pbalance[t, k] += ntc_vars.bus_vars.Pinj[t, k]

    # minimize the power at area 2 (receiving area), maximize at area 1 (sending area)
    # minimize the slacks
    # f_obj += ntc_vars.delta_2[t] - ntc_vars.delta_1[t] + ntc_vars.delta_sl_1[t] + ntc_vars.delta_sl_2[t]
    f_obj += - ntc_vars.delta_1[t]

    return f_obj, base_power


# def add_linear_injections_formulation_proper(t: Union[int, None],
#                                              Sbase: float,
#                                              gen_data_t: GeneratorData,
#                                              batt_data_t: BatteryData,
#                                              load_data_t: LoadData,
#                                              bus_data_t: BusData,
#                                              branch_data_t: PassiveBranchData,
#                                              active_branch_data_t: ActiveBranchData,
#                                              hvdc_data_t: HvdcData,
#                                              bus_a1_idx: IntVec,
#                                              bus_a2_idx: IntVec,
#                                              transfer_method: AvailableTransferMode,
#                                              skip_generation_limits: bool,
#                                              ntc_vars: NtcVars,
#                                              prob: LpModel,
#                                              logger: Logger):
#     """
#     Add MIP injections formulation
#     :param t: time step
#     :param Sbase: base power (100 MVA)
#     :param gen_data_t: GeneratorData structure
#     :param batt_data_t: BatteryData structure
#     :param load_data_t: LoadData structure
#     :param bus_data_t: BusData structure
#     :param branch_data_t:
#     :param active_branch_data_t:
#     :param hvdc_data_t:
#     :param bus_a1_idx: bus indices within area "from"
#     :param bus_a2_idx: bus indices within area "to"
#     :param transfer_method: Exchange transfer method
#     :param skip_generation_limits: Skip generation limits?
#     :param ntc_vars: MIP variables structure
#     :param prob: MIP problem
#     :param logger: logger instance
#     :return objective function
#     """
#
#     gen_per_bus = gen_data_t.get_injections_per_bus().real / Sbase
#     batt_per_bus = batt_data_t.get_injections_per_bus().real / Sbase
#     load_per_bus = load_data_t.get_injections_per_bus().real / Sbase  # this comes with the proper sign already
#     base_power = gen_per_bus + batt_per_bus + load_per_bus
#
#     f_obj = 0
#
#     # get the area of every generator
#     gen_idx_1 = np.where(np.isin(gen_data_t.bus_idx, bus_a1_idx))[0]
#     gen_idx_2 = np.where(np.isin(gen_data_t.bus_idx, bus_a2_idx))[0]
#
#     batt_idx_1 = np.where(np.isin(batt_data_t.bus_idx, bus_a1_idx))[0]
#     batt_idx_2 = np.where(np.isin(batt_data_t.bus_idx, bus_a2_idx))[0]
#
#     load_idx_1 = np.where(np.isin(load_data_t.bus_idx, bus_a1_idx))[0]
#     load_idx_2 = np.where(np.isin(load_data_t.bus_idx, bus_a2_idx))[0]
#
#     ntc_vars.gen_vars.p[t, :] = gen_data_t.p / Sbase
#     ntc_vars.batt_vars.p[t, :] = batt_data_t.p / Sbase
#     ntc_vars.load_vars.p[t, :] = load_data_t.S.real / Sbase
#
#     for k in gen_idx_1:
#         if gen_data_t.p[k] < gen_data_t.pmax[k] and gen_data_t.active[k]:
#
#             if skip_generation_limits:
#                 margin_up = 9999.0
#             else:
#                 margin_up = (gen_data_t.pmax[k] - gen_data_t.p[k]) / Sbase
#
#             ntc_vars.gen_vars.p_inc[t, k] = prob.add_var(lb=0, ub=margin_up, name=join("gen_p_inc_", [t, k]))
#             ntc_vars.gen_vars.p[t, k] = gen_data_t.p[k] / Sbase + ntc_vars.gen_vars.p_inc[t, k]
#             ntc_vars.delta_1[t] += ntc_vars.gen_vars.p_inc[t, k]
#
#             i = gen_data_t.bus_idx[k]
#             ntc_vars.bus_vars.delta_p[t, i] += ntc_vars.gen_vars.p_inc[t, k]
#
#             f_obj += - ntc_vars.gen_vars.p_inc[t, k] * gen_data_t.shift_key[k]
#         else:
#             # the generator is maxed out
#             pass
#
#     for k in batt_idx_1:
#         if batt_data_t.p[k] < batt_data_t.pmax[k]:
#             if skip_generation_limits:
#                 margin_up = 9999.0
#             else:
#                 margin_up = (batt_data_t.pmax[k] - batt_data_t.p[k]) / Sbase
#
#             ntc_vars.batt_vars.p_inc[t, k] = prob.add_var(lb=0, ub=margin_up, name=join("batt_p_inc_", [t, k]))
#             ntc_vars.batt_vars.p[t, k] += ntc_vars.batt_vars.p_inc[t, k]
#             ntc_vars.delta_1[t] += ntc_vars.batt_vars.p_inc[t, k]
#
#             i = batt_data_t.bus_idx[k]
#             ntc_vars.bus_vars.delta_p[t, i] += ntc_vars.batt_vars.p_inc[t, k]
#
#             f_obj += - ntc_vars.batt_vars.p_inc[t, k] * batt_data_t.shift_key[k]
#         else:
#             # the battery is maxed out
#             pass
#
#     for k in gen_idx_2:
#         if gen_data_t.p[k] > gen_data_t.pmin[k] and gen_data_t.active[k]:
#
#             if skip_generation_limits:
#                 margin_dwn = gen_data_t.p[k] / Sbase
#             else:
#                 margin_dwn = (gen_data_t.p[k] - gen_data_t.pmin[k]) / Sbase
#             ntc_vars.gen_vars.p_inc[t, k] = prob.add_var(lb=0, ub=margin_dwn, name=join("gen_n_inc_", [t, k]))
#             ntc_vars.gen_vars.p[t, k] = (gen_data_t.p[k] / Sbase) - ntc_vars.gen_vars.p_inc[t, k]
#             ntc_vars.delta_2[t] += ntc_vars.gen_vars.p_inc[t, k]
#
#             i = gen_data_t.bus_idx[k]
#             ntc_vars.bus_vars.delta_p[t, i] += - ntc_vars.gen_vars.p_inc[t, k]
#
#             f_obj += - ntc_vars.gen_vars.p_inc[t, k] * gen_data_t.shift_key[k]
#         else:
#             # the generator cannot go lower
#             pass
#
#     for k in batt_idx_2:
#         if batt_data_t.p[k] > batt_data_t.pmin[k]:
#             if skip_generation_limits:
#                 margin_dwn = batt_data_t.p[k] / Sbase
#             else:
#                 margin_dwn = (batt_data_t.p[k] - batt_data_t.pmin[k]) / Sbase
#             ntc_vars.batt_vars.p_inc[t, k] = prob.add_var(lb=0, ub=margin_dwn, name=join("batt_n_inc_", [t, k]))
#             ntc_vars.batt_vars.p[t, k] += - ntc_vars.batt_vars.p_inc[t, k]
#             ntc_vars.delta_2[t] += ntc_vars.batt_vars.p_inc[t, k]
#
#             i = batt_data_t.bus_idx[k]
#             ntc_vars.bus_vars.delta_p[t, i] += - ntc_vars.batt_vars.p_inc[t, k]
#
#             f_obj += -ntc_vars.batt_vars.p_inc[t, k] * batt_data_t.shift_key[k]
#         else:
#             # the battery cannot go lower
#             pass
#
#     # formulate the nodal summations
#     for k in range(gen_data_t.nelm):
#         i = gen_data_t.bus_idx[k]
#         ntc_vars.bus_vars.Pinj[t, i] += ntc_vars.gen_vars.p[t, k]
#         ntc_vars.bus_vars.Pbalance[t, i] += ntc_vars.gen_vars.p[t, k]
#
#     for k in range(batt_data_t.nelm):
#         i = batt_data_t.bus_idx[k]
#         ntc_vars.bus_vars.Pinj[t, i] += ntc_vars.batt_vars.p[t, k]
#         ntc_vars.bus_vars.Pbalance[t, i] += ntc_vars.batt_vars.p[t, k]
#
#     for k in range(load_data_t.nelm):
#         i = load_data_t.bus_idx[k]
#         ntc_vars.bus_vars.Pinj[t, i] += -ntc_vars.load_vars.p[t, k]
#         ntc_vars.bus_vars.Pbalance[t, i] += -ntc_vars.load_vars.p[t, k]
#
#     # add the area equality constraint
#     ntc_vars.delta_sl_1[t] = prob.add_var(lb=0, ub=prob.INFINITY, name=join("DeltaSL_up_", [t]))
#     ntc_vars.delta_sl_2[t] = prob.add_var(lb=0, ub=prob.INFINITY, name=join("DeltaSL_down_", [t]))
#     prob.add_cst(
#         cst=ntc_vars.delta_1[t] - ntc_vars.delta_sl_1[t] == ntc_vars.delta_2[t] - ntc_vars.delta_sl_2[t],
#         name=join(f'deltas_equality_', [t], "_")
#     )
#
#     # minimize the power at area 2 (receiving area), maximize at area 1 (sending area)
#     # minimize the slacks
#     # f_obj += ntc_vars.delta_2[t] - ntc_vars.delta_1[t] + ntc_vars.delta_sl_1[t] + ntc_vars.delta_sl_2[t]
#     f_obj += ntc_vars.delta_sl_1[t] + ntc_vars.delta_sl_2[t]
#
#     return f_obj, base_power


def add_linear_branches_formulation(t_idx: int,
                                    Sbase: float,
                                    branch_data_t: PassiveBranchData,
                                    active_branch_data_t: ActiveBranchData,
                                    branch_vars: BranchNtcVars,
                                    bus_vars: BusNtcVars,
                                    prob: LpModel,
                                    monitor_only_sensitive_branches: bool,
                                    monitor_only_ntc_load_rule_branches: bool,
                                    alpha: Vec,
                                    alpha_threshold: float,
                                    structural_ntc: float,
                                    ntc_load_rule: float,
                                    loading: Vec,
                                    logger: Logger,
                                    inf=1e20,
                                    slack_all_limits: bool = False) -> LpExp:
    """
    Formulate the branches
    :param t_idx: time index
    :param Sbase: base power (100 MVA)
    :param branch_data_t: BranchData
    :param branch_vars: BranchVars
    :param active_branch_data_t:
    :param bus_vars: BusVars
    :param prob: OR problem
    :param monitor_only_ntc_load_rule_branches:
    :param monitor_only_sensitive_branches:
    :param alpha: Array of branch sensitivity to the exchange
    :param alpha_threshold: Threshold for sensitivity consideration
    :param structural_ntc
    :param ntc_load_rule
    :param loading
    :param logger
    :param inf: number considered infinite
    :param slack_all_limits: give EVERY monitored branch the penalized slack pair instead
                             of a hard bound. Used as a feasibility retry.
    :return objective function
    """
    f_obj = 0.0

    # for each branch
    for m in range(branch_data_t.nelm):
        fr = branch_data_t.F[m]
        to = branch_data_t.T[m]

        # copy rates
        branch_vars.rates[t_idx, m] = branch_data_t.rates[m]

        if branch_data_t.active[m]:

            # compute rate in per unit
            rate_pu = branch_data_t.rates[m] / Sbase

            if branch_data_t.dc[m]:

                # declare the flow LPVar
                branch_vars.flows[t_idx, m] = prob.add_var(
                    lb=-inf,
                    ub=inf,
                    name=join("dc_flow_", [t_idx, m], "_")
                )

                # DC Branch: R x P = ΔV. Dividing by R instead puts 1/R in the matrix, and HiGHS
                # rejects entries above 1e15 (this fixes an ideal cable as it has an R of 1e-20) 
                prob.add_cst(
                    cst=branch_data_t.R[m] * branch_vars.flows[t_idx, m] == bus_vars.Vm[t_idx, fr] - bus_vars.Vm[t_idx, to],
                    name=join("dc_flows_", [t_idx, m], "_")
                )

            else:
                # AC branch
                # declare the flow LPVar
                branch_vars.flows[t_idx, m] = prob.add_var(
                    lb=-inf,
                    ub=inf,
                    name=join("ac_flow_", [t_idx, m], "_")
                )

                # compute the branch susceptance as the linear model (PTDF, linear power flow) does,
                # with the tap module, so the NTC flows equal those of a linear power flow
                x_eff: float = branch_data_t.X[m] * active_branch_data_t.tap_module[m]
                if x_eff == 0.0:
                    bk: float = 1e-6  # setting a value too low will "break" the linear solver
                else:
                    bk = 1.0 / x_eff

                # compute the flow
                if (active_branch_data_t.tap_phase_control_mode[m] == TapPhaseControl.Pf.idx() or
                        active_branch_data_t.tap_phase_control_mode[m] == TapPhaseControl.Pt.idx()):

                    # add angle
                    branch_vars.tap_angles[t_idx, m] = prob.add_var(
                        lb=active_branch_data_t.tap_angle_min[m],
                        ub=active_branch_data_t.tap_angle_max[m],
                        name=join("tap_ang_", [t_idx, m], "_")
                    )

                    # is a phase shifter device (like phase shifter transformer or VSC with P control)
                    prob.add_cst(
                        cst=branch_vars.flows[t_idx, m] == bk * (bus_vars.Va[t_idx, fr] -
                                                                 bus_vars.Va[t_idx, to] -
                                                                 branch_vars.tap_angles[t_idx, m]),
                        name=join("ac_flows_ps_", [t_idx, m], "_")
                    )

                else:

                    if active_branch_data_t.tap_angle[m] != 0.0:
                        branch_vars.tap_angles[t_idx, m] = active_branch_data_t.tap_angle[m]

                        # rest of the branches
                        prob.add_cst(
                            cst=branch_vars.flows[t_idx, m] == bk * (bus_vars.Va[t_idx, fr] -
                                                                     bus_vars.Va[t_idx, to] -
                                                                     branch_vars.tap_angles[t_idx, m]),
                            name=join("ac_flow_ps_fix", [t_idx, m], "_")
                        )
                    else:
                        # rest of the branches with tau = 0
                        prob.add_cst(
                            cst=branch_vars.flows[t_idx, m] == bk * (bus_vars.Va[t_idx, fr] - bus_vars.Va[t_idx, to]),
                            name=join("ac_flows_", [t_idx, m], "_")
                        )

            # We save in Pcalc the balance of the branch flows
            bus_vars.Pbalance[t_idx, fr] = bus_vars.Pbalance[t_idx, fr] - branch_vars.flows[t_idx, m]
            bus_vars.Pbalance[t_idx, to] = bus_vars.Pbalance[t_idx, to] + branch_vars.flows[t_idx, m]

            # Monitoring logic: Avoid unrealistic ntc flows over CEP rule limit in N condition
            if monitor_only_ntc_load_rule_branches:
                """
                Calculo el porcentaje del ratio de la línea que se reserva al intercambio según la regla de ACER, 
                y paso dicho valor a la frontera, y si el valor es mayor que el máximo intercambio estructural 
                significa que la linea no puede limitar el intercambio
                Ejemplo:
                    ntc_load_rule = 0.7
                    rate = 1700
                    alpha = 0.05
                    structural_rate = 5200
                    0.7 * 1700 --> 1190 mw para el intercambio
                    1190 / 0.05 --> 23.800 MW en la frontera en N
                    23.800 >>>> 5200 --> esta linea no puede ser declarada como limitante en la NTC en N.
                   """
                monitor_by_load_rule_n = ntc_load_rule * branch_data_t.rates[m] / (alpha[m] + 1e-20) <= structural_ntc
            else:
                monitor_by_load_rule_n = True

            # Monitoring logic: Exclude branches with not enough sensibility to exchange in N condition
            if monitor_only_sensitive_branches:
                monitor_by_sensitivity_n = abs(alpha[m]) > alpha_threshold
            else:
                monitor_by_sensitivity_n = True

            # DC branches are always monitored when the user enabled their monitoring: their
            # AC-PTDF sensitivity (alpha) is structurally 0, so the sensitivity
            # filters would drop these elements and let them overload freely
            branch_vars.monitor_logic[t_idx, m] = int(branch_data_t.monitor_loading[m]
                                                      and (branch_data_t.dc[m]
                                                           or (monitor_by_sensitivity_n
                                                               and monitor_by_load_rule_n)))

            # add the rate constraint if the branch is monitored
            if branch_vars.monitor_logic[t_idx, m]:

                if abs(loading[m]) > 1.0 or slack_all_limits:
                    # Allow penalized relaxation while controls seek to resolve the overload.
                    # Report actual slack after solving; an initial overload is not a result.
                    pos_sl: LpVar = prob.add_var(0, 1e20, join("base_flow_pos_sl_", [t_idx, m], "_"))
                    neg_sl: LpVar = prob.add_var(0, 1e20, join("base_flow_neg_sl_", [t_idx, m], "_"))
                    branch_vars.flow_slacks_pos[t_idx, m] = pos_sl
                    branch_vars.flow_slacks_neg[t_idx, m] = neg_sl
                    prob.add_cst(cst=branch_vars.flows[t_idx, m] - pos_sl <= rate_pu,
                                 name=join("base_flow_upper_lim_", [t_idx, m], "_"))
                    prob.add_cst(cst=branch_vars.flows[t_idx, m] + neg_sl >= -rate_pu,
                                 name=join("base_flow_lower_lim_", [t_idx, m], "_"))

                    f_obj += 1e4 * (pos_sl + neg_sl)
                else:
                    # here flows is always a variable
                    prob.set_var_bounds(branch_vars.flows[t_idx, m], lb=-rate_pu, ub=rate_pu)

    # add the inter-area flows to the objective function with the correct sign
    # for k, sense in branch_vars.inter_space_branches:
    # f_obj += -branch_vars.flows[t_idx, k] * sense

    f_obj += 0.0

    return f_obj


def add_corrective_converter_deltas(prob: LpModel,
                                    t_idx: int,
                                    c: int,
                                    Sbase: float,
                                    compensated_df: Union[csc_matrix, None],
                                    base_flows: ObjVec,
                                    rates_mw: Vec,
                                    outaged_indices: IntVec,
                                    active_mask: Union[BoolVec, None],
                                    name_tag: str,
                                    row_filter: BoolVec,
                                    delta_vars: Dict[int, LpVar],
                                    branch_terms: Dict[int, LpExp]) -> None:
    """
    Declare the per-contingency corrective set-point change variables for one converter family (VSC or HVDC)
    and accumulate their linear effect on the branch flows that they influence.

    :param prob: linear problem the variables and constraints are added to
    :param t_idx: time index being formulated
    :param c: contingency (group) index, used only to build unique variable/constraint names.
    :param Sbase:
    :param compensated_df: post-contingency distribution-factor matrix (all_branches, n_converter)
    :param base_flows: base-case converter flows in per unit
    :param rates_mw: converter ratings in MW
    :param outaged_indices: indices of the converters that are part of the contingency
    :param active_mask: in-service flag per converter
    :param name_tag: "vsc" / "hvdc" used to name the variables and constraints
    :param row_filter: per-branch flag, True for monitorable branches plus the inter-area ones
    :param delta_vars: lookup converter-index -> Δ variable
    :param branch_terms: lookup branch-index -> accumulated corrective LP expression
    :return: nothing
    """
    # decide whether this converter family contributes anything at all for this contingency
    if compensated_df is None:
        has_data: bool = False
    else:
        has_data = (compensated_df.shape[1] > 0) and (compensated_df.nnz > 0)

    if has_data:
        # converters that are themselves tripped by this contingency: their loss is already inside the
        # preventive contingency_flows, so they must not also be used as a corrective lever
        outaged: set[int] = set(int(x) for x in outaged_indices)

        # Walk the factors column by column (one column per converter)
        n_converters: int = int(compensated_df.shape[1])
        indptr: IntVec = compensated_df.indptr
        indices: IntVec = compensated_df.indices
        data: Vec = compensated_df.data

        for d in range(n_converters):

            start: int = int(indptr[d])
            end: int = int(indptr[d + 1])

            # a converter can act correctively only if it is in service and is not the tripped element
            is_tripped: bool = d in outaged
            if active_mask is None:
                is_out_of_service: bool = False
            else:
                is_out_of_service = not bool(active_mask[d])

            if is_tripped or is_out_of_service or end == start:
                # this converter cannot move, or influences nothing, so it contributes nothing
                pass
            else:
                # declare the corrective set-point change variable the first time we meet converter d.
                if d in delta_vars:
                    delta: LpVar = delta_vars[d]
                else:
                    rate_pu: float = rates_mw[d] / Sbase
                    delta = prob.add_var(-1e20, 1e20, join("corr_" + name_tag + "_d_", [t_idx, d, c], "_"))
                    delta_vars[d] = delta
                    # the set-point may move, but the contingency flow stays within the rating
                    prob.add_cst(cst=base_flows[d] + delta <= rate_pu,
                                 name=join("corr_" + name_tag + "_up_", [t_idx, d, c], "_"))
                    prob.add_cst(cst=base_flows[d] + delta >= -rate_pu,
                                 name=join("corr_" + name_tag + "_lo_", [t_idx, d, c], "_"))

                # Drop the branches we can get rid of
                col_rows: IntVec = indices[start:end]
                keep: BoolVec = row_filter[col_rows]
                kept_rows: IntVec = col_rows[keep]
                kept_vals: Vec = data[start:end][keep]

                for kk in range(len(kept_rows)):
                    m: int = int(kept_rows[kk])

                    # accumulate cDF[m, d] * Δ_d, i.e. the flow change on branch m caused by this move
                    contribution: LpExp = float(kept_vals[kk]) * delta
                    if m in branch_terms:
                        branch_terms[m] += contribution
                    else:
                        branch_terms[m] = contribution
    else:
        # this converter family does not participate in this contingency
        pass


def add_corrective_contingency_formulation(t_idx: int,
                                           c: int,
                                           Sbase: float,
                                           contingency: LinearMultiContingency,
                                           contingency_flows: ObjVec,
                                           changed_idx: IntVec,
                                           branch_data_t: PassiveBranchData,
                                           branch_vars: BranchNtcVars,
                                           vsc_vars: VscNtcVars,
                                           hvdc_vars: HvdcNtcVars,
                                           prob: LpModel,
                                           corrective_rows: BoolVec,
                                           vsc_active: Union[BoolVec, None] = None,
                                           hvdc_active: Union[BoolVec, None] = None,
                                           vsc_delta_vars: Union[Dict[int, LpVar], None] = None,
                                           hvdc_delta_vars: Union[Dict[int, LpVar], None] = None,
                                           add_exchange_preservation: bool = True,
                                           enforce_rows: Union[BoolVec, None] = None) -> Union[float, LpExp]:
    """
    Formulate a single contingency allowing corrective re-dispatch of the VSC and HVDC converters
    Rationale: VSCs and HVDCs can change their powers quickly after the contingency

    For each non-outaged converter ``d`` we introduce a per-contingency
    set-point change ``Δ_d`` and write the post-contingency monitored flow as:

        f_c[m] = f0[m] + MLODF[m, βδ]·f0[βδ] + Σ_d cDF[m, d]·Δ_d

    where ``cDF`` is the post-contingency converter distribution factor.
    The post-contingency converter flow ``flow0_d + Δ_d`` is
    bounded by the converter rate. 
    ``Δ_d`` carries no objective cost, so it is a pure feasibility (corrective) lever.

    :param t_idx: time index being formulated
    :param c: contingency (group) index, used to build unique variable/constraint names
    :param Sbase:
    :param contingency: the linear multi-contingency providing the outaged indices and the compensated factors
    :param contingency_flows: per-branch preventive post-contingency flow expressions
    :param changed_idx: indices of the branches whose flow changes under the outage itself
    :param branch_data_t: passive branch data
    :param branch_vars: branch LP variable container
    :param vsc_vars: VSC LP variable container
    :param hvdc_vars: HVDC LP variable container
    :param prob: linear problem the variables and constraints are added to
    :param corrective_rows: per-branch flag, True for the branches whose corrective term is read back
    :param vsc_active: in-service flag per VSC, or None to treat every VSC as in service
    :param hvdc_active: in-service flag per HVDC, or None to treat every HVDC as in service
    :param vsc_delta_vars: persistent per-VSC Δ variable store for this contingency, or None
                           for a fresh one
    :param hvdc_delta_vars: persistent per-HVDC Δ variable store, same rationale
    :param add_exchange_preservation: add the exchange-preservation equality
    :param enforce_rows: per-branch flag restricting which rows get their limit constraint
    """
    f_obj: Union[float, LpExp] = 0.0

    branch_terms: Dict[int, LpExp] = dict()
    if vsc_delta_vars is None:
        vsc_delta_vars = dict()
    else:
        pass  # reuse the caller's persistent store
    if hvdc_delta_vars is None:
        hvdc_delta_vars = dict()
    else:
        pass  # reuse the caller's persistent store

    # VSC converters are dispatchable, so they may re-dispatch their set-point after the outage
    add_corrective_converter_deltas(prob=prob, t_idx=t_idx, c=c, Sbase=Sbase,
                                    compensated_df=contingency.compensated_vsc_df,
                                    base_flows=vsc_vars.flows[t_idx, :], rates_mw=vsc_vars.rates[t_idx, :],
                                    outaged_indices=contingency.vsc_indices, active_mask=vsc_active,
                                    name_tag="vsc", row_filter=corrective_rows,
                                    delta_vars=vsc_delta_vars, branch_terms=branch_terms)

    # HVDC links are equally dispatchable and are treated exactly the same way
    add_corrective_converter_deltas(prob=prob, t_idx=t_idx, c=c, Sbase=Sbase,
                                    compensated_df=contingency.compensated_hvdc_df,
                                    base_flows=hvdc_vars.flows[t_idx, :], rates_mw=hvdc_vars.rates[t_idx, :],
                                    outaged_indices=contingency.hvdc_indices, active_mask=hvdc_active,
                                    name_tag="hvdc", row_filter=corrective_rows,
                                    delta_vars=hvdc_delta_vars, branch_terms=branch_terms)

    # Exchange preservation: the corrective re-dispatch must reroute the 
    # transfer across the boundary, not change its total
    boundary_terms: list[LpExp] = list()

    # inter-area branches: their corrective change is the branch term accumulated above
    for branch_m, branch_sense in branch_vars.inter_space_branches:
        if branch_m in branch_terms:
            boundary_terms.append(branch_sense * branch_terms[branch_m])
        else:
            # this boundary branch is not influenced by any corrective converter move
            pass

    # inter-area VSC converters: their own set-point change crosses the boundary directly
    for vsc_k, vsc_sense in vsc_vars.inter_space_vsc:
        if vsc_k in vsc_delta_vars:
            boundary_terms.append(vsc_sense * vsc_delta_vars[vsc_k])
        else:
            # this boundary VSC has no corrective variable (out of service or unaffected)
            pass

    # inter-area HVDC links: same treatment as the inter-area VSC converters
    for hvdc_k, hvdc_sense in hvdc_vars.inter_space_hvdc:
        if hvdc_k in hvdc_delta_vars:
            boundary_terms.append(hvdc_sense * hvdc_delta_vars[hvdc_k])
        else:
            # this boundary HVDC has no corrective variable (out of service or unaffected)
            pass

    if len(boundary_terms) > 0 and add_exchange_preservation:
        # fold the terms into one expression starting from the first term so the type stays LpExp throughout
        boundary_expr: LpExp = boundary_terms[0]
        fold_idx: int = 1
        while fold_idx < len(boundary_terms):
            boundary_expr = boundary_expr + boundary_terms[fold_idx]
            fold_idx += 1
        prob.add_cst(cst=boundary_expr == 0.0, name=join("corr_exchange_preserve_", [t_idx, c], "_"))
    else:
        pass

    # Enforce the post-contingency limits
    candidate_rows: set = set(int(b) for b in changed_idx) | set(branch_terms.keys())
    if enforce_rows is None:
        branches_to_check: list[int] = sorted(candidate_rows)
    else:
        # only the admitted rows get their limit built in this call
        branches_to_check = sorted(m for m in candidate_rows if enforce_rows[m])

    for m in branches_to_check:

        # a branch is enforced if it is a DC branch (always monitored) or it is flagged for monitoring
        is_monitored: bool = bool(branch_data_t.dc[m]) or bool(branch_vars.monitor_logic[t_idx, m])

        if not is_monitored:
            # not monitored under this contingency: no limit is enforced on this branch
            pass
        else:
            # post-contingency flow = preventive redistribution + corrective converter contribution (if any)
            flow_expr: Union[float, LpExp] = contingency_flows[m]
            if m in branch_terms:
                flow_expr = flow_expr + branch_terms[m]
            else:
                # this branch is unaffected by any corrective move; only the preventive flow applies
                pass

            if isinstance(flow_expr, LpExp):
                # Initial overloads still need a limit so slack accounts for any remaining excess.
                rate_pu: float = branch_data_t.contingency_rates[m] / Sbase
                pos_slack: LpVar = prob.add_var(0, 1e20, join("br_cst_flow_pos_sl_", [t_idx, m, c], "_"))
                neg_slack: LpVar = prob.add_var(0, 1e20, join("br_cst_flow_neg_sl_", [t_idx, m, c], "_"))

                # record the flow so the result extraction can evaluate the post-contingency loading later
                branch_vars.add_contingency_flow(t=t_idx, m=m, c=c, flow_var=flow_expr,
                                                 neg_slack=neg_slack, pos_slack=pos_slack)

                prob.add_cst(cst=flow_expr - pos_slack <= rate_pu,
                             name=join("br_cst_flow_upper_lim_", [t_idx, m, c], "_"))
                prob.add_cst(cst=flow_expr + neg_slack >= -rate_pu,
                             name=join("br_cst_flow_lower_lim_", [t_idx, m, c], "_"))

                # 1e4 per p.u. of slack penalty, arbitrary
                f_obj += 1e4 * (pos_slack + neg_slack)
            else:
                # the flow is a pure constant (no decision variables): there is nothing to constrain
                pass

    return f_obj


def add_preventive_contingency_formulation(t_idx: int,
                                           c: int,
                                           Sbase: float,
                                           contingency: LinearMultiContingency,
                                           contingency_flows: ObjVec,
                                           changed_idx: IntVec,
                                           branch_data_t: PassiveBranchData,
                                           branch_vars: BranchNtcVars,
                                           monitor_only_ntc_load_rule_branches: bool,
                                           monitor_only_sensitive_branches: bool,
                                           structural_ntc: float,
                                           ntc_load_rule: float,
                                           alpha_threshold: float,
                                           alpha_n1: Mat,
                                           prob: LpModel) -> Union[float, LpExp]:
    """
    Formulate a single contingency with the preventive N-1 rule 
    :param t_idx: time index being formulated
    :param c: contingency (group) index, used to build unique variable/constraint names
    :param Sbase:
    :param contingency: the linear multi-contingency providing the outaged-branch indices
    :param contingency_flows: per-branch post-contingency flow expressions
    :param changed_idx: indices of the branches whose flow changes under this contingency
    :param branch_data_t: passive branch data 
    :param branch_vars: branch LP variable container
    :param monitor_only_ntc_load_rule_branches: only monitor branches that pass the ACER
    :param monitor_only_sensitive_branches: only monitor branches sensitive enough to the exchange
    :param structural_ntc: structural NTC used by the ACER
    :param ntc_load_rule: fraction of the rating reserved to the exchange (ACER rule)
    :param alpha_threshold: minimum N-1 exchange sensitivity for a branch to be monitored
    :param alpha_n1: N-1 exchange-sensitivity matrix indexed as (branch, outaged-branch)
    :param prob: linear problem the variables and constraints are added to
    :return: objective contribution (sum of the contingency overload slacks)
    """
    f_obj: Union[float, LpExp] = 0.0

    # iterate the branches whose flow changes under this contingency 
    for occ, m in enumerate(changed_idx):

        if isinstance(contingency_flows[m], LpExp):

            # Monitoring logic: avoid unrealistic NTC flows over the CEP-rule limit in the N-1 condition
            if monitor_only_ntc_load_rule_branches:
                monitor_by_load_rule_n1: bool = True
                for c_br in contingency.branch_indices:
                    monitor_by_load_rule_n1 = (monitor_by_load_rule_n1 and
                                               (ntc_load_rule * branch_data_t.rates[m] / (
                                                       abs(alpha_n1[m, c_br]) + 1e-20) <= structural_ntc))
            else:
                # the load-rule filter is disabled: keep the branch as a candidate
                monitor_by_load_rule_n1 = True

            # Monitoring logic: exclude branches that are not sensitive enough
            if monitor_only_sensitive_branches:
                monitor_by_sensitivity_n1: bool = True
                for c_br in contingency.branch_indices:
                    monitor_by_sensitivity_n1 = (monitor_by_sensitivity_n1 and
                                                 (abs(alpha_n1[m, c_br]) > alpha_threshold))
            else:
                # the sensitivity filter is disabled: keep the branch as a candidate
                monitor_by_sensitivity_n1 = True

            # DC branches are always monitored because their AC-PTDF sensitivity is structurally zero
            if branch_data_t.dc[m] or (monitor_by_load_rule_n1 and monitor_by_sensitivity_n1):

                # Initial overloads still need symmetric limits with explicit relaxation.
                pos_slack: LpVar = prob.add_var(0, 1e20, join("br_cst_flow_pos_sl_", [t_idx, m, c, occ]))
                neg_slack: LpVar = prob.add_var(0, 1e20, join("br_cst_flow_neg_sl_", [t_idx, m, c, occ]))

                # record the flow so the result extraction can evaluate the post-contingency loading later
                branch_vars.add_contingency_flow(t=t_idx, m=m, c=c,
                                                 flow_var=contingency_flows[m],
                                                 neg_slack=neg_slack,
                                                 pos_slack=pos_slack)

                # Ensure the slacks relax
                prob.add_cst(
                    cst=contingency_flows[m] - pos_slack <= branch_data_t.contingency_rates[m] / Sbase,
                    name=join("br_cst_flow_upper_lim_", [t_idx, m, c, occ])
                )

                # lower rate constraint
                prob.add_cst(
                    cst=contingency_flows[m] + neg_slack >= -branch_data_t.contingency_rates[m] / Sbase,
                    name=join("br_cst_flow_lower_lim_", [t_idx, m, c, occ])
                )

                # Penalty for the slacks which is arbitrary
                f_obj += 1e4 * (pos_slack + neg_slack)
            else:
                # the branch is not monitored under this contingency: nothing to enforce
                pass
        else:
            # the post-contingency flow is a pure constant (no decision variables): nothing to constrain
            pass

    return f_obj


def get_contingency_monitorable_branches(branch_data_t: PassiveBranchData,
                                         branch_vars: BranchNtcVars,
                                         t_idx: int,
                                         corrective_contingencies: bool,
                                         monitor_only_sensitive_branches: bool,
                                         monitor_only_ntc_load_rule_branches: bool,
                                         alpha_threshold: float,
                                         alpha_n1: Mat,
                                         structural_ntc: float,
                                         ntc_load_rule: float) -> BoolVec:
    """
    Flag the branches that may receive a post-contingency limit under any of the contingencies.
    This exists so the post contingency flow expressions of the branches where no contingency 
    could constrain them are never built. 

    :param branch_data_t: passive branch data
    :param branch_vars: branch LP variable container
    :param t_idx: time index being formulated
    :param corrective_contingencies: True when the corrective formulation is used
    :param monitor_only_sensitive_branches: True to drop the branches with a low exchange sensitivity
    :param monitor_only_ntc_load_rule_branches: True to apply the CEP load rule
    :param alpha_threshold: minimum N-1 exchange sensitivity for a branch to be monitored
    :param alpha_n1: N-1 exchange sensitivities, branches x outaged branches
    :param structural_ntc: sum of the inter-area ratings
    :param ntc_load_rule: share of the rating a branch may contribute to the exchange
    :return: per-branch flag, True for the branches worth formulating
    """
    # DC branches are always monitored. Their AC exchange sensitivity is zero, so no
    # sensitivity rule can select them
    monitorable: BoolVec = np.array(branch_data_t.dc, dtype=bool)

    if corrective_contingencies:
        # the corrective loop monitors exactly the branches flagged in the base case
        monitorable = np.logical_or(monitorable, np.array(branch_vars.monitor_logic[t_idx, :], dtype=bool))

    else:
        # The preventive loop derives its decision per contingency from alpha_n1
        if alpha_n1.ndim == 2 and alpha_n1.shape[0] == branch_data_t.nelm and alpha_n1.shape[1] > 0:
            alpha_max: Vec = np.max(np.abs(alpha_n1), axis=1)

            candidate: BoolVec = np.ones(branch_data_t.nelm, dtype=bool)

            if monitor_only_sensitive_branches:
                candidate = np.logical_and(candidate, alpha_max > alpha_threshold)
            else:
                # the sensitivity filter is disabled so every branch stays a candidate
                pass

            if monitor_only_ntc_load_rule_branches:
                candidate = np.logical_and(
                    candidate,
                    ntc_load_rule * branch_data_t.rates / (alpha_max + 1e-20) <= structural_ntc
                )
            else:
                # the load rule filter is disabled so every branch stays a candidate
                pass

            monitorable = np.logical_or(monitorable, candidate)

        else:
            # no usable sensitivity matrix so keep every branch
            monitorable = np.ones(branch_data_t.nelm, dtype=bool)

    return monitorable


def evaluate_corrective_flow_addons(multi_contingencies: List[LinearMultiContingency],
                                           group_indices,
                                           vsc_delta_store: Dict[int, Dict[int, LpVar]],
                                           hvdc_delta_store: Dict[int, Dict[int, LpVar]],
                                           n_vsc: int,
                                           n_hvdc: int,
                                           n_branch: int,
                                           model: LpModel) -> Dict[int, Vec]:
    """
    Evaluate the numeric branch flow change of every group's solved corrective Δ set-points.

    Each addon is ``compensated_df · Δ`` in per unit.

    :param multi_contingencies: formulated multi-contingencies in LP order
    :param group_indices: formulated-group positions to evaluate
    :param vsc_delta_store: per group position, the per-VSC Δ variable dictionary
    :param hvdc_delta_store: per group position, the per-HVDC Δ variable dictionary
    :param n_vsc: number of VSC converters
    :param n_hvdc: number of HVDC links
    :param n_branch: number of passive branches
    :param model: solved LP model the Δ values are read from
    :return: per group position, the corrective flow change (p.u.) on every branch
    """
    addons: Dict[int, Vec] = dict()
    for c in group_indices:
        c_int: int = int(c)
        contingency: LinearMultiContingency = multi_contingencies[c_int]
        addon_c: Vec = np.zeros(n_branch)
        has_delta: bool = False

        vsc_deltas: Dict[int, LpVar] = vsc_delta_store.get(c_int, dict())
        if len(vsc_deltas) > 0 and contingency.compensated_vsc_df is not None:
            dv: Vec = np.zeros(n_vsc)
            for d, var in vsc_deltas.items():
                dv[d] = model.get_value(var)
            addon_c += contingency.compensated_vsc_df @ dv
            has_delta = True
        else:
            pass  # this group moves no VSC correctively

        hvdc_deltas: Dict[int, LpVar] = hvdc_delta_store.get(c_int, dict())
        if len(hvdc_deltas) > 0 and contingency.compensated_hvdc_df is not None:
            dh: Vec = np.zeros(n_hvdc)
            for d, var in hvdc_deltas.items():
                dh[d] = model.get_value(var)
            addon_c += contingency.compensated_hvdc_df @ dh
            has_delta = True
        else:
            pass  # this group moves no HVDC correctively

        if has_delta:
            addons[c_int] = addon_c
        else:
            pass  # no corrective action in this group, the preventive flow applies

    return addons


def add_absolute_value(prob: LpModel, expr: LpVar | LpExp, name: str) -> LpVar:
    """
    Declare a variable bounded below by the absolute value of an expression.
    When it is minimised it equals that absolute value.

    :param prob: linear problem the variable and constraints are added to
    :param expr: expression whose magnitude is measured
    :param name: unique name of the variable
    :return: the absolute value variable
    """
    abs_var: LpVar = prob.add_var(lb=0.0, ub=prob.INFINITY, name=name)
    prob.add_cst(cst=abs_var >= expr, name=name + "_pos")
    prob.add_cst(cst=abs_var >= -expr, name=name + "_neg")
    return abs_var


def add_base_control_effort(prob: LpModel,
                            t_idx: int,
                            branch_data_t: PassiveBranchData,
                            active_branch_data_t: ActiveBranchData,
                            branch_vars: BranchVariables,
                            vsc_vars: ConverterVariables,
                            hvdc_vars: ConverterVariables,
                            effort: List[LpExp]) -> None:
    """
    Append the N-state control effort terms in p.u. of power.

    Phase shifter angles and free converter powers carry no cost in the transfer
    objective, so many operating points reach the same TTC. Their effort is the
    flow shifted by the angle change (|Δτ| / X) and the converter power |P|.
    Each term is weighted 1 + 1e-3 x device index, so equal effort alternatives
    (e.g. two identical corridors) resolve to the same device in every run.

    :param prob: linear problem the effort variables are added to
    :param t_idx: time index being formulated
    :param branch_data_t: passive branch data, for the phase shifter reactance
    :param active_branch_data_t: active branch data, for the scheduled tap angles
    :param branch_vars: branch LP variable container
    :param vsc_vars: VSC LP variable container
    :param hvdc_vars: HVDC LP variable container
    :param effort: output list the weighted absolute-value terms are appended to
    :return: None
    """
    m: int
    for m in range(branch_data_t.nelm):
        tap: float | LpVar = branch_vars.tap_angles[t_idx, m]
        if isinstance(tap, LpVar):
            # same susceptance the flow equation uses
            x_eff: float = branch_data_t.X[m] * active_branch_data_t.tap_module[m]
            if x_eff == 0.0:
                bk: float = 1e-6
            else:
                bk = 1.0 / x_eff
            effort.append((1.0 + 1e-3 * m) * add_absolute_value(
                prob=prob, expr=bk * (tap - active_branch_data_t.tap_angle[m]),
                name=join("effort_tap_", [t_idx, m], "_")))
        else:
            pass  # fixed angle: not a control

    k: int
    for k in range(vsc_vars.flows.shape[1]):
        if isinstance(vsc_vars.flows[t_idx, k], LpVar):
            effort.append((1.0 + 1e-3 * k) * add_absolute_value(
                prob=prob, expr=vsc_vars.flows[t_idx, k], name=join("effort_vsc_", [t_idx, k], "_")))
        else:
            pass  # fixed set-point: not a control

    for k in range(hvdc_vars.flows.shape[1]):
        if isinstance(hvdc_vars.flows[t_idx, k], LpVar):
            effort.append((1.0 + 1e-3 * k) * add_absolute_value(
                prob=prob, expr=hvdc_vars.flows[t_idx, k], name=join("effort_hvdc_", [t_idx, k], "_")))
        else:
            pass  # fixed set-point: not a control


def add_corrective_control_effort(prob: LpModel,
                                  vsc_delta_store: Dict[int, Dict[int, LpVar]],
                                  hvdc_delta_store: Dict[int, Dict[int, LpVar]],
                                  counted: Set[Tuple[int, int, int]],
                                  effort: List[LpExp]) -> None:
    """
    Append |Δ| for every corrective converter set-point change not yet counted,
    weighted 1 + 1e-3 x converter index to resolve equal-effort alternatives.

    :param prob: linear problem the effort variables are added to
    :param vsc_delta_store: per group position, the per-VSC Δ variables
    :param hvdc_delta_store: per group position, the per-HVDC Δ variables
    :param counted: (family, group, converter) keys already in the effort, updated in place
    :param effort: output list the weighted absolute-value terms are appended to
    :return: None
    """
    family: int
    store: Dict[int, Dict[int, LpVar]]
    c: int
    deltas: Dict[int, LpVar]
    d: int
    delta: LpVar
    for family, store in enumerate((vsc_delta_store, hvdc_delta_store)):
        for c, deltas in store.items():
            for d, delta in deltas.items():
                key: Tuple[int, int, int] = (family, int(c), int(d))
                if key in counted:
                    pass  # this Δ is already measured
                else:
                    effort.append((1.0 + 1e-3 * (d + 0.5)) * add_absolute_value(
                        prob=prob, expr=delta, name=join("effort_corr_", [family, c, d], "_")))
                    counted.add(key)


def solve_least_control_effort(prob: LpModel,
                               objective: LpExp,
                               transfer: LpVar,
                               effort: List[LpExp],
                               logger: Logger,
                               robust: bool,
                               show_logs: bool,
                               progress_text: Union[None, Callable[[str], None]]) -> int:
    """
    Second stage. Among the solutions that reach the first stage TTC, take the one with the
    least control effort. This makes the reported operating point and its limiting pairs
    reproducible instead of an arbitrary optimal vertex.

    The TTC is held exactly by fixing the transfer variable through its bounds, which the
    solver honours without tolerance. The limit slack penalties stay in the objective and the
    effort is added with a 1e-3 weight. A slack costs 1e4 per p.u., so 1 MW of limit relaxation
    outweighs 1e7 MW of control effort. 

    :param prob: linear problem solved at the first stage optimum
    :param objective: first stage objective expression (transfer and limit slack penalties)
    :param transfer: area 1 increase, the variable the TTC is maximised through, declared with bounds [0, inf)
    :param effort: weighted absolute-value effort terms
    :param logger: logger for the fallback warning
    :param robust: robust solver mode
    :param show_logs: display the solver logs
    :param progress_text: GUI text callback
    :return: solver status
    """
    # hold the transfer at its optimum
    value: float = max(0.0, prob.get_value(transfer))
    prob.set_var_bounds(var=transfer, lb=value, ub=value)

    # keep the slacks minimal and, behind them, take the least control effort
    prob.minimize(objective + 1e-3 * prob.sum(effort))
    status: int = prob.solve(robust=robust, show_logs=show_logs, progress_text=progress_text)

    if status == prob.OPTIMAL:
        pass  # least effort optimum found
    else:
        # numerical trouble so keep the first stage optimum, which is valid but not unique
        logger.add_warning("Least control effort stage not solved, keeping the first stage optimum",
                           value=prob.status2string(status))
        prob.set_var_bounds(var=transfer, lb=0.0, ub=prob.INFINITY)
        prob.minimize(objective)
        status = prob.solve(robust=robust, show_logs=show_logs, progress_text=progress_text)
    return status


def screen_contingency_violations(multi_contingencies: List[LinearMultiContingency],
                                  admitted_rows: Dict[int, BoolVec],
                                  f0: Vec,
                                  hvdc0: Vec,
                                  vsc0: Vec,
                                  inj0: Vec,
                                  monitorable: BoolVec,
                                  con_rates_pu: Vec,
                                  tol_pu: float,
                                  at_risk_fraction: float,
                                  delta_flow_addons: Union[Dict[int, Vec], None] = None) -> List[Tuple[int, IntVec]]:
    """
    Numerically evaluate every contingency group against a solved operating point and
    return, per violated group, the rows to admit into the LP. This accelerates the
    calculation quite a lot.

    :param multi_contingencies: list of LinearMultiContingency
    :param admitted_rows: per group index, boolean mask of the rows already in the LP
    :param f0: solved branch flows (p.u.)
    :param hvdc0: solved HVDC flows (p.u.)
    :param vsc0: solved VSC flows (p.u.)
    :param inj0: solved bus injections (p.u.)
    :param monitorable: per-branch flag of branches that may get a post-contingency limit
    :param con_rates_pu: branch contingency ratings (p.u.)
    :param tol_pu: feasibility tolerance (p.u.) added to the rating before flagging
    :param at_risk_fraction: fraction of the rating above which a row of a violated group
                             is admitted preventively along with the violated rows
    :param delta_flow_addons: per group index, the numeric flow change caused by that
                              group's solved corrective Δ set-points (compensated DF · Δ)
    :return: list of (group index, row indices to admit)
    """
    # Check every monitorable row at the solved operating point, regardless of initial loading.
    limits: Vec = con_rates_pu + tol_pu

    admissions: List[Tuple[int, IntVec]] = list()
    for c, contingency in enumerate(multi_contingencies):

        # rows of this group that are not yet enforced by the LP
        already: Union[BoolVec, None] = admitted_rows.get(c, None)
        if already is None:
            pending: BoolVec = monitorable
        else:
            pending = monitorable & (~already)

        if np.any(pending):
            fc: Vec = f0.copy()
            if len(contingency.branch_indices) > 0:
                fc += contingency.mlodf_factors @ f0[contingency.branch_indices]
            else:
                pass  # no branch outages in this group
            if len(contingency.hvdc_indices) > 0:
                fc += contingency.hvdc_odf @ hvdc0[contingency.hvdc_indices]
            else:
                pass  # no HVDC outages in this group
            if len(contingency.vsc_indices) > 0:
                fc += contingency.vsc_odf @ vsc0[contingency.vsc_indices]
            else:
                pass  # no VSC outages in this group
            if len(contingency.bus_indices) > 0:
                # same expression as the LP path: factor-scaled injection loss
                fc += contingency.compensated_ptdf_factors @ (
                        contingency.injections_factor * inj0[contingency.bus_indices])
            else:
                pass  # no injection outages in this group

            # apply the solved corrective set-point changes of this group, if any
            if delta_flow_addons is not None:
                addon: Union[Vec, None] = delta_flow_addons.get(c, None)
                if addon is not None:
                    fc += addon
                else:
                    pass  # this group has no corrective Δ in the LP yet
            else:
                pass  # preventive screening only

            fc_abs: Vec = np.abs(fc)
            if np.any(pending & (fc_abs > limits)):
                # admit the violated rows plus the near-limit rows of the same group
                admit_mask: BoolVec = pending & (fc_abs > at_risk_fraction * con_rates_pu)
                admissions.append((c, np.flatnonzero(admit_mask)))
            else:
                # the current solution survives this outage on every pending row
                pass
        else:
            # every checkable row of this group is already enforced by the LP
            pass

    return admissions


def fill_worst_contingency_per_branch(grid: MultiCircuit,
                                      multi_contingencies: Union[LinearMultiContingencies, None],
                                      f0_mw: Vec,
                                      hvdc0_mw: Vec,
                                      vsc0_mw: Vec,
                                      inj0_mw: Vec,
                                      contingency_rates_mw: Vec,
                                      alpha: Vec,
                                      worst_idx: IntVec,
                                      worst_flow: Vec,
                                      worst_loading: Vec,
                                      alpha_n1_worst: Vec,
                                      tied_groups: List[Tuple[int, int, float, float, float]],
                                      branch_data: PassiveBranchData,
                                      solved_flows: Mat | CompactContingencies | None = None,
                                      corrective_addons_mw: Dict[int, Vec] | None = None) -> None:
    """
    For every branch, keep the contingency group that maximises post-contingency loading.

    The N-state loading is the starting point. A group is recorded only when its N-1
    loading is worse by more than 1e-4 p.u., so an unaffected line keeps index -1 and
    N-1 flow = N flow. Ties go to the group that comes first in the grid.

    :param grid: circuit that owns the contingency groups
    :param multi_contingencies: formulated multi-contingencies, or None when N-1 is off
    :param f0_mw: solved N-state branch flows (MW)
    :param hvdc0_mw: solved N-state HVDC flows (MW)
    :param vsc0_mw: solved N-state VSC flows (MW)
    :param inj0_mw: solved N-state bus injections (MW)
    :param contingency_rates_mw: branch contingency ratings (MW)
    :param alpha: N-state exchange sensitivity of every branch
    :param worst_idx: output, group index per branch, filled in place
    :param worst_flow: output, N-1 flow (MW) of the worst group, filled in place
    :param worst_loading: output, |N-1 flow| / contingency rate, filled in place
    :param alpha_n1_worst: output, exchange sensitivity under the worst group, filled in place
    :param tied_groups: output, (branch, group index, N-1 flow MW, N-1 loading p.u., alpha N-1)
                        of the twin outages tied with the branch worst, filled in place
    :param branch_data: passive branch data, to recognise the twin outages
    :param solved_flows: solved physical contingency branch flows (groups x branches, MW), if available
    :param corrective_addons_mw: per formulated group position, the solved corrective
                                 converter redispatch flow change (MW)
    :return: None
    """
    # numeric copies so LP extracts still enter the sparse matvecs as float
    f0: Vec = np.asarray(f0_mw, dtype=float)
    hvdc0: Vec = np.asarray(hvdc0_mw, dtype=float)
    vsc0: Vec = np.asarray(vsc0_mw, dtype=float)
    inj0: Vec = np.asarray(inj0_mw, dtype=float)
    rates: Vec = np.asarray(contingency_rates_mw, dtype=float)
    alpha_n: Vec = np.asarray(alpha, dtype=float)

    # N-state is the baseline so no group is assigned until some outage raises the loading
    worst_idx[:] = -1
    worst_flow[:] = f0
    worst_loading[:] = np.abs(f0) / (rates + 1e-20)
    alpha_n1_worst[:] = 0.0
    tied_groups.clear()

    if multi_contingencies is None:
        return
    else:
        n_used: int = len(multi_contingencies.multi_contingencies)
        if n_used == 0:
            return
        else:
            # map each formulated group onto the full grid group index used by the report
            all_groups = grid.get_contingency_groups()
            id_to_i: Dict[str, int] = dict()
            i_g: int
            for i_g in range(len(all_groups)):
                id_to_i[all_groups[i_g].idtag] = i_g

            used_groups = multi_contingencies.contingency_groups_used
            result_indices: IntVec = np.empty(n_used, dtype=int)
            c: int
            for c in range(n_used):
                mapped_i: Union[int, None] = id_to_i.get(used_groups[c].idtag, None)
                if mapped_i is None:
                    result_indices[c] = -1
                else:
                    result_indices[c] = mapped_i

            # Visit the groups in grid order and require a loading increase above the
            # numerical noise, so equally loading outages resolve to the same group whatever
            # the order they were selected in, and an N-limited line keeps index -1.
            tie_tolerance: float = 1e-4
            visit_order: IntVec = np.argsort(result_indices, kind="stable")

            # Twin outages trip only parallel branches with the same terminals, impedance and
            # ratings, so they are interchangeable.
            twin_class: IntVec = np.arange(n_used, dtype=int)
            has_twin: BoolVec = np.zeros(n_used, dtype=bool)
            class_of_signature: Dict[Tuple[Tuple[int, int, float, float, float, float], ...], int] = dict()
            for c in range(n_used):
                outage: LinearMultiContingency = multi_contingencies.multi_contingencies[c]
                if (len(outage.branch_indices) > 0 and len(outage.hvdc_indices) == 0
                        and len(outage.vsc_indices) == 0 and len(outage.bus_indices) == 0):
                    parts: List[Tuple[int, int, float, float, float, float]] = list()
                    k_br: int
                    for k_br in outage.branch_indices:
                        f_bus: int = int(branch_data.F[k_br])
                        t_bus: int = int(branch_data.T[k_br])
                        parts.append((min(f_bus, t_bus), max(f_bus, t_bus), float(branch_data.R[k_br]),
                                      float(branch_data.X[k_br]), float(branch_data.rates[k_br]),
                                      float(branch_data.contingency_rates[k_br])))
                    parts.sort()
                    signature: Tuple[Tuple[int, int, float, float, float, float], ...] = tuple(parts)
                    first_c: Union[int, None] = class_of_signature.get(signature, None)
                    if first_c is None:
                        class_of_signature[signature] = c
                    else:
                        twin_class[c] = first_c
                        has_twin[c] = True
                        has_twin[first_c] = True
                else:
                    pass  # converter or injection outages are never twins

            # Only twin outages that raise the loading above the N-state can tie
            n_loading: Vec = worst_loading.copy()
            worst_position: IntVec = np.full(len(worst_idx), -1, dtype=int)
            tie_candidates: List[Tuple[int, IntVec, Vec, Vec, Vec]] = list()
            position: int
            for position in range(n_used):
                c = int(visit_order[position])
                contingency: LinearMultiContingency = multi_contingencies.multi_contingencies[c]
                result_idx_c: int = int(result_indices[c])

                # the same linear N-1 combination as the lazy screening, evaluated in MW
                fc: Vec = f0.copy()
                if len(contingency.branch_indices) > 0:
                    fc = fc + contingency.mlodf_factors @ f0[contingency.branch_indices]
                else:
                    pass  # this group outages no AC branch

                if len(contingency.hvdc_indices) > 0 and hvdc0.size > 0:
                    fc = fc + contingency.hvdc_odf @ hvdc0[contingency.hvdc_indices]
                else:
                    pass  # this group outages no HVDC

                if len(contingency.vsc_indices) > 0 and vsc0.size > 0:
                    fc = fc + contingency.vsc_odf @ vsc0[contingency.vsc_indices]
                else:
                    pass  # this group outages no VSC

                if len(contingency.bus_indices) > 0 and inj0.size > 0:
                    fc = fc + contingency.compensated_ptdf_factors @ (
                            contingency.injections_factor * inj0[contingency.bus_indices])
                else:
                    pass  # this group outages no injection

                # N-1 exchange sensitivity of the monitored flow with alpha plus the LODF redistribution
                alpha_c: Vec = alpha_n.copy()
                if len(contingency.branch_indices) > 0:
                    alpha_c = alpha_c + contingency.mlodf_factors @ alpha_n[contingency.branch_indices]
                else:
                    pass  # converter only outages do not shift the AC alpha through MLODF

                if solved_flows is not None:
                    if isinstance(solved_flows, CompactContingencies):
                        physical_state = solved_flows.numeric_state(c)
                        fc = physical_state[1] * solved_flows.nc.Sbase
                    else:
                        fc = solved_flows[c, :]
                elif corrective_addons_mw is not None:
                    addon_mw: Union[Vec, None] = corrective_addons_mw.get(c, None)
                    if addon_mw is not None:
                        # the LP relieved this group correctively
                        fc = fc + addon_mw
                    else:
                        pass  # no corrective action in this group, keep the preventive flow
                else:
                    pass  # Keep the contingency flow already calculated

                loading_c: Vec = np.abs(fc) / (rates + 1e-20)
                better: BoolVec = loading_c > worst_loading + tie_tolerance
                if has_twin[c] and result_idx_c >= 0:
                    tie_now: IntVec = np.flatnonzero((~better)
                                                     & (loading_c >= worst_loading - tie_tolerance)
                                                     & (loading_c > n_loading + tie_tolerance))
                    if len(tie_now) > 0:
                        tie_candidates.append((c, tie_now, fc[tie_now], loading_c[tie_now], alpha_c[tie_now]))
                    else:
                        pass  # this group ties with no branch worst so far
                else:
                    pass  # without a twin there is no equivalent outage to list
                worst_loading[better] = loading_c[better]
                worst_position[better] = c
                worst_flow[better] = fc[better]
                if result_idx_c >= 0:
                    worst_idx[better] = result_idx_c
                else:
                    pass  # unmapped group so we keep the previous index
                alpha_n1_worst[better] = alpha_c[better]

            # keep the twins of each branch worst that are still within the tolerance of it
            c_tie: int
            m_tie: IntVec
            flow_tie: Vec
            loading_tie: Vec
            alpha_tie: Vec
            for c_tie, m_tie, flow_tie, loading_tie, alpha_tie in tie_candidates:
                worst_pos_tie: IntVec = worst_position[m_tie]
                still_tied: BoolVec = ((np.abs(loading_tie - worst_loading[m_tie]) <= tie_tolerance)
                                       & (worst_pos_tie >= 0)
                                       & (worst_pos_tie != c_tie)
                                       & (twin_class[np.maximum(worst_pos_tie, 0)] == twin_class[c_tie]))
                k: int
                for k in np.flatnonzero(still_tied):
                    tied_groups.append((int(m_tie[k]), int(result_indices[c_tie]), float(flow_tie[k]),
                                        float(loading_tie[k]), float(alpha_tie[k])))

def add_linear_branches_contingencies_formulation(t_idx: int,
                                                  Sbase: float,
                                                  branch_data_t: PassiveBranchData,
                                                  branch_vars: BranchNtcVars,
                                                  bus_vars: BusNtcVars,
                                                  hvdc_vars: HvdcNtcVars,
                                                  vsc_vars: VscNtcVars,
                                                  prob: LpModel,
                                                  linear_multi_contingencies: LinearMultiContingencies,
                                                  monitor_only_ntc_load_rule_branches: bool,
                                                  monitor_only_sensitive_branches: bool,
                                                  structural_ntc: float,
                                                  ntc_load_rule: float,
                                                  alpha_threshold: float,
                                                  alpha_n1: Mat,
                                                  corrective_contingencies: bool = False,
                                                  vsc_active: BoolVec | None = None,
                                                  hvdc_active: BoolVec | None = None,
                                                  group_indices: Union[IntVec, None] = None,
                                                  group_rows: Union[Dict[int, IntVec], None] = None,
                                                  vsc_delta_store: Union[Dict[int, Dict[int, LpVar]], None] = None,
                                                  hvdc_delta_store: Union[Dict[int, Dict[int, LpVar]], None] = None,
                                                  preservation_done: Union[set, None] = None):
    """
    Formulate the branches
    :param t_idx: time index
    :param Sbase: base power (100 MVA)
    :param branch_data_t: BranchData
    :param branch_vars: BranchVars
    :param bus_vars: BusVars
    :param hvdc_vars: HvdcNtcVars
    :param vsc_vars: VscNtcVars
    :param prob: OR problem
    :param linear_multi_contingencies: LinearMultiContingencies
    :param monitor_only_ntc_load_rule_branches:
    :param monitor_only_sensitive_branches:
    :param structural_ntc:
    :param ntc_load_rule:
    :param alpha_threshold:
    :param alpha_n1:
    :param corrective_contingencies: if True, allow corrective re-dispatch of the VSC/HVDC
    :param group_indices: subset of multi-contingency indices to formulate (None = all)
    :param group_rows: per group index, the row indices to enforce
    :param vsc_delta_store: per group index, the persistent VSC Δ variable dictionary
    :param hvdc_delta_store: per group index, the persistent HVDC Δ variable dictionary
    :param preservation_done: group indices whose exchange-preservation equality is already
                              in the LP
    :return objective function
    """
    f_obj = 0.0

    # Which branches can possibly get a post-contingency limit
    monitorable = get_contingency_monitorable_branches(
        branch_data_t=branch_data_t,
        branch_vars=branch_vars,
        t_idx=t_idx,
        corrective_contingencies=corrective_contingencies,
        monitor_only_sensitive_branches=monitor_only_sensitive_branches,
        monitor_only_ntc_load_rule_branches=monitor_only_ntc_load_rule_branches,
        alpha_threshold=alpha_threshold,
        alpha_n1=alpha_n1,
        structural_ntc=structural_ntc,
        ntc_load_rule=ntc_load_rule
    )

    # The corrective converter terms are read back for the monitorable and inter area branches
    corrective_rows: BoolVec = monitorable.copy()
    boundary_rows: BoolVec = np.zeros(branch_data_t.nelm, dtype=bool)
    for branch_m, branch_sense in branch_vars.inter_space_branches:
        corrective_rows[branch_m] = True
        boundary_rows[branch_m] = True

    # which multi-contingency indices to formulate: either all, or the caller's subset
    if group_indices is None:
        group_list: IntVec = np.arange(len(linear_multi_contingencies.multi_contingencies))
    else:
        group_list = group_indices

    for c in group_list:
        contingency = linear_multi_contingencies.multi_contingencies[c]

        # restrict the enforced rows when the lazy admission provides them for this group
        if group_rows is None:
            row_filter_c: BoolVec = monitorable
            enforce_rows_c: Union[BoolVec, None] = None
            corrective_rows_c: BoolVec = corrective_rows
        else:
            enforce_rows_c = np.zeros(branch_data_t.nelm, dtype=bool)
            enforce_rows_c[group_rows[c]] = True
            row_filter_c = monitorable & enforce_rows_c
            # The corrective terms are only read back on the admitted rows and on the boundary
            # (exchange preservation), thus saving time.
            corrective_rows_c = corrective_rows & (enforce_rows_c | boundary_rows)

        contingency_flows, mask, changed_idx = contingency.get_lp_contingency_flows(
            base_flow=branch_vars.flows[t_idx, :],
            injections=bus_vars.Pinj[t_idx, :],
            hvdc_flow=hvdc_vars.flows[t_idx, :],
            vsc_flow=vsc_vars.flows[t_idx, :],
            row_filter=row_filter_c
        )

        if corrective_contingencies:
            # the Δ variables of this group persist across admissions when a store is given
            if vsc_delta_store is None:
                vsc_deltas_c: Union[Dict[int, LpVar], None] = None
                hvdc_deltas_c: Union[Dict[int, LpVar], None] = None
            else:
                vsc_deltas_c = vsc_delta_store.setdefault(int(c), dict())
                hvdc_deltas_c = hvdc_delta_store.setdefault(int(c), dict())

            # the exchange-preservation equality goes in at most once per group
            if preservation_done is None:
                add_preservation_c: bool = True
            else:
                add_preservation_c = int(c) not in preservation_done
                preservation_done.add(int(c))

            f_obj += add_corrective_contingency_formulation(
                t_idx=t_idx, c=c, Sbase=Sbase, contingency=contingency,
                contingency_flows=contingency_flows, changed_idx=changed_idx,
                branch_data_t=branch_data_t, branch_vars=branch_vars,
                vsc_vars=vsc_vars, hvdc_vars=hvdc_vars,
                prob=prob, corrective_rows=corrective_rows_c,
                vsc_active=vsc_active, hvdc_active=hvdc_active,
                vsc_delta_vars=vsc_deltas_c, hvdc_delta_vars=hvdc_deltas_c,
                add_exchange_preservation=add_preservation_c,
                enforce_rows=enforce_rows_c)
        else:
            # preventive N-1: the converters stay at their base-case set-point
            f_obj += add_preventive_contingency_formulation(
                t_idx=t_idx, c=c, Sbase=Sbase, contingency=contingency,
                contingency_flows=contingency_flows, changed_idx=changed_idx,
                branch_data_t=branch_data_t, branch_vars=branch_vars,
                monitor_only_ntc_load_rule_branches=monitor_only_ntc_load_rule_branches,
                monitor_only_sensitive_branches=monitor_only_sensitive_branches,
                structural_ntc=structural_ntc, ntc_load_rule=ntc_load_rule,
                alpha_threshold=alpha_threshold, alpha_n1=alpha_n1, prob=prob)

    return f_obj


def add_linear_hvdc_formulation(t_idx: int,
                                Sbase: float,
                                hvdc_data_t: HvdcData,
                                hvdc_vars: HvdcNtcVars,
                                vars_bus: BusNtcVars,
                                prob: LpModel,
                                logger: Logger,
                                saturate: bool = True,):
    """

    :param t_idx:
    :param Sbase:
    :param hvdc_data_t:
    :param hvdc_vars:
    :param vars_bus:
    :param prob:
    :param logger:
    :param saturate:
    :return:
    """

    f_obj = 0.0

    for m in range(hvdc_data_t.nelm):

        fr = hvdc_data_t.F[m]
        to = hvdc_data_t.T[m]
        hvdc_vars.rates[t_idx, m] = hvdc_data_t.rates[m]

        if hvdc_data_t.active[m]:

            if hvdc_data_t.control_mode_int[m] == HvdcControlType.type_0_free.idx():  # P-MODE 3

                # set the flow based on the angular difference
                P0 = hvdc_data_t.Pset[m] / Sbase

                # convert MW/deg to pu/rad
                droop = hvdc_data_t.get_angle_droop_in_pu_rad_at(m, Sbase)
                if droop == 0.0:
                    logger.add_warning("Zero HVDC droop",
                                       device=hvdc_data_t.names[m], value=droop, expected_value=">0")
                    droop = 1e-20

                if saturate:
                    hvdc_vars.flows[t_idx, m] = pmode3_formulation(
                        prob=prob, t_idx=t_idx, m=m, rate=hvdc_data_t.rates[m] / Sbase,
                        P0=P0, droop=droop,
                        theta_f=vars_bus.Va[t_idx, fr], theta_t=vars_bus.Va[t_idx, to],
                        base_name="hvdc",
                        angle_range=(vars_bus.angle_min[fr] - vars_bus.angle_max[to],
                                     vars_bus.angle_max[fr] - vars_bus.angle_min[to]))

                else:
                    # Simple Pmode 3 with no saturation magic
                    # declare the flow var
                    hvdc_vars.flows[t_idx, m] = prob.add_var(
                        lb=-hvdc_data_t.rates[m] / Sbase,
                        ub=hvdc_data_t.rates[m] / Sbase,
                        name=join("hvdc_flow_", [t_idx, m], "_")
                    )

                    # flow = P0 + k · (theta_f - theta_t)
                    prob.add_cst(
                        cst=hvdc_vars.flows[t_idx, m] == P0 + droop * (
                                vars_bus.Va[t_idx, fr] - vars_bus.Va[t_idx, to]),
                        name=join("hvdc_flow_cst_", [t_idx, m], "_")
                    )

                # add the injections matching the flow
                vars_bus.Pbalance[t_idx, fr] += - hvdc_vars.flows[t_idx, m]
                vars_bus.Pbalance[t_idx, to] += hvdc_vars.flows[t_idx, m]

            elif hvdc_data_t.control_mode_int[m] == HvdcControlType.type_1_Pset.idx():

                if hvdc_data_t.dispatchable[m]:

                    # declare the flow var
                    hvdc_vars.flows[t_idx, m] = prob.add_var(
                        lb=-hvdc_data_t.rates[m] / Sbase,
                        ub=hvdc_data_t.rates[m] / Sbase,
                        name=join("hvdc_flow_", [t_idx, m], "_")
                    )

                    # add the injections matching the flow
                    vars_bus.Pbalance[t_idx, fr] += -hvdc_vars.flows[t_idx, m]
                    vars_bus.Pbalance[t_idx, to] += hvdc_vars.flows[t_idx, m]

                else:

                    if hvdc_data_t.Pset[m] > hvdc_data_t.rates[m]:
                        P0 = hvdc_data_t.rates[m] / Sbase

                    elif hvdc_data_t.Pset[m] < -hvdc_data_t.rates[m]:
                        P0 = -hvdc_data_t.rates[m] / Sbase

                    else:
                        P0 = hvdc_data_t.Pset[m] / Sbase

                    # make the flow equal to P0
                    hvdc_vars.flows[t_idx, m] = P0

                    # add the injections matching the flow
                    vars_bus.Pbalance[t_idx, fr] += -hvdc_vars.flows[t_idx, m]
                    vars_bus.Pbalance[t_idx, to] += hvdc_vars.flows[t_idx, m]
            else:
                raise Exception('OPF: Unknown HVDC control mode {}'.format(hvdc_data_t.control_mode_int[m]))
        else:
            # not active, therefore the flow is exactly zero
            prob.set_var_bounds(var=hvdc_vars.flows[t_idx, m], ub=0.0, lb=0.0)

    # add the flows to the objective function
    # for k, sense in hvdc_vars.inter_space_hvdc:
    #   f_obj += -hvdc_vars.flows[t_idx, k] * sense
    f_obj += 0.0

    return f_obj


def compute_vsc_pmode3_saturation_rates(vsc_data_t: VscData,
                                        branch_data_t: PassiveBranchData,
                                        bus_data_t: BusData) -> Vec:
    """
    Compute the effective P-mode 3 saturation rate of each VSC in MW.
    A P-mode 3 droop saturates when the converter cannot deliver more power, and that limit
    is the converter rating or the total rating of the DC branches attached to the
    converter's DC bus, whichever is lower.

    :param vsc_data_t: VscData structure
    :param branch_data_t: PassiveBranchData structure (contains the DC lines)
    :param bus_data_t: BusData structure (provides the is_dc marker)
    :return: array of effective saturation rates (MW) per VSC
    """
    # total rating of the active DC branches incident to each bus
    dc_rate_per_bus: Vec = np.zeros(bus_data_t.nbus)
    for k in range(branch_data_t.nelm):
        f: int = branch_data_t.F[k]
        t: int = branch_data_t.T[k]
        if branch_data_t.active[k] and bus_data_t.is_dc[f] and bus_data_t.is_dc[t]:
            dc_rate_per_bus[f] += branch_data_t.rates[k]
            dc_rate_per_bus[t] += branch_data_t.rates[k]
        else:
            # AC branch or inactive branch: it does not limit the DC-side transfer
            pass

    # a meshed DC grid may have remoter bottlenecks, avoid for now
    sat_rates: Vec = vsc_data_t.rates.copy()
    for m in range(vsc_data_t.nelm):
        fr: int = vsc_data_t.F[m]
        if bus_data_t.is_dc[fr] and dc_rate_per_bus[fr] > 0.0:
            # the converter cannot push more than what its DC cables can carry
            sat_rates[m] = min(sat_rates[m], dc_rate_per_bus[fr])
        else:
            # back-to-back converter or no DC branch attached, so keep the converter rating
            pass

    return sat_rates


def add_linear_vsc_formulation(t_idx: int,
                               Sbase: float,
                               vsc_data_t: VscData,
                               vsc_vars: VscNtcVars,
                               bus_vars: BusNtcVars,
                               prob: LpModel,
                               logger: Logger,
                               sat_rates: Vec,
                               saturate: bool = True):
    """

    :param t_idx:
    :param Sbase:
    :param vsc_data_t:
    :param vsc_vars:
    :param bus_vars:
    :param bus_vars:
    :param prob:
    :param logger:
    :param sat_rates: per VSC P-mode 3 saturation rates in MW
    :param saturate: True to bound the converter flows by their saturation rates
    :return: objective function contribution
    """

    f_obj = 0.0
    any_dc_slack = False
    for m in range(vsc_data_t.nelm):

        fr = vsc_data_t.F[m]
        to = vsc_data_t.T[m]

        # remote AC bus the droop measures its angle difference against (-1 when the user did not set it)
        control_bus_idx = vsc_data_t.control1_bus_idx[m]

        vsc_vars.rates[t_idx, m] = vsc_data_t.rates[m]

        if vsc_data_t.active[m]:

            if (vsc_data_t.control1_int[m] == ConverterControlType.Pdc_angle_droop.idx() and
                    vsc_data_t.control2_int[m] == ConverterControlType.Pac.idx()):  # P-MODE 3

                # set the flow based on the angular difference
                P0 = vsc_data_t.control2_val[m] / Sbase

                # convert MW/deg to pu/rad
                droop = vsc_data_t.control1_val[m] * 57.295779513 / Sbase  # MW/deg -> p.u./rad

                if control_bus_idx == -1:
                    # Without a reference bus there is no angle difference to droop against
                    logger.add_error(msg="P-mode 3 VSC without an angle-droop reference bus: "
                                         "set 'control1_dev' to the AC bus at the other end of the DC link. "
                                         "The converter is held at its P set-point instead.",
                                     device=str(vsc_data_t.names[m]))
                    vsc_vars.flows[t_idx, m] = P0

                elif saturate:
                    vsc_vars.flows[t_idx, m] = pmode3_formulation(
                        prob=prob, t_idx=t_idx, m=m, rate=sat_rates[m] / Sbase,
                        P0=P0, droop=droop,
                        theta_f=bus_vars.Va[t_idx, control_bus_idx], theta_t=bus_vars.Va[t_idx, to],
                        base_name="vsc",
                        angle_range=(bus_vars.angle_min[control_bus_idx] - bus_vars.angle_max[to],
                                     bus_vars.angle_max[control_bus_idx] - bus_vars.angle_min[to]))

                else:

                    # Simple Pmode 3 with no saturation magic
                    # declare the flow var
                    vsc_vars.flows[t_idx, m] = prob.add_var(
                        lb=-sat_rates[m] / Sbase,
                        ub=sat_rates[m] / Sbase,
                        name=join("vsc_flow_", [t_idx, m], "_")
                    )

                    # flow = P0 + k · (theta_f - theta_t)
                    prob.add_cst(
                        cst=vsc_vars.flows[t_idx, m] == P0 + droop * (
                                bus_vars.Va[t_idx, control_bus_idx] - bus_vars.Va[t_idx, to]),
                        name=join("vsc_flow_cst_", [t_idx, m], "_")
                    )

            elif (vsc_data_t.control1_int[m] == ConverterControlType.Vm_dc.idx() and
                  vsc_data_t.control2_int[m] == ConverterControlType.Pac.idx()):

                # set the DC slack
                val = vsc_data_t.control1_val[m]
                if val == 0:
                    val = 1
                prob.set_var_bounds(var=bus_vars.Vm[t_idx, fr], lb=val, ub=val)
                any_dc_slack = True

                # declare the flow var
                vsc_vars.flows[t_idx, m] = prob.add_var(
                    lb=-vsc_data_t.rates[m] / Sbase,
                    ub=vsc_data_t.rates[m] / Sbase,
                    name=join("vsc_flow_", [t_idx, m], "_")
                )

            elif (vsc_data_t.control1_int[m] == ConverterControlType.Pdc.idx() and
                  vsc_data_t.control2_int[m] == ConverterControlType.Vm_ac.idx()):

                # Pmode1: fix the flow at the Pdc setpoint (clamped to rate)
                P0 = vsc_data_t.control1_val[m] / Sbase
                rate_pu = vsc_data_t.rates[m] / Sbase
                P0 = max(-rate_pu, min(rate_pu, P0))

                vsc_vars.flows[t_idx, m] = P0

            elif (vsc_data_t.control1_int[m] == ConverterControlType.Pac.idx() and
                  vsc_data_t.control2_int[m] == ConverterControlType.Vm_dc.idx()):

                # set the DC slack
                val = vsc_data_t.control2_val[m]
                if val == 0:
                    val = 1
                prob.set_var_bounds(var=bus_vars.Vm[t_idx, fr], lb=val, ub=val)
                any_dc_slack = True

                # declare the flow var
                vsc_vars.flows[t_idx, m] = prob.add_var(
                    lb=-vsc_data_t.rates[m] / Sbase,
                    ub=vsc_data_t.rates[m] / Sbase,
                    name=join("vsc_flow_", [t_idx, m], "_")
                )

            elif (vsc_data_t.control1_int[m] == ConverterControlType.Vm_dc.idx() and
                  vsc_data_t.control2_int[m] == ConverterControlType.Vm_ac.idx()):

                # set the DC slack
                val = vsc_data_t.control1_val[m]
                if val == 0:
                    val = 1
                prob.set_var_bounds(var=bus_vars.Vm[t_idx, fr], lb=val, ub=val)
                any_dc_slack = True

            elif (vsc_data_t.control1_int[m] == ConverterControlType.Vm_dc.idx() and
                  vsc_data_t.control2_int[m] == ConverterControlType.Pdc.idx()):

                # set the DC slack
                val = vsc_data_t.control1_val[m]
                if val == 0:
                    val = 1
                prob.set_var_bounds(var=bus_vars.Vm[t_idx, fr], lb=val, ub=val)
                any_dc_slack = True

                # declare the flow var
                vsc_vars.flows[t_idx, m] = prob.add_var(
                    lb=-vsc_data_t.rates[m] / Sbase,
                    ub=vsc_data_t.rates[m] / Sbase,
                    name=join("vsc_flow_", [t_idx, m], "_")
                )

            elif (vsc_data_t.control1_int[m] == ConverterControlType.Pdc.idx() and
                  vsc_data_t.control2_int[m] == ConverterControlType.Vm_dc.idx()):

                # set the DC slack
                val = vsc_data_t.control2_val[m]
                if val == 0:
                    val = 1
                prob.set_var_bounds(var=bus_vars.Vm[t_idx, fr], lb=val, ub=val)
                any_dc_slack = True

                # declare the flow var
                vsc_vars.flows[t_idx, m] = prob.add_var(
                    lb=-vsc_data_t.rates[m] / Sbase,
                    ub=vsc_data_t.rates[m] / Sbase,
                    name=join("vsc_flow_", [t_idx, m], "_")
                )

            elif (vsc_data_t.control1_int[m] == ConverterControlType.Pdc.idx() and
                  vsc_data_t.control2_int[m] == ConverterControlType.Pac.idx()):

                # declare the flow var
                vsc_vars.flows[t_idx, m] = prob.add_var(
                    lb=-vsc_data_t.rates[m] / Sbase,
                    ub=vsc_data_t.rates[m] / Sbase,
                    name=join("vsc_flow_", [t_idx, m], "_")
                )

            elif (vsc_data_t.control1_int[m] == ConverterControlType.Pac.idx() and
                  vsc_data_t.control2_int[m] == ConverterControlType.Pdc.idx()):

                # declare the flow var
                vsc_vars.flows[t_idx, m] = prob.add_var(
                    lb=-vsc_data_t.rates[m] / Sbase,
                    ub=vsc_data_t.rates[m] / Sbase,
                    name=join("vsc_flow_", [t_idx, m], "_")
                )

            else:
                logger.add_error(msg=f"Unsupported controls",
                                 value=f"{vsc_data_t.control1_int[m]}, {vsc_data_t.control2_int[m]}")

            # add the injections matching the flow
            bus_vars.Pbalance[t_idx, fr] += -vsc_vars.flows[t_idx, m]
            bus_vars.Pbalance[t_idx, to] += vsc_vars.flows[t_idx, m]

        else:
            # not active, therefore the flow is exactly zero
            prob.set_var_bounds(var=vsc_vars.flows[t_idx, m], ub=0.0, lb=0.0)

    # add the flows to the objective function
    for k, sense in vsc_vars.inter_space_vsc:
        f_obj += -vsc_vars.flows[t_idx, k] * sense

    if not any_dc_slack and vsc_data_t.nelm > 0:
        logger.add_warning("No DC Slack! set Vm_dc in any of the converters")

    return f_obj


def add_linear_node_balance(t_idx: int,
                            vd: IntVec,
                            bus_data: BusData,
                            bus_vars: BusNtcVars,
                            prob: LpModel,
                            logger: Logger):
    """
    Add the kirchhoff nodal equality
    :param t_idx: time step
    :param vd: Array of slack indices
    :param bus_data: BusData
    :param bus_vars: BusVars
    :param prob: LpModel
    :param logger: Logger
    """

    # Note: At this point, Pbalance has all the devices' power summed up inside (including branches)

    # add the equality restrictions
    for k in range(bus_data.nbus):

        if isinstance(bus_vars.Pbalance[t_idx, k], (int, float)):
            bus_vars.kirchhoff[t_idx, k] = prob.add_cst(
                cst=bus_vars.Va[t_idx, k] == 0,
                name=join("island_bus_", [t_idx, k], "_")
            )
            logger.add_warning("bus isolated",
                               device=bus_data.names[k] + f'@t={t_idx}')

        else:
            bus_vars.kirchhoff[t_idx, k] = prob.add_cst(
                cst=bus_vars.Pbalance[t_idx, k] == 0,
                name=join("kirchhoff_", [t_idx, k], "_"))

    # set this to the set value
    Va = np.angle(bus_data.Vbus)
    for i in vd:
        prob.set_var_bounds(var=bus_vars.Va[t_idx, i], lb=Va[i], ub=Va[i])


def has_pmode3_control(nc: NumericalCircuit) -> bool:
    """Whether there is some converter that needs an angle dependent contingency state."""
    vsc = nc.vsc_data
    hvdc = nc.hvdc_data
    return bool(np.any(vsc.active & (vsc.control1_int == ConverterControlType.Pdc_angle_droop.idx())
                       & (vsc.control2_int == ConverterControlType.Pac.idx()))
                or np.any(hvdc.active & (hvdc.control_mode_int == HvdcControlType.type_0_free.idx())))


def run_linear_ntc_opf(grid: MultiCircuit,
                       t: Union[int, None],
                       solver_type: MIPSolvers = MIPSolvers.HIGHS,
                       zonal_grouping: ZonalGrouping = ZonalGrouping.NoGrouping,
                       skip_generation_limits: bool = False,
                       consider_contingencies: bool = False,
                       corrective_contingencies: bool = True,
                       contingency_groups_used: List[ContingencyGroup] = (),
                       alpha_threshold: float = 0.001,
                       lodf_threshold: float = 0.001,
                       bus_a1_idx: IntVec | None = None,
                       bus_a2_idx: IntVec | None = None,
                       transfer_method: AvailableTransferMode = AvailableTransferMode.InstalledPower,
                       monitor_only_sensitive_branches: bool = True,
                       monitor_only_ntc_load_rule_branches: bool = False,
                       ntc_load_rule: float = 0.7,  # 70%
                       slack_all_limits: bool = False,
                       logger: Logger = Logger(),
                       progress_text: Union[None, Callable[[str], None]] = None,
                       progress_func: Union[None, Callable[[float], None]] = None,
                       verbose: int = 0,
                       robust: bool = False,
                       mip_framework: MIPFramework = MIPFramework.PuLP,
                       max_lazy_rounds: int = 100) -> Tuple[NtcVars, LpModel]:
    """

    :param grid: MultiCircuit instance
    :param t: Time indices (in the general scheme)
    :param solver_type: MIP solver to use
    :param zonal_grouping: Zonal grouping?
    :param skip_generation_limits: Skip the generation limits?
    :param consider_contingencies: Consider the contingencies?
    :param corrective_contingencies: allow corrective (post-contingency) re-dispatch of the VSC/HVDC converters
    :param contingency_groups_used: List of contingency groups to simulate
    :param alpha_threshold: threshold to consider the exchange sensitivity
    :param lodf_threshold: threshold to consider LODF sensitivities
    :param bus_a1_idx: array of bus indices in the area 1
    :param bus_a2_idx: array of bus indices in the area 2
    :param transfer_method: AvailableTransferMode
    :param monitor_only_sensitive_branches
    :param monitor_only_ntc_load_rule_branches
    :param ntc_load_rule: Amount of exchange branches power that should be dedicated to exchange
    :param slack_all_limits: penalized slacks on every monitored branch limit
    :param logger: logger instance
    :param progress_text: function to report text messages
    :param progress_func: function to report progress
    :param verbose: Verbosity level
    :param robust: Robust optimization?
    :param mip_framework: MIPFramework to use
    :param max_lazy_rounds: Maximum number of lazy contingency constraint admission rounds
    :return: NtcVars class with the results
    """
    mode_2_int = {
        AvailableTransferMode.Generation: 0,
        AvailableTransferMode.InstalledPower: 1,
        AvailableTransferMode.Load: 2,
        AvailableTransferMode.GenerationAndLoad: 3
    }

    bus_dict = {bus: i for i, bus in enumerate(grid.buses)}
    areas_dict = {elm: i for i, elm in enumerate(grid.areas)}

    n = grid.get_bus_number()
    nbr = grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True)
    ng = grid.get_generators_number()
    nb = grid.get_batteries_number()
    nl = grid.get_load_like_device_number()
    n_hvdc = grid.get_hvdc_number()
    n_vsc = grid.get_vsc_number()

    # Declare the LP model
    lp_model: LpModel = get_model_instance(tpe=mip_framework, solver_type=solver_type)
    print("Solving NTC with", lp_model.name)
    logger.add_info(f"MIP Framework", value=lp_model.name)
    logger.add_info(f"MIP Solver", value=solver_type.value)

    # declare structures of LP vars
    mip_vars = NtcVars(nt=1, nbus=n, ng=ng, nb=nb, nl=nl, nbr=nbr, n_hvdc=n_hvdc, n_vsc=n_vsc,
                       model=lp_model)

    # objective function
    f_obj = 0.0
    t_idx = 0

    # compile the circuit at the master time index ------------------------------------------------------------
    # note: There are very small chances of simplifying this step and experience shows it is not
    #        worth the effort, so compile every time step
    nc: NumericalCircuit = compile_numerical_circuit_at(circuit=grid,
                                                        t_idx=t,  # yes, this is not a bug
                                                        bus_dict=bus_dict,
                                                        areas_dict=areas_dict,
                                                        logger=logger)

    # The N-1 report divides by these ratings even when no contingency row enters the LP
    mip_vars.branch_vars.contingency_rates[t_idx, :] = nc.passive_branch_data.contingency_rates

    # branch index, branch object, flow sense w.r.t the area exchange
    bus_a1_idx_set = set(bus_a1_idx)
    bus_a2_idx_set = set(bus_a2_idx)

    # find the inter-space branches given the bus indices of each space
    mip_vars.branch_vars.inter_space_branches = nc.passive_branch_data.get_inter_areas(bus_idx_from=bus_a1_idx_set,
                                                                                       bus_idx_to=bus_a2_idx_set)

    mip_vars.hvdc_vars.inter_space_hvdc = nc.hvdc_data.get_inter_areas(bus_idx_from=bus_a1_idx_set,
                                                                       bus_idx_to=bus_a2_idx_set)

    mip_vars.bus_vars.angle_min = nc.bus_data.angle_min
    mip_vars.bus_vars.angle_max = nc.bus_data.angle_max

    # formulate the bus angles ---------------------------------------------------------------------------------
    for k in range(nc.bus_data.nbus):
        if nc.bus_data.is_dc[k]:
            mip_vars.bus_vars.Vm[t_idx, k] = lp_model.add_var(
                lb=nc.bus_data.Vmin[k],
                ub=nc.bus_data.Vmax[k],
                name=join("Vm_", [t_idx, k], "_")
            )
        else:
            mip_vars.bus_vars.Va[t_idx, k] = lp_model.add_var(
                lb=nc.bus_data.angle_min[k],
                ub=nc.bus_data.angle_max[k],
                name=join("Va_", [t_idx, k], "_")
            )

    # formulate injections -------------------------------------------------------------------------------------
    indices = nc.get_simulation_indices()

    inj_f_obj, Pbus = add_linear_injections_formulation(
        t=t_idx,
        Sbase=nc.Sbase,
        gen_data_t=nc.generator_data,
        batt_data_t=nc.battery_data,
        load_data_t=nc.load_data,
        bus_data_t=nc.bus_data,
        branch_data_t=nc.passive_branch_data,
        active_branch_data_t=nc.active_branch_data,
        hvdc_data_t=nc.hvdc_data,
        bus_a1_idx=bus_a1_idx,
        bus_a2_idx=bus_a2_idx,
        transfer_method=transfer_method,
        skip_generation_limits=skip_generation_limits,
        ntc_vars=mip_vars,
        prob=lp_model,
        logger=logger
    )
    # inj_f_obj, Pbus = add_linear_injections_formulation_proper(
    #     t=t_idx,
    #     Sbase=nc.Sbase,
    #     gen_data_t=nc.generator_data,
    #     batt_data_t=nc.battery_data,
    #     load_data_t=nc.load_data,
    #     bus_data_t=nc.bus_data,
    #     branch_data_t=nc.passive_branch_data,
    #     active_branch_data_t=nc.active_branch_data,
    #     hvdc_data_t=nc.hvdc_data,
    #     bus_a1_idx=bus_a1_idx,
    #     bus_a2_idx=bus_a2_idx,
    #     transfer_method=transfer_method,
    #     skip_generation_limits=skip_generation_limits,
    #     ntc_vars=mip_vars,
    #     prob=lp_model,
    #     logger=logger
    # )
    f_obj += inj_f_obj

    # formulate hvdc -------------------------------------------------------------------------------------------
    f_obj += add_linear_hvdc_formulation(
        t_idx=t_idx,
        Sbase=nc.Sbase,
        hvdc_data_t=nc.hvdc_data,
        hvdc_vars=mip_vars.hvdc_vars,
        vars_bus=mip_vars.bus_vars,
        prob=lp_model,
        logger=logger,
        saturate=True
    )

    # formulate vsc -------------------------------------------------------------------------------------------
    f_obj += add_linear_vsc_formulation(
        t_idx=t_idx,
        Sbase=nc.Sbase,
        vsc_data_t=nc.vsc_data,
        vsc_vars=mip_vars.vsc_vars,
        bus_vars=mip_vars.bus_vars,
        prob=lp_model,
        logger=logger,
        sat_rates=compute_vsc_pmode3_saturation_rates(vsc_data_t=nc.vsc_data,
                                                      branch_data_t=nc.passive_branch_data,
                                                      bus_data_t=nc.bus_data)
    )

    # lazy formulation state is filled when contingencies are on and there are groups
    controlled_states: CompactContingencies | None = None
    report_mctg: LinearMultiContingencies | None = None
    lazy_mctg: Union[LinearMultiContingencies, None] = None
    lazy_alpha_n1: Union[Mat, None] = None

    if zonal_grouping == ZonalGrouping.NoGrouping:

        # declare the linear analysis and compute the PTDF and LODF
        # converters_as_setpoint makes the sensitivities, monitoring and base loadings
        # the same for every converter control mode of the grid, so
        # the NTC of the Pmode1 and Pmode3 builds stays comparable (Pmode1 >= Pmode3)
        ls = LinearAnalysis(nc=nc,
                            distributed_slack=False,
                            correct_values=True,
                            converters_as_setpoint=True,
                            logger=logger)

        # compute the power flow
        # get_flows works in MW while this formulation works in p.u., so convert in and out
        branch_flows = ls.get_flows(Pbus.real * nc.Sbase) / nc.Sbase
        branch_loading = branch_flows / (nc.passive_branch_data.rates / nc.Sbase + 1e-20)

        # compute the sensitivity to the exchange
        dP = compute_dP(
            P0=Pbus.real,  # already scaled within add_linear_injections_formulation
            P_installed=nc.bus_data.installed_power,
            Pgen=nc.generator_data.get_injections_per_bus().real,
            Pload=nc.load_data.get_injections_per_bus().real,
            bus_a1_idx=bus_a1_idx,
            bus_a2_idx=bus_a2_idx,
            mode=mode_2_int[transfer_method],
            dT=1.0
        )

        alpha = compute_alpha(
            ptdf=ls.PTDF,
            dP=dP,
            dT=1.0
        )

        mip_vars.branch_vars.alpha[t_idx, :] = alpha

        # compute the structural NTC: this is the sum of ratings in the inter-area
        structural_ntc = nc.get_structural_ntc(bus_a1_idx=bus_a1_idx, bus_a2_idx=bus_a2_idx)
        mip_vars.structural_ntc[t_idx] = structural_ntc

        # formulate branches -----------------------------------------------------------------------------------

        f_obj += add_linear_branches_formulation(
            t_idx=t_idx,
            Sbase=nc.Sbase,
            branch_data_t=nc.passive_branch_data,
            active_branch_data_t=nc.active_branch_data,
            branch_vars=mip_vars.branch_vars,
            bus_vars=mip_vars.bus_vars,
            prob=lp_model,
            monitor_only_sensitive_branches=monitor_only_sensitive_branches,
            monitor_only_ntc_load_rule_branches=monitor_only_ntc_load_rule_branches,
            alpha=alpha,
            alpha_threshold=alpha_threshold,
            structural_ntc=float(structural_ntc),
            ntc_load_rule=ntc_load_rule,
            loading=branch_loading,
            logger=logger,
            inf=1e20,
            slack_all_limits=slack_all_limits,
        )

        # formulate nodes ---------------------------------------------------------------------------------------
        add_linear_node_balance(t_idx=t_idx,
                                vd=indices.vd,
                                bus_data=nc.bus_data,
                                bus_vars=mip_vars.bus_vars,
                                prob=lp_model,
                                logger=logger)

        # formulate contingencies --------------------------------------------------------------------------------

        if consider_contingencies:

            if len(contingency_groups_used) > 0:

                has_pmode3: bool = has_pmode3_control(nc)

                # declare the multi-contingencies analysis and compute
                mctg = LinearMultiContingencies(grid=grid,
                                                contingency_groups_used=contingency_groups_used)
                mctg.compute(lin=ls,
                             ptdf_threshold=lodf_threshold,
                             lodf_threshold=lodf_threshold,
                             with_corrective_converter_df=corrective_contingencies and not has_pmode3)

                alpha_n1 = compute_alpha_n1(
                    ptdf=ls.PTDF,
                    lodf=ls.LODF,
                    alpha=alpha,
                    dP=dP,
                    dT=1.0
                )

                # Pmode3 needs physical states even when fixed-power screening is clean.
                # Other control modes retain the existing lazy flow-factor formulation.
                report_mctg = mctg
                if corrective_contingencies and has_pmode3:
                    # the feasibility retry also absorbs every part a contingency cuts off
                    controlled_states = CompactContingencies(
                        nc=nc, base_vars=mip_vars, multi_contingencies=mctg,
                        prob=lp_model, logger=logger, absorb_islands=slack_all_limits)
                else:
                    lazy_mctg = mctg
                    lazy_alpha_n1 = alpha_n1

            else:
                print("Contingencies enabled, but no contingency groups provided")
                logger.add_warning(msg="Contingencies enabled, but no contingency groups provided. "
                                       "You need to add them in the OptimalPowerFlowOptions")

    elif zonal_grouping == ZonalGrouping.All:
        # this is the copper plate approach
        pass

    # set the objective function
    lp_model.minimize(f_obj)

    # solve
    if progress_text is not None:
        progress_text("Solving...")

    if progress_func is not None:
        progress_func(0)

    # solve the model
    status = lp_model.solve(robust=robust, show_logs=verbose > 0, progress_text=progress_text)

    admitted_rows: Dict[int, BoolVec] = dict()
    vsc_delta_store: Dict[int, Dict[int, LpVar]] = dict()
    hvdc_delta_store: Dict[int, Dict[int, LpVar]] = dict()
    preservation_done: Set[int] = set()
    n_rows_admitted = 0

    # least control effort second stage, applied after every first stage solve
    effort: List[LpExp] = list()
    effort_counted: Set[Tuple[int, int, int]] = set()
    transfer: LpVar = mip_vars.delta_1[t_idx]

    # the N-1 screening never ran out of rounds unless proven otherwise
    screening_certified: bool = True

    if controlled_states is not None:
        status = controlled_states.solve(f_obj, status, robust=robust, show_logs=verbose > 0,
                                         progress=SolverProgress(progress_text))
    else:
        add_base_control_effort(prob=lp_model, t_idx=t_idx,
                                branch_data_t=nc.passive_branch_data,
                                active_branch_data_t=nc.active_branch_data,
                                branch_vars=mip_vars.branch_vars,
                                vsc_vars=mip_vars.vsc_vars,
                                hvdc_vars=mip_vars.hvdc_vars,
                                effort=effort)
        if status == lp_model.OPTIMAL and len(effort) > 0:
            status = solve_least_control_effort(prob=lp_model, objective=f_obj, transfer=transfer, effort=effort,
                                                logger=logger, robust=robust, show_logs=verbose > 0,
                                                progress_text=progress_text)
        else:
            pass  # nothing to choose among the optima, or the first stage failed

    if lazy_mctg is not None:
        monitorable_lazy = get_contingency_monitorable_branches(
            branch_data_t=nc.passive_branch_data,
            branch_vars=mip_vars.branch_vars,
            t_idx=t_idx,
            corrective_contingencies=corrective_contingencies,
            monitor_only_sensitive_branches=monitor_only_sensitive_branches,
            monitor_only_ntc_load_rule_branches=monitor_only_ntc_load_rule_branches,
            alpha_threshold=alpha_threshold,
            alpha_n1=lazy_alpha_n1,
            structural_ntc=float(mip_vars.structural_ntc[t_idx]),
            ntc_load_rule=ntc_load_rule
        )

        for lazy_branch_m, _lazy_branch_sense in mip_vars.branch_vars.inter_space_branches:
            monitorable_lazy[lazy_branch_m] = True
        monitorable_lazy = monitorable_lazy | (nc.passive_branch_data.dc.astype(bool)
                                               & nc.passive_branch_data.monitor_loading.astype(bool))
        con_rates_pu_lazy = nc.passive_branch_data.contingency_rates / nc.Sbase

        lazy_round: int = 0
        clean_pass: bool = False
        while lazy_round < max_lazy_rounds and status == lp_model.OPTIMAL and not clean_pass:
            # numeric snapshot of the solved operating point
            f0_num: Vec = np.array([lp_model.get_value(x) for x in mip_vars.branch_vars.flows[t_idx, :]])
            hvdc0_num: Vec = np.array([lp_model.get_value(x) for x in mip_vars.hvdc_vars.flows[t_idx, :]])
            vsc0_num: Vec = np.array([lp_model.get_value(x) for x in mip_vars.vsc_vars.flows[t_idx, :]])
            inj0_num: Vec = np.array([lp_model.get_value(x) for x in mip_vars.bus_vars.Pinj[t_idx, :]])

            # numeric flow change of every admitted corrective group's solved Δ set-points
            delta_addons: Dict[int, Vec] = evaluate_corrective_flow_addons(
                multi_contingencies=lazy_mctg.multi_contingencies,
                group_indices=list(admitted_rows.keys()),
                vsc_delta_store=vsc_delta_store,
                hvdc_delta_store=hvdc_delta_store,
                n_vsc=nc.vsc_data.nelm,
                n_hvdc=nc.hvdc_data.nelm,
                n_branch=nc.passive_branch_data.nelm,
                model=lp_model,
            )

            admissions: List[Tuple[int, IntVec]] = screen_contingency_violations(
                multi_contingencies=lazy_mctg.multi_contingencies,
                admitted_rows=admitted_rows,
                f0=f0_num, hvdc0=hvdc0_num, vsc0=vsc0_num, inj0=inj0_num,
                monitorable=monitorable_lazy,
                con_rates_pu=con_rates_pu_lazy,
                tol_pu=1e-4,
                at_risk_fraction=0.9,
                delta_flow_addons=delta_addons
            )

            if len(admissions) == 0:
                # clean screening pass as the solution survives every contingency group
                clean_pass = True
            else:
                # per group row lookup for the formulation call
                group_rows_now: Dict[int, IntVec] = dict()
                for c_new, rows_new in admissions:
                    group_rows_now[int(c_new)] = rows_new

                f_obj += add_linear_branches_contingencies_formulation(
                    t_idx=t_idx,
                    Sbase=nc.Sbase,
                    branch_data_t=nc.passive_branch_data,
                    branch_vars=mip_vars.branch_vars,
                    bus_vars=mip_vars.bus_vars,
                    hvdc_vars=mip_vars.hvdc_vars,
                    vsc_vars=mip_vars.vsc_vars,
                    prob=lp_model,
                    linear_multi_contingencies=lazy_mctg,
                    monitor_only_sensitive_branches=monitor_only_sensitive_branches,
                    monitor_only_ntc_load_rule_branches=monitor_only_ntc_load_rule_branches,
                    structural_ntc=float(mip_vars.structural_ntc[t_idx]),
                    ntc_load_rule=ntc_load_rule,
                    alpha_threshold=alpha_threshold,
                    alpha_n1=lazy_alpha_n1,
                    corrective_contingencies=corrective_contingencies,
                    vsc_active=nc.vsc_data.active,
                    hvdc_active=nc.hvdc_data.active,
                    group_indices=np.array([c_new for c_new, _ in admissions], dtype=int),
                    group_rows=group_rows_now,
                    vsc_delta_store=vsc_delta_store,
                    hvdc_delta_store=hvdc_delta_store,
                    preservation_done=preservation_done
                )

                # record the admitted rows so the screening skips them from now on
                for c_new, rows_new in admissions:
                    mask_prev: Union[BoolVec, None] = admitted_rows.get(int(c_new), None)
                    if mask_prev is None:
                        mask_prev = np.zeros(nc.passive_branch_data.nelm, dtype=bool)
                        admitted_rows[int(c_new)] = mask_prev
                    else:
                        pass  # extending the group existing admission
                    mask_prev[rows_new] = True
                    n_rows_admitted += len(rows_new)

                # first stage again, the new rows may lower the reachable transfer, so free it
                lp_model.set_var_bounds(var=transfer, lb=0.0, ub=lp_model.INFINITY)
                lp_model.minimize(f_obj)
                status = lp_model.solve(robust=robust, show_logs=verbose > 0, progress_text=progress_text)

                # second stage: also pin the new corrective Δ, so they cannot wander onto unchecked rows
                add_corrective_control_effort(prob=lp_model, vsc_delta_store=vsc_delta_store,
                                              hvdc_delta_store=hvdc_delta_store,
                                              counted=effort_counted, effort=effort)
                if status == lp_model.OPTIMAL and len(effort) > 0:
                    status = solve_least_control_effort(prob=lp_model, objective=f_obj, transfer=transfer,
                                                        effort=effort, logger=logger, robust=robust,
                                                        show_logs=verbose > 0, progress_text=progress_text)
                else:
                    pass  # nothing to choose among the optima, or the first stage failed
                lazy_round += 1

        if status == lp_model.OPTIMAL and not clean_pass:
            # unchecked contingency rows may still be violated, so the hour is not certified
            screening_certified = False
            logger.add_error("N-1 screening did not converge within the round budget, the solution is not "
                             "certified against every contingency",
                             value=f"{max_lazy_rounds} rounds, {n_rows_admitted} rows admitted")
        else:
            pass  # certified by a clean screening pass, or the solve failed and is reported below
    else:
        pass  # no lazy contingency screening for this formulation

    if lazy_mctg is not None:
        logger.add_info("Lazy contingency formulation: groups/rows added",
                        value=f"{len(admitted_rows)} groups, {n_rows_admitted} rows "
                              f"of {len(lazy_mctg.multi_contingencies)} groups")
    else:
        pass  # no lazy formulation was used

    if is_infeasible(model=lp_model, status=status) and not slack_all_limits:
        # Feasibility retry. Rebuild once with the penalized slack for every 
        # monitored limit so the answer is reported as slack instead of a failure. 
        logger.add_warning("Infeasible with hard branch limits, retrying with all "
                           "monitored limits slacked",
                           value=lp_model.status2string(status))
        # this attempt is discarded, so release its compact states (see the end of this function)
        if controlled_states is not None:
            controlled_states.states.fill(None)
        else:
            pass  # no compact contingency states to release
        return run_linear_ntc_opf(grid=grid, t=t, solver_type=solver_type,
                                  zonal_grouping=zonal_grouping,
                                  skip_generation_limits=skip_generation_limits,
                                  consider_contingencies=consider_contingencies,
                                  corrective_contingencies=corrective_contingencies,
                                  contingency_groups_used=contingency_groups_used,
                                  alpha_threshold=alpha_threshold,
                                  lodf_threshold=lodf_threshold,
                                  bus_a1_idx=bus_a1_idx, bus_a2_idx=bus_a2_idx,
                                  transfer_method=transfer_method,
                                  monitor_only_sensitive_branches=monitor_only_sensitive_branches,
                                  monitor_only_ntc_load_rule_branches=monitor_only_ntc_load_rule_branches,
                                  ntc_load_rule=ntc_load_rule,
                                  slack_all_limits=True,
                                  logger=logger,
                                  progress_text=progress_text,
                                  progress_func=progress_func,
                                  verbose=verbose, robust=robust,
                                  mip_framework=mip_framework,
                                  max_lazy_rounds=max_lazy_rounds)
    else:
        pass  # solved, or the retry already ran

    # gather the results
    logger.add_info(msg="Status", value=lp_model.status2string(status))

    if status == lp_model.OPTIMAL:
        # the transfer objective, not the second stage effort the model last minimised
        logger.add_info("Objective function", value=lp_model.get_value(f_obj))
        mip_vars.acceptable_solution[t_idx] = screening_certified
    else:
        logger.add_error('The problem does not have an optimal solution.')
        mip_vars.acceptable_solution[t_idx] = False
        lp_file_name = os.path.join(opf_file_path(), f"{grid.name} ntc debug.lp")
        lp_model.save_model(file_name=lp_file_name)
        logger.add_info("Debug LP model saved", value=lp_file_name)

    # gather the values of the variables
    vars_v = mip_vars.get_values(Sbase=grid.Sbase, model=lp_model)

    if controlled_states is None:
        reporting_contingencies = report_mctg
        solved_flows = None
    elif controlled_states.complete:
        reporting_contingencies = report_mctg
        solved_flows = controlled_states
    else:
        reporting_contingencies = None
        solved_flows = None

    # The worst contingency report must reflect the same corrected N-1 state the limits
    # were enforced
    corrective_addons_mw: Union[Dict[int, Vec], None] = None
    if status == lp_model.OPTIMAL and lazy_mctg is not None:
        final_addons_pu: Dict[int, Vec] = evaluate_corrective_flow_addons(
            multi_contingencies=lazy_mctg.multi_contingencies,
            group_indices=list(admitted_rows.keys()),
            vsc_delta_store=vsc_delta_store,
            hvdc_delta_store=hvdc_delta_store,
            n_vsc=nc.vsc_data.nelm,
            n_hvdc=nc.hvdc_data.nelm,
            n_branch=nc.passive_branch_data.nelm,
            model=lp_model,
        )
        if len(final_addons_pu) > 0:
            corrective_addons_mw = {c: addon * grid.Sbase for c, addon in final_addons_pu.items()}
        else:
            pass  # preventive run or no corrective move so we report the preventive flows
    else:
        pass  # failed solve or no lazy formulation so report the preventive flows

    # one numeric N-1 pass on the final operating point
    fill_worst_contingency_per_branch(
        grid=grid,
        multi_contingencies=reporting_contingencies,
        f0_mw=np.asarray(vars_v.branch_vars.flows[t_idx, :], dtype=float),
        hvdc0_mw=np.asarray(vars_v.hvdc_vars.flows[t_idx, :], dtype=float),
        vsc0_mw=np.asarray(vars_v.vsc_vars.flows[t_idx, :], dtype=float),
        inj0_mw=np.asarray(vars_v.bus_vars.Pinj[t_idx, :], dtype=float),
        contingency_rates_mw=np.asarray(vars_v.branch_vars.contingency_rates[t_idx, :], dtype=float),
        alpha=np.asarray(vars_v.branch_vars.alpha[t_idx, :], dtype=float),
        worst_idx=vars_v.branch_vars.worst_contingency_idx[t_idx, :],
        worst_flow=vars_v.branch_vars.worst_contingency_flow[t_idx, :],
        worst_loading=vars_v.branch_vars.worst_contingency_loading[t_idx, :],
        alpha_n1_worst=vars_v.branch_vars.alpha_n1_worst[t_idx, :],
        tied_groups=vars_v.branch_vars.worst_contingency_ties,
        branch_data=nc.passive_branch_data,
        solved_flows=solved_flows,
        corrective_addons_mw=corrective_addons_mw,
    )

    # The compact states and their coordinator reference each other through a numpy object
    # array, which the garbage collector cannot traverse: without this release every hour
    # leaked its whole LP (~470 MB per hour on the 6000 h national grid)
    if controlled_states is not None:
        controlled_states.states.fill(None)
    else:
        pass  # no compact contingency states to release

    # fill the power shift
    vars_v.power_shift = vars_v.bus_vars.delta_p[:, bus_a1_idx]

    # The area 1 increase must equal the area 2 decrease. The balance slacks carry no cost, so only
    # their difference (= delta_1 - delta_2) is a mismatch
    area_mismatch_mw: float = abs(vars_v.delta_1[t_idx] - vars_v.delta_2[t_idx]) * grid.Sbase
    if area_mismatch_mw > 1e-3:
        logger.add_error(msg="Area 1 increase and area 2 decrease differ (MW)",
                         value=area_mismatch_mw, expected_value=0.0)
    else:
        pass  # both areas moved the same power

    # Kirchhoff balance of every networked bus (MW). Isolated buses were reported when formulated
    bus_k: int
    for bus_k in range(nc.bus_data.nbus):
        if isinstance(mip_vars.bus_vars.Pbalance[t_idx, bus_k], (int, float)):
            pass  # isolated bus, no balance equation
        elif abs(vars_v.bus_vars.Pbalance[t_idx, bus_k]) > 1e-3:
            logger.add_error(msg="Nodal balance not fulfilled (MW)", device=nc.bus_data.names[bus_k],
                             value=vars_v.bus_vars.Pbalance[t_idx, bus_k], expected_value=0.0)
        else:
            pass  # balanced within tolerance

    # add the model logger to the main logger
    logger += lp_model.logger

    # ------------------------------------------------------------------------------------------------------------------
    # Total inter area flows

    # List of (branch index, branch object, flow sense w.r.t the area exchange)
    inter_info = nc.passive_branch_data.get_inter_areas(bus_idx_from=bus_a1_idx, bus_idx_to=bus_a2_idx)
    inter_area_branch_idx = [x[0] for x in inter_info]
    inter_area_branch_sense = [x[1] for x in inter_info]

    inter_info_hvdc = nc.hvdc_data.get_inter_areas(bus_idx_from=bus_a1_idx, bus_idx_to=bus_a2_idx)
    inter_area_hvdc_idx = [x[0] for x in inter_info_hvdc]
    inter_area_hvdc_sense = [x[1] for x in inter_info_hvdc]

    inter_info_vsc = nc.vsc_data.get_inter_areas(bus_idx_from=bus_a1_idx, bus_idx_to=bus_a2_idx)
    inter_area_vsc_idx: List[int] = [x[0] for x in inter_info_vsc]
    inter_area_vsc_sense: List[float] = [x[1] for x in inter_info_vsc]

    for k in inter_area_branch_idx:
        logger.add_info("Inter area branch", device=f"({k}) - {nc.passive_branch_data.names[k]}",
                        value=vars_v.branch_vars.flows[t_idx, k])

    for k in inter_area_hvdc_idx:
        logger.add_info("Inter area HvdcLine", device=f"({k}) - {nc.hvdc_data.names[k]}",
                        value=vars_v.hvdc_vars.flows[t_idx, k])

    for k in inter_area_vsc_idx:
        logger.add_info("Inter area Vsc", device=f"({k}) - {nc.vsc_data.names[k]}",
                        value=vars_v.vsc_vars.flows[t_idx, k])

    for k, (sl_up, sl_down) in enumerate(zip(vars_v.branch_vars.flow_slacks_pos[t_idx, :],
                                             vars_v.branch_vars.flow_slacks_neg[t_idx, :])):
        if sl_up > 0.0:
            logger.add_warning("Overload (+)", device=f"({k}) - {nc.passive_branch_data.names[k]}", value=sl_up)

        if sl_down > 0.0:
            logger.add_warning("Overload (-)", device=f"({k}) - {nc.passive_branch_data.names[k]}", value=sl_down)

    # Report the post-contingency limits that had to be relaxed to keep the LP feasible:
    # these are structural N-1 overloads the dispatch cannot avoid, and the NTC result is
    # only meaningful knowing they exist.
    n_relaxed: int = 0
    largest_slack_mw: float = 0.0
    largest_device: str = ""
    for (t_c, m_c, c_c, flow_c, neg_sl, pos_sl) in vars_v.branch_vars.contingency_flow_data:
        if isinstance(neg_sl, float) and isinstance(pos_sl, float):
            slack_mw: float = abs(neg_sl) + abs(pos_sl)
            if slack_mw > 1e-6:
                n_relaxed += 1
                if slack_mw > largest_slack_mw:
                    largest_slack_mw = slack_mw
                    largest_device = f"({m_c}) - {nc.passive_branch_data.names[m_c]} @ctg {c_c}"
                else:
                    pass  # a smaller relaxation than the largest so far
            else:
                # the limit held without relaxation
                pass
        else:
            # the slack was not evaluated to a number (should not happen after get_values)
            pass
    if n_relaxed > 0:
        logger.add_warning("Unavoidable post-contingency overloads (limits relaxed)",
                           device=f"largest: {largest_device}",
                           value=f"{n_relaxed} rows, largest {largest_slack_mw:.3f} MW")
    else:
        pass  # every post-contingency limit held

    # The summation of flow increments in the inter-area branches must be ΔP in A1.
    vars_v.inter_area_flows[t_idx] = (
            np.sum(vars_v.branch_vars.flows[t_idx, inter_area_branch_idx] * inter_area_branch_sense)
            + np.sum(vars_v.hvdc_vars.flows[t_idx, inter_area_hvdc_idx] * inter_area_hvdc_sense)
            + np.sum(vars_v.vsc_vars.flows[t_idx, inter_area_vsc_idx] * inter_area_vsc_sense)
    )

    logger.add_info("Structural inter-area rate", value=vars_v.structural_ntc[t_idx])
    logger.add_info("Inter-area NTC", value=vars_v.inter_area_flows[t_idx])

    # summary of the limit-relaxation slacks
    base_slack_mw: float = (float(np.sum(np.abs(vars_v.branch_vars.flow_slacks_pos[t_idx, :])))
                            + float(np.sum(np.abs(vars_v.branch_vars.flow_slacks_neg[t_idx, :]))))
    ctg_slack_mw: float = 0.0
    for slack_item in vars_v.branch_vars.contingency_flow_data:
        t_s, m_s, c_s, flow_s, neg_s, pos_s = slack_item
        if isinstance(neg_s, float) and isinstance(pos_s, float):
            ctg_slack_mw += abs(neg_s) + abs(pos_s)
        else:
            pass  # slack not evaluated to a number, nothing to add
    logger.add_info("Total base overload slack (MW)", value=base_slack_mw)
    logger.add_info("Total contingency relaxation slack (MW)", value=ctg_slack_mw)
    logger.add_info("Total slack (MW)", value=base_slack_mw + ctg_slack_mw, expected_value=0.1)

    return vars_v, lp_model
