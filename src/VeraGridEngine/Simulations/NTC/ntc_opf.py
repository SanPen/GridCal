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
from typing import List, Union, Tuple, Callable

from VeraGridEngine.enumerations import MIPSolvers, ZonalGrouping
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Aggregation.contingency_group import ContingencyGroup
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
from VeraGridEngine.Utils.MIP.selected_interface import LpExp, LpVar, LpModel, join
from VeraGridEngine.enumerations import TapPhaseControl, HvdcControlType, AvailableTransferMode, ConverterControlType
from VeraGridEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis, LinearMultiContingencies
from VeraGridEngine.Simulations.ATC.available_transfer_capacity_driver import compute_alpha, compute_alpha_n1, compute_dP
from VeraGridEngine.IO.file_system import opf_file_path


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
    gen_per_bus = gen_data_t.get_injections_per_bus() / Sbase
    load_per_bus = load_data_t.get_injections_per_bus() / Sbase
    pinst_per_bus = gen_data_t.get_installed_power_per_bus() / Sbase

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
        dispatchable_bus = gen_data_t.get_dispatchable_per_bus().astype(float)

    elif transfer_method == AvailableTransferMode.Generation:
        p_ref = gen_per_bus

        if skip_generation_limits:
            p_min = np.full(bus_data_t.nbus, -inf_value)
            p_max = np.full(bus_data_t.nbus, inf_value)

        else:
            p_min = gen_data_t.get_pmin_per_bus() / Sbase
            p_max = gen_data_t.get_pmax_per_bus() / Sbase

        # dispatchable_bus = (gen_data_t.C_bus_elm * gen_data_t.dispatchable).astype(bool).astype(float)
        dispatchable_bus = gen_data_t.get_dispatchable_per_bus().astype(float)

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
    :return: proportions (rounded)
    """
    proportions_a1 = get_sensed_proportions(power=power, idx=bus_a1_idx, logger=logger)
    proportions_a2 = get_sensed_proportions(power=power, idx=bus_a2_idx, logger=logger)
    proportions = proportions_a1 - proportions_a2

    return np.round(proportions, decimals)


def pmode3_formulation(prob, t_idx, m, rate, P0, droop, theta_f, theta_t):
    """
    Formulation
    ------------------------------------------------------------

    1. Region selector:
        z_neg + z_mid + z_pos == 1

    2. Linear flow equation:
        flow_lin == P0 + k * (theta_f - theta_t)

    3. Lower region:  flow = -rate if z_neg == 1
        flow <= -rate + M * (1 - z_neg)
        flow >= -rate - M * (1 - z_neg)
        flow_lin <= -rate + M * (1 - z_neg)

    4. Mid region:    flow = flow_lin if z_mid == 1
        flow <= flow_lin + M * (1 - z_mid)
        flow >= flow_lin - M * (1 - z_mid)
        flow_lin <= rate - epsilon + M * (1 - z_mid)
        flow_lin >= -rate + epsilon - M * (1 - z_mid)

    5. Upper region:  flow = rate if z_pos == 1
        flow <= rate + M * (1 - z_pos)
        flow >= rate - M * (1 - z_pos)
        flow_lin >= rate - M * (1 - z_pos)
    """

    flow = prob.add_var(
        lb=-prob.INFINITY,
        ub=prob.INFINITY,
        name=join("hvdc_flow_", [t_idx, m], "_")
    )
    z_neg = prob.add_int(lb=0, ub=1, name=join("hvdc_zn_", [t_idx, m], "_"))
    z_mid = prob.add_int(lb=0, ub=1, name=join("hvdc_zm_", [t_idx, m], "_"))
    z_pos = prob.add_int(lb=0, ub=1, name=join("hvdc_zp_", [t_idx, m], "_"))

    M = 2 * rate  # M >= 2 * rate
    epsilon = 1e-4

    # 1. Region selector -------------------------------------------------------------------------------
    prob.add_cst(
        cst=z_neg + z_mid + z_pos == 1.0,
        name=join("region_sel_", [t_idx, m], "_")
    )

    # 2. Linear flow equation --------------------------------------------------------------------------
    flow_lin = P0 + droop * (theta_f - theta_t)

    # 3. Lower region:  flow = -rate if z_neg == 1 -----------------------------------------------------
    prob.add_cst(
        cst=flow <= -rate + M * (1 - z_neg),
        name=join("hvdc_lower1_", [t_idx, m], "_")
    )
    prob.add_cst(
        cst=flow >= -rate - M * (1 - z_neg),
        name=join("hvdc_lower2_", [t_idx, m], "_")
    )
    prob.add_cst(
        cst=flow_lin <= -rate + M * (1 - z_neg),
        name=join("hvdc_lower3_", [t_idx, m], "_")
    )

    # 4. Mid-region: flow = flow_lin if z_mid == 1 -----------------------------------------------------
    prob.add_cst(
        cst=flow <= flow_lin + M * (1 - z_mid),
        name=join("hvdc_mid1_", [t_idx, m], "_")
    )
    prob.add_cst(
        cst=flow >= flow_lin - M * (1 - z_mid),
        name=join("hvdc_mid2_", [t_idx, m], "_")
    )
    prob.add_cst(
        cst=flow_lin <= rate - epsilon + M * (1 - z_mid),
        name=join("hvdc_mid3_", [t_idx, m], "_")
    )
    prob.add_cst(
        cst=flow_lin >= -rate + epsilon - M * (1 - z_mid),
        name=join("hvdc_mid4_", [t_idx, m], "_")
    )

    # 5. Upper region: flow = rate if z_pos == 1 -------------------------------------------------------
    prob.add_cst(
        cst=flow <= rate + M * (1 - z_pos),
        name=join("hvdc_upper1_", [t_idx, m], "_")
    )
    prob.add_cst(
        cst=flow >= rate - M * (1 - z_pos),
        name=join("hvdc_upper2_", [t_idx, m], "_")
    )
    prob.add_cst(
        cst=flow_lin >= rate - M * (1 - z_pos),
        name=join("hvdc_upper3_", [t_idx, m], "_")
    )

    return flow


def pmode3_formulation2(prob, t_idx, m, rate, P0, droop, theta_f, theta_t, base_name: str = "hvdc"):
    """
    Formulation
    ------------------------------------------------------------

    Variables:
      flow continuous
      flow_lin continuous
      z1 binary
      z2 binary

    Constraints:
      pmode3_eq: flow_lin = P0 + k * (th_f - th_t)

      upper_bound_flow_le: flow <= rate + M * z1
      upper_bound_flowlin_le: flow_lin - rate <= M * (1 - z1)
      upper_bound_flow_ge: flow >= rate - M * (1 - z1)

      lower_bound_flow_ge: flow >= -rate - M * z2
      lower_bound_flowlin_ge: -rate - flow_lin <= M * (1 - z2)
      lower_bound_flow_le: flow <= -rate + M * (1 - z2)

      intermediate_flow_le: flow <= flow_lin + M * (z1 + z2)
      intermediate_flow_ge: flow >= flow_lin - M * (z1 + z2)
      intermediate_always_true: 1 - z1 - z2 <= 1

      single_case_active: z1 + z2 <= 1
    """

    flow = prob.add_var(
        lb=-prob.INFINITY,
        ub=prob.INFINITY,
        name=join(f"{base_name}_flow_", [t_idx, m], "_")
    )

    flow_lin = prob.add_var(
        lb=-prob.INFINITY,
        ub=prob.INFINITY,
        name=join("pmode3_eq", [t_idx, m], "_")
    )
    z1 = prob.add_int(lb=0, ub=1, name=join(f"{base_name}_z1_", [t_idx, m], "_"))
    z2 = prob.add_int(lb=0, ub=1, name=join(f"{base_name}_z2_", [t_idx, m], "_"))

    M = 2 * rate  # exactly this

    prob.add_cst(flow_lin == P0 + droop * (theta_f - theta_t), name=f"flow_lin_def_{t_idx}_{m}")

    # upper violation
    prob.add_cst(flow <= rate + M * z1, name=f"upper_bound_flow_le_{t_idx}_{m}")
    prob.add_cst(flow_lin - rate <= M * (1 - z1), name=f"upper_bound_flowlin_le_{t_idx}_{m}")
    prob.add_cst(flow >= rate - M * (1 - z1), name=f"upper_bound_flow_ge_{t_idx}_{m}")

    # lower violation
    prob.add_cst(flow >= -rate - M * z2, name=f"lower_bound_flow_ge_{t_idx}_{m}")
    prob.add_cst(-rate - flow_lin <= M * (1 - z2), name=f"lower_bound_flowlin_ge_{t_idx}_{m}")
    prob.add_cst(flow <= -rate + M * (1 - z2), name=f"lower_bound_flow_le_{t_idx}_{m}")

    # intermediate
    prob.add_cst(flow <= flow_lin + M * (z1 + z2), name=f"intermediate_flow_le_{t_idx}_{m}")
    prob.add_cst(flow >= flow_lin - M * (z1 + z2), name=f"intermediate_flow_ge_{t_idx}_{m}")
    prob.add_cst(1 - z1 - z2 <= 1, name=f"intermediate_always_true_{t_idx}_{m}")

    # only one option at a time
    prob.add_cst(z1 + z2 <= 1, name=f"single_case_active_{t_idx}_{m}")

    return flow


def formulate_lp_abs_value(prob: LpModel, lp_var: LpVar, ub: float, M: float, name: str):
    """
    Generic function to compute lp abs variable
    :param prob: lp solver instance
    :param lp_var: variable to make abs
    :param ub: variable upper bound
    :param M: float value represents infinity
    :param name: variable name
    :return: abs variable, boolean to define sense
    """

    # define abs variable
    lp_var_abs = prob.add_var(lb=0, ub=ub, name=name)

    z = formulate_lp_piece_wise(
        solver=prob,
        lp_var=lp_var_abs,
        higher_exp=lp_var,
        lower_exp=-lp_var,
        condition=lp_var,
        M=M,
        name='sense_' + name)

    return lp_var_abs, z


def formulate_lp_piece_wise(
        solver: LpModel,
        lp_var: Union[float, LpVar],
        higher_exp: Union[float, LpExp, LpVar],
        lower_exp: Union[float, LpExp, LpVar],
        condition: Union[float, LpExp, LpVar],
        name: str,
        M: float):
    """
    Generic function to implement piece wise linear function
    :param solver: lp solver instance
    :param lp_var: output variable
    :param higher_exp: expresion when condition >= 0
    :param lower_exp: expresion when condition <= 0
    :param condition: bounding condition
    :param name: output variable name
    :param M: Value representing the infinite (i.e. 1e20)
    :return: lp_var, boolean indicating condition behavior
    """

    # Boolean variable to set step. 4 equations:
    '''
    Z boolean variable to define condition behavior
       z = 1: cond <= 0
       z = 0: cond >= 0
    '''
    z = solver.add_int(name='z_' + name, lb=0, ub=1)

    '''
    Behavior implementation:
        Exp1 - M * (1-z) <= y <= Exp1 + M (1- z)
        Exp2 - M * z <= y <= Exp2 + M * z
    '''
    solver.add_cst(higher_exp - M * z <= lp_var)
    solver.add_cst(lp_var <= higher_exp + M * z)

    solver.add_cst(lower_exp - M * (1 - z) <= lp_var)
    solver.add_cst(lp_var <= lower_exp + M * (1 - z))

    '''
    Define w = cond * z:
        To avoid boolean variable * variable
    '''
    # Formulate conditions
    w = solver.add_var(lb=-M, ub=M, name='w_' + name)

    '''
    Define z=1 if cond <=0 and z=0 if cond >= 0
       cond * (1-z) >= 0
       cond * z <= 0
    '''
    solver.add_cst(condition - w >= 0)
    solver.add_cst(w <= 0)

    '''
    w implementation (w = cond * z):
       lb * z <= w <= ub * z
       cond - (1-z) * M <= w <= cond + (1-z) * M
    '''

    solver.add_cst(0 - M * z <= w)
    solver.add_cst(0 + M * z >= w)

    solver.add_cst(condition - (1 - z) * M <= w)
    solver.add_cst(condition + (1 - z) * M >= w)

    return z


def formulate_hvdc_Pmode3_single_flow(
        solver: LpModel,
        active,
        P0,
        rate,
        Sbase,
        angle_droop,
        angle_max_f,
        angle_max_t,
        suffix,
        angle_f,
        angle_t,
        inf):
    """
        Formulate the HVDC flow
        :param solver: Solver instance to which add the equations
        :param rate: HVDC rate
        :param P0: Power offset for HVDC
        :param angle_f: bus voltage angle node from (LP Variable)
        :param angle_t: bus voltage angle node to (LP Variable)
        :param angle_max_f: maximum bus voltage angle node from (LP Variable)
        :param angle_max_t: maximum bus voltage angle node to (LP Variable)
        :param active: Boolean. HVDC active status (True / False)
        :param angle_droop:  Flow multiplier constant (MW/decimal degree).
        :param Sbase: Base power (i.e. 100 MVA)
        :param suffix: suffix to add to the constraints names.
        :param inf: Value representing the infinite (i.e. 1e20)
        :return:
            - flow_f: Array of formulated HVDC flows (mix of values and variables)
        """

    if active:
        rate = rate / Sbase

        # formulate the hvdc flow as an AC line equivalent
        # to pass from MW/deg to p.u./rad -> * 180 / pi / (sbase=100)
        k = angle_droop * 57.295779513 / Sbase

        # Variables declaration
        if P0 > 0:
            lim_a = P0 + k * (angle_max_f + angle_max_t)
        else:
            lim_a = -P0 + k * (angle_max_f + angle_max_t)

        a = solver.add_var(lb=-lim_a, ub=lim_a, name='a_' + suffix)

        b = solver.add_var(lb=-rate, ub=rate, name='b_' + suffix)

        a_abs, za = formulate_lp_abs_value(
            prob=solver,
            lp_var=a,
            ub=lim_a,
            M=inf * 10,
            name='a_abs_' + suffix)

        b_abs, zb = formulate_lp_abs_value(
            prob=solver,
            lp_var=b,
            ub=rate,
            M=inf,  # this limit could be enough with inf value in order to improve solution convergence
            name='b_abs_' + suffix)

        # Force same power sign
        solver.add_cst(za - zb == 0)

        # Constraints formulation, 'a' is Pmode3 behavior
        solver.add_cst(a == P0 + k * (angle_f - angle_t))

        condition_ub = lim_a - rate
        condition_lb = -rate

        condition = solver.add_var(
            lb=condition_lb,
            ub=condition_ub,
            name='cond_' + suffix)

        solver.add_cst(condition == a_abs - rate)

        # Constraints formulation, b is the solution
        formulate_lp_piece_wise(
            solver=solver,
            lp_var=b_abs,
            higher_exp=rate,
            lower_exp=a_abs,
            condition=condition,
            M=inf * 10,
            name='theoretical_unconstrainded_flow_' + suffix)

    else:
        b = 0

    return b


class BusNtcVars:
    """
    Struct to store the bus related vars
    """

    def __init__(self, nt: int, n_elm: int):
        """
        BusVars structure
        :param nt: Number of time steps
        :param n_elm: Number of branches
        """
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
        :return: HvdcVars
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
    #         branch_bus_dp[f] -= ps
    #         branch_bus_dp[t] += ps

    base_power = gen_per_bus + batt_per_bus + load_per_bus  # + branch_bus_dp

    # Mandatory scaling so that we can do the deltas madness
    diff = base_power.sum()
    if diff != 0.0:
        gen_sum = gen_per_bus.sum()
        if gen_sum != 0:
            share = gen_per_bus / gen_sum
            gen_per_bus -= share * diff  # we make the generators balance the system
        else:
            raise ValueError("Cannot balance the circumstance")

        base_power = gen_per_bus + batt_per_bus + load_per_bus
        new_diff = np.sum(base_power)

        if np.isclose(new_diff, 0, atol=1e-10):
            logger.add_warning("The base circumstance had to be balanced", value=diff, expected_value=new_diff)
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
                    cst=ntc_vars.bus_vars.delta_p[t, k] <= bus_pmax_t[k],
                    name=join(f'delta_p_up', [t, k], "_")
                )

    for k in bus_a2_idx:
        if bus_data_t.active[k] and proportions[k] != 0:
            # the proportion already has the sign
            ntc_vars.bus_vars.delta_p[t, k] = ntc_vars.delta_2[t] * proportions[k]

            if not skip_generation_limits:
                prob.add_cst(
                    cst=-ntc_vars.bus_vars.delta_p[t, k] >= bus_pmin_t[k],
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
    f_obj += ntc_vars.delta_2[t] - ntc_vars.delta_1[t] + ntc_vars.delta_sl_1[t] + ntc_vars.delta_sl_2[t]

    return f_obj, base_power


def add_linear_injections_formulation_proper(t: Union[int, None],
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

    gen_per_bus = gen_data_t.get_injections_per_bus().real / Sbase
    batt_per_bus = batt_data_t.get_injections_per_bus().real / Sbase
    load_per_bus = load_data_t.get_injections_per_bus().real / Sbase  # this comes with the proper sign already
    base_power = gen_per_bus + batt_per_bus + load_per_bus

    f_obj = 0

    # get the area of every generator
    gen_idx_1 = np.where(np.isin(gen_data_t.bus_idx, bus_a1_idx))[0]
    gen_idx_2 = np.where(np.isin(gen_data_t.bus_idx, bus_a2_idx))[0]

    batt_idx_1 = np.where(np.isin(batt_data_t.bus_idx, bus_a1_idx))[0]
    batt_idx_2 = np.where(np.isin(batt_data_t.bus_idx, bus_a2_idx))[0]

    load_idx_1 = np.where(np.isin(load_data_t.bus_idx, bus_a1_idx))[0]
    load_idx_2 = np.where(np.isin(load_data_t.bus_idx, bus_a2_idx))[0]

    ntc_vars.gen_vars.p[t, :] = gen_data_t.p / Sbase
    ntc_vars.batt_vars.p[t, :] = batt_data_t.p / Sbase
    ntc_vars.load_vars.p[t, :] = load_data_t.S.real / Sbase

    for k in gen_idx_1:
        if gen_data_t.p[k] < gen_data_t.pmax[k] and gen_data_t.active[k]:

            if skip_generation_limits:
                margin_up = 9999.0
            else:
                margin_up = (gen_data_t.pmax[k] - gen_data_t.p[k]) / Sbase

            ntc_vars.gen_vars.p_inc[t, k] = prob.add_var(lb=0, ub=margin_up, name=join("gen_p_inc_", [t, k]))
            ntc_vars.gen_vars.p[t, k] = gen_data_t.p[k] / Sbase + ntc_vars.gen_vars.p_inc[t, k]
            ntc_vars.delta_1[t] += ntc_vars.gen_vars.p_inc[t, k]

            i = gen_data_t.bus_idx[k]
            ntc_vars.bus_vars.delta_p[t, i] += ntc_vars.gen_vars.p_inc[t, k]

            f_obj -= ntc_vars.gen_vars.p_inc[t, k] * gen_data_t.shift_key[k]
        else:
            # the generator is maxed out
            pass

    for k in batt_idx_1:
        if batt_data_t.p[k] < batt_data_t.pmax[k]:
            if skip_generation_limits:
                margin_up = 9999.0
            else:
                margin_up = (batt_data_t.pmax[k] - batt_data_t.p[k]) / Sbase

            ntc_vars.batt_vars.p_inc[t, k] = prob.add_var(lb=0, ub=margin_up, name=join("batt_p_inc_", [t, k]))
            ntc_vars.batt_vars.p[t, k] += ntc_vars.batt_vars.p_inc[t, k]
            ntc_vars.delta_1[t] += ntc_vars.batt_vars.p_inc[t, k]

            i = batt_data_t.bus_idx[k]
            ntc_vars.bus_vars.delta_p[t, i] += ntc_vars.batt_vars.p_inc[t, k]

            f_obj -= ntc_vars.batt_vars.p_inc[t, k] * batt_data_t.shift_key[k]
        else:
            # the battery is maxed out
            pass

    for k in gen_idx_2:
        if gen_data_t.p[k] > gen_data_t.pmin[k] and gen_data_t.active[k]:

            if skip_generation_limits:
                margin_dwn = gen_data_t.p[k] / Sbase
            else:
                margin_dwn = (gen_data_t.p[k] - gen_data_t.pmin[k]) / Sbase
            ntc_vars.gen_vars.p_inc[t, k] = prob.add_var(lb=0, ub=margin_dwn, name=join("gen_n_inc_", [t, k]))
            ntc_vars.gen_vars.p[t, k] = (gen_data_t.p[k] / Sbase) - ntc_vars.gen_vars.p_inc[t, k]
            ntc_vars.delta_2[t] += ntc_vars.gen_vars.p_inc[t, k]

            i = gen_data_t.bus_idx[k]
            ntc_vars.bus_vars.delta_p[t, i] -= ntc_vars.gen_vars.p_inc[t, k]

            f_obj -= ntc_vars.gen_vars.p_inc[t, k] * gen_data_t.shift_key[k]
        else:
            # the generator cannot go lower
            pass

    for k in batt_idx_2:
        if batt_data_t.p[k] > batt_data_t.pmin[k]:
            if skip_generation_limits:
                margin_dwn = batt_data_t.p[k] / Sbase
            else:
                margin_dwn = (batt_data_t.p[k] - batt_data_t.pmin[k]) / Sbase
            ntc_vars.batt_vars.p_inc[t, k] = prob.add_var(lb=0, ub=margin_dwn, name=join("batt_n_inc_", [t, k]))
            ntc_vars.batt_vars.p[t, k] -= ntc_vars.batt_vars.p_inc[t, k]
            ntc_vars.delta_2[t] += ntc_vars.batt_vars.p_inc[t, k]

            i = batt_data_t.bus_idx[k]
            ntc_vars.bus_vars.delta_p[t, i] -= ntc_vars.batt_vars.p_inc[t, k]

            f_obj -= ntc_vars.batt_vars.p_inc[t, k] * batt_data_t.shift_key[k]
        else:
            # the battery cannot go lower
            pass

    # formulate the nodal summations
    for k in range(gen_data_t.nelm):
        i = gen_data_t.bus_idx[k]
        ntc_vars.bus_vars.Pinj[t, i] += ntc_vars.gen_vars.p[t, k]
        ntc_vars.bus_vars.Pbalance[t, i] += ntc_vars.gen_vars.p[t, k]

    for k in range(batt_data_t.nelm):
        i = batt_data_t.bus_idx[k]
        ntc_vars.bus_vars.Pinj[t, i] += ntc_vars.batt_vars.p[t, k]
        ntc_vars.bus_vars.Pbalance[t, i] += ntc_vars.batt_vars.p[t, k]

    for k in range(load_data_t.nelm):
        i = load_data_t.bus_idx[k]
        ntc_vars.bus_vars.Pinj[t, i] -= ntc_vars.load_vars.p[t, k]
        ntc_vars.bus_vars.Pbalance[t, i] -= ntc_vars.load_vars.p[t, k]

    # add the area equality constraint
    ntc_vars.delta_sl_1[t] = prob.add_var(lb=0, ub=prob.INFINITY, name=join("DeltaSL_up_", [t]))
    ntc_vars.delta_sl_2[t] = prob.add_var(lb=0, ub=prob.INFINITY, name=join("DeltaSL_down_", [t]))
    prob.add_cst(
        cst=ntc_vars.delta_1[t] - ntc_vars.delta_sl_1[t] == ntc_vars.delta_2[t] - ntc_vars.delta_sl_2[t],
        name=join(f'deltas_equality_', [t], "_")
    )

    # minimize the power at area 2 (receiving area), maximize at area 1 (sending area)
    # minimize the slacks
    # f_obj += ntc_vars.delta_2[t] - ntc_vars.delta_1[t] + ntc_vars.delta_sl_1[t] + ntc_vars.delta_sl_2[t]
    f_obj += ntc_vars.delta_sl_1[t] + ntc_vars.delta_sl_2[t]

    return f_obj, base_power


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
                                    inf=1e20, ) -> LpExp:
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

                # DC Branch
                # compute the branch susceptance
                if branch_data_t.R[m] == 0.0:
                    bk = 1e-6  # setting a value too low will "break" the linear solver
                else:
                    bk = 1.0 / branch_data_t.R[m]

                prob.add_cst(
                    cst=branch_vars.flows[t_idx, m] == bk * (bus_vars.Vm[t_idx, fr] - bus_vars.Vm[t_idx, to]),
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

                # compute the branch susceptance
                if branch_data_t.X[m] == 0.0:
                    bk = 1e-6  # setting a value too low will "break" the linear solver
                else:
                    bk = 1.0 / branch_data_t.X[m]

                # compute the flow
                if (active_branch_data_t.tap_phase_control_mode[m] == TapPhaseControl.Pf or
                        active_branch_data_t.tap_phase_control_mode[m] == TapPhaseControl.Pt):

                    # add angle
                    branch_vars.tap_angles[t_idx, m] = prob.add_var(
                        lb=active_branch_data_t.tap_angle_min[m],
                        ub=active_branch_data_t.tap_angle_max[m],
                        name=join("tap_ang_", [t_idx, m], "_")
                    )

                    # is a phase shifter device (like phase shifter transformer or VSC with P control)
                    prob.add_cst(
                        cst=branch_vars.flows[t_idx, m] == bk * (bus_vars.Va[t_idx, fr] -
                                                                 bus_vars.Va[t_idx, to] +
                                                                 branch_vars.tap_angles[t_idx, m]),
                        name=join("ac_flows_ps_", [t_idx, m], "_")
                    )

                else:

                    if active_branch_data_t.tap_angle[m] != 0.0:
                        branch_vars.tap_angles[t_idx, m] = active_branch_data_t.tap_angle[m]

                        # rest of the branches
                        prob.add_cst(
                            cst=branch_vars.flows[t_idx, m] == bk * (bus_vars.Va[t_idx, fr] -
                                                                     bus_vars.Va[t_idx, to] +
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
            bus_vars.Pbalance[t_idx, fr] -= branch_vars.flows[t_idx, m]
            bus_vars.Pbalance[t_idx, to] += branch_vars.flows[t_idx, m]

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

            branch_vars.monitor_logic[t_idx, m] = int(branch_data_t.monitor_loading[m]
                                                      and monitor_by_sensitivity_n
                                                      and monitor_by_load_rule_n)

            # add the rate constraint if the branch is monitored
            if branch_vars.monitor_logic[t_idx, m]:

                if abs(loading[m]) > 1.0:
                    logger.add_error("Base overload on sensitive branch, rates extended",
                                     device=f"{m}: {branch_data_t.names[m]}",
                                     value=f"{loading[m] * 100} %")

                    # here flows is always a variable
                    prob.set_var_bounds(branch_vars.flows[t_idx, m],
                                   lb=-rate_pu * (abs(loading[m]) + 0.1),
                                   ub=rate_pu * (abs(loading[m]) + 0.1))
                else:
                    # here flows is always a variable
                    prob.set_var_bounds(branch_vars.flows[t_idx, m], lb=-rate_pu, ub=rate_pu)

    # add the inter-area flows to the objective function with the correct sign
    for k, sense in branch_vars.inter_space_branches:
        f_obj -= branch_vars.flows[t_idx, k] * sense

    return f_obj


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
                                                  base_loading: Vec,
                                                  con_loading: Vec,
                                                  logger: Logger):
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
    :param base_loading: loading w.r.t the normal ratings
    :param con_loading: Loading w.r.t the contingency rates
    :param logger
    :return objective function
    """
    f_obj = 0.0
    for c, contingency in enumerate(linear_multi_contingencies.multi_contingencies):

        contingency_flows, mask, changed_idx = contingency.get_lp_contingency_flows(
            base_flow=branch_vars.flows[t_idx, :],
            injections=bus_vars.Pinj[t_idx, :],
            hvdc_flow=hvdc_vars.flows[t_idx, :],
            vsc_flow=vsc_vars.flows[t_idx, :]
        )

        for m in changed_idx:

            if isinstance(contingency_flows[m], LpExp):

                # Monitoring logic: Avoid unrealistic ntc flows over CEP rule limit in N-1 condition
                if monitor_only_ntc_load_rule_branches:
                    """
                    Calculo el porcentaje del ratio de la línea que se reserva al intercambio según la regla de ACER,
                    y paso dicho valor a la frontera, y si el valor es mayor que el máximo intercambio estructural
                    significa que la linea no puede limitar el intercambio
                    Ejemplo:
                        ntc_load_rule = 0.7
                        rate = 1700
                        alpha_n1 = 0.05
                        structural_rate = 5200
                        0.7 * 1700 --> 1190 mw para el intercambio
                        1190 / 0.05 --> 23.800 MW en la frontera en N
                        23.800 >>>> 5200 --> esta linea no puede ser declarada como limitante en la NTC en N.
                       """
                    monitor_by_load_rule_n1 = True
                    for c_br in contingency.branch_indices:
                        monitor_by_load_rule_n1 = (monitor_by_load_rule_n1 and
                                                   (ntc_load_rule * branch_data_t.rates[m] / (
                                                           abs(alpha_n1[m, c_br]) + 1e-20) <= structural_ntc))

                else:
                    monitor_by_load_rule_n1 = True

                # Monitoring logic: Exclude branches with not enough sensibility to exchange in N-1 condition
                if monitor_only_sensitive_branches:
                    monitor_by_sensitivity_n1 = True
                    for c_br in contingency.branch_indices:
                        monitor_by_sensitivity_n1 = (monitor_by_sensitivity_n1 and
                                                     (abs(alpha_n1[m, c_br]) > alpha_threshold))
                else:
                    monitor_by_sensitivity_n1 = True

                if monitor_by_load_rule_n1 and monitor_by_sensitivity_n1:

                    if con_loading[m] < 1.0:
                        # declare slack variables
                        pos_slack = prob.add_var(0, 1e20, join("br_cst_flow_pos_sl_", [t_idx, m, c]))
                        neg_slack = prob.add_var(0, 1e20, join("br_cst_flow_neg_sl_", [t_idx, m, c]))

                        # register the contingency data to evaluate the result at the end
                        branch_vars.add_contingency_flow(t=t_idx, m=m, c=c,
                                                         flow_var=contingency_flows[m],
                                                         neg_slack=neg_slack,
                                                         pos_slack=pos_slack)

                        # add upper rate constraint
                        prob.add_cst(
                            cst=contingency_flows[m] + pos_slack <= branch_data_t.contingency_rates[m] / Sbase,
                            name=join("br_cst_flow_upper_lim_", [t_idx, m, c])
                        )

                        # add lower rate constraint
                        prob.add_cst(
                            cst=contingency_flows[m] - neg_slack >= -branch_data_t.contingency_rates[m] / Sbase,
                            name=join("br_cst_flow_lower_lim_", [t_idx, m, c])
                        )

                        f_obj += pos_slack + neg_slack
                    else:
                        logger.add_error("Contingency overload on sensitive branch, contingency skipped",
                                         device=branch_data_t.names[m],
                                         value=f"{base_loading[m] * 100} %")
                else:
                    pass
            else:
                pass

    # copy the contingency rates
    branch_vars.contingency_rates[t_idx, :] = branch_data_t.contingency_rates

    return f_obj


