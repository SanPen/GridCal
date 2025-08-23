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
from scipy.sparse import csc_matrix

from GridCalEngine.IO.file_system import opf_file_path
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Devices.Aggregation.inter_aggregation_info import InterAggregationInfo
from GridCalEngine.Devices.Aggregation.contingency_group import ContingencyGroup
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.DataStructures.generator_data import GeneratorData
from GridCalEngine.DataStructures.battery_data import BatteryData
from GridCalEngine.DataStructures.load_data import LoadData
from GridCalEngine.DataStructures.passive_branch_data import PassiveBranchData
from GridCalEngine.DataStructures.active_branch_data import ActiveBranchData
from GridCalEngine.DataStructures.hvdc_data import HvdcData
from GridCalEngine.DataStructures.vsc_data import VscData
from GridCalEngine.DataStructures.bus_data import BusData
from GridCalEngine.DataStructures.fluid_node_data import FluidNodeData
from GridCalEngine.DataStructures.fluid_path_data import FluidPathData
from GridCalEngine.DataStructures.fluid_turbine_data import FluidTurbineData
from GridCalEngine.DataStructures.fluid_pump_data import FluidPumpData
from GridCalEngine.DataStructures.fluid_p2x_data import FluidP2XData
from GridCalEngine.basic_structures import Logger, Vec, IntVec, DateVec, Mat
from GridCalEngine.Utils.MIP.selected_interface import LpExp, LpVar, LpModel, lpDot, join
from GridCalEngine.enumerations import HvdcControlType, ZonalGrouping, MIPSolvers, TapPhaseControl, ConverterControlType
from GridCalEngine.Simulations.LinearFactors.linear_analysis import (LinearAnalysis, LinearMultiContingency,
                                                                     LinearMultiContingencies)


def get_contingency_flow_with_filter(multi_contingency: LinearMultiContingency,
                                     base_flow: Vec,
                                     injections: Union[None, Vec],
                                     threshold: float,
                                     m: int) -> LpExp:
    """
    Get contingency flow
    :param multi_contingency: MultiContingency object
    :param base_flow: Base branch flows (nbranch)
    :param injections: Bus injections increments (nbus)
    :param threshold: threshold to filter contingency elements
    :param m: branch monitor index (int)
    :return: New flows (nbranch)
    """

    res = base_flow[m] + 0

    if len(multi_contingency.branch_indices):
        for i, c in enumerate(multi_contingency.branch_indices):
            if abs(multi_contingency.mlodf_factors[m, i]) >= threshold:
                res += multi_contingency.mlodf_factors[m, i] * base_flow[c]

    if len(multi_contingency.bus_indices):
        for i, c in enumerate(multi_contingency.bus_indices):
            if abs(multi_contingency.compensated_ptdf_factors[m, i]) >= threshold:
                res += multi_contingency.compensated_ptdf_factors[m, i] * multi_contingency.injections_factor[i] * \
                       injections[c]

    return res


class BusVars:
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
        self.Pinj = np.zeros((nt, n_elm), dtype=object)
        self.Pbalance = np.zeros((nt, n_elm), dtype=object)
        self.kirchhoff = np.zeros((nt, n_elm), dtype=object)
        self.shadow_prices = np.zeros((nt, n_elm), dtype=float)

    def get_values(self, Sbase: float, model: LpModel) -> "BusVars":
        """
        Return an instance of this class where the array's content
        is not LP vars but their value
        :return: BusVars
        """
        nt, n_elm = self.Va.shape
        data = BusVars(nt=nt, n_elm=n_elm)

        data.shadow_prices = self.shadow_prices

        for t in range(nt):
            for i in range(n_elm):
                data.Va[t, i] = model.get_value(self.Va[t, i])
                data.Vm[t, i] = model.get_value(self.Vm[t, i])
                data.Pinj[t, i] = model.get_value(self.Pinj[t, i])
                data.Pbalance[t, i] = model.get_value(self.Pbalance[t, i]) * Sbase
                data.shadow_prices[t, i] = model.get_dual_value(self.kirchhoff[t, i])

        # format the arrays appropriately
        data.Va = data.Va.astype(float, copy=False)
        data.Vm = data.Vm.astype(float, copy=False)
        data.Pinj = data.Pinj.astype(float, copy=False)
        data.Pbalance = data.Pbalance.astype(float, copy=False)

        return data


class NodalCapacityVars:
    """
    Struct to store the nodal capacity related vars
    """

    def __init__(self, nt: int, n_elm: int):
        """
        BusVars structure
        :param nt: Number of time steps
        :param n_elm: Number of buses to optimize the capacity for
        """
        self.P = np.zeros((nt, n_elm), dtype=object)  # in per-unit power

    def get_values(self, Sbase: float, model: LpModel) -> "NodalCapacityVars":
        """
        Return an instance of this class where the array's
        content is not LP vars but their value
        :return: BusVars
        """
        nt, n_elm = self.P.shape
        data = NodalCapacityVars(nt=nt, n_elm=n_elm)

        for t in range(nt):
            for i in range(n_elm):
                data.P[t, i] = model.get_value(self.P[t, i]) * Sbase

        # format the arrays appropriately
        data.P = data.P.astype(float, copy=False)

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
        self.shedding = np.zeros((nt, n_elm), dtype=object)

        self.p = np.zeros((nt, n_elm), dtype=object)  # to be filled (no vars)

        self.shedding_cost = np.zeros((nt, n_elm), dtype=object)

    def get_values(self, Sbase: float, model: LpModel) -> "LoadVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: LoadVars
        """
        nt, n_elm = self.shedding.shape
        data = LoadVars(nt=nt, n_elm=n_elm)

        for t in range(nt):
            for i in range(n_elm):
                data.shedding[t, i] = model.get_value(self.shedding[t, i]) * Sbase
                data.p[t, i] = model.get_value(self.p[t, i]) * Sbase
                data.shedding_cost[t, i] = model.get_value(self.shedding_cost[t, i]) * Sbase

        # format the arrays appropriately
        data.shedding = data.shedding.astype(float, copy=False)
        data.p = data.p.astype(float, copy=False)
        data.shedding_cost = data.shedding_cost.astype(float, copy=False)

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
        self.shedding = np.zeros((nt, n_elm), dtype=object)
        self.producing = np.zeros((nt, n_elm), dtype=object)
        self.starting_up = np.zeros((nt, n_elm), dtype=object)
        self.shutting_down = np.zeros((nt, n_elm), dtype=object)
        self.cost = np.zeros((nt, n_elm), dtype=object)
        self.invested = np.zeros((nt, n_elm), dtype=object)

    def get_values(self,
                   Sbase: float,
                   model: LpModel,
                   gen_emissions_rates_matrix: csc_matrix,
                   gen_fuel_rates_matrix: csc_matrix) -> "GenerationVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :param Sbase: Base power (100 MVA)
        :param model: LpModel
        :param gen_emissions_rates_matrix: emissins rates matrix (n_emissions, n_gen)
        :param gen_fuel_rates_matrix: fuel rates matrix (n_fuels, n_gen)
        :return: GenerationVars
        """
        nt, n_elm = self.p.shape
        data = GenerationVars(nt=nt, n_elm=n_elm)

        for t in range(nt):
            for i in range(n_elm):
                data.p[t, i] = model.get_value(self.p[t, i]) * Sbase
                data.shedding[t, i] = model.get_value(self.shedding[t, i]) * Sbase
                data.producing[t, i] = model.get_value(self.producing[t, i])
                data.starting_up[t, i] = model.get_value(self.starting_up[t, i])
                data.shutting_down[t, i] = model.get_value(self.shutting_down[t, i])
                data.cost[t, i] = model.get_value(self.cost[t, i]) * Sbase
                data.invested[t, i] = model.get_value(self.invested[t, i])

        # format the arrays appropriately
        data.p = data.p.astype(float, copy=False)
        data.shedding = data.shedding.astype(float, copy=False)
        data.producing = data.producing.astype(bool, copy=False)
        data.starting_up = data.starting_up.astype(bool, copy=False)
        data.shutting_down = data.shutting_down.astype(bool, copy=False)
        data.cost = data.cost.astype(float, copy=False)
        data.invested = data.invested.astype(bool, copy=False)

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
        self.e = np.zeros((nt, n_elm), dtype=object)

    def get_values(self, Sbase: float, model: LpModel,
                   gen_emissions_rates_matrix: csc_matrix = None,  # not needed but included for compatibiliy
                   gen_fuel_rates_matrix: csc_matrix = None  # not needed but included for compatibiliy
                   ) -> "BatteryVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: GenerationVars
        """
        nt, n_elm = self.p.shape
        data = BatteryVars(nt=nt, n_elm=n_elm)

        for t in range(nt):
            for i in range(n_elm):
                data.p[t, i] = model.get_value(self.p[t, i]) * Sbase
                data.e[t, i] = model.get_value(self.e[t, i]) * Sbase
                data.shedding[t, i] = model.get_value(self.shedding[t, i]) * Sbase
                data.producing[t, i] = model.get_value(self.producing[t, i])
                data.starting_up[t, i] = model.get_value(self.starting_up[t, i])
                data.shutting_down[t, i] = model.get_value(self.shutting_down[t, i])
                data.cost[t, i] = model.get_value(self.cost[t, i])
                data.invested[t, i] = model.get_value(self.invested[t, i])

            # format the arrays appropriately
            data.p = data.p.astype(float, copy=False)
            data.e = data.e.astype(float, copy=False)
            data.shedding = data.shedding.astype(float, copy=False)
            data.producing = data.producing.astype(int, copy=False)
            data.starting_up = data.starting_up.astype(int, copy=False)
            data.shutting_down = data.shutting_down.astype(int, copy=False)
            data.cost = data.cost.astype(float, copy=False)
            data.invested = data.invested.astype(bool, copy=False)

        return data


class BranchVars:
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
        self.overload_cost = np.zeros((nt, n_elm), dtype=object)

        self.rates = np.zeros((nt, n_elm), dtype=float)
        self.loading = np.zeros((nt, n_elm), dtype=float)

        # t, m, c, contingency, negative_slack, positive_slack
        self.contingency_flow_data: List[Tuple[int, int, int, Union[float, LpVar, LpExp], LpVar, LpVar]] = list()

    def get_values(self, Sbase: float, model: LpModel) -> "BranchVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: BranchVars
        """
        nt, n_elm = self.flows.shape
        data = BranchVars(nt=nt, n_elm=n_elm)
        data.rates = self.rates

        for t in range(nt):
            for i in range(n_elm):
                data.flows[t, i] = model.get_value(self.flows[t, i]) * Sbase
                data.flow_slacks_pos[t, i] = model.get_value(self.flow_slacks_pos[t, i]) * Sbase
                data.flow_slacks_neg[t, i] = model.get_value(self.flow_slacks_neg[t, i]) * Sbase
                data.tap_angles[t, i] = model.get_value(self.tap_angles[t, i])
                data.flow_constraints_ub[t, i] = model.get_value(self.flow_constraints_ub[t, i])
                data.flow_constraints_lb[t, i] = model.get_value(self.flow_constraints_lb[t, i])
                data.overload_cost[t, i] = model.get_value(self.overload_cost[t, i]) * Sbase

        for i in range(len(self.contingency_flow_data)):
            t, m, c, var, neg_slack, pos_slack = self.contingency_flow_data[i]
            self.contingency_flow_data[i] = (t, m, c,
                                             model.get_value(var),
                                             model.get_value(neg_slack),
                                             model.get_value(pos_slack))

        # format the arrays appropriately
        data.flows = data.flows.astype(float, copy=False)
        data.flow_slacks_pos = data.flow_slacks_pos.astype(float, copy=False)
        data.flow_slacks_neg = data.flow_slacks_neg.astype(float, copy=False)
        data.overload_cost = data.overload_cost.astype(float, copy=False)
        data.tap_angles = data.tap_angles.astype(float, copy=False)

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


