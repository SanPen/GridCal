# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

"""
This file implements a DC-OPF for time series
That means that solves the OPF problem for a complete time series at once
"""
import numpy as np
from typing import List, Union, Tuple, Callable
from GridCalEngine.enumerations import TransformerControlType, HvdcControlType, GenerationNtcFormulation

from GridCalEngine.basic_structures import ZonalGrouping
from GridCalEngine.basic_structures import MIPSolvers
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Core.DataStructures.numerical_circuit import NumericalCircuit, compile_numerical_circuit_at
from GridCalEngine.Core.DataStructures.generator_data import GeneratorData
from GridCalEngine.Core.DataStructures.battery_data import BatteryData
from GridCalEngine.Core.DataStructures.load_data import LoadData
from GridCalEngine.Core.DataStructures.branch_data import BranchData
from GridCalEngine.Core.DataStructures.hvdc_data import HvdcData
from GridCalEngine.Core.DataStructures.bus_data import BusData
from GridCalEngine.basic_structures import Logger, Mat, Vec, IntVec, BoolVec, StrVec, DateVec, CxMat
from GridCalEngine.Utils.MIP.selected_interface import (LpExp, LpVar, LpModel, get_lp_var_value, lpDot,
                                                        set_var_bounds, join)
from GridCalEngine.enumerations import TransformerControlType, HvdcControlType, AvailableTransferMode
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis, LinearMultiContingencies




def get_structural_ntc(inter_area_branches, inter_area_hvdcs, branch_ratings, hvdc_ratings):
    '''

    :param inter_area_branches:
    :param inter_area_hvdcs:
    :param branch_ratings:
    :param hvdc_ratings:
    :return:
    '''
    if len(inter_area_branches):
        idx_branch, b = list(zip(*inter_area_branches))
        idx_branch = list(idx_branch)
        sum_ratings = sum(branch_ratings[idx_branch])
    else:
        sum_ratings = 0.0

    if len(inter_area_hvdcs):
        idx_hvdc, b = list(zip(*inter_area_hvdcs))
        idx_hvdc = list(idx_hvdc)
        sum_ratings += sum(hvdc_ratings[idx_hvdc])

    return sum_ratings


def formulate_monitorization_logic(
        monitor_only_sensitive_branches: bool, monitor_only_ntc_load_rule_branches: bool,
        monitor_loading: BoolVec, alpha: Vec, alpha_n1: Vec, branch_sensitivity_threshold: float,
        base_flows: Vec, structural_ntc: float, ntc_load_rule: float, rates: Vec) -> Tuple[BoolVec, StrVec, Vec, Vec]:
    """
    Function to formulate branch monitor status due the given logic
    :param monitor_only_sensitive_branches: boolean to apply sensitivity threshold to the monitorization logic.
    :param monitor_only_ntc_load_rule_branches: boolean to apply ntc load rule to the monitorization logic.
    :param monitor_loading: Array of branch monitor loading status given by user(True/False)
    :param alpha: Array of branch sensitivity to the exchange in n condition
    :param alpha_n1: Array of branch sensitivity to the exchange in n-1 condition
    :param branch_sensitivity_threshold: branch sensitivity to the exchange threshold
    :param base_flows: branch base flows
    :param structural_ntc: Maximun NTC available by thermal interconexion rates.
    :param ntc_load_rule: percentage of loading reserved to exchange flow (Clean Energy Package rule by ACER).
    :param rates: array of branch rates
    return:
        - monitor: Array of final monitor status per branch after applying the logic
        - monitor_loading: monitor status per branch set by user interface
        - monitor_by_sensitivity: monitor status per branch due exchange sensibility
        - monitor_by_unrealistic_ntc: monitor status per branch due unrealistic minimum ntc
        - monitor_by_zero_exchange: monitor status per branch due zero exchange loading
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


def get_reference_per_bus(bus_data_t: BusData,
                          gen_data_t: GeneratorData,
                          load_data_t: LoadData,
                          transfer_method: AvailableTransferMode,
                          skip_generation_limits: bool,
                          inf_value: float,
                          Sbase: float):

    """

    :param bus_data_t: BusData structure
    :param gen_data_t: GenData structure
    :param load_data_t: LoadData structure
    :param transfer_method: Exchange transfer method
    :param skip_generation_limits: Skip generation limits?
    :param inf_value: infinity value. Ex 1e-20
    :param Sbase: base power (100 MVA)
    :return:
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
            p_min = gen_data_t.C_bus_elm * gen_data_t.pmin / Sbase
            p_max = gen_data_t.C_bus_elm * gen_data_t.pmax / Sbase

        dispachable_bus = (gen_data_t.C_bus_elm * gen_data_t.dispatchable).astype(bool).astype(float)

    elif transfer_method == AvailableTransferMode.Generation:
        p_ref = gen_per_bus

        if skip_generation_limits:
            p_min = np.full(bus_data_t.nbus, -inf_value)
            p_max = np.full(bus_data_t.nbus, inf_value)

        else:
            p_min = gen_data_t.C_bus_elm * gen_data_t.pmin / Sbase
            p_max = gen_data_t.C_bus_elm * gen_data_t.pmax / Sbase

        dispachable_bus = (gen_data_t.C_bus_elm * gen_data_t.dispatchable).astype(bool).astype(float)

    elif transfer_method == AvailableTransferMode.Load:
        p_ref = load_per_bus
        p_min = -inf_value
        p_max = inf_value

        #todo check
        dispachable_bus = (load_data_t.C_bus_elm * load_data_t.S).astype(bool).astype(float)

    elif transfer_method == AvailableTransferMode.GenerationAndLoad:
        p_ref = gen_per_bus - load_per_bus
        if skip_generation_limits:
            p_min = np.full(bus_data_t.nbus, -inf_value)
            p_max = np.full(bus_data_t.nbus, inf_value)
        else:
            p_min = gen_data_t.C_bus_elm * gen_data_t.pmin / Sbase
            p_max = gen_data_t.C_bus_elm * gen_data_t.pmax / Sbase

        #todo check
        dispachable_bus = (load_data_t.C_bus_elm * load_data_t.S).astype(bool).astype(float)


    else:
        raise Exception('Undefined available transfer mode')

    return p_ref * dispachable_bus, p_max, p_min