def add_linear_hvdc_formulation(t_idx: int,
                                Sbase: float,
                                hvdc_data_t: HvdcData,
                                hvdc_vars: HvdcNtcVars,
                                vars_bus: BusNtcVars,
                                prob: LpModel,
                                saturate: bool = True):
    """

    :param t_idx:
    :param Sbase:
    :param hvdc_data_t:
    :param hvdc_vars:
    :param vars_bus:
    :param prob:
    :param saturate:
    :return:
    """

    f_obj = 0.0

    for m in range(hvdc_data_t.nelm):

        fr = hvdc_data_t.F[m]
        to = hvdc_data_t.T[m]
        hvdc_vars.rates[t_idx, m] = hvdc_data_t.rates[m]

        if hvdc_data_t.active[m]:

            if hvdc_data_t.control_mode[m] == HvdcControlType.type_0_free:  # P-MODE 3

                # set the flow based on the angular difference
                P0 = hvdc_data_t.Pset[m] / Sbase

                # convert MW/deg to pu/rad
                droop = hvdc_data_t.get_angle_droop_in_pu_rad_at(m, Sbase)

                if saturate:
                    # hvdc_vars.flows[t_idx, m] = pmode3_formulation(prob=prob,
                    #                                                t_idx=t_idx,
                    #                                                m=m,
                    #                                                rate=hvdc_data_t.rates[m] / Sbase,
                    #                                                P0=P0,
                    #                                                droop=droop,
                    #                                                theta_f=vars_bus.theta[t_idx, fr],
                    #                                                theta_t=vars_bus.theta[t_idx, to])

                    hvdc_vars.flows[t_idx, m] = pmode3_formulation2(prob=prob,
                                                                    t_idx=t_idx,
                                                                    m=m,
                                                                    rate=hvdc_data_t.rates[m] / Sbase,
                                                                    P0=P0,
                                                                    droop=droop,
                                                                    theta_f=vars_bus.Va[t_idx, fr],
                                                                    theta_t=vars_bus.Va[t_idx, to],
                                                                    base_name="hvdc")

                    # hvdc_vars.flows[t_idx, m] = formulate_hvdc_Pmode3_single_flow(
                    #     solver=prob,
                    #     active=hvdc_data_t.active[m],
                    #     P0=P0,
                    #     rate=hvdc_data_t.rates[m] / Sbase,
                    #     Sbase=Sbase,
                    #     angle_droop=hvdc_data_t.angle_droop[m],
                    #     angle_max_f=-6.28,
                    #     angle_max_t=6.28,
                    #     angle_f=vars_bus.theta[t_idx, fr],
                    #     angle_t=vars_bus.theta[t_idx, to],
                    #     suffix=join("", [t_idx, m], "_"),
                    #     inf=prob.INFINITY)

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
                vars_bus.Pbalance[t_idx, fr] -= hvdc_vars.flows[t_idx, m]
                vars_bus.Pbalance[t_idx, to] += hvdc_vars.flows[t_idx, m]

            elif hvdc_data_t.control_mode[m] == HvdcControlType.type_1_Pset:

                if hvdc_data_t.dispatchable[m]:

                    # declare the flow var
                    hvdc_vars.flows[t_idx, m] = prob.add_var(
                        lb=-hvdc_data_t.rates[m] / Sbase,
                        ub=hvdc_data_t.rates[m] / Sbase,
                        name=join("hvdc_flow_", [t_idx, m], "_")
                    )

                    # add the injections matching the flow
                    vars_bus.Pbalance[t_idx, fr] -= hvdc_vars.flows[t_idx, m]
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
                    vars_bus.Pbalance[t_idx, fr] -= hvdc_vars.flows[t_idx, m]
                    vars_bus.Pbalance[t_idx, to] += hvdc_vars.flows[t_idx, m]
            else:
                raise Exception('OPF: Unknown HVDC control mode {}'.format(hvdc_data_t.control_mode[m]))
        else:
            # not active, therefore the flow is exactly zero
            prob.set_var_bounds(var=hvdc_vars.flows[t_idx, m], ub=0.0, lb=0.0)

    # add the flows to the objective function
    for k, sense in hvdc_vars.inter_space_hvdc:
        f_obj -= hvdc_vars.flows[t_idx, k] * sense

    return f_obj