class HvdcVars:
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

    def get_values(self, Sbase: float, model: LpModel) -> "HvdcVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: HvdcVars
        """
        nt, n_elm = self.flows.shape
        data = HvdcVars(nt=nt, n_elm=n_elm)
        data.rates = self.rates

        for t in range(nt):
            for i in range(n_elm):
                data.flows[t, i] = model.get_value(self.flows[t, i]) * Sbase

        # format the arrays appropriately
        data.flows = data.flows.astype(float, copy=False)

        data.loading = data.flows / (data.rates + 1e-20)

        return data


class VscVars:
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

    def get_values(self, Sbase: float, model: LpModel) -> "HvdcVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: HvdcVars
        """
        nt, n_elm = self.flows.shape
        data = HvdcVars(nt=nt, n_elm=n_elm)
        data.rates = self.rates

        for t in range(nt):
            for i in range(n_elm):
                data.flows[t, i] = model.get_value(self.flows[t, i]) * Sbase

        # format the arrays appropriately
        data.flows = data.flows.astype(float, copy=False)

        data.loading = data.flows / (data.rates + 1e-20)

        return data


class FluidNodeVars:
    """
    Struct to store the vars of nodes of fluid type
    """

    def __init__(self, nt: int, n_elm: int):
        """
        FluidNodeVars structure
        :param nt: Number of time steps
        :param n_elm: Number of nodes
        """

        # the objects below are extracted from data
        # self.min_level = np.zeros((nt, n_elm), dtype=float)  # m3
        # self.max_level = np.zeros((nt, n_elm), dtype=float)  # m3
        # self.initial_level = np.zeros((nt, n_elm), dtype=float)  # m3

        self.p2x_flow = np.zeros((nt, n_elm), dtype=object)  # m3
        self.current_level = np.zeros((nt, n_elm), dtype=object)  # m3
        self.spillage = np.zeros((nt, n_elm), dtype=object)  # m3/s
        self.flow_in = np.zeros((nt, n_elm), dtype=object)  # m3/s
        self.flow_out = np.zeros((nt, n_elm), dtype=object)  # m3/s

    def get_values(self, model: LpModel) -> "FluidNodeVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :param model: LP model from where we extract the values
        :return: FluidNodeVars
        """
        nt, n_elm = self.p2x_flow.shape
        data = FluidNodeVars(nt=nt, n_elm=n_elm)

        for t in range(nt):
            for i in range(n_elm):
                data.p2x_flow[t, i] = model.get_value(self.p2x_flow[t, i])
                data.current_level[t, i] = model.get_value(self.current_level[t, i])
                data.spillage[t, i] = model.get_value(self.spillage[t, i])
                data.flow_in[t, i] = model.get_value(self.flow_in[t, i])
                data.flow_out[t, i] = model.get_value(self.flow_out[t, i])

        # format the arrays appropriately
        data.p2x_flow = data.p2x_flow.astype(float, copy=False)
        data.current_level = data.current_level.astype(float, copy=False)
        data.spillage = data.spillage.astype(float, copy=False)
        data.flow_in = data.flow_in.astype(float, copy=False)
        data.flow_out = data.flow_out.astype(float, copy=False)

        # from the data object itself
        # data.min_level = self.min_level
        # data.max_level = self.max_level
        # data.initial_level = self.initial_level

        return data


class FluidPathVars:
    """
    Struct to store the vars of paths of fluid type
    """

    def __init__(self, nt: int, n_elm: int):
        """
        FluidPathVars structure
        :param nt: Number of time steps
        :param n_elm: Number of paths (rivers)
        """

        # from the data object
        # self.min_flow = np.zeros((nt, n_elm), dtype=float)  # m3/s
        # self.max_flow = np.zeros((nt, n_elm), dtype=float)  # m3/s

        self.flow = np.zeros((nt, n_elm), dtype=object)  # m3/s

    def get_values(self, model: LpModel) -> "FluidPathVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :param model: LP model from where we extract the values
        :return: FluidPathVars
        """
        nt, n_elm = self.flow.shape
        data = FluidPathVars(nt=nt, n_elm=n_elm)

        for t in range(nt):
            for i in range(n_elm):
                data.flow[t, i] = model.get_value(self.flow[t, i])

        # format the arrays appropriately
        data.flow = data.flow.astype(float, copy=False)

        # data.min_flow = self.min_flow
        # data.max_flow = self.max_flow

        return data


class FluidInjectionVars:
    """
    Struct to store the vars of injections of fluid type
    """

    def __init__(self, nt: int, n_elm: int):
        """
        FluidInjectionVars structure
        :param nt: Number of time steps
        :param n_elm: Number of elements moving fluid
        """

        self.flow = np.zeros((nt, n_elm), dtype=object)  # m3/s

    def get_values(self, model: LpModel) -> "FluidInjectionVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :param model: LP model from where we extract the values
        :return: FluidInjectionVars
        """
        nt, n_elm = self.flow.shape
        data = FluidInjectionVars(nt=nt, n_elm=n_elm)

        for t in range(nt):
            for i in range(n_elm):
                data.flow[t, i] = model.get_value(self.flow[t, i])

        # format the arrays appropriately
        data.flow = data.flow.astype(float, copy=False)

        return data


class SystemVars:
    """
    Struct to store the system vars
    """

    def __init__(self, nt: int):
        """
        SystemVars structure
        :param nt: Number of time steps
        """
        self.system_fuel = np.zeros(nt, dtype=float)
        self.system_emissions = np.zeros(nt, dtype=float)
        self.system_unit_energy_cost = np.zeros(nt, dtype=float)
        self.system_total_energy_cost = np.zeros(nt, dtype=float)
        self.power_by_technology = np.zeros(nt, dtype=float)

    def compute(self,
                gen_emissions_rates_matrix: csc_matrix,
                gen_fuel_rates_matrix: csc_matrix,
                gen_tech_shares_matrix: csc_matrix,
                batt_tech_shares_matrix: csc_matrix,
                gen_p: Mat,
                gen_cost: Mat,
                batt_p: Mat,
                shedding_cost: Mat,
                overload_cost: Mat):
        """
        Compute the system values
        :param gen_emissions_rates_matrix: emissions rates matrix (n_emissions, n_gen)
        :param gen_fuel_rates_matrix: fuel rates matrix (n_fuels, n_gen)
        :param gen_tech_shares_matrix: technology shares of the generators
        :param batt_tech_shares_matrix technology shares of the batteries
        :param gen_p: Generation power values (nt, ngen)
        :param gen_cost: Generation cost values (nt, ngen)
        :param batt_p: Battery power values (nt, nbatt)
        :param shedding_cost: Shedding cost values (nt, ngen)
        :param overload_cost: Overload cost values (nt, ngen)
        """
        self.system_fuel = (gen_fuel_rates_matrix * gen_p.T).T
        self.system_emissions = (gen_emissions_rates_matrix * gen_p.T).T
        self.power_by_technology = (gen_tech_shares_matrix * gen_p.T).T
        self.power_by_technology += (batt_tech_shares_matrix * batt_p.T).T

        with np.errstate(divide='ignore', invalid='ignore'):  # numpy magic to ignore the zero divisions

            self.system_total_energy_cost = np.nan_to_num(gen_cost).sum(axis=1)
            self.system_total_energy_cost += np.nan_to_num(shedding_cost).sum(axis=1)
            self.system_total_energy_cost += np.nan_to_num(overload_cost).sum(axis=1)

            self.system_unit_energy_cost = self.system_total_energy_cost / np.nan_to_num(gen_p).sum(axis=1)

        return self


class OpfVars:
    """
    Structure to host the opf variables
    """

    def __init__(self, nt: int, nbus: int, ng: int, nb: int, nl: int, nbr: int, n_hvdc: int, n_vsc: int,
                 n_fluid_node: int,
                 n_fluid_path: int, n_fluid_inj: int, n_cap_buses: int):
        """
        Constructor
        :param nt: number of time steps
        :param nbus: number of nodes
        :param ng: number of generators
        :param nb: number of batteries
        :param nl: number of loads
        :param nbr: number of branches
        :param n_hvdc: number of HVDC
        :param n_fluid_node: number of fluid nodes
        :param n_fluid_path: number of fluid paths
        :param n_fluid_inj: number of fluid injections
        """
        self.nt = nt
        self.nbus = nbus
        self.ng = ng
        self.nb = nb
        self.nl = nl
        self.nbr = nbr
        self.n_hvdc = n_hvdc
        self.n_vsc = n_vsc
        self.n_fluid_node = n_fluid_node
        self.n_fluid_path = n_fluid_path
        self.n_fluid_inj = n_fluid_inj
        self.n_cap_buses = n_cap_buses

        self.acceptable_solution = False

        self.bus_vars = BusVars(nt=nt, n_elm=nbus)
        self.nodal_capacity_vars = NodalCapacityVars(nt=nt, n_elm=n_cap_buses)
        self.load_vars = LoadVars(nt=nt, n_elm=nl)
        self.gen_vars = GenerationVars(nt=nt, n_elm=ng)
        self.batt_vars = BatteryVars(nt=nt, n_elm=nb)
        self.branch_vars = BranchVars(nt=nt, n_elm=nbr)
        self.hvdc_vars = HvdcVars(nt=nt, n_elm=n_hvdc)
        self.vsc_vars = VscVars(nt=nt, n_elm=n_vsc)

        self.fluid_node_vars = FluidNodeVars(nt=nt, n_elm=n_fluid_node)
        self.fluid_path_vars = FluidPathVars(nt=nt, n_elm=n_fluid_path)
        self.fluid_inject_vars = FluidInjectionVars(nt=nt, n_elm=n_fluid_inj)

        self.sys_vars = SystemVars(nt=nt)

    def get_values(self, Sbase: float, model: LpModel,
                   gen_emissions_rates_matrix: csc_matrix,
                   gen_fuel_rates_matrix: csc_matrix,
                   gen_tech_shares_matrix: csc_matrix,
                   batt_tech_shares_matrix: csc_matrix) -> "OpfVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: OpfVars instance
        """
        data = OpfVars(nt=self.nt,
                       nbus=self.nbus,
                       ng=self.ng,
                       nb=self.nb,
                       nl=self.nl,
                       nbr=self.nbr,
                       n_hvdc=self.n_hvdc,
                       n_vsc=self.n_vsc,
                       n_fluid_node=self.n_fluid_node,
                       n_fluid_path=self.n_fluid_path,
                       n_fluid_inj=self.n_fluid_inj,
                       n_cap_buses=self.n_cap_buses)

        data.bus_vars = self.bus_vars.get_values(Sbase, model)
        data.nodal_capacity_vars = self.nodal_capacity_vars.get_values(Sbase, model)
        data.load_vars = self.load_vars.get_values(Sbase, model)
        data.gen_vars = self.gen_vars.get_values(Sbase=Sbase,
                                                 model=model,
                                                 gen_emissions_rates_matrix=gen_emissions_rates_matrix,
                                                 gen_fuel_rates_matrix=gen_fuel_rates_matrix)
        data.batt_vars = self.batt_vars.get_values(Sbase, model)
        data.branch_vars = self.branch_vars.get_values(Sbase, model)
        data.hvdc_vars = self.hvdc_vars.get_values(Sbase, model)
        data.vsc_vars = self.vsc_vars.get_values(Sbase, model)
        data.fluid_node_vars = self.fluid_node_vars.get_values(model)
        data.fluid_path_vars = self.fluid_path_vars.get_values(model)
        data.fluid_inject_vars = self.fluid_inject_vars.get_values(model)
        data.sys_vars = self.sys_vars.compute(gen_emissions_rates_matrix=gen_emissions_rates_matrix,
                                              gen_fuel_rates_matrix=gen_fuel_rates_matrix,
                                              gen_tech_shares_matrix=gen_tech_shares_matrix,
                                              batt_tech_shares_matrix=batt_tech_shares_matrix,
                                              gen_p=data.gen_vars.p,
                                              batt_p=data.batt_vars.p,
                                              gen_cost=data.gen_vars.cost,
                                              shedding_cost=data.load_vars.shedding_cost,
                                              overload_cost=data.branch_vars.overload_cost)

        data.acceptable_solution = self.acceptable_solution

        return data