def get_nodal_proportions(nbus: int,
                          p_ref: Vec,
                          p_max: Vec,
                          p_min: Vec,
                          bus_a1: IntVec,
                          bus_a2: IntVec,
                          logger: Logger):

    """
    Get generation proportions by transfer method with sign consideration.
    :param nbus: number of buses
    :param bus_a1: bus indices within area 1
    :param bus_a2: bus indices within area 2
    :param logger: logger instance
    :return: proportions, sense, p_max, p_min
    """

    # bus area mask
    isin_a1 = np.isin(range(nbus), bus_a1, assume_unique=True)
    isin_a2 = np.isin(range(nbus), bus_a2, assume_unique=True)

    p_ref_a1 = p_ref * isin_a1 * (p_ref <= p_max)
    p_ref_a2 = p_ref * isin_a2 * (p_ref >= p_min)

    # get proportions of contribution by sense (gen or pump) and area
    # the idea is both techs contributes to achieve the power shift goal in the same proportion
    # that in base situation

    # Filter positive and negative generators. Same vectors lenght, set not matched values to zero.
    gen_pos_a1 = np.where(p_ref_a1 < 0, 0, p_ref_a1)
    gen_neg_a1 = np.where(p_ref_a1 > 0, 0, p_ref_a1)
    gen_pos_a2 = np.where(p_ref_a2 < 0, 0, p_ref_a2)
    gen_neg_a2 = np.where(p_ref_a2 > 0, 0, p_ref_a2)

    prop_up_a1 = np.sum(gen_pos_a1) / np.sum(np.abs(p_ref_a1))
    prop_dw_a1 = np.sum(gen_neg_a1) / np.sum(np.abs(p_ref_a1))
    prop_up_a2 = np.sum(gen_pos_a2) / np.sum(np.abs(p_ref_a2))
    prop_dw_a2 = np.sum(gen_neg_a2) / np.sum(np.abs(p_ref_a2))

    # get proportion by production (ammount of power contributed by generator to his sensed area).

    if np.sum(np.abs(gen_pos_a1)) != 0:
        prop_up_gen_a1 = gen_pos_a1 / np.sum(np.abs(gen_pos_a1))
    else:
        prop_up_gen_a1 = np.zeros_like(gen_pos_a1)

    if np.sum(np.abs(gen_neg_a1)) != 0:
        prop_dw_gen_a1 = gen_neg_a1 / np.sum(np.abs(gen_neg_a1))
    else:
        prop_dw_gen_a1 = np.zeros_like(gen_neg_a1)

    if np.sum(np.abs(gen_pos_a2)) != 0:
        prop_up_gen_a2 = gen_pos_a2 / np.sum(np.abs(gen_pos_a2))
    else:
        prop_up_gen_a2 = np.zeros_like(gen_pos_a2)

    if np.sum(np.abs(gen_neg_a2)) != 0:
        prop_dw_gen_a2 = gen_neg_a2 / np.sum(np.abs(gen_neg_a2))
    else:
        prop_dw_gen_a2 = np.zeros_like(gen_neg_a2)

    # delta proportion by generator (considering both proportions: sense and production)
    prop_gen_delta_up_a1 = prop_up_gen_a1 * prop_up_a1
    prop_gen_delta_dw_a1 = prop_dw_gen_a1 * prop_dw_a1
    prop_gen_delta_up_a2 = prop_up_gen_a2 * prop_up_a2
    prop_gen_delta_dw_a2 = prop_dw_gen_a2 * prop_dw_a2

    # Join generator proportions into one vector
    # Notice they will not added: just joining like 'or' logical operation
    proportions_a1 = prop_gen_delta_up_a1 + prop_gen_delta_dw_a1
    proportions_a2 = prop_gen_delta_up_a2 + prop_gen_delta_dw_a2
    proportions = proportions_a1 + proportions_a2

    # some checks
    if not np.isclose(np.sum(proportions_a1), 1, rtol=1e-6):
        logger.add_warning('Issue computing proportions to scale delta generation in area 1.')

    if not np.isclose(np.sum(proportions_a2), 1, rtol=1e-6):
        logger.add_warning('Issue computing proportions to scale delta generation in area 2')

    # apply power shift sense based on area (increase a1, decrease a2)
    sense = (1 * isin_a1) + (-1 * isin_a2)

    return proportions, sense, p_max, p_min


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
        self.theta = np.zeros((nt, n_elm), dtype=object)
        self.kirchhoff = np.zeros((nt, n_elm), dtype=object)
        self.shadow_prices = np.zeros((nt, n_elm), dtype=float)

        # nodal load
        self.load_p = np.zeros((nt, n_elm), dtype=float)
        self.load_shedding = np.zeros((nt, n_elm), dtype=object)

        # nodal gen
        self.inj_p = np.zeros((nt, n_elm), dtype=float)
        self.inj_delta = np.zeros((nt, n_elm), dtype=object)

    def get_values(self, Sbase: float) -> "BusNtcVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: BusVars
        """
        nt, n_elm = self.theta.shape
        data = BusNtcVars(nt=nt, n_elm=n_elm)

        data.shadow_prices = self.shadow_prices
        data.load_p = self.load_p * Sbase

        for t in range(nt):

            for i in range(n_elm):
                data.theta[t, i] = get_lp_var_value(self.theta[t, i])
                data.shadow_prices[t, i] = get_lp_var_value(self.kirchhoff[t, i])

                data.load_shedding[t, i] = get_lp_var_value(self.load_shedding[t, i]) * Sbase

                data.inj_p[t, i] = get_lp_var_value(self.inj_p[t, i]) * Sbase
                data.inj_delta[t, i] = get_lp_var_value(self.inj_delta[t, i])

        # format the arrays appropriately
        data.theta = data.theta.astype(float, copy=False)

        data.load_shedding = data.load_shedding.astype(float, copy=False)

        data.inj_p = data.inj_p.astype(float, copy=False)
        data.inj_delta = data.inj_delta.astype(float, copy=False)

        data.power_shift = data.power_shift.astype(float, copy=False)

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
        self.loading = np.zeros((nt, n_elm), dtype=float)

        self.monitor = np.zeros((nt, n_elm), dtype=bool)
        self.monitor_type = np.zeros((nt, n_elm), dtype=object)

        self.contingency_flow_data: List[Tuple[int, int, int, Union[float, LpVar, LpExp]]] = list()


    def get_values(self, Sbase: float) -> "BranchNtcVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: BranchVars
        """
        nt, n_elm = self.flows.shape
        data = BranchNtcVars(nt=nt, n_elm=n_elm)

        data.rates = self.rates

        for t in range(nt):
            for i in range(n_elm):
                data.flows[t, i] = get_lp_var_value(self.flows[t, i]) * Sbase
                data.flow_slacks_pos[t, i] = get_lp_var_value(self.flow_slacks_pos[t, i]) * Sbase
                data.flow_slacks_neg[t, i] = get_lp_var_value(self.flow_slacks_neg[t, i]) * Sbase
                data.tap_angles[t, i] = get_lp_var_value(self.tap_angles[t, i])
                data.flow_constraints_ub[t, i] = get_lp_var_value(self.flow_constraints_ub[t, i])
                data.flow_constraints_lb[t, i] = get_lp_var_value(self.flow_constraints_lb[t, i])

        for i in range(len(self.contingency_flow_data)):
            t, m, c, var = self.contingency_flow_data[i]
            val = get_lp_var_value(var)
            self.contingency_flow_data[i] = (t, m, c, val)

        # format the arrays appropriately
        data.flows = data.flows.astype(float, copy=False)
        data.flow_slacks_pos = data.flow_slacks_pos.astype(float, copy=False)
        data.flow_slacks_neg = data.flow_slacks_neg.astype(float, copy=False)
        data.tap_angles = data.tap_angles.astype(float, copy=False)

        # compute loading
        data.loading = data.flows / (data.rates + 1e-20)

        return data

    def add_contingency_flow(self, t: int, m: int, c: int, flow_var: Union[float, LpVar, LpExp]):
        """
        Add contingency flow
        :param t: time index
        :param m: monitored index
        :param c: contingency group index
        :param flow_var: flow var
        :return:
        """
        self.contingency_flow_data.append((t, m, c, flow_var))


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

        self.rates = np.zeros((nt, n_elm), dtype=float)
        self.loading = np.zeros((nt, n_elm), dtype=float)

    def get_values(self, Sbase: float) -> "HvdcNtcVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: HvdcVars
        """
        nt, n_elm = self.flows.shape
        data = HvdcNtcVars(nt=nt, n_elm=n_elm)
        data.rates = self.rates

        for t in range(nt):
            for i in range(n_elm):
                data.flows[t, i] = get_lp_var_value(self.flows[t, i]) * Sbase

        # format the arrays appropriately
        data.flows = data.flows.astype(float, copy=False)

        data.loading = data.flows / (data.rates + 1e-20)

        return data


class NtcVars:
    """
    Structure to host the opf variables
    """

    def __init__(self, nt: int, nbus: int, ng: int, nb: int, nl: int, nbr: int, n_hvdc: int, model: LpModel):
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
        self.model = model

        self.acceptable_solution = False

        self.bus_vars = BusNtcVars(nt=nt, n_elm=nbus)
        self.branch_vars = BranchNtcVars(nt=nt, n_elm=nbr)
        self.hvdc_vars = HvdcNtcVars(nt=nt, n_elm=n_hvdc)

        # power shift
        self.power_shift = np.zeros((nt, 1), dtype=object)

    def get_values(self, Sbase: float) -> "NtcVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: OpfVars instance
        """

        nt = self.nt

        data = NtcVars(nt=self.nt,
                       nbus=self.nbus,
                       ng=self.ng,
                       nb=self.nb,
                       nl=self.nl,
                       nbr=self.nbr,
                       n_hvdc=self.n_hvdc,
                       model=self.model)

        data.bus_vars = self.bus_vars.get_values(Sbase)
        data.branch_vars = self.branch_vars.get_values(Sbase)
        data.hvdc_vars = self.hvdc_vars.get_values(Sbase)

        # todo: check if acceptable_solution must to be an array, one solution per hour
        data.acceptable_solution = self.acceptable_solution

        for t in range(nt):
            data.power_shift[t] = get_lp_var_value(self.power_shift[t])

        # format the arrays appropriately
        data.power_shift = data.power_shift.astype(float, copy=False)

        return data

    def get_voltages(self) -> CxMat:
        return np.ones((self.nt, self.nbus)) * np.exp(1j * self.bus_vars.theta)