def add_linear_vsc_formulation(t_idx: int,
                               Sbase: float,
                               vsc_data_t: VscData,
                               vsc_vars: VscNtcVars,
                               bus_vars: BusNtcVars,
                               prob: LpModel,
                               logger: Logger,
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
    :param saturate:
    :return:
    """

    f_obj = 0.0
    any_dc_slack = False
    for m in range(vsc_data_t.nelm):

        fr = vsc_data_t.F[m]
        to = vsc_data_t.T[m]

        control_bus_idx = vsc_data_t.control1_bus_idx[m]
        if control_bus_idx == -1:
            control_bus_idx = fr  # pick the DC angle which is 0

        vsc_vars.rates[t_idx, m] = vsc_data_t.rates[m]

        if vsc_data_t.active[m]:

            if (vsc_data_t.control1[m] == ConverterControlType.Pdc_angle_droop and
                    vsc_data_t.control2[m] == ConverterControlType.Pac):  # P-MODE 3

                # set the flow based on the angular difference
                P0 = vsc_data_t.control2_val[m] / Sbase

                # convert MW/deg to pu/rad
                droop = vsc_data_t.control1_val * 57.295779513 / Sbase  # MW/deg -> p.u./rad

                if saturate:

                    vsc_vars.flows[t_idx, m] = pmode3_formulation2(
                        prob=prob,
                        t_idx=t_idx,
                        m=m,
                        rate=vsc_data_t.rates[m] / Sbase,
                        P0=P0,
                        droop=droop,
                        theta_f=bus_vars.Va[t_idx, control_bus_idx],  # control bus
                        theta_t=bus_vars.Va[t_idx, to],  # ac bus
                        base_name="vsc"
                    )

                else:

                    # Simple Pmode 3 with no saturation magic

                    # declare the flow var
                    vsc_vars.flows[t_idx, m] = prob.add_var(
                        lb=-vsc_data_t.rates[m] / Sbase,
                        ub=vsc_data_t.rates[m] / Sbase,
                        name=join("vsc_flow_", [t_idx, m], "_")
                    )

                    # flow = P0 + k · (theta_f - theta_t)
                    prob.add_cst(
                        cst=vsc_vars.flows[t_idx, m] == P0 + droop * (
                                bus_vars.Va[t_idx, fr] - bus_vars.Va[control_bus_idx, to]),
                        name=join("vsc_flow_cst_", [t_idx, m], "_")
                    )

            elif (vsc_data_t.control1[m] == ConverterControlType.Vm_dc and
                  vsc_data_t.control2[m] == ConverterControlType.Pac):

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

            elif (vsc_data_t.control1[m] == ConverterControlType.Pac and
                  vsc_data_t.control2[m] == ConverterControlType.Vm_dc):

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

            elif (vsc_data_t.control1[m] == ConverterControlType.Vm_dc and
                  vsc_data_t.control2[m] == ConverterControlType.Pdc):

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

            elif (vsc_data_t.control1[m] == ConverterControlType.Pdc and
                  vsc_data_t.control2[m] == ConverterControlType.Vm_dc):

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

            elif (vsc_data_t.control1[m] == ConverterControlType.Pdc and
                  vsc_data_t.control2[m] == ConverterControlType.Pac):

                # declare the flow var
                vsc_vars.flows[t_idx, m] = prob.add_var(
                    lb=-vsc_data_t.rates[m] / Sbase,
                    ub=vsc_data_t.rates[m] / Sbase,
                    name=join("vsc_flow_", [t_idx, m], "_")
                )

            elif (vsc_data_t.control1[m] == ConverterControlType.Pac and
                  vsc_data_t.control2[m] == ConverterControlType.Pdc):

                # declare the flow var
                vsc_vars.flows[t_idx, m] = prob.add_var(
                    lb=-vsc_data_t.rates[m] / Sbase,
                    ub=vsc_data_t.rates[m] / Sbase,
                    name=join("vsc_flow_", [t_idx, m], "_")
                )

            else:
                logger.add_error(msg=f"Unsupported controls",
                                 value=f"{vsc_data_t.control1[m]}, {vsc_data_t.control2[m]}")

            # add the injections matching the flow
            bus_vars.Pbalance[t_idx, fr] -= vsc_vars.flows[t_idx, m]
            bus_vars.Pbalance[t_idx, to] += vsc_vars.flows[t_idx, m]

        else:
            # not active, therefore the flow is exactly zero
            prob.set_var_bounds(var=vsc_vars.flows[t_idx, m], ub=0.0, lb=0.0)

    # add the flows to the objective function
    for k, sense in vsc_vars.inter_space_vsc:
        f_obj -= vsc_vars.flows[t_idx, k] * sense

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


def run_linear_ntc_opf(grid: MultiCircuit,
                       t: Union[int, None],
                       solver_type: MIPSolvers = MIPSolvers.HIGHS,
                       zonal_grouping: ZonalGrouping = ZonalGrouping.NoGrouping,
                       skip_generation_limits: bool = False,
                       consider_contingencies: bool = False,
                       contingency_groups_used: List[ContingencyGroup] = (),
                       alpha_threshold: float = 0.001,
                       lodf_threshold: float = 0.001,
                       bus_a1_idx: IntVec | None = None,
                       bus_a2_idx: IntVec | None = None,
                       transfer_method: AvailableTransferMode = AvailableTransferMode.InstalledPower,
                       monitor_only_sensitive_branches: bool = True,
                       monitor_only_ntc_load_rule_branches: bool = False,
                       ntc_load_rule: float = 0.7,  # 70%
                       logger: Logger = Logger(),
                       progress_text: Union[None, Callable[[str], None]] = None,
                       progress_func: Union[None, Callable[[float], None]] = None,
                       export_model_fname: Union[None, str] = None,
                       verbose: int = 0,
                       robust: bool = False) -> NtcVars:
    """

    :param grid: MultiCircuit instance
    :param t: Time indices (in the general scheme)
    :param solver_type: MIP solver to use
    :param zonal_grouping: Zonal grouping?
    :param skip_generation_limits: Skip the generation limits?
    :param consider_contingencies: Consider the contingencies?
    :param contingency_groups_used: List of contingency groups to simulate
    :param alpha_threshold: threshold to consider the exchange sensitivity
    :param lodf_threshold: threshold to consider LODF sensitivities
    :param bus_a1_idx: array of bus indices in the area 1
    :param bus_a2_idx: array of bus indices in the area 2
    :param transfer_method: AvailableTransferMode
    :param monitor_only_sensitive_branches
    :param monitor_only_ntc_load_rule_branches
    :param ntc_load_rule: Amount of exchange branches power that should be dedicated to exchange
    :param logger: logger instance
    :param progress_text: function to report text messages
    :param progress_func: function to report progress
    :param export_model_fname: Export the model into LP and MPS?
    :param verbose: Verbosity level
    :param robust: Robust optimization?
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
    lp_model: LpModel = LpModel(solver_type)

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

    # branch index, branch object, flow sense w.r.t the area exchange
    bus_a1_idx_set = set(bus_a1_idx)
    bus_a2_idx_set = set(bus_a2_idx)

    # find the inter-space branches given the bus indices of each space
    mip_vars.branch_vars.inter_space_branches = nc.passive_branch_data.get_inter_areas(bus_idx_from=bus_a1_idx_set,
                                                                                       bus_idx_to=bus_a2_idx_set)

    mip_vars.hvdc_vars.inter_space_hvdc = nc.hvdc_data.get_inter_areas(bus_idx_from=bus_a1_idx_set,
                                                                       bus_idx_to=bus_a2_idx_set)

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
    )

    # formulate vsc -------------------------------------------------------------------------------------------
    f_obj += add_linear_vsc_formulation(
        t_idx=t_idx,
        Sbase=nc.Sbase,
        vsc_data_t=nc.vsc_data,
        vsc_vars=mip_vars.vsc_vars,
        bus_vars=mip_vars.bus_vars,
        prob=lp_model,
        logger=logger
    )

    if zonal_grouping == ZonalGrouping.NoGrouping:

        # declare the linear analysis and compute the PTDF and LODF
        ls = LinearAnalysis(nc=nc,
                            distributed_slack=False,
                            correct_values=True,
                            logger=logger)

        # compute the power flow
        branch_flows = ls.get_flows(Pbus.real)
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

                # declare the multi-contingencies analysis and compute
                mctg = LinearMultiContingencies(grid=grid,
                                                contingency_groups_used=contingency_groups_used)
                mctg.compute(lin=ls,
                             ptdf_threshold=lodf_threshold,
                             lodf_threshold=lodf_threshold)

                alpha_n1 = compute_alpha_n1(
                    ptdf=ls.PTDF,
                    lodf=ls.LODF,
                    alpha=alpha,
                    dP=dP,
                    dT=1.0
                )

                branch_loading_con = np.abs(branch_flows / (nc.passive_branch_data.contingency_rates / nc.Sbase + 1e-20))

                # formulate the contingencies
                f_obj += add_linear_branches_contingencies_formulation(
                    t_idx=t_idx,
                    Sbase=nc.Sbase,
                    branch_data_t=nc.passive_branch_data,
                    branch_vars=mip_vars.branch_vars,
                    bus_vars=mip_vars.bus_vars,
                    hvdc_vars=mip_vars.hvdc_vars,
                    vsc_vars=mip_vars.vsc_vars,
                    prob=lp_model,
                    linear_multi_contingencies=mctg,
                    monitor_only_sensitive_branches=monitor_only_sensitive_branches,
                    monitor_only_ntc_load_rule_branches=monitor_only_ntc_load_rule_branches,
                    structural_ntc=structural_ntc,
                    ntc_load_rule=ntc_load_rule,
                    alpha_threshold=alpha_threshold,
                    alpha_n1=alpha_n1,
                    base_loading=branch_loading,
                    con_loading=branch_loading_con,
                    logger=logger
                )

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

    if export_model_fname is not None:
        lp_model.save_model(file_name=export_model_fname)
        logger.add_info("LP model saved", value=export_model_fname)
        print('LP model saved as:', export_model_fname)

    # solve the model
    status = lp_model.solve(robust=robust, show_logs=verbose > 0, progress_text=progress_text)

    # gather the results
    logger.add_info(msg="Status", value=lp_model.status2string(status))

    if status == LpModel.OPTIMAL:
        logger.add_info("Objective function", value=lp_model.fobj_value())
        mip_vars.acceptable_solution[t_idx] = True
    else:
        logger.add_error('The problem does not have an optimal solution.')
        mip_vars.acceptable_solution[t_idx] = False
        lp_file_name = os.path.join(opf_file_path(), f"{grid.name} ntc debug.lp")
        lp_model.save_model(file_name=lp_file_name)
        logger.add_info("Debug LP model saved", value=lp_file_name)

    # gather the values of the variables
    vars_v = mip_vars.get_values(Sbase=grid.Sbase, model=lp_model)

    # fill the power shift
    vars_v.power_shift = vars_v.bus_vars.delta_p[:, bus_a1_idx]

    # register the slacks
    if vars_v.delta_sl_1[t_idx] > 1e-6:
        logger.add_error(msg="Inter area equality not fulfilled for area 1",
                         value=vars_v.delta_sl_1[t_idx])

    if vars_v.delta_sl_2[t_idx] > 1e-6:
        logger.add_error(msg="Inter area equality not fulfilled for area 2",
                         value=vars_v.delta_sl_2[t_idx])

    for i in range(nb):
        if abs(vars_v.bus_vars.Pbalance[t_idx, i]) > 1e-8:
            logger.add_error(msg="Inter area equality not fulfilled for area 2",
                             device=f"Bus {i}",
                             value=vars_v.bus_vars.Pbalance[t_idx, i])

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
    inter_area_vsc_idx = [x[0] for x in inter_info_vsc]
    inter_area_vsc_sense = [x[2] for x in inter_info_vsc]

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

    # The summation of flow increments in the inter-area branches must be ΔP in A1.
    vars_v.inter_area_flows[t_idx] = (
            np.sum(vars_v.branch_vars.flows[t_idx, inter_area_branch_idx] * inter_area_branch_sense)
            + np.sum(vars_v.hvdc_vars.flows[t_idx, inter_area_hvdc_idx] * inter_area_hvdc_sense)
            + np.sum(vars_v.vsc_vars.flows[t_idx, inter_area_vsc_idx] * inter_area_vsc_sense)
    )

    logger.add_info("Structural inter-area rate", value=vars_v.structural_ntc[t_idx])
    logger.add_info("Inter-area NTC", value=vars_v.inter_area_flows[t_idx])

    return vars_v