def add_linear_generation_formulation(t: Union[int, None],
                                      Sbase: float,
                                      time_array: DateVec,
                                      bus_vars: BusVars,
                                      gen_data_t: GeneratorData,
                                      gen_vars: GenerationVars,
                                      prob: LpModel,
                                      unit_commitment: bool,
                                      ramp_constraints: bool,
                                      skip_generation_limits: bool,
                                      all_generators_fixed: bool,
                                      vd: IntVec,
                                      nodal_capacity_active: bool,
                                      generation_expansion_planning: bool):
    """
    Add MIP generation formulation
    :param t: time step
    :param Sbase: base power (100 MVA)
    :param time_array: complete time array
    :param bus_vars: BusVars
    :param gen_data_t: GeneratorData structure
    :param gen_vars: GenerationVars structure
    :param prob: LpModel
    :param unit_commitment: formulate unit commitment?
    :param ramp_constraints: formulate ramp constraints?
    :param skip_generation_limits: skip the generation limits?
    :param all_generators_fixed: All generators take their snapshot or profile values
                                 instead of resorting to dispatchable status
    :param vd: slack indices
    :param nodal_capacity_active: nodal capacity active?
    :param generation_expansion_planning: generation expansion plan?
    :return objective function
    """
    f_obj = 0.0

    if nodal_capacity_active:
        # TODO: This looks like a bug
        # id_gen_nonvd = [i for i in range(gen_data_t.C_bus_elm.shape[1]) if i not in vd]
        id_gen_nonvd = [i for i in range(gen_data_t.nelm) if i not in vd]
    else:
        id_gen_nonvd = []

    if time_array is not None:
        if len(time_array) > 0:
            year = time_array[t].year - time_array[0].year
        else:
            year = 0
    else:
        year = 0

    # add generation stuff
    for k in range(gen_data_t.nelm):

        gen_vars.cost[t, k] = 0.0
        bus_idx = gen_data_t.bus_idx[k]
        # nodal_cap_condition = gen_data_t.bus_idx[k] not in vd if nodal_capacity_active else True

        if gen_data_t.active[k] and k not in id_gen_nonvd and bus_idx > -1:  # TODO Review and change this stuff

            if gen_data_t.dispatchable[k] and not all_generators_fixed:

                # declare active power var (limits will be applied later)
                gen_vars.p[t, k] = prob.add_var(-1e20, 1e20, join("gen_p_", [t, k], "_"))

                if unit_commitment:

                    # declare unit commitment vars
                    gen_vars.starting_up[t, k] = prob.add_int(0, 1,
                                                              join("gen_starting_up_", [t, k], "_"))
                    gen_vars.producing[t, k] = prob.add_int(0, 1,
                                                            join("gen_producing_", [t, k], "_"))
                    gen_vars.shutting_down[t, k] = prob.add_int(0, 1,
                                                                join("gen_shutting_down_", [t, k], "_"))

                    # operational cost (linear...)
                    gen_vars.cost[t, k] += (gen_data_t.cost_1[k] * gen_vars.p[t, k]
                                            + gen_data_t.cost_0[k] * gen_vars.producing[t, k])

                    # start-up cost
                    gen_vars.cost[t, k] += gen_data_t.startup_cost[k] * gen_vars.starting_up[t, k]

                    # power boundaries of the generator
                    if not skip_generation_limits:
                        prob.add_cst(
                            cst=gen_vars.p[t, k] >= (gen_data_t.pmin[k] / Sbase * gen_vars.producing[t, k]),
                            name=join("gen_geq_Pmin", [t, k], "_"))
                        prob.add_cst(
                            cst=gen_vars.p[t, k] <= (gen_data_t.pmax[k] / Sbase * gen_vars.producing[t, k]),
                            name=join("gen_leq_Pmax", [t, k], "_"))

                    if t is not None:
                        if t == 0:
                            prob.add_cst(cst=gen_vars.starting_up[t, k] - gen_vars.shutting_down[t, k] ==
                                             gen_vars.producing[t, k] - float(gen_data_t.active[k]),
                                         name=join("binary_alg1_", [t, k], "_"))
                            prob.add_cst(cst=gen_vars.starting_up[t, k] + gen_vars.shutting_down[t, k] <= 1,
                                         name=join("binary_alg2_", [t, k], "_"))
                        else:
                            prob.add_cst(
                                cst=(gen_vars.starting_up[t, k] - gen_vars.shutting_down[t, k] ==
                                     gen_vars.producing[t, k] - gen_vars.producing[t - 1, k]),
                                name=join("binary_alg3_", [t, k], "_")
                            )
                            prob.add_cst(
                                cst=gen_vars.starting_up[t, k] + gen_vars.shutting_down[t, k] <= 1,
                                name=join("binary_alg4_", [t, k], "_")
                            )
                else:
                    # No unit commitment

                    # Operational cost (linear...)
                    gen_vars.cost[t, k] += (gen_data_t.cost_1[k] * gen_vars.p[t, k]) + gen_data_t.cost_0[k]

                    if not skip_generation_limits:
                        prob.set_var_bounds(var=gen_vars.p[t, k],
                                       lb=gen_data_t.pmin[k] / Sbase,
                                       ub=gen_data_t.pmax[k] / Sbase)

                # add the ramp constraints
                if ramp_constraints and t is not None:
                    if t > 0:
                        if gen_data_t.ramp_up[k] < gen_data_t.pmax[k] and gen_data_t.ramp_down[k] < gen_data_t.pmax[k]:
                            # if the ramp is actually sufficiently restrictive...
                            dt = (time_array[t] - time_array[t - 1]).seconds / 3600.0  # time increment in hours

                            # - ramp_down · dt <= P(t) - P(t-1) <= ramp_up · dt
                            prob.add_cst(
                                cst=-gen_data_t.ramp_down[k] / Sbase * dt <= gen_vars.p[t, k] - gen_vars.p[t - 1, k]
                            )
                            prob.add_cst(
                                cst=gen_vars.p[t, k] - gen_vars.p[t - 1, k] <= gen_data_t.ramp_up[k] / Sbase * dt
                            )

                # Generation Expansion Planning
                if gen_data_t.is_candidate[k] and generation_expansion_planning:

                    money_factor = np.power(1.0 + gen_data_t.discount_rate[k] / 100.0, year)

                    # declare the investment binary
                    gen_vars.invested[t, k] = prob.add_int(lb=0, ub=1, name=join("Ig_", [t, k]))

                    # add the investment cost to the objective
                    f_obj += gen_vars.invested[t, k] * (gen_data_t.pmax[k] / Sbase) * gen_data_t.capex[k] * money_factor

                    if t > 0:
                        # installation persistence
                        prob.add_cst(gen_vars.invested[t - 1, k] <= gen_vars.invested[t, k],
                                     name=join("persist_", [t, k]))

                    # maximum production constraint
                    prob.add_cst(gen_vars.p[t, k] <= (gen_data_t.pmax[k] / Sbase) * gen_vars.invested[t, k],
                                 name=join("max_prod_", [t, k]))
                else:
                    # is invested for already
                    gen_vars.invested[t, k] = 1

            else:

                ## it is NOT dispatchable
                p = gen_data_t.p[k] / Sbase

                # the generator is not dispatchable at time step
                if p > 0:

                    gen_vars.shedding[t, k] = prob.add_var(0, p, join("gen_shedding_", [t, k], "_"))

                    gen_vars.p[t, k] = p - gen_vars.shedding[t, k]

                    gen_vars.cost[t, k] += gen_data_t.cost_1[k] * gen_vars.shedding[t, k]

                elif p < 0:
                    # the negative sign is because P is already negative here, to make it positive
                    gen_vars.shedding[t, k] = prob.add_var(0, -p, join("gen_shedding_", [t, k], "_"))

                    gen_vars.p[t, k] = p + gen_vars.shedding[t, k]

                    gen_vars.cost[t, k] += gen_data_t.cost_1[k] * gen_vars.shedding[t, k]

                else:
                    # the generation value is exactly zero
                    prob.set_var_bounds(var=gen_vars.p[t, k], lb=0.0, ub=0.0)

                gen_vars.producing[t, k] = 1
                gen_vars.shutting_down[t, k] = 0
                gen_vars.starting_up[t, k] = 0

                # Operational cost (linear...)
                gen_vars.cost[t, k] += (gen_data_t.cost_1[k] * gen_vars.p[t, k]) + gen_data_t.cost_0[k]

            # add to the balance
            bus_vars.Pbalance[t, bus_idx] += gen_vars.p[t, k]

        else:
            # the generator is not available at time step
            gen_vars.p[t, k] = 0.0  # there has not been any variable assigned to p[t, k] at this point

        # add to the objective function the total cost of the generator
        f_obj += gen_vars.cost[t, k]

    return f_obj