def add_linear_injections_formulation(t: Union[int, None],
                                      Sbase: float,
                                      gen_data_t: GeneratorData,
                                      load_data_t: LoadData,
                                      bus_data_t: BusData,
                                      p_bus_t: Vec,
                                      bus_a1: IntVec,
                                      bus_a2: IntVec,
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
    :param load_data_t: LoadData structure
    :param bus_data_t: BusData structure
    :param p_bus_t: Real power injections per bus (p.u.)
    :param bus_a1: bus indices within area "from"
    :param bus_a2: bus indices within area "to"
    :param transfer_method: Exchange transfer method
    :param skip_generation_limits: Skip generation limits?
    :param ntc_vars: MIP variables structure
    :param prob: MIP problem
    :param logger: logger instance
    :return objective function
    """

    ntc_vars.power_shift[t] = prob.add_var(
        lb=-prob.INFINITY,
        ub=prob.INFINITY,
        name=join("power_shift_", [t], "_"))

    p_ref, p_max, p_min = get_reference_per_bus(
        bus_data_t=bus_data_t,
        gen_data_t=gen_data_t,
        load_data_t=load_data_t,
        transfer_method=transfer_method,
        skip_generation_limits=skip_generation_limits,
        inf_value=prob.INFINITY,
        Sbase=Sbase)

    proportions, sense, bus_pmax_t, bus_pmin_t = get_nodal_proportions(
        nbus=bus_data_t.nbus,
        p_ref=p_ref,
        p_max=p_max,
        p_min=p_min,
        bus_a1=bus_a1,
        bus_a2=bus_a2,
        logger=logger)

    f_obj = 0.0

    for k in range(bus_data_t.nbus):

        if bus_data_t.active[k] and proportions[k] != 0:

            # declare bus delta injections
            ntc_vars.bus_vars.inj_delta[t, k] = prob.add_var(
                lb=-prob.INFINITY,
                ub=prob.INFINITY,
                name=join("delta_p", [t, k], "_"))

            prob.add_cst(
                cst=ntc_vars.bus_vars.inj_delta[t, k] == ntc_vars.power_shift[t] * proportions[k] * sense[k],
                name='bus_{0}_assignment'.format(bus_data_t.names[k]))

            # declare bus injections
            ntc_vars.bus_vars.inj_p[t, k] = prob.add_var(
                lb=bus_pmin_t[k],
                ub=bus_pmax_t[k],
                name=join("inj_p", [t, k], "_"))

            prob.add_cst(
                cst=ntc_vars.bus_vars.inj_p[t, k] == p_bus_t[k] + ntc_vars.bus_vars.inj_delta[t, k],
                name=join("bus_balance", [t, k], "_"))

    return f_obj


def add_linear_branches_formulation(t: int,
                                    Sbase: float,
                                    branch_data_t: BranchData,
                                    branch_vars: BranchNtcVars,
                                    vars_bus: BusNtcVars,
                                    prob: LpModel,
                                    consider_contingencies: bool,
                                    linear_multicontingencies: Union[LinearMultiContingencies, None],
                                    lodf_threshold: float,
                                    alpha_threshold: float,
                                    monitor_only_sensitive_branches: bool,
                                    monitor_only_ntc_load_rule_branches: bool,
                                    alpha: Vec,
                                    alpha_n1: Vec,
                                    base_flows: Vec,
                                    structural_ntc: float,
                                    ntc_load_rule: float,
                                    inf=1e20):
    """
    Formulate the branches
    :param t: time index
    :param Sbase: base power (100 MVA)
    :param branch_data_t: BranchData
    :param branch_vars: BranchVars
    :param vars_bus: BusVars
    :param prob: OR problem
    :param consider_contingencies:
    :param linear_multicontingencies: Linear Multicontingencies object
    :param lodf_threshold: LODF threshold to cut-off
    :param inf: number considered infinte
    :return objective function
    """
    f_obj = 0.0
    if consider_contingencies:
        assert linear_multicontingencies is not None

    # for each branch
    for m in range(branch_data_t.nelm):
        fr = branch_data_t.F[m]
        to = branch_data_t.T[m]

        # copy rates
        branch_vars.rates[t, m] = branch_data_t.rates[m]

        if branch_data_t.active[m]:

            # declare the flow LPVar
            branch_vars.flows[t, m] = prob.add_var(
                lb=-inf,
                ub=inf,
                name=join("flow_", [t, m], "_"))

            # compute the branch susceptance
            if branch_data_t.X[m] == 0.0:
                if branch_data_t.R[m] != 0.0:
                    bk = 1.0 / branch_data_t.R[m]
                else:
                    bk = 1e-20
            else:
                bk = 1.0 / branch_data_t.X[m]

            # compute the flow
            if branch_data_t.control_mode[m] == TransformerControlType.Pt:

                # add angle
                branch_vars.tap_angles[t, m] = prob.add_var(
                    lb=branch_data_t.tap_angle_min[m],
                    ub=branch_data_t.tap_angle_max[m],
                    name=join("tap_ang_", [t, m], "_"))

                # is a phase shifter device (like phase shifter transformer or VSC with P control)
                prob.add_cst(
                    cst=branch_vars.flows[t, m] == bk * (vars_bus.theta[t, fr] -
                                                         vars_bus.theta[t, to] +
                                                         branch_vars.tap_angles[t, m]),
                    name=join("Branch_flow_set_with_ps_", [t, m], "_"))

                # power injected and subtracted due to the phase shift
                vars_bus.inj_p[t, fr] = -bk * branch_vars.tap_angles[t, m]
                vars_bus.inj_p[t, to] = bk * branch_vars.tap_angles[t, m]

            else:  # rest of the branches
                # is a phase shifter device (like phase shifter transformer or VSC with P control)
                prob.add_cst(
                    cst=branch_vars.flows[t, m] == bk * (vars_bus.theta[t, fr] -
                                                         vars_bus.theta[t, to]),
                    name=join("Branch_flow_set_", [t, m], "_"))

            # Compute monitorization logic: Avoid unrealistic ntc && Exclude branches with 'interchange zero' flows over CEP rule limit
            if monitor_only_ntc_load_rule_branches:
                branch_ntc_load_rule_n = ntc_load_rule * branch_data_t.rates / (alpha + 1e-20) <= structural_ntc
                branch_ntc_load_rule_n1 = ntc_load_rule * branch_data_t.rates / (alpha_n1 + 1e-20) <= structural_ntc
                branch_ntc_load_rule = branch_ntc_load_rule_n * branch_ntc_load_rule_n1
                branch_zero_exchange_load_n = base_flows * (1 - alpha) / branch_data_t.rates >= (1 - ntc_load_rule)
                branch_zero_exchange_load_n1 = base_flows * (1 - alpha_n1) / branch_data_t.rates >= (1 - ntc_load_rule)
                branch_zero_exchange_load = branch_zero_exchange_load_n * branch_zero_exchange_load_n1
            else:
                branch_ntc_load_rule = np.ones(len(base_flows), dtype=bool)
                branch_zero_exchange_load = np.ones(len(base_flows), dtype=bool)

            # Compute monitorization logic: Exclude branches with not enough sensibility to exchange
            if monitor_only_sensitive_branches:
                monitor_by_sensitivity_n = alpha > alpha_threshold
                monitor_by_sensitivity_n1 = alpha_n1 > alpha_threshold
                monitor_by_sensitivity = monitor_by_sensitivity_n * monitor_by_sensitivity_n1
            else:
                monitor_by_sensitivity = np.ones(len(base_flows), dtype=bool)

            # Compute monitorization logic
            c1 = branch_data_t.monitor_loading[m]  # user interface monitor checkbox
            c2 = monitor_by_sensitivity[m]  # alpha monitor
            c3 = branch_ntc_load_rule[m]
            c4 = branch_zero_exchange_load[m]

            # add the flow constraint if monitored
            if c1 and c2 and c3 and c4:
                branch_vars.flow_slacks_pos[t, m] = prob.add_var(
                    lb=0,
                    ub=inf,
                    name=join("flow_slack_pos_", [t, m], "_"))

                branch_vars.flow_slacks_neg[t, m] = prob.add_var(
                    lb=0,
                    ub=inf,
                    name=join("flow_slack_neg_", [t, m], "_"))

                # add upper rate constraint
                branch_vars.flow_constraints_ub[t, m] = (branch_vars.flows[t, m] +
                                                         branch_vars.flow_slacks_pos[t, m] -
                                                         branch_vars.flow_slacks_neg[t, m]) \
                                                        <= branch_data_t.rates[m] / Sbase
                prob.add_cst(
                    cst=branch_vars.flow_constraints_ub[t, m],
                    name=join("br_flow_upper_lim_", [t, m]))

                # add lower rate constraint
                branch_vars.flow_constraints_lb[t, m] = (branch_vars.flows[t, m] +
                                                         branch_vars.flow_slacks_pos[t, m] -
                                                         branch_vars.flow_slacks_neg[t, m]) \
                                                         >= -branch_data_t.rates[m] / Sbase

                prob.add_cst(
                    cst=branch_vars.flow_constraints_lb[t, m],
                    name=join("br_flow_lower_lim_", [t, m]))

                # add to the objective function
                f_obj += branch_data_t.overload_cost[m] * branch_vars.flow_slacks_pos[t, m]
                f_obj += branch_data_t.overload_cost[m] * branch_vars.flow_slacks_neg[t, m]

    if consider_contingencies:
        for c, contingency in enumerate(linear_multicontingencies.multi_contingencies):

            contingency_flows = contingency.get_lp_contingency_flows(
                base_flow=branch_vars.flows[t, :],
                injections=vars_bus.inj_p[t, :])

            for m, contingency_flow in enumerate(contingency_flows):
                keep = False

                if isinstance(contingency_flow, LpExp):
                    branch_vars.add_contingency_flow(t=t, m=m, c=c, flow_var=contingency_flow)

                    # add upper rate constraint
                    prob.add_cst(
                        cst=contingency_flow <= branch_data_t.rates[m] / Sbase,
                        name=join("br_cst_flow_upper_lim_", [t, m, c]))

                    # add lower rate constraint
                    prob.add_cst(
                        cst=contingency_flow >= -branch_data_t.rates[m] / Sbase,
                        name=join("br_cst_flow_lower_lim_", [t, m, c]))

    return f_obj


def add_linear_hvdc_formulation(t: int,
                                Sbase: float,
                                hvdc_data_t: HvdcData,
                                hvdc_vars: HvdcNtcVars,
                                vars_bus: BusNtcVars,
                                prob: LpModel):
    """

    :param t:
    :param Sbase:
    :param hvdc_data_t:
    :param hvdc_vars:
    :param vars_bus:
    :param prob:
    :return:
    """

    f_obj = 0.0

    for m in range(hvdc_data_t.nelm):

        fr = hvdc_data_t.F[m]
        to = hvdc_data_t.T[m]
        hvdc_vars.rates[t, m] = hvdc_data_t.rate[m]

        if hvdc_data_t.active[m]:

            # declare the flow var
            hvdc_vars.flows[t, m] = prob.add_var(
                lb=-hvdc_data_t.rate[m] / Sbase,
                ub=hvdc_data_t.rate[m] / Sbase,
                name=join("hvdc_flow_", [t, m], "_"))

            if hvdc_data_t.control_mode[m] == HvdcControlType.type_0_free:

                # set the flow based on the angular difference
                P0 = hvdc_data_t.Pset[m] / Sbase
                prob.add_cst(
                    cst=hvdc_vars.flows[t, m] == P0 + hvdc_data_t.angle_droop[m] * (vars_bus.theta[t, fr] -
                                                                                    vars_bus.theta[t, to]),
                    name=join("hvdc_flow_cst_", [t, m], "_"))

                # add the injections matching the flow
                vars_bus.inj_p[t, fr] -= hvdc_vars.flows[t, m]
                vars_bus.inj_p[t, to] += hvdc_vars.flows[t, m]

            elif hvdc_data_t.control_mode[m] == HvdcControlType.type_1_Pset:

                if hvdc_data_t.dispatchable[m]:

                    # add the injections matching the flow
                    vars_bus.inj_p[t, fr] -= hvdc_vars.flows[t, m]
                    vars_bus.inj_p[t, to] += hvdc_vars.flows[t, m]

                else:

                    if hvdc_data_t.Pset[m] > hvdc_data_t.rate[m]:
                        P0 = hvdc_data_t.rate[m] / Sbase

                    elif hvdc_data_t.Pset[m] < -hvdc_data_t.rate[m]:
                        P0 = -hvdc_data_t.rate[m] / Sbase

                    else:
                        P0 = hvdc_data_t.Pset[m] / Sbase

                    # make the flow equal to P0
                    set_var_bounds(var=hvdc_vars.flows[t, m], ub=P0, lb=P0)

                    # add the injections matching the flow
                    vars_bus.inj_p[t, fr] -= hvdc_vars.flows[t, m]
                    vars_bus.inj_p[t, to] += hvdc_vars.flows[t, m]
            else:
                raise Exception('OPF: Unknown HVDC control mode {}'.format(hvdc_data_t.control_mode[m]))
        else:
            # not active, therefore the flow is exactly zero
            set_var_bounds(var=hvdc_vars.flows[t, m], ub=0.0, lb=0.0)

    return f_obj


def add_linear_node_balance(t_idx: int,
                            Bbus,
                            vd: IntVec,
                            bus_data: BusData,
                            bus_vars: BusNtcVars,
                            prob: LpModel):
    """
    Add the kirchoff nodal equality
    :param t_idx: time step
    :param Bbus: susceptance matrix (complete)
    :param bus_data: BusData
    :param bus_vars: BusVars
    :param prob: LpModel
    """
    B = Bbus.tocsc()

    P_esp = bus_vars.inj_p[t_idx, :]

    # calculate the linear nodal inyection
    P_calc = lpDot(B, bus_vars.theta[t_idx, :])

    # add the equality restrictions
    for k in range(bus_data.nbus):

        bus_vars.kirchhoff[t_idx, k] = prob.add_cst(
            cst=P_calc[k] == P_esp[k],
            name=join("kirchoff_", [t_idx, k], "_"))

    for i in vd:
        set_var_bounds(var=bus_vars.theta[t_idx, i], lb=0.0, ub=0.0)


def run_linear_ntc_opf_ts(grid: MultiCircuit,
                          time_indices: Union[IntVec, None],
                          solver_type: MIPSolvers = MIPSolvers.CBC,
                          zonal_grouping: ZonalGrouping = ZonalGrouping.NoGrouping,
                          skip_generation_limits: bool = False,
                          consider_contingencies: bool = False,
                          lodf_threshold: float = 0.001,
                          buses_areas_1: IntVec = None,
                          buses_areas_2: IntVec = None,
                          transfer_method: AvailableTransferMode = AvailableTransferMode.InstalledPower,
                          monitor_only_sensitive_branches: bool = True,
                          monitor_only_ntc_load_rule_branches: bool = False,
                          logger: Logger = Logger(),
                          progress_text: Union[None, Callable[[str], None]] = None,
                          progress_func: Union[None, Callable[[float], None]] = None,
                          export_model_fname: Union[None, str] = None) -> NtcVars:
    """

    :param grid: MultiCircuit instance
    :param time_indices: Time indices (in the general scheme)
    :param solver_type: MIP solver to use
    :param zonal_grouping: Zonal grouping?
    :param skip_generation_limits: Skip the generation limits?
    :param consider_contingencies: Consider the contingencies?
    :param lodf_threshold:
    :param buses_areas_1:
    :param buses_areas_2:
    :param transfer_method:
    :param logger: logger instance
    :param progress_text:
    :param progress_func:
    :param export_model_fname: Export the model into LP and MPS?
    :return: OpfVars
    """
    bus_dict = {bus: i for i, bus in enumerate(grid.buses)}
    areas_dict = {elm: i for i, elm in enumerate(grid.areas)}

    if time_indices is None:
        time_indices = [None]
    else:
        if len(time_indices) > 0:
            # time indices are ok
            pass
        else:
            time_indices = [None]

    nt = len(time_indices) if len(time_indices) > 0 else 1
    n = grid.get_bus_number()
    nbr = grid.get_branch_number_wo_hvdc()
    ng = grid.get_generators_number()
    nb = grid.get_batteries_number()
    nl = grid.get_calculation_loads_number()
    n_hvdc = grid.get_hvdc_number()


    lp_model: LpModel = LpModel(solver_type)

    # declare structures of LP vars
    mip_vars = NtcVars(nt=nt, nbus=n, ng=ng, nb=nb, nl=nl, nbr=nbr, n_hvdc=n_hvdc, model=lp_model)

    # objective function
    f_obj = 0.0

    for t_idx, t in enumerate(time_indices):  # use time_indices = [None] to simulate the snapshot

        # compile the circuit at the master time index ------------------------------------------------------------
        # note: There are very little chances of simplifying this step and experience shows it is not
        #        worth the effort, so compile every time step
        nc: NumericalCircuit = compile_numerical_circuit_at(
            circuit=grid,
            t_idx=t,  # yes, this is not a bug
            bus_dict=bus_dict,
            areas_dict=areas_dict)

        if consider_contingencies:
            # if we want to include contingencies, we'll need the LODF at this time step
            ls = LinearAnalysis(
                numerical_circuit=nc,
                distributed_slack=False,
                correct_values=True)

            ls.run()
            mctg = LinearMultiContingencies(grid=grid)
            mctg.update(
                lodf=ls.LODF,
                ptdf=ls.PTDF,
            )
        else:
            mctg = None

        # formulate the bus angles ---------------------------------------------------------------------------------
        for k in range(nc.bus_data.nbus):
            mip_vars.bus_vars.theta[t_idx, k] = lp_model.add_var(
                lb=nc.bus_data.angle_min[k],
                ub=nc.bus_data.angle_max[k],
                name=join("th_", [t_idx, k], "_"))

        # formulate injections -------------------------------------------------------------------------------------
        f_obj += add_linear_injections_formulation(
            t=t_idx,
            Sbase=nc.Sbase,
            gen_data_t=nc.generator_data,
            load_data_t=nc.load_data,
            bus_data_t=nc.bus_data,
            p_bus_t=nc.Pbus,
            bus_a1=buses_areas_1,
            bus_a2=buses_areas_2,
            transfer_method=transfer_method,
            skip_generation_limits=skip_generation_limits,
            ntc_vars=mip_vars,
            prob=lp_model,
            logger=logger)

        # formulate hvdc -------------------------------------------------------------------------------------------
        f_obj += add_linear_hvdc_formulation(
            t=t_idx,
            Sbase=nc.Sbase,
            hvdc_data_t=nc.hvdc_data,
            hvdc_vars=mip_vars.hvdc_vars,
            vars_bus=mip_vars.bus_vars,
            prob=lp_model)

        if zonal_grouping == ZonalGrouping.NoGrouping:
            # formulate branches -----------------------------------------------------------------------------------
            f_obj += add_linear_branches_formulation(
                t=t_idx,
                Sbase=nc.Sbase,
                branch_data_t=nc.branch_data,
                branch_vars=mip_vars.branch_vars,
                vars_bus=mip_vars.bus_vars,
                prob=lp_model,
                consider_contingencies=consider_contingencies,
                linear_multicontingencies=mctg,
                lodf_threshold=lodf_threshold,
                monitor_only_sensitive_branches=monitor_only_sensitive_branches,
                monitor_only_ntc_load_rule_branches=monitor_only_ntc_load_rule_branches,
                alpha=,
                alpha_n1=,
                alpha_threshold=,
                inf=1e20)

            # formulate nodes ---------------------------------------------------------------------------------------
            add_linear_node_balance(
                t_idx=t_idx,
                Bbus=nc.Bbus,
                vd=nc.vd,
                bus_data=nc.bus_data,
                bus_vars=mip_vars.bus_vars,
                prob=lp_model)

        elif zonal_grouping == ZonalGrouping.All:
            # this is the copper plate approach
            pass

        # todo: delete this??
        # production equals demand ---------------------------------------------------------------------------------
        lp_model.add_cst(cst=(lp_model.sum(mip_vars.gen_vars.p[t_idx, :]) +
                              lp_model.sum(mip_vars.batt_vars.p[t_idx, :]) >=
                              mip_vars.load_vars.p[t_idx, :].sum() -
                              mip_vars.load_vars.shedding[t_idx].sum()),
                         name="satisfy_demand_at_{0}".format(t_idx))

        if progress_func is not None:
            progress_func((t_idx + 1) / nt * 100.0)

    # set the objective function
    lp_model.minimize(f_obj)

    # solve
    if progress_text is not None:
        progress_text("Solving...")

    if progress_func is not None:
        progress_func(0)

    if export_model_fname is not None:
        lp_model.save_model(file_name=export_model_fname)
        print('LP model saved as:', export_model_fname)

    status = lp_model.solve()

    # gather the results
    if status == LpModel.OPTIMAL:
        print('Solution:')
        print('Objective value =', lp_model.fobj_value())
        mip_vars.acceptable_solution = True
    else:
        print('The problem does not have an optimal solution.')
        mip_vars.acceptable_solution = False
        lp_file_name = grid.name + "_debug.lp"
        lp_model.save_model(file_name=lp_file_name)
        print("Debug LP model saved as:", lp_file_name)

    vars_v = mip_vars.get_values(grid.Sbase)

    return vars_v