def add_linear_battery_formulation(t: Union[int, None],
                                   Sbase: float,
                                   time_array: DateVec,
                                   bus_vars: BusVars,
                                   batt_data_t: BatteryData,
                                   batt_vars: BatteryVars,
                                   prob: LpModel,
                                   unit_commitment: bool,
                                   ramp_constraints: bool,
                                   skip_generation_limits: bool,
                                   generation_expansion_planning: bool,
                                   energy_0: Vec):
    """
    Add MIP generation formulation
    :param t: time step, if None we assume single time step
    :param Sbase: base power (100 MVA)
    :param time_array: complete time array
    :param bus_vars: BusVars
    :param batt_data_t: BatteryData structure
    :param batt_vars: BatteryVars structure
    :param prob: ORTools problem
    :param unit_commitment: formulate unit commitment?
    :param ramp_constraints: formulate ramp constraints?
    :param skip_generation_limits: skip the generation limits?
    :param generation_expansion_planning: generation expansion planning?
    :param energy_0: initial value of the energy stored
    :return objective function
    """
    f_obj = 0.0
    for k in range(batt_data_t.nelm):

        bus_idx = batt_data_t.bus_idx[k]

        if batt_data_t.active[k] and bus_idx > -1:

            # declare active power var (limits will be applied later)
            p_pos = prob.add_var(0, 1e20, join("batt_ppos_", [t, k], "_"))
            p_neg = prob.add_var(0, 1e20, join("batt_pneg_", [t, k], "_"))
            batt_vars.p[t, k] = p_pos - p_neg

            if batt_data_t.dispatchable[k]:

                if unit_commitment:

                    # declare unit commitment vars
                    batt_vars.starting_up[t, k] = prob.add_int(0, 1,
                                                               join("bat_starting_up_", [t, k], "_"))

                    batt_vars.producing[t, k] = prob.add_int(0, 1,
                                                             join("bat_producing_", [t, k], "_"))

                    batt_vars.shutting_down[t, k] = prob.add_int(0, 1,
                                                                 join("bat_shutting_down_", [t, k], "_"))

                    # operational cost (linear...)
                    f_obj += (batt_data_t.cost_1[k] * p_pos
                              + batt_data_t.cost_0[k] * batt_vars.producing[t, k])

                    # start-up cost
                    f_obj += batt_data_t.startup_cost[k] * batt_vars.starting_up[t, k]

                    # power boundaries of the generator
                    if not skip_generation_limits:
                        prob.add_cst(
                            cst=(batt_vars.p[t, k] >= (batt_data_t.pmin[k] / Sbase * batt_vars.producing[t, k])),
                            name=join("batt_geq_Pmin", [t, k], "_"))

                        prob.add_cst(
                            cst=(batt_vars.p[t, k] <= (batt_data_t.pmax[k] / Sbase * batt_vars.producing[t, k])),
                            name=join("batt_leq_Pmax", [t, k], "_"))

                    if t is not None:
                        if t == 0:
                            prob.add_cst(
                                cst=(batt_vars.starting_up[t, k] - batt_vars.shutting_down[t, k] ==
                                     batt_vars.producing[t, k] - float(batt_data_t.active[k])),
                                name=join("binary_bat_alg1_", [t, k], "_"))

                            prob.add_cst(
                                cst=batt_vars.starting_up[t, k] + batt_vars.shutting_down[t, k] <= 1,
                                name=join("binary_bat_alg2_", [t, k], "_"))
                        else:
                            prob.add_cst(
                                cst=(batt_vars.starting_up[t, k] - batt_vars.shutting_down[t, k] ==
                                     batt_vars.producing[t, k] - batt_vars.producing[t - 1, k]),
                                name=join("binary_bat_alg3_", [t, k], "_"))

                            prob.add_cst(
                                cst=batt_vars.starting_up[t, k] + batt_vars.shutting_down[t, k] <= 1,
                                name=join("binary_bat_alg4_", [t, k], "_"))
                else:
                    # No unit commitment

                    # Operational cost (linear...)
                    f_obj += (batt_data_t.cost_1[k] * p_pos) + batt_data_t.cost_0[k]

                    # power boundaries of the generator
                    if not skip_generation_limits:
                        prob.set_var_bounds(var=p_pos, lb=0, ub=+batt_data_t.pmax[k] / Sbase)
                        prob.set_var_bounds(var=p_neg, lb=0, ub=-batt_data_t.pmin[k] / Sbase)

                # compute the time increment in hours
                if len(time_array) > 1:
                    dt = (time_array[t] - time_array[t - 1]).seconds / 3600.0
                else:
                    dt = 1.0

                if ramp_constraints and t is not None:
                    if t > 0:

                        # add the ramp constraints
                        if batt_data_t.ramp_up[k] < batt_data_t.pmax[k] and \
                                batt_data_t.ramp_down[k] < batt_data_t.pmax[k]:
                            # if the ramp is actually sufficiently restrictive...
                            # - ramp_down · dt <= P(t) - P(t-1) <= ramp_up · dt
                            prob.add_cst(
                                cst=-batt_data_t.ramp_down[k] / Sbase * dt <= batt_vars.p[t, k] - batt_vars.p[t - 1, k])
                            prob.add_cst(
                                cst=batt_vars.p[t, k] - batt_vars.p[t - 1, k] <= batt_data_t.ramp_up[k] / Sbase * dt)

                # # # set the energy  value Et = E(t - 1) + dt * Pb / eff
                batt_vars.e[t, k] = prob.add_var(batt_data_t.e_min[k] / Sbase,
                                                 batt_data_t.e_max[k] / Sbase,
                                                 join("batt_e_", [t, k], "_"))

                if t > 0:
                    # energy decreases / increases with power · dt
                    prob.add_cst(cst=(batt_vars.e[t, k] == batt_vars.e[t - 1, k]
                                      + dt * (batt_data_t.discharge_efficiency[k] * p_pos
                                              - batt_data_t.charge_efficiency[k] * p_neg)),
                                 name=join("batt_energy_", [t, k], "_"))
                else:
                    # set the initial energy value
                    batt_vars.e[t, k] = energy_0[k] / Sbase

            else:

                # it is NOT dispatchable

                # Operational cost (linear...)
                f_obj += (batt_data_t.cost_1[k] * p_pos) + batt_data_t.cost_0[k]

                p = batt_data_t.p[k] / Sbase

                # the generator is not dispatchable at time step
                if p > 0:

                    batt_vars.shedding[t, k] = prob.add_var(0, p, join("bat_shedding_", [t, k], "_"))

                    prob.add_cst(
                        cst=batt_vars.p[t, k] == batt_data_t.p[k] / Sbase - batt_vars.shedding[t, k],
                        name=join("batt==PB-PBslack", [t, k], "_"))

                    f_obj += batt_data_t.cost_1[k] * batt_vars.shedding[t, k]

                elif p < 0:
                    # the negative sign is because P is already negative here
                    batt_vars.shedding[t, k] = prob.add_var(lb=0,
                                                            ub=-p,
                                                            name=join("bat_shedding_", [t, k], "_"))

                    prob.add_cst(
                        cst=batt_vars.p[t, k] == batt_data_t.p[k] / Sbase + batt_vars.shedding[t, k],
                        name=join("batt==PB+PBslack", [t, k], "_"))

                    f_obj += batt_data_t.cost_1[k] * batt_vars.shedding[t, k]

                else:
                    # the generation value is exactly zero, pass
                    pass

                batt_vars.producing[t, k] = 1
                batt_vars.shutting_down[t, k] = 0
                batt_vars.starting_up[t, k] = 0

            # add to the balance
            bus_vars.Pbalance[t, bus_idx] += batt_vars.p[t, k]

        else:
            # the generator is not available at a time step
            batt_vars.p[t, k] = 0.0

    return f_obj


def add_nodal_capacity_formulation(t: Union[int, None],
                                   nodal_capacity_vars: NodalCapacityVars,
                                   nodal_capacity_sign: float,
                                   capacity_nodes_idx: IntVec,
                                   prob: LpModel):
    """
    Add MIP generation formulation
    :param t: time step, if None we assume single time step
    :param nodal_capacity_vars: NodalCapacityVars structure
    :param nodal_capacity_sign:
    :param capacity_nodes_idx: IntVec
    :param prob: ORTools problem
    :return objective function
    """
    f_obj = 0.0
    for k, idx in enumerate(capacity_nodes_idx):
        # assign load shedding variable
        if nodal_capacity_sign < 0:
            nodal_capacity_vars.P[t, k] = prob.add_var(lb=0.0,
                                                       ub=9999.9,
                                                       name=join("nodal_capacity_", [t, k], "_"))

        else:
            nodal_capacity_vars.P[t, k] = prob.add_var(lb=-9999.9,
                                                       ub=0.0,
                                                       name=join("nodal_capacity_", [t, k], "_"))

        # maximize the nodal power injection
        f_obj += 100 * nodal_capacity_sign * nodal_capacity_vars.P[t, k]

    return f_obj


def add_linear_load_formulation(t: Union[int, None],
                                Sbase: float,
                                bus_vars: BusVars,
                                load_data_t: LoadData,
                                load_vars: LoadVars,
                                prob: LpModel):
    """
    Add MIP generation formulation
    :param t: time step, if None we assume single time step
    :param Sbase: base power (100 MVA)
    :param bus_vars: BusVars
    :param load_data_t: BatteryData structure
    :param load_vars: BatteryVars structure
    :param prob: ORTools problem
    :return objective function
    """
    f_obj = 0.0
    for k in range(load_data_t.nelm):

        bus_idx = load_data_t.bus_idx[k]

        if load_data_t.active[k] and bus_idx > -1:

            p_set = load_data_t.S[k].real / Sbase

            if p_set > 0.0:

                # assign load shedding variable
                load_vars.shedding[t, k] = prob.add_var(lb=0,
                                                        ub=p_set,
                                                        name=join("load_shedding_", [t, k], "_"))

                # store the load
                load_vars.p[t, k] = p_set - load_vars.shedding[t, k]

                load_vars.shedding_cost[t, k] = load_data_t.cost[k] * load_vars.shedding[t, k]

                # minimize the load shedding
                f_obj += load_vars.shedding_cost[t, k]
            else:
                # the load is negative, won't shed?
                load_vars.shedding[t, k] = 0.0

                # store the load
                load_vars.p[t, k] = load_data_t.S[k].real / Sbase

            # add to the balance
            bus_vars.Pbalance[t, bus_idx] -= load_vars.p[t, k]

        else:
            # the load is not available at time step
            load_vars.shedding[t, k] = 0.0

    return f_obj


def add_linear_branches_formulation(t: int,
                                    Sbase: float,
                                    bus_data_t: BusData,
                                    branch_data_t: PassiveBranchData,
                                    ctrl_branch_data_t: ActiveBranchData,
                                    branch_vars: BranchVars,
                                    bus_vars: BusVars,
                                    prob: LpModel,
                                    inf=1e20):
    """
    Formulate the branches
    :param t: time index
    :param Sbase: base power (100 MVA)
    :param bus_data_t: BusData
    :param branch_data_t: BranchData
    :param ctrl_branch_data_t: ControllableBranchData
    :param branch_vars: BranchVars
    :param bus_vars: BusVars
    :param prob: OR problem
    :param inf: number considered infinite
    :return objective function
    """
    f_obj = 0.0

    # for each branch
    for m in range(branch_data_t.nelm):
        fr = branch_data_t.F[m]
        to = branch_data_t.T[m]

        # copy rates
        branch_vars.rates[t, m] = branch_data_t.rates[m]

        if branch_data_t.active[m]:

            # declare the flow LPVar
            branch_vars.flows[t, m] = prob.add_var(lb=-inf,
                                                   ub=inf,
                                                   name=join("flow_", [t, m], "_"))

            if branch_data_t.dc[m]:

                # DC Branch
                if branch_data_t.R[m] == 0.0:
                    bk = 1e-20
                else:
                    bk = 1.0 / branch_data_t.R[m]

                branch_vars.flows[t, m] = bk * (bus_vars.Vm[t, fr] - bus_vars.Vm[t, to])

            else:
                # AC branch

                # compute the branch susceptance
                if branch_data_t.X[m] == 0.0:
                    bk = 1e-20
                else:
                    bk = 1.0 / branch_data_t.X[m]

                # compute the flow
                if ctrl_branch_data_t.tap_phase_control_mode[m] == TapPhaseControl.Pf:

                    # add angle
                    branch_vars.tap_angles[t, m] = prob.add_var(lb=ctrl_branch_data_t.tap_angle_min[m],
                                                                ub=ctrl_branch_data_t.tap_angle_max[m],
                                                                name=join("tap_ang_", [t, m], "_"))

                    # is a phase shifter device (like phase shifter transformer or VSC with P control)
                    # flow_ctr = branch_vars.flows[t, m] == bk * (
                    #         bus_vars.theta[t, fr] - bus_vars.theta[t, to] + branch_vars.tap_angles[t, m])
                    # prob.add_cst(cst=flow_ctr, name=join("Branch_flow_set_with_ps_", [t, m], "_"))

                    branch_vars.flows[t, m] = bk * (bus_vars.Va[t, fr] -
                                                    bus_vars.Va[t, to] +
                                                    branch_vars.tap_angles[t, m])

                else:  # rest of the branches
                    # is a phase shifter device (like phase shifter transformer or VSC with P control)
                    # flow_ctr = branch_vars.flows[t, m] == bk * (bus_vars.theta[t, fr] - bus_vars.theta[t, to])
                    # prob.add_cst(cst=flow_ctr, name=join("Branch_flow_set_", [t, m], "_"))

                    branch_vars.flows[t, m] = bk * (bus_vars.Va[t, fr] - bus_vars.Va[t, to])

            # power injected and subtracted due to the phase shift
            bus_vars.Pbalance[t, fr] -= branch_vars.flows[t, m]
            bus_vars.Pbalance[t, to] += branch_vars.flows[t, m]

            # add the flow constraint if monitored
            if branch_data_t.monitor_loading[m]:
                branch_vars.flow_slacks_pos[t, m] = prob.add_var(0, inf,
                                                                 name=join("flow_slack_pos_", [t, m], "_"))
                branch_vars.flow_slacks_neg[t, m] = prob.add_var(0, inf,
                                                                 name=join("flow_slack_neg_", [t, m], "_"))

                # add upper rate constraint
                branch_vars.flow_constraints_ub[t, m] = (branch_vars.flows[t, m] +
                                                         branch_vars.flow_slacks_pos[t, m] -
                                                         branch_vars.flow_slacks_neg[t, m]
                                                         <= branch_data_t.rates[m] / Sbase)
                prob.add_cst(cst=branch_vars.flow_constraints_ub[t, m],
                             name=join("br_flow_upper_lim_", [t, m]))

                # add lower rate constraint
                branch_vars.flow_constraints_lb[t, m] = (branch_vars.flows[t, m] +
                                                         branch_vars.flow_slacks_pos[t, m] -
                                                         branch_vars.flow_slacks_neg[t, m]
                                                         >= -branch_data_t.rates[m] / Sbase)
                prob.add_cst(cst=branch_vars.flow_constraints_lb[t, m],
                             name=join("br_flow_lower_lim_", [t, m]))

                branch_vars.overload_cost[t, m] = (branch_data_t.overload_cost[m] * branch_vars.flow_slacks_pos[t, m]
                                                   + branch_data_t.overload_cost[m] * branch_vars.flow_slacks_neg[t, m])
                # add to the objective function
                f_obj += branch_vars.overload_cost[t, m]

    return f_obj


def add_linear_branches_contingencies_formulation(t_idx: int,
                                                  Sbase: float,
                                                  branch_data_t: PassiveBranchData,
                                                  hvdc_vars: HvdcVars,
                                                  vsc_vars: VscVars,
                                                  branch_vars: BranchVars,
                                                  bus_vars: BusVars,
                                                  prob: LpModel,
                                                  linear_multi_contingencies: LinearMultiContingencies):
    """
    Formulate the branches
    :param t_idx: time index
    :param Sbase: base power (100 MVA)
    :param branch_data_t: BranchData
    :param hvdc_vars: HvdcVars
    :param vsc_vars: VscVars
    :param branch_vars: BranchVars
    :param bus_vars: BusVars
    :param prob: OR problem
    :param linear_multi_contingencies: LinearMultiContingencies
    :return objective function
    """
    f_obj = 0.0
    for c, contingency in enumerate(linear_multi_contingencies.multi_contingencies):

        # compute the contingency flow (Lp expression)
        contingency_flows, mask, changed_idx = contingency.get_lp_contingency_flows(
            base_flow=branch_vars.flows[t_idx, :],
            injections=bus_vars.Pinj[t_idx, :],
            hvdc_flow=hvdc_vars.flows[t_idx, :],
            vsc_flow=vsc_vars.flows[t_idx, :]
        )

        for m, contingency_flow in enumerate(contingency_flows):

            if mask[m]:

                if isinstance(contingency_flow, LpExp):  # if the contingency is not 0

                    # declare slack variables
                    pos_slack = prob.add_var(0, 1e20, join("br_cst_flow_pos_sl_", [t_idx, m, c]))
                    neg_slack = prob.add_var(0, 1e20, join("br_cst_flow_neg_sl_", [t_idx, m, c]))

                    # register the contingency data to evaluate the result at the end
                    branch_vars.add_contingency_flow(t=t_idx, m=m, c=c,
                                                     flow_var=contingency_flow,
                                                     neg_slack=neg_slack,
                                                     pos_slack=pos_slack)

                    # add upper rate constraint
                    prob.add_cst(
                        cst=contingency_flow + pos_slack - neg_slack <= branch_data_t.rates[m] / Sbase,
                        name=join("br_cst_flow_upper_lim_", [t_idx, m, c])
                    )

                    # add lower rate constraint
                    prob.add_cst(
                        cst=contingency_flow + pos_slack - neg_slack >= -branch_data_t.rates[m] / Sbase,
                        name=join("br_cst_flow_lower_lim_", [t_idx, m, c])
                    )

                    f_obj += pos_slack + neg_slack

    return f_obj


def add_linear_hvdc_formulation(t: int,
                                Sbase: float,
                                hvdc_data_t: HvdcData,
                                hvdc_vars: HvdcVars,
                                bus_vars: BusVars,
                                prob: LpModel):
    """

    :param t:
    :param Sbase:
    :param hvdc_data_t:
    :param hvdc_vars:
    :param bus_vars:
    :param prob:
    :return:
    """
    f_obj = 0.0
    for m in range(hvdc_data_t.nelm):

        fr = hvdc_data_t.F[m]
        to = hvdc_data_t.T[m]
        hvdc_vars.rates[t, m] = hvdc_data_t.rates[m]

        if hvdc_data_t.active[m]:

            if hvdc_data_t.control_mode[m] == HvdcControlType.type_0_free:

                # set the flow based on the angular difference
                P0 = hvdc_data_t.Pset[m] / Sbase
                k = hvdc_data_t.angle_droop[m]
                hvdc_vars.flows[t, m] = (P0 + k * (bus_vars.Va[t, fr] - bus_vars.Va[t, to]))

                # add the injections matching the flow
                bus_vars.Pbalance[t, fr] -= hvdc_vars.flows[t, m]
                bus_vars.Pbalance[t, to] += hvdc_vars.flows[t, m]

            elif hvdc_data_t.control_mode[m] == HvdcControlType.type_1_Pset:

                if hvdc_data_t.dispatchable[m]:

                    # declare the flow var
                    hvdc_vars.flows[t, m] = prob.add_var(lb=-hvdc_data_t.rates[m] / Sbase,
                                                         ub=hvdc_data_t.rates[m] / Sbase,
                                                         name=join("hvdc_flow_", [t, m], "_"))

                    # add the injections matching the flow
                    bus_vars.Pbalance[t, fr] -= hvdc_vars.flows[t, m]
                    bus_vars.Pbalance[t, to] += hvdc_vars.flows[t, m]

                else:

                    if hvdc_data_t.Pset[m] > hvdc_data_t.rates[m]:
                        P0 = hvdc_data_t.rates[m] / Sbase
                    elif hvdc_data_t.Pset[m] < -hvdc_data_t.rates[m]:
                        P0 = -hvdc_data_t.rates[m] / Sbase
                    else:
                        P0 = hvdc_data_t.Pset[m] / Sbase

                    # declare the flow var
                    hvdc_vars.flows[t, m] = prob.add_var(lb=P0, ub=P0,
                                                         name=join("hvdc_flow_", [t, m], "_"))

                    # add the injections matching the flow
                    bus_vars.Pbalance[t, fr] -= hvdc_vars.flows[t, m]
                    bus_vars.Pbalance[t, to] += hvdc_vars.flows[t, m]
            else:
                raise Exception('OPF: Unknown HVDC control mode {}'.format(hvdc_data_t.control_mode[m]))
        else:
            # not active, therefore the flow is exactly zero
            hvdc_vars.flows[t, m] = 0.0

    return f_obj


def add_linear_vsc_formulation(t: int,
                               Sbase: float,
                               vsc_data_t: VscData,
                               vsc_vars: VscVars,
                               bus_vars: BusVars,
                               prob: LpModel,
                               logger: Logger):
    """

    :param t:
    :param Sbase:
    :param vsc_data_t:
    :param vsc_vars:
    :param bus_vars:
    :param prob:
    :param logger:
    :return:
    """
    f_obj = 0.0
    any_dc_slack = False
    for m in range(vsc_data_t.nelm):

        fr = vsc_data_t.F[m]
        to = vsc_data_t.T[m]
        vsc_vars.rates[t, m] = vsc_data_t.rates[m]

        if vsc_data_t.active[m]:

            # declare the flow var
            vsc_vars.flows[t, m] = prob.add_var(lb=-vsc_data_t.rates[m] / Sbase,
                                                ub=vsc_data_t.rates[m] / Sbase,
                                                name=join("vsc_flow_", [t, m], "_"))

            # add the injections matching the flow
            bus_vars.Pbalance[t, fr] -= vsc_vars.flows[t, m]
            bus_vars.Pbalance[t, to] += vsc_vars.flows[t, m]

            if (vsc_data_t.control1[m] == ConverterControlType.Vm_dc or
                    vsc_data_t.control2[m] == ConverterControlType.Vm_dc):
                # set the DC slack
                bus_vars.Vm[t, fr] = 1.0
                any_dc_slack = True

        else:
            # not active, therefore the flow is exactly zero
            vsc_vars.flows[t, m] = 0.0

    if not any_dc_slack and vsc_data_t.nelm > 0:
        logger.add_warning("No DC Slack! set Vm_dc in any of the converters")

    return f_obj


def add_linear_node_balance(t_idx: int,
                            vd: IntVec,
                            bus_data: BusData,
                            bus_vars: BusVars,
                            nodal_capacity_vars: NodalCapacityVars,
                            capacity_nodes_idx: IntVec,
                            prob: LpModel,
                            logger: Logger):
    """
    Add the Kirchhoff nodal equality
    :param t_idx: time step
    :param vd: List of slack node indices
    :param bus_data: BusData
    :param bus_vars: BusVars
    :param nodal_capacity_vars: NodalCapacityVars
    :param capacity_nodes_idx: IntVec
    :param prob: LpModel
    :param logger: Logger
    """

    # Note: At this point, Pbalance has all the devices' power summed up inside (including branches)

    if len(capacity_nodes_idx) > 0:
        bus_vars.Pbalance[t_idx, capacity_nodes_idx] += nodal_capacity_vars.P[t_idx, :]

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
                name=join("kirchoff_", [t_idx, k], "_")
            )

    Va = np.angle(bus_data.Vbus)
    for i in vd:
        prob.set_var_bounds(var=bus_vars.Va[t_idx, i], lb=Va[i], ub=Va[i])


def add_copper_plate_balance(t_idx: int,
                             bus_vars: BusVars,
                             prob: LpModel, ):
    """
    Add the copperplate equality
    :param t_idx: time step
    :param bus_vars: BusVars
    :param prob: LpModel
    """

    bus_vars.kirchhoff[t_idx, 0] = prob.add_cst(
        cst=sum(bus_vars.Pbalance[t_idx, :]) == 0,
        name=join("copper_plate_", [t_idx, 0], "_")
    )


def add_hydro_formulation(t: Union[int, None],
                          time_global_tidx: Union[int, None],
                          time_array: DateVec,
                          Sbase: float,
                          node_vars: FluidNodeVars,
                          path_vars: FluidPathVars,
                          inj_vars: FluidInjectionVars,
                          node_data: FluidNodeData,
                          path_data: FluidPathData,
                          turbine_data: FluidTurbineData,
                          pump_data: FluidPumpData,
                          p2x_data: FluidP2XData,
                          generator_data: GeneratorData,
                          generator_vars: GenerationVars,
                          fluid_level_0: Vec,
                          prob: LpModel,
                          logger: Logger):
    """
    Formulate the branches
    :param t: local time index
    :param time_global_tidx: global time index
    :param time_array: list of time indices
    :param Sbase: base power of the system
    :param node_vars: FluidNodeVars
    :param path_vars: FluidPathVars
    :param inj_vars: FluidInjectionVars
    :param node_data: FluidNodeData
    :param path_data: FluidPathData
    :param turbine_data: FluidTurbineData
    :param pump_data: FluidPumpData
    :param p2x_data: FluidP2XData
    :param generator_data: GeneratorData
    :param generator_vars: GeneratorVars
    :param fluid_level_0: Initial node level
    :param prob: OR problem
    :param logger: log of the LP
    :return objective function
    """

    f_obj = 0.0

    for m in range(node_data.nelm):
        node_vars.spillage[t, m] = prob.add_var(lb=0.00,
                                                ub=1e20,
                                                name=join("NodeSpillage_", [t, m], "_"))

        f_obj += node_data.spillage_cost[m] * node_vars.spillage[t, m]
        # f_obj += node_vars.spillage[t, m]

        min_abs_level = node_data.max_level[m] * node_data.min_soc[m]

        node_vars.current_level[t, m] = prob.add_var(lb=min_abs_level,
                                                     ub=node_data.max_level[m] * node_data.max_soc[m],
                                                     name=join("level_", [t, m], "_"))

        if min_abs_level < node_data.min_level[m]:
            logger.add_error(msg='Node SOC is below the allowed minimum level',
                             value=min_abs_level,
                             expected_value=node_data.min_level[m],
                             device_class="FluidNode",
                             device_property=f"Min SOC at {t}")

    for m in range(path_data.nelm):
        path_vars.flow[t, m] = prob.add_var(lb=path_data.min_flow[m],
                                            ub=path_data.max_flow[m],
                                            name=join("hflow_", [t, m], "_"))

    # Constraints
    for m in range(path_data.nelm):
        # inflow: fluid flow entering the target node in m3/s
        # outflow: fluid flow leaving the source node in m3/s
        # flow: amount of fluid flowing through the river in m3/s
        node_vars.flow_in[t, path_data.target_idx[m]] += path_vars.flow[t, m]
        node_vars.flow_out[t, path_data.source_idx[m]] += path_vars.flow[t, m]

    for m in range(turbine_data.nelm):
        gen_idx = turbine_data.generator_idx[m]
        plant_idx = turbine_data.plant_idx[m]

        # flow [m3/s] = pgen [pu] * max_flow [m3/s] / (Pgen_max [MW] / Sbase [MW] * eff)
        coeff = turbine_data.max_flow_rate[m] / (generator_data.pmax[gen_idx] / Sbase * turbine_data.efficiency[m])
        turbine_flow = (generator_vars.p[t, gen_idx] * coeff)
        # node_vars.flow_out[t, plant_idx] = turbine_flow  # assume only 1 turbine connected

        # if t > 0:
        inj_vars.flow[t, m] = turbine_flow  # to retrieve the value later on

        prob.add_cst(cst=(node_vars.flow_out[t, plant_idx] == turbine_flow),
                     name=join("turbine_river_", [t, m], "_"))

        if generator_data.pmin[gen_idx] < 0:
            logger.add_error(msg='Turbine generator pmin < 0 is not possible',
                             value=generator_data.pmin[gen_idx])

        # f_obj += turbine_flow

    for m in range(pump_data.nelm):
        gen_idx = pump_data.generator_idx[m]
        plant_idx = pump_data.plant_idx[m]

        # flow [m3/s] = pcons [pu] * max_flow [m3/s] * eff / (Pcons_min [MW] / Sbase [MW])
        # invert the efficiency compared to a turbine
        # pmin instead of pmax because the sign should be inverted (consuming instead of generating)
        coeff = pump_data.max_flow_rate[m] * pump_data.efficiency[m] / (abs(generator_data.pmin[gen_idx]) / Sbase)
        pump_flow = (generator_vars.p[t, gen_idx] * coeff)
        # node_vars.flow_in[t, plant_idx] = pump_flow  # assume only 1 pump connected

        # if t > 0:
        inj_vars.flow[t, m + turbine_data.nelm] = - pump_flow
        prob.add_cst(cst=(node_vars.flow_in[t, plant_idx] == - pump_flow),
                     name=join("pump_river_", [t, m], "_"))

        if generator_data.pmax[gen_idx] > 0:
            logger.add_error(msg='Pump generator pmax > 0 is not possible',
                             value=generator_data.pmax[gen_idx])

        # f_obj -= pump_flow

    for m in range(p2x_data.nelm):
        gen_idx = p2x_data.generator_idx[m]

        # flow[m3/s] = pcons [pu] * max_flow [m3/s] * eff / (Pcons_max [MW] / Sbase [MW])
        # invert the efficiency compared to a turbine
        # pmin instead of pmax because the sign should be inverted (consuming instead of generating)
        coeff = p2x_data.max_flow_rate[m] * p2x_data.efficiency[m] / (abs(generator_data.pmin[gen_idx]) / Sbase)
        p2x_flow = (generator_vars.p[t, gen_idx] * coeff)

        # if t > 0:
        node_vars.p2x_flow[t, p2x_data.plant_idx[m]] -= p2x_flow
        inj_vars.flow[t, m + turbine_data.nelm + pump_data.nelm] = - p2x_flow

        if generator_data.pmax[gen_idx] > 0:
            logger.add_error(msg='P2X generator pmax > 0 is not possible',
                             value=generator_data.pmax[gen_idx])

        # f_obj -= p2x_flow

    if time_global_tidx is not None:
        # constraints for the node level
        for m in range(node_data.nelm):
            if t == 0:
                if len(time_array) > time_global_tidx + 1:
                    dt = (time_array[time_global_tidx + 1] - time_array[time_global_tidx]).seconds
                else:
                    dt = 3600

                # Initialize level at fluid_level_0
                prob.add_cst(cst=(node_vars.current_level[t, m] ==
                                  fluid_level_0[m]
                                  + dt * node_data.inflow[m]
                                  + dt * node_vars.flow_in[t, m]
                                  + dt * node_vars.p2x_flow[t, m]
                                  - dt * node_vars.spillage[t, m]
                                  - dt * node_vars.flow_out[t, m]),
                             name=join("nodal_balance_", [t, m], "_"))
            else:
                # Update the level according to the in and out flows as time passes
                dt = (time_array[time_global_tidx] - time_array[time_global_tidx - 1]).seconds

                prob.add_cst(cst=(node_vars.current_level[t, m] ==
                                  node_vars.current_level[t - 1, m]
                                  + dt * node_data.inflow[m]
                                  + dt * node_vars.flow_in[t, m]
                                  + dt * node_vars.p2x_flow[t, m]
                                  - dt * node_vars.spillage[t, m]
                                  - dt * node_vars.flow_out[t, m]),
                             name=join("nodal_balance_", [t, m], "_"))
    return f_obj


def run_linear_opf_ts(grid: MultiCircuit,
                      time_indices: Union[IntVec, None],
                      solver_type: MIPSolvers = MIPSolvers.HIGHS,
                      zonal_grouping: ZonalGrouping = ZonalGrouping.NoGrouping,
                      skip_generation_limits: bool = False,
                      consider_contingencies: bool = False,
                      contingency_groups_used: Union[List[ContingencyGroup], None] = None,
                      unit_commitment: bool = False,
                      ramp_constraints: bool = False,
                      generation_expansion_planning: bool = False,
                      all_generators_fixed: bool = False,
                      lodf_threshold: float = 0.001,
                      maximize_inter_area_flow: bool = False,
                      inter_aggregation_info: InterAggregationInfo | None = None,
                      energy_0: Union[Vec, None] = None,
                      fluid_level_0: Union[Vec, None] = None,
                      optimize_nodal_capacity: bool = False,
                      nodal_capacity_sign: float = 1.0,
                      capacity_nodes_idx: Union[IntVec, None] = None,
                      logger: Logger = Logger(),
                      progress_text: Union[None, Callable[[str], None]] = None,
                      progress_func: Union[None, Callable[[float], None]] = None,
                      export_model_fname: Union[None, str] = None,
                      verbose: int = 0,
                      robust: bool = False) -> OpfVars:
    """
    Run linear optimal power flow
    :param grid: MultiCircuit instance
    :param time_indices: Time indices (in the general scheme)
    :param solver_type: MIP solver to use
    :param zonal_grouping: Zonal grouping?
    :param skip_generation_limits: Skip the generation limits?
    :param consider_contingencies: Consider the contingencies?
    :param contingency_groups_used: List of contingency groups to use
    :param unit_commitment: Formulate unit commitment?
    :param ramp_constraints: Formulate ramp constraints?
    :param generation_expansion_planning: Generation expansion planning?
    :param all_generators_fixed: All generators take their snapshot or profile values
                                 instead of resorting to dispatchable status
    :param lodf_threshold: LODF threshold value to consider contingencies
    :param maximize_inter_area_flow: Maximize the inter-area flow?
    :param inter_aggregation_info: Inter rea (or country, etc) information
    :param energy_0: Vector of initial energy for batteries (size: Number of batteries)
    :param fluid_level_0: initial fluid level of the nodes
    :param optimize_nodal_capacity: Optimize the nodal capacity? (optional)
    :param nodal_capacity_sign: if > 0 the generation is maximized, if < 0 the load is maximized
    :param capacity_nodes_idx: Array of bus indices to optimize their nodal capacity for
    :param logger: logger instance
    :param progress_text: Text progress callback
    :param progress_func: Numerical progress callback
    :param export_model_fname: Export the model into LP and MPS?
    :param verbose: verbosity level
    :param robust: Robust optimization?
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

    active_nodal_capacity = True
    if capacity_nodes_idx is None:
        active_nodal_capacity = False
        capacity_nodes_idx = np.zeros(0, dtype=int)

    if contingency_groups_used is None:
        contingency_groups_used = grid.get_contingency_groups()

    nt = len(time_indices) if len(time_indices) > 0 else 1
    n = grid.get_bus_number()
    nbr = grid.get_branch_number(add_vsc=False, add_hvdc=False, add_switch=True)
    ng = grid.get_generators_number()
    nb = grid.get_batteries_number()
    nl = grid.get_load_like_device_number()
    n_hvdc = grid.get_hvdc_number()
    n_vsc = grid.get_vsc_number()
    n_fluid_node = grid.get_fluid_nodes_number()
    n_fluid_path = grid.get_fluid_paths_number()
    n_fluid_inj = grid.get_fluid_injection_number()

    # gather the fuels and emission rates matrices
    gen_emissions_rates_matrix = grid.get_gen_emission_rates_sparse_matrix()
    gen_fuel_rates_matrix = grid.get_gen_fuel_rates_sparse_matrix()
    gen_tech_shares_matrix = grid.get_gen_technology_connectivity_matrix()
    batt_tech_shares_matrix = grid.get_batt_technology_connectivity_matrix()

    if maximize_inter_area_flow:
        inter_area_branches = inter_aggregation_info.lst_br
        inter_area_hvdc = inter_aggregation_info.lst_br_hvdc
    else:
        inter_area_branches = list()
        inter_area_hvdc = list()

    # declare structures of LP vars
    mip_vars = OpfVars(nt=nt, nbus=n, ng=ng, nb=nb, nl=nl,
                       nbr=nbr, n_hvdc=n_hvdc, n_vsc=n_vsc,
                       n_fluid_node=n_fluid_node,
                       n_fluid_path=n_fluid_path,
                       n_fluid_inj=n_fluid_inj,
                       n_cap_buses=len(capacity_nodes_idx))

    # create the MIP problem object
    lp_model: LpModel = LpModel(solver_type)

    # objective function
    f_obj: Union[LpExp, float] = 0.0

    for local_t_idx, global_t_idx in enumerate(time_indices):  # use time_indices = [None] to simulate the snapshot

        # time indices:
        # imagine that the complete GridCal DB time goes from 0 to 1000
        # but, for whatever reason, time_indices is [100..200]
        # local_t_idx would go from 0..100
        # global_t_idx would go from 100..200

        # compile the circuit at the master time index ------------------------------------------------------------
        # note: There are very little chances of simplifying this step and experience shows
        #       it is not worth the effort, so compile every time step
        nc: NumericalCircuit = compile_numerical_circuit_at(
            circuit=grid,
            t_idx=global_t_idx,  # yes, this is not a bug
            bus_dict=bus_dict,
            areas_dict=areas_dict,
            fill_gep=generation_expansion_planning,
            logger=logger
        )

        indices = nc.get_simulation_indices()

        # formulate the bus angles ---------------------------------------------------------------------------------
        for k in range(nc.bus_data.nbus):
            # we declare Vm for DC buses and Va for AC buses
            if nc.bus_data.is_dc[k]:
                mip_vars.bus_vars.Vm[local_t_idx, k] = lp_model.add_var(
                    lb=nc.bus_data.Vmin[k],
                    ub=nc.bus_data.Vmax[k],
                    name=join("Vm_", [local_t_idx, k], "_")
                )
            else:
                mip_vars.bus_vars.Va[local_t_idx, k] = lp_model.add_var(
                    lb=nc.bus_data.angle_min[k],
                    ub=nc.bus_data.angle_max[k],
                    name=join("Va_", [local_t_idx, k], "_")
                )

        # formulate loads ------------------------------------------------------------------------------------------
        f_obj += add_linear_load_formulation(
            t=local_t_idx,
            Sbase=nc.Sbase,
            load_data_t=nc.load_data,
            bus_vars=mip_vars.bus_vars,
            load_vars=mip_vars.load_vars,
            prob=lp_model
        )

        # formulate generation -------------------------------------------------------------------------------------
        f_obj += add_linear_generation_formulation(
            t=local_t_idx,
            Sbase=nc.Sbase,
            time_array=grid.time_profile,
            bus_vars=mip_vars.bus_vars,
            gen_data_t=nc.generator_data,
            gen_vars=mip_vars.gen_vars,
            prob=lp_model,
            unit_commitment=unit_commitment,
            ramp_constraints=ramp_constraints,
            skip_generation_limits=skip_generation_limits,
            all_generators_fixed=all_generators_fixed,
            vd=indices.vd,
            nodal_capacity_active=active_nodal_capacity,
            generation_expansion_planning=generation_expansion_planning,
        )

        # formulate batteries --------------------------------------------------------------------------------------
        if local_t_idx == 0 and energy_0 is None:
            # declare the initial energy of the batteries
            energy_0 = nc.battery_data.soc_0 * nc.battery_data.enom  # in MWh here

        f_obj += add_linear_battery_formulation(
            t=local_t_idx,
            Sbase=nc.Sbase,
            time_array=grid.time_profile,
            bus_vars=mip_vars.bus_vars,
            batt_data_t=nc.battery_data,
            batt_vars=mip_vars.batt_vars,
            prob=lp_model,
            unit_commitment=unit_commitment,
            ramp_constraints=ramp_constraints,
            skip_generation_limits=skip_generation_limits,
            generation_expansion_planning=generation_expansion_planning,
            energy_0=energy_0
        )

        # formulate batteries --------------------------------------------------------------------------------------
        if optimize_nodal_capacity:
            f_obj += add_nodal_capacity_formulation(
                t=local_t_idx,
                nodal_capacity_vars=mip_vars.nodal_capacity_vars,
                nodal_capacity_sign=nodal_capacity_sign,
                capacity_nodes_idx=capacity_nodes_idx,
                prob=lp_model
            )

        # add emissions ------------------------------------------------------------------------------------------------
        if gen_emissions_rates_matrix.shape[0] > 0:
            # amount of emissions per gas
            emissions = lpDot(gen_emissions_rates_matrix, mip_vars.gen_vars.p[local_t_idx, :])

            f_obj += lp_model.sum(emissions)

        # add fuels ----------------------------------------------------------------------------------------------------
        if gen_fuel_rates_matrix.shape[0] > 0:
            # amount of fuels
            fuels_amount = lpDot(gen_fuel_rates_matrix, mip_vars.gen_vars.p[local_t_idx, :])

            f_obj += lp_model.sum(fuels_amount)

        # --------------------------------------------------------------------------------------------------------------
        # if no zonal grouping, all the grid is considered...
        if zonal_grouping == ZonalGrouping.NoGrouping:

            # formulate hvdc -------------------------------------------------------------------------------------------
            f_obj += add_linear_hvdc_formulation(
                t=local_t_idx,
                Sbase=nc.Sbase,
                hvdc_data_t=nc.hvdc_data,
                hvdc_vars=mip_vars.hvdc_vars,
                bus_vars=mip_vars.bus_vars,
                prob=lp_model
            )

            # formulate vsc --------------------------------------------------------------------------------------------
            f_obj += add_linear_vsc_formulation(
                t=local_t_idx,
                Sbase=nc.Sbase,
                vsc_data_t=nc.vsc_data,
                vsc_vars=mip_vars.vsc_vars,
                bus_vars=mip_vars.bus_vars,
                prob=lp_model,
                logger=logger
            )

            # formulate branches ---------------------------------------------------------------------------------------
            f_obj += add_linear_branches_formulation(
                t=local_t_idx,
                Sbase=nc.Sbase,
                bus_data_t=nc.bus_data,
                branch_data_t=nc.passive_branch_data,
                ctrl_branch_data_t=nc.active_branch_data,
                branch_vars=mip_vars.branch_vars,
                bus_vars=mip_vars.bus_vars,
                prob=lp_model,
                inf=1e20
            )

            # formulate nodes ------------------------------------------------------------------------------------------

            add_linear_node_balance(
                t_idx=local_t_idx,
                vd=indices.vd,
                bus_data=nc.bus_data,
                bus_vars=mip_vars.bus_vars,
                nodal_capacity_vars=mip_vars.nodal_capacity_vars,
                capacity_nodes_idx=capacity_nodes_idx,
                prob=lp_model,
                logger=logger
            )

            # add branch contingencies ---------------------------------------------------------------------------------
            if consider_contingencies:

                if len(contingency_groups_used) > 0:
                    # The contingencies' formulation uses the total nodal injection stored in bus_vars,
                    # hence, this step goes before the add_linear_node_balance function

                    # compute the PTDF and LODF
                    ls = LinearAnalysis(nc=nc,
                                        distributed_slack=False,
                                        correct_values=True)

                    # Compute the more generalistic contingency structures
                    mctg = LinearMultiContingencies(grid=grid,
                                                    contingency_groups_used=contingency_groups_used)

                    mctg.compute(lin=ls,
                                 ptdf_threshold=lodf_threshold,
                                 lodf_threshold=lodf_threshold)

                    # formulate the contingencies
                    f_obj += add_linear_branches_contingencies_formulation(
                        t_idx=local_t_idx,
                        Sbase=nc.Sbase,
                        branch_data_t=nc.passive_branch_data,
                        branch_vars=mip_vars.branch_vars,
                        hvdc_vars=mip_vars.hvdc_vars,
                        vsc_vars=mip_vars.vsc_vars,
                        bus_vars=mip_vars.bus_vars,
                        prob=lp_model,
                        linear_multi_contingencies=mctg
                    )
                else:
                    logger.add_warning(msg="Contingencies enabled, but no contingency groups provided")

            # add inter area branch flow maximization ------------------------------------------------------------------
            if maximize_inter_area_flow:

                for branches_list in [inter_area_branches, inter_area_hvdc]:
                    for k, branch, sense in branches_list:
                        # we want to maximize, hence the minus sign
                        f_obj += mip_vars.branch_vars.flows[local_t_idx, k] * (- sense)

            # add hydro side -------------------------------------------------------------------------------------------
            if local_t_idx == 0 and fluid_level_0 is None:
                # declare the initial level of the fluid nodes
                fluid_level_0 = nc.fluid_node_data.initial_level

            if n_fluid_node > 0:
                f_obj += add_hydro_formulation(t=local_t_idx,
                                               time_global_tidx=global_t_idx,
                                               time_array=grid.time_profile,
                                               Sbase=nc.Sbase,
                                               node_vars=mip_vars.fluid_node_vars,
                                               path_vars=mip_vars.fluid_path_vars,
                                               inj_vars=mip_vars.fluid_inject_vars,
                                               node_data=nc.fluid_node_data,
                                               path_data=nc.fluid_path_data,
                                               turbine_data=nc.fluid_turbine_data,
                                               pump_data=nc.fluid_pump_data,
                                               p2x_data=nc.fluid_p2x_data,
                                               generator_data=nc.generator_data,
                                               generator_vars=mip_vars.gen_vars,
                                               fluid_level_0=fluid_level_0,
                                               prob=lp_model,
                                               logger=logger)

        elif zonal_grouping == ZonalGrouping.All:
            # this is the copper plate approach
            add_copper_plate_balance(
                t_idx=local_t_idx,
                bus_vars=mip_vars.bus_vars,
                prob=lp_model,
            )

        # production equals demand -------------------------------------------------------------------------------------
        # NOTE: The production == demand, happens with the kirchoff equation for the grid and with the
        # copper plate balance for the copper plate scenario

        if progress_func is not None:
            progress_func((local_t_idx + 1) / nt * 100.0)

    # set the objective function
    lp_model.minimize(f_obj)

    # solve
    if progress_text is not None:
        progress_text("Solving...")

    if progress_func is not None:
        progress_func(0)

    if export_model_fname is not None:
        lp_model.save_model(file_name=export_model_fname)
        logger.add_info("LP model saved as", value=export_model_fname)
        print('LP model saved as:', export_model_fname)

    status = lp_model.solve(robust=robust, show_logs=verbose > 0, progress_text=progress_text)

    # gather the results
    logger.add_info(msg="Status", value=lp_model.status2string(status))

    if status == LpModel.OPTIMAL:
        logger.add_info("Objective function", value=lp_model.fobj_value())
        mip_vars.acceptable_solution = True
    else:
        logger.add_error("The problem does not have an optimal solution.")
        mip_vars.acceptable_solution = False
        lp_file_name = os.path.join(opf_file_path(), f"{grid.name} opf debug.lp")
        lp_model.save_model(file_name=lp_file_name)
        logger.add_info("Debug LP model saved", value=lp_file_name)

    # convert the lp vars to their values
    vars_v = mip_vars.get_values(Sbase=grid.Sbase,
                                 model=lp_model,
                                 gen_emissions_rates_matrix=gen_emissions_rates_matrix,
                                 gen_fuel_rates_matrix=gen_fuel_rates_matrix,
                                 gen_tech_shares_matrix=gen_tech_shares_matrix,
                                 batt_tech_shares_matrix=batt_tech_shares_matrix)

    # add the model logger to the main logger
    logger += lp_model.logger

    # lp_model.save_model('nodal_opf.lp')
    return vars_v
