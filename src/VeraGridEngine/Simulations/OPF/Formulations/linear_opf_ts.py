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

from VeraGridEngine.IO.file_system import opf_file_path
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Aggregation.inter_aggregation_info import InterAggregationInfo
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
from VeraGridEngine.DataStructures.fluid_node_data import FluidNodeData
from VeraGridEngine.DataStructures.fluid_path_data import FluidPathData
from VeraGridEngine.DataStructures.fluid_turbine_data import FluidTurbineData
from VeraGridEngine.DataStructures.fluid_pump_data import FluidPumpData
from VeraGridEngine.DataStructures.fluid_p2x_data import FluidP2XData
from VeraGridEngine.basic_structures import Logger, Vec, IntVec, DateVec, Mat
from VeraGridEngine.Utils.MIP.selected_interface import LpExp, LpVar, LpModel, lpDot, join, get_model_instance
from VeraGridEngine.enumerations import (HvdcControlType, ZonalGrouping, MIPSolvers, TapPhaseControl,
                                         ConverterControlType, MIPFramework, OpfDispatchMode)
from VeraGridEngine.Simulations.LinearFactors.linear_analysis import (LinearAnalysis, LinearMultiContingency,
                                                                      LinearMultiContingencies)


def get_hydro_power_to_flow_coeff(flow_rate: float,
                                  efficiency: float,
                                  rated_power: float,
                                  sbase: float,
                                  logger: Logger,
                                  device_label: str) -> float:
    """
    Build one safe power-to-flow conversion coefficient for hydro-like devices.

    :param flow_rate: Device maximum flow rate.
    :param efficiency: Device efficiency factor.
    :param rated_power: Absolute generator power magnitude used in the conversion.
    :param sbase: System base power.
    :param logger: Simulation logger.
    :param device_label: Device family label for diagnostics.
    :return: Finite coefficient or ``0.0`` for invalid data.
    """
    if not np.isfinite(flow_rate) or flow_rate < 0.0:
        logger.add_error(msg=f'Invalid {device_label} flow rate for hydro OPF coefficient',
                         value=flow_rate)
        return 0.0
    else:
        pass

    if not np.isfinite(efficiency) or efficiency <= 0.0:
        logger.add_error(msg=f'Invalid {device_label} efficiency for hydro OPF coefficient',
                         value=efficiency)
        return 0.0
    else:
        pass

    if not np.isfinite(rated_power) or rated_power <= 0.0:
        logger.add_error(msg=f'Invalid {device_label} generator power bound for hydro OPF coefficient',
                         value=rated_power)
        return 0.0
    else:
        pass

    if not np.isfinite(sbase) or sbase <= 0.0:
        logger.add_error(msg='Invalid system base power for hydro OPF coefficient',
                         value=sbase)
        return 0.0
    else:
        pass

    return flow_rate / (rated_power / sbase * efficiency)


class BusVars:
    """
    Struct to store the bus related vars
    """

    __slots__ = (
        'Va',
        'Vm',
        'Pinj',
        'Pgen',
        'Pbalance',
        'kirchhoff',
        'shadow_prices',
    )

    def __init__(self, nt: int, n_elm: int):
        """
        BusVars structure
        :param nt: Number of time steps
        :param n_elm: Number of branches
        """
        self.Va = np.zeros((nt, n_elm), dtype=object)
        self.Vm = np.ones((nt, n_elm), dtype=object)
        self.Pinj = np.zeros((nt, n_elm), dtype=object)
        self.Pgen = np.zeros((nt, n_elm), dtype=object)
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

        for t in range(nt):
            for i in range(n_elm):
                data.Va[t, i] = model.get_value(self.Va[t, i])
                data.Vm[t, i] = model.get_value(self.Vm[t, i])
                data.Pinj[t, i] = model.get_value(self.Pinj[t, i]) * Sbase
                data.Pgen[t, i] = model.get_value(self.Pgen[t, i])
                data.Pbalance[t, i] = model.get_value(self.Pbalance[t, i]) * Sbase
                data.shadow_prices[t, i] = model.get_dual_value(self.kirchhoff[t, i])

        # format the arrays appropriately
        data.Va = data.Va.astype(float, copy=False)
        data.Vm = data.Vm.astype(float, copy=False)
        data.Pinj = data.Pinj.astype(float, copy=False)
        data.Pgen = data.Pgen.astype(float, copy=False)
        data.Pbalance = data.Pbalance.astype(float, copy=False)
        data.shadow_prices = data.shadow_prices.astype(float, copy=False)

        return data


class NodalCapacityVars:
    """
    Struct to store the nodal capacity related vars
    """

    __slots__ = (
        'P',
    )

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

    __slots__ = (
        'shedding',
        'p',
        'shedding_cost',
    )

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

    __slots__ = (
        'p',
        'dp',
        'shedding',
        'reserve',
        'producing',
        'starting_up',
        'shutting_down',
        'cost',
        'invested',
    )

    def __init__(self, nt: int, n_elm: int):
        """
        GenerationVars structure
        :param nt: Number of time steps
        :param n_elm: Number of generators
        """
        self.p = np.zeros((nt, n_elm), dtype=object)
        self.dp = np.zeros((nt, n_elm), dtype=object)
        self.shedding = np.zeros((nt, n_elm), dtype=object)
        self.reserve = np.zeros((nt, n_elm), dtype=object)
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
                data.dp[t, i] = model.get_value(self.dp[t, i]) * Sbase
                data.shedding[t, i] = model.get_value(self.shedding[t, i]) * Sbase
                data.reserve[t, i] = model.get_value(self.reserve[t, i]) * Sbase
                data.producing[t, i] = model.get_value(self.producing[t, i])
                data.starting_up[t, i] = model.get_value(self.starting_up[t, i])
                data.shutting_down[t, i] = model.get_value(self.shutting_down[t, i])
                data.cost[t, i] = model.get_value(self.cost[t, i]) * Sbase
                data.invested[t, i] = model.get_value(self.invested[t, i])

        # format the arrays appropriately
        data.p = data.p.astype(float, copy=False)
        data.dp = data.dp.astype(float, copy=False)
        data.shedding = data.shedding.astype(float, copy=False)
        data.reserve = data.reserve.astype(float, copy=False)
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

    __slots__ = (
        'e',
    )

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

    __slots__ = (
        'flows',
        'z_flows',
        'losses',
        'flow_slacks_pos',
        'flow_slacks_neg',
        'tap_angles',
        'flow_constraints_ub',
        'flow_constraints_lb',
        'overload_cost',
        'rates',
        'loading',
        'contingency_flow_data',
    )

    def __init__(self, nt: int, n_elm: int):
        """
        BranchVars structure
        :param nt: Number of time steps
        :param n_elm: Number of branches
        """
        self.flows = np.zeros((nt, n_elm), dtype=object)
        self.z_flows = np.zeros((nt, n_elm), dtype=object)  # absolute used with add_losses_approximation
        self.losses = np.zeros((nt, n_elm), dtype=object)  # absolute used with add_losses_approximation
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
                data.losses[t, i] = model.get_value(self.losses[t, i]) * Sbase

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

    __slots__ = ("flows", "rates", "loading")

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

    __slots__ = ("flows", "rates", "loading")

    def __init__(self, nt: int, n_elm: int):
        """
        GenerationVars structure
        :param nt: Number of time steps
        :param n_elm: Number of branches
        """
        self.flows = np.zeros((nt, n_elm), dtype=object)

        self.rates = np.zeros((nt, n_elm), dtype=float)
        self.loading = np.zeros((nt, n_elm), dtype=float)

    def get_values(self, Sbase: float, model: LpModel) -> "VscVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: VscVars
        """
        nt, n_elm = self.flows.shape
        data = VscVars(nt=nt, n_elm=n_elm)
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

    __slots__ = ("p2x_flow", "current_level", "spillage", "flow_in", "flow_out", "water_balance", "fluid_value")

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
        self.water_balance = np.zeros((nt, n_elm), dtype=object)
        self.fluid_value = np.zeros((nt, n_elm), dtype=float)

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
                water_balance: object = self.water_balance[t, i]
                if isinstance(water_balance, (int, float)):
                    data.fluid_value[t, i] = 0.0
                else:
                    water_balance_dual: float = model.get_dual_value(water_balance)
                    # IMPORTANT FLUID VALUE SIGN CONVENTION:
                    # The LP dual belongs to the equality written as
                    # level[t] = previous_level + inflows - spillage - outflows.
                    # That raw row dual has the opposite sign of the intuitive
                    # marginal value of one extra stored m3 of fluid.  The public
                    # result therefore reports -dual so positive values mean that
                    # stored fluid reduces the OPF objective cost.
                    data.fluid_value[t, i] = -water_balance_dual

        # format the arrays appropriately
        data.p2x_flow = data.p2x_flow.astype(float, copy=False)
        data.current_level = data.current_level.astype(float, copy=False)
        data.spillage = data.spillage.astype(float, copy=False)
        data.flow_in = data.flow_in.astype(float, copy=False)
        data.flow_out = data.flow_out.astype(float, copy=False)
        data.fluid_value = data.fluid_value.astype(float, copy=False)

        # from the data object itself
        # data.min_level = self.min_level
        # data.max_level = self.max_level
        # data.initial_level = self.initial_level

        return data


class FluidPathVars:
    """
    Struct to store the vars of paths of fluid type
    """

    __slots__ = ("flow",)

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

    __slots__ = ("flow",)

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

    __slots__ = (
        "system_fuel",
        "system_emissions",
        "system_unit_energy_cost",
        "system_total_energy_cost",
        "power_by_technology",
    )

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
                shedding_cost: Mat):
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
        """
        self.system_fuel = (gen_fuel_rates_matrix * gen_p.T).T
        self.system_emissions = (gen_emissions_rates_matrix * gen_p.T).T
        self.power_by_technology = (gen_tech_shares_matrix * gen_p.T).T
        self.power_by_technology += (batt_tech_shares_matrix * batt_p.T).T

        with np.errstate(divide='ignore', invalid='ignore'):  # numpy magic to ignore the zero divisions

            self.system_total_energy_cost = np.nan_to_num(gen_cost).sum(axis=1)
            self.system_total_energy_cost += np.nan_to_num(shedding_cost).sum(axis=1)

            self.system_unit_energy_cost = self.system_total_energy_cost / np.nan_to_num(gen_p).sum(axis=1)

        return self


class OpfVars:
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
        "n_fluid_node",
        "n_fluid_path",
        "n_fluid_inj",
        "n_cap_buses",
        "acceptable_solution",
        "bus_vars",
        "nodal_capacity_vars",
        "load_vars",
        "gen_vars",
        "batt_vars",
        "branch_vars",
        "hvdc_vars",
        "vsc_vars",
        "fluid_node_vars",
        "fluid_path_vars",
        "fluid_inject_vars",
        "sys_vars",
    )

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
                                              shedding_cost=data.load_vars.shedding_cost)

        data.acceptable_solution = self.acceptable_solution

        return data


def get_time_increment_seconds(time_array: DateVec, idx: int) -> float:
    """
    Return the duration represented by a time step.
    """
    if len(time_array) <= 1:
        return 3600.0
    if idx > 0:
        return (time_array[idx] - time_array[idx - 1]).total_seconds()
    return (time_array[1] - time_array[0]).total_seconds()


def get_time_increment_hours(time_array: DateVec, idx: int) -> float:
    """
    Return the duration represented by a time step in hours.
    """
    return get_time_increment_seconds(time_array=time_array, idx=idx) / 3600.0


def get_model_step_hours(time_array: DateVec, local_t: int, global_t: Union[int, None]) -> float:
    """
    Return the time-step duration in hours for a local optimization row.
    """
    idx: int = local_t
    if local_t == 0 and global_t is not None:
        idx = global_t
    else:
        idx = local_t
    return get_time_increment_hours(time_array=time_array, idx=idx)


def get_min_time_window(time_array: DateVec, local_t: int, min_hours: float) -> list[int]:
    """
    Return the backward-looking window of indices that must honor a minimum up/down duration.
    """
    if min_hours <= 0.0:
        return list()

    covered_hours = 0.0
    window: list[int] = list()
    tau = local_t
    while tau >= 0 and covered_hours + 1e-12 < min_hours:
        window.append(tau)
        covered_hours += get_time_increment_hours(time_array, tau)
        tau -= 1

    return window


def add_generator_ramp_constraints(local_t: int,
                                   k: int,
                                   Sbase: float,
                                   time_array: DateVec,
                                   gen_data_t: GeneratorData,
                                   gen_vars: "GenerationVars",
                                   prob: LpModel,
                                   logger: Logger) -> None:
    """
    Add symmetric generator ramp constraints using positive ramp-up/ramp-down limits.
    """
    dt = get_time_increment_hours(time_array, local_t)

    ramp_up = gen_data_t.ramp_up[k]
    if 0.0 < ramp_up < gen_data_t.pmax[k]:
        prob.add_cst(
            gen_vars.p[local_t, k] - gen_vars.p[local_t - 1, k] <= ramp_up / Sbase * dt,
            name=f"ramp_up_{local_t}_{k}"
        )

    ramp_down = gen_data_t.ramp_down[k]
    if 0.0 < ramp_down < gen_data_t.pmax[k]:
        prob.add_cst(
            gen_vars.p[local_t - 1, k] - gen_vars.p[local_t, k] <= ramp_down / Sbase * dt,
            name=f"ramp_dwn_{local_t}_{k}"
        )


def add_generator_piecewise_quadratic_variable_cost(local_t: int,
                                                    k: int,
                                                    Sbase: float,
                                                    gen_data_t: GeneratorData,
                                                    gen_vars: "GenerationVars",
                                                    prob: LpModel,
                                                    producing_var: LpVar | int | float | None = None,
                                                    segment_count: int = 4) -> LpExp | float:
    """
    Add a piecewise-linear approximation of one generator quadratic variable cost.

    The helper approximates ``cost_2 * p^2 + cost_1 * p`` with an incremental
    convex envelope over ``[0, pmax]``. This keeps the formulation linear/MIP
    while activating the otherwise-unused ``cost_2`` coefficient.

    :param local_t: Local time index.
    :param k: Generator index.
    :param Sbase: System base power in MVA.
    :param gen_data_t: Generator data container.
    :param gen_vars: Generator variable container.
    :param prob: Linear/MIP model instance.
    :param producing_var: Commitment/on-off indicator used to disable segments when the unit is off.
    :param segment_count: Number of linear segments for the approximation.
    :return: Linear expression representing the approximated variable cost.
    """
    quadratic_cost: float = gen_data_t.cost_2[k]
    max_power: float = gen_data_t.pmax[k]
    linear_cost: float = gen_data_t.cost_1[k]

    if quadratic_cost == 0.0:
        return linear_cost * gen_vars.p[local_t, k]
    else:
        if max_power <= 0.0 or gen_data_t.pmin[k] < 0.0 or segment_count <= 0:
            return (quadratic_cost * max_power + linear_cost) * gen_vars.p[local_t, k]

    block_count: int = int(segment_count)
    block_width_mw: float = max_power / block_count
    approximated_cost: LpExp | float = 0.0
    block_vars: list[LpVar] = list()

    # Split the generator dispatch into fixed-width blocks so the objective remains linear.
    for block_idx in range(block_count):
        block_var: LpVar = prob.add_var(
            lb=0.0,
            ub=block_width_mw / Sbase,
            name=f"gen_quad_block_{local_t}_{k}_{block_idx}"
        )
        block_vars.append(block_var)

        if producing_var is not None:
            prob.add_cst(
                cst=block_var <= (block_width_mw / Sbase) * producing_var,
                name=f"gen_quad_block_cap_{local_t}_{k}_{block_idx}"
            )

        left_power: float = block_idx * block_width_mw
        right_power: float = (block_idx + 1) * block_width_mw

        # Use secant slopes so the approximation matches the quadratic curve at breakpoints.
        left_cost: float = quadratic_cost * left_power * left_power + linear_cost * left_power
        right_cost: float = quadratic_cost * right_power * right_power + linear_cost * right_power
        slope: float = (right_cost - left_cost) / block_width_mw
        approximated_cost += slope * block_var

    # Tie the block decomposition to the physical dispatch variable.
    prob.add_cst(
        cst=prob.sum(block_vars) == gen_vars.p[local_t, k],
        name=f"gen_quad_balance_{local_t}_{k}"
    )

    return approximated_cost


def get_generator_cost_expression(local_t: int,
                                  k: int,
                                  Sbase: float,
                                  gen_data_t: GeneratorData,
                                  gen_vars: "GenerationVars",
                                  prob: LpModel,
                                  use_glsk_as_cost: bool,
                                  quadratic_costs: bool,
                                  producing_var: LpVar | int | float | None = None,
                                  starting_up_var: LpVar | int | float | None = None,
                                  shutting_down_var: LpVar | int | float | None = None) -> LpExp | float:
    """
    Build the full operating-cost expression for one generator at one time step.

    This helper centralizes the generator operating-cost assembly so the callers
    only decide which commitment variables exist in their formulation. The
    production term can stay purely linear, use GLSK weights, or use the
    piecewise-linear quadratic approximation.

    :param local_t: Local time index.
    :param k: Generator index.
    :param Sbase: System base power in MVA.
    :param gen_data_t: Generator data container.
    :param gen_vars: Generator variable container.
    :param prob: Linear/MIP model instance.
    :param use_glsk_as_cost: Use GLSK participation factors instead of generator costs.
    :param quadratic_costs: Enable the piecewise-linear quadratic cost approximation.
    :param producing_var: Commitment/on-off variable when a no-load term should be commitment-dependent.
    :param starting_up_var: Optional startup indicator.
    :param shutting_down_var: Optional shutdown indicator.
    :return: Linear expression representing the operating cost.
    """
    cost_expression: LpExp | float = 0.0

    if use_glsk_as_cost:
        cost_expression += gen_data_t.shift_key[k] * gen_vars.p[local_t, k]
    else:
        if quadratic_costs:
            cost_expression += add_generator_piecewise_quadratic_variable_cost(
                local_t=local_t,
                k=k,
                Sbase=Sbase,
                gen_data_t=gen_data_t,
                gen_vars=gen_vars,
                prob=prob,
                producing_var=producing_var
            )
        else:
            cost_expression += gen_data_t.cost_1[k] * gen_vars.p[local_t, k]

        if producing_var is None:
            cost_expression += gen_data_t.cost_0[k]
        else:
            cost_expression += gen_data_t.cost_0[k] * producing_var

        if starting_up_var is not None and gen_data_t.startup_cost[k] != 0.0:
            cost_expression += gen_data_t.startup_cost[k] * starting_up_var

        if shutting_down_var is not None and gen_data_t.shut_down_cost[k] != 0.0:
            cost_expression += gen_data_t.shut_down_cost[k] * shutting_down_var

    return cost_expression


def build_area_spinning_reserve_requirement_matrix(grid: MultiCircuit,
                                                   time_indices: list[int | None]) -> Mat:
    """
    Build the time-area spinning reserve requirement matrix in MW.

    :param grid: MultiCircuit instance.
    :param time_indices: Global time indices, or ``None`` for snapshot runs.
    :return: Dense matrix with shape ``(nt, n_areas)`` in MW.
    """
    nt = len(time_indices)
    n_areas = len(grid.areas)
    matrix = np.zeros((nt, n_areas), dtype=float)

    for local_t_idx, global_t_idx in enumerate(time_indices):
        for area_idx, area in enumerate(grid.areas):
            matrix[local_t_idx, area_idx] = area.get_spinning_reserve_requirement_at(global_t_idx)

    return matrix


def add_area_spinning_reserve_formulation(local_t: int,
                                          Sbase: float,
                                          gen_data_t: GeneratorData,
                                          gen_vars: GenerationVars,
                                          prob: LpModel,
                                          area_generator_indices: list[IntVec],
                                          area_requirements_mw: Vec) -> None:
    """
    Add area spinning reserve variables and constraints for one time step.

    :param local_t: Local time index.
    :param Sbase: Base power.
    :param gen_data_t: Generator data for the current compiled circuit.
    :param gen_vars: Generator LP variables.
    :param prob: LP model.
    :param area_generator_indices: Dispatchable active generator indices grouped by area.
    :param area_requirements_mw: Reserve requirement per area in MW.
    :return: None.
    """
    for area_idx, generator_indices in enumerate(area_generator_indices):

        for gen_idx in generator_indices:
            gen_vars.reserve[local_t, gen_idx] = prob.add_var(
                lb=0.0,
                ub=gen_data_t.pmax[gen_idx] / Sbase,
                name=f"gen_reserve_{local_t}_{area_idx}_{gen_idx}"
            )

            producing_var = gen_vars.producing[local_t, gen_idx]
            if isinstance(producing_var, (int, float, np.integer, np.floating)):
                if float(producing_var) == 0.0:
                    producing_var = 1
                else:
                    pass
            else:
                pass

            prob.add_cst(
                cst=(gen_vars.reserve[local_t, gen_idx] <=
                     (gen_data_t.pmax[gen_idx] / Sbase) * producing_var - gen_vars.p[local_t, gen_idx]),
                name=f"gen_reserve_headroom_{local_t}_{area_idx}_{gen_idx}"
            )

        if area_requirements_mw[area_idx] > 0.0:
            area_reserve_sum = sum(gen_vars.reserve[local_t, gen_idx] for gen_idx in generator_indices)
            prob.add_cst(
                cst=area_reserve_sum >= area_requirements_mw[area_idx] / Sbase,
                name=f"area_spinning_reserve_{local_t}_{area_idx}"
            )
        else:
            pass


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


def add_linear_simple_generation_formulation(local_t: Union[int, None],
                                             Sbase: float,
                                             time_array: DateVec,
                                             bus_vars: BusVars,
                                             gen_data_t: GeneratorData,
                                             gen_vars: GenerationVars,
                                             prob: LpModel,
                                             ramp_constraints: bool,
                                             consider_time_up_down: bool,
                                             area_spinning_reserve: bool,
                                             quadratic_costs: bool,
                                             skip_generation_limits: bool,
                                             use_glsk_as_cost: bool,
                                             logger: Logger) -> LpExp | float:
    """
    Add MIP generation formulation
    :param local_t: time step
    :param Sbase: base power (100 MVA)
    :param time_array: complete time array
    :param bus_vars: BusVars
    :param gen_data_t: GeneratorData structure
    :param gen_vars: GenerationVars structure
    :param prob: LpModel
    :param ramp_constraints: formulate ramp constraints?
    :param consider_time_up_down: consider time up/down?
    :param area_spinning_reserve: area spinning reserve?
    :param quadratic_costs: enable the piecewise-linear quadratic cost approximation?
    :param skip_generation_limits: skip the generation limits?
    :param use_glsk_as_cost: if true, the GLSK values are used instead of the traditional costs
    :param logger: Logger object
    :return objective function
    """
    f_obj = 0.0

    # add generation stuff
    for k in range(gen_data_t.nelm):

        gen_vars.cost[local_t, k] = 0.0
        bus_idx = gen_data_t.bus_idx[k]
        # nodal_cap_condition = gen_data_t.bus_idx[k] not in vd if nodal_capacity_active else True

        if gen_data_t.active[k] and bus_idx > -1:

            if gen_data_t.dispatchable[k]:

                # declare active power var (limits will be applied later)
                gen_vars.p[local_t, k] = prob.add_var(-1e20, 1e20, f"gen_p_{local_t}_{k}")

                # NOTE: Must run is the same as this, so we skip it
                if gen_data_t.must_run[k]:
                    logger.add_warning(
                        msg="Must run has no further effects since unit commitment is deactivated",
                        device_class="Generator",
                        device=gen_data_t.names[k]
                    )

                gen_vars.cost[local_t, k] += get_generator_cost_expression(
                    local_t=local_t,
                    k=k,
                    Sbase=Sbase,
                    gen_data_t=gen_data_t,
                    gen_vars=gen_vars,
                    prob=prob,
                    use_glsk_as_cost=use_glsk_as_cost,
                    quadratic_costs=quadratic_costs
                )

                if not skip_generation_limits:
                    prob.set_var_bounds(var=gen_vars.p[local_t, k],
                                        lb=gen_data_t.pmin[k] / Sbase,
                                        ub=gen_data_t.pmax[k] / Sbase)

                # add the ramp constraints
                if ramp_constraints and local_t > 0 and not skip_generation_limits:
                    add_generator_ramp_constraints(local_t=local_t,
                                                   k=k,
                                                   Sbase=Sbase,
                                                   time_array=time_array,
                                                   gen_data_t=gen_data_t,
                                                   gen_vars=gen_vars,
                                                   prob=prob,
                                                   logger=logger)

            else:

                # NOTE: it is NOT dispatchable
                p = gen_data_t.p[k] / Sbase

                # the generator is not dispatchable at time step
                if p > 0:

                    gen_vars.shedding[local_t, k] = prob.add_var(
                        lb=0, ub=p,
                        name=f"gen_shedding_{local_t}_{k}"
                    )

                    gen_vars.p[local_t, k] = p - gen_vars.shedding[local_t, k]

                    if use_glsk_as_cost:
                        gen_vars.cost[local_t, k] += gen_data_t.shift_key[k] * gen_vars.shedding[local_t, k]
                    else:
                        gen_vars.cost[local_t, k] += gen_data_t.cost_1[k] * gen_vars.shedding[local_t, k]

                elif p < 0:
                    # the negative sign is because P is already negative here, to make it positive
                    gen_vars.shedding[local_t, k] = prob.add_var(
                        lb=0, ub=-p,
                        name=f"gen_shedding_{local_t}_{k}"
                    )

                    gen_vars.p[local_t, k] = p + gen_vars.shedding[local_t, k]

                    if use_glsk_as_cost:
                        gen_vars.cost[local_t, k] += gen_data_t.shift_key[k] * gen_vars.shedding[local_t, k]
                    else:
                        gen_vars.cost[local_t, k] += gen_data_t.cost_1[k] * gen_vars.shedding[local_t, k]

                else:
                    # the generation value is exactly zero
                    prob.set_var_bounds(var=gen_vars.p[local_t, k], lb=0.0, ub=0.0)

                gen_vars.producing[local_t, k] = 1
                gen_vars.shutting_down[local_t, k] = 0
                gen_vars.starting_up[local_t, k] = 0

                if gen_data_t.must_run[k]:
                    logger.add_warning("Ignoring must run, because it is not dispatchable",
                                       device_class="Generator",
                                       device=gen_data_t.names[k])

                gen_vars.cost[local_t, k] += get_generator_cost_expression(
                    local_t=local_t,
                    k=k,
                    Sbase=Sbase,
                    gen_data_t=gen_data_t,
                    gen_vars=gen_vars,
                    prob=prob,
                    use_glsk_as_cost=use_glsk_as_cost,
                    quadratic_costs=quadratic_costs
                )

            # add to the balance
            bus_vars.Pbalance[local_t, bus_idx] += gen_vars.p[local_t, k]

            # add to the net injections
            bus_vars.Pinj[local_t, bus_idx] += gen_vars.p[local_t, k]

            # add to the generation injections in case of inter-area
            bus_vars.Pgen[local_t, bus_idx] += gen_vars.p[local_t, k]

        else:
            # the generator is not available at time step
            gen_vars.p[local_t, k] = 0.0  # there has not been any variable assigned to p[t, k] at this point

        # add to the objective function the total cost of the generator
        f_obj += gen_vars.cost[local_t, k]

    return f_obj


def add_linear_generation_expansion_planning_formulation(local_t: Union[int, None],
                                                         Sbase: float,
                                                         time_array: DateVec,
                                                         bus_vars: BusVars,
                                                         gen_data_t: GeneratorData,
                                                         gen_vars: GenerationVars,
                                                         prob: LpModel,
                                                         ramp_constraints: bool,
                                                         quadratic_costs: bool,
                                                         skip_generation_limits: bool,
                                                         use_glsk_as_cost: bool,
                                                         logger: Logger) -> LpExp | float:
    """
    Add MIP generation formulation
    :param local_t: time step
    :param Sbase: base power (100 MVA)
    :param time_array: complete time array
    :param bus_vars: BusVars
    :param gen_data_t: GeneratorData structure
    :param gen_vars: GenerationVars structure
    :param prob: LpModel
    :param ramp_constraints: formulate ramp constraints?
    :param quadratic_costs: enable the piecewise-linear quadratic cost approximation?
    :param skip_generation_limits: skip the generation limits?
    :param use_glsk_as_cost: if true, the GLSK values are used instead of the traditional costs
    :param logger: Logger object
    :return objective function
    """
    f_obj = 0.0

    if time_array is not None:
        if len(time_array) > 0:
            year = time_array[local_t].year - time_array[0].year
        else:
            year = 0
    else:
        year = 0

    # add generation stuff
    for k in range(gen_data_t.nelm):

        gen_vars.cost[local_t, k] = 0.0
        bus_idx = gen_data_t.bus_idx[k]
        # nodal_cap_condition = gen_data_t.bus_idx[k] not in vd if nodal_capacity_active else True

        if gen_data_t.active[k] and bus_idx > -1:

            if gen_data_t.dispatchable[k]:

                # declare active power var (limits will be applied later)
                gen_vars.p[local_t, k] = prob.add_var(-1e20, 1e20, f"gen_p_{local_t}_{k}")

                # NOTE: Must run is the same as this, so we skip it
                if gen_data_t.must_run[k]:
                    logger.add_warning(
                        msg="Must run has no further effects since unit commitment is deactivated",
                        device_class="Generator",
                        device=gen_data_t.names[k]
                    )

                gen_vars.cost[local_t, k] += get_generator_cost_expression(
                    local_t=local_t,
                    k=k,
                    Sbase=Sbase,
                    gen_data_t=gen_data_t,
                    gen_vars=gen_vars,
                    prob=prob,
                    use_glsk_as_cost=use_glsk_as_cost,
                    quadratic_costs=quadratic_costs
                )

                if not skip_generation_limits:
                    prob.set_var_bounds(var=gen_vars.p[local_t, k],
                                        lb=gen_data_t.pmin[k] / Sbase,
                                        ub=gen_data_t.pmax[k] / Sbase)

                # add the ramp constraints
                if ramp_constraints and local_t > 0 and not skip_generation_limits:
                    add_generator_ramp_constraints(local_t=local_t,
                                                   k=k,
                                                   Sbase=Sbase,
                                                   time_array=time_array,
                                                   gen_data_t=gen_data_t,
                                                   gen_vars=gen_vars,
                                                   prob=prob,
                                                   logger=logger)

                # Generation Expansion Planning
                if gen_data_t.is_candidate[k]:

                    money_factor = np.power(1.0 + gen_data_t.discount_rate[k] / 100.0, year)

                    # declare the investment binary
                    gen_vars.invested[local_t, k] = prob.add_int(lb=0, ub=1, name=f"Ig_{local_t}_{k}")

                    # add the investment cost to the objective
                    f_obj += gen_vars.invested[local_t, k] * (gen_data_t.pmax[k] / Sbase) * gen_data_t.capex[
                        k] * money_factor

                    if local_t > 0:
                        # installation persistence
                        prob.add_cst(
                            gen_vars.invested[local_t - 1, k] <= gen_vars.invested[local_t, k],
                            name=f"persist_{local_t}_{k}"
                        )

                    # maximum production constraint
                    prob.add_cst(gen_vars.p[local_t, k] <= (gen_data_t.pmax[k] / Sbase) * gen_vars.invested[local_t, k],
                                 name=f"max_prod_{local_t}_{k}")
                else:
                    # is invested for already
                    gen_vars.invested[local_t, k] = 1

            else:

                # NOTE: it is NOT dispatchable
                p = gen_data_t.p[k] / Sbase

                # the generator is not dispatchable at time step
                if p > 0:

                    gen_vars.shedding[local_t, k] = prob.add_var(
                        lb=0, ub=p,
                        name=f"gen_shedding_{local_t}_{k}"
                    )

                    gen_vars.p[local_t, k] = p - gen_vars.shedding[local_t, k]

                    if use_glsk_as_cost:
                        gen_vars.cost[local_t, k] += gen_data_t.shift_key[k] * gen_vars.shedding[local_t, k]
                    else:
                        gen_vars.cost[local_t, k] += gen_data_t.cost_1[k] * gen_vars.shedding[local_t, k]

                elif p < 0:
                    # the negative sign is because P is already negative here, to make it positive
                    gen_vars.shedding[local_t, k] = prob.add_var(
                        lb=0, ub=-p,
                        name=f"gen_shedding_{local_t}_{k}"
                    )

                    gen_vars.p[local_t, k] = p + gen_vars.shedding[local_t, k]

                    if use_glsk_as_cost:
                        gen_vars.cost[local_t, k] += gen_data_t.shift_key[k] * gen_vars.shedding[local_t, k]
                    else:
                        gen_vars.cost[local_t, k] += gen_data_t.cost_1[k] * gen_vars.shedding[local_t, k]

                else:
                    # the generation value is exactly zero
                    prob.set_var_bounds(var=gen_vars.p[local_t, k], lb=0.0, ub=0.0)

                gen_vars.producing[local_t, k] = 1
                gen_vars.shutting_down[local_t, k] = 0
                gen_vars.starting_up[local_t, k] = 0

                if gen_data_t.must_run[k]:
                    logger.add_warning("Ignoring must run, because it is not dispatchable",
                                       device_class="Generator",
                                       device=gen_data_t.names[k])

                gen_vars.cost[local_t, k] += get_generator_cost_expression(
                    local_t=local_t,
                    k=k,
                    Sbase=Sbase,
                    gen_data_t=gen_data_t,
                    gen_vars=gen_vars,
                    prob=prob,
                    use_glsk_as_cost=use_glsk_as_cost,
                    quadratic_costs=quadratic_costs
                )

            # add to the balance
            bus_vars.Pbalance[local_t, bus_idx] += gen_vars.p[local_t, k]

            # add to the generation injections in case of inter-area
            bus_vars.Pgen[local_t, bus_idx] += gen_vars.p[local_t, k]

        else:
            # the generator is not available at time step
            gen_vars.p[local_t, k] = 0.0  # there has not been any variable assigned to p[t, k] at this point

        # add to the objective function the total cost of the generator
        f_obj += gen_vars.cost[local_t, k]

    return f_obj


def add_linear_generation_unit_commitment_formulation(
        local_t: Union[int, None],
        Sbase: float,
        time_array: DateVec,
        bus_vars: BusVars,
        gen_data_t: GeneratorData,
        gen_vars: GenerationVars,
        prob: LpModel,
        ramp_constraints: bool,
        consider_time_up_down: bool,
        area_spinning_reserve: bool,
        quadratic_costs: bool,
        skip_generation_limits: bool,
        use_glsk_as_cost: bool,
        logger: Logger) -> LpExp | float:
    """
    Add MIP generation formulation
    :param local_t: time step
    :param Sbase: base power (100 MVA)
    :param time_array: complete time array
    :param bus_vars: BusVars
    :param gen_data_t: GeneratorData structure
    :param gen_vars: GenerationVars structure
    :param prob: LpModel
    :param ramp_constraints: formulate ramp constraints?
    :param consider_time_up_down: consider time up/down?
    :param area_spinning_reserve: area spinning reserve?
    :param quadratic_costs: enable the piecewise-linear quadratic cost approximation?
    :param skip_generation_limits: skip the generation limits?
    :param use_glsk_as_cost: if true, the GLSK values are used instead of the traditional costs
    :param logger: Logger object
    :return objective function
    """
    f_obj = 0.0

    # add generation stuff
    for k in range(gen_data_t.nelm):

        gen_vars.cost[local_t, k] = 0.0
        bus_idx = gen_data_t.bus_idx[k]
        # nodal_cap_condition = gen_data_t.bus_idx[k] not in vd if nodal_capacity_active else True

        if gen_data_t.active[k] and bus_idx > -1:

            if gen_data_t.dispatchable[k]:

                # declare active power var (limits will be applied later)
                gen_vars.p[local_t, k] = prob.add_var(-1e20, 1e20, f"gen_p_{local_t}_{k}")

                if gen_data_t.must_run[k]:
                    # NOTE: Unit commitment is incompatible with "must run"

                    logger.add_warning("Unit commitment overridden by must run",
                                       device_class="Generator",
                                       device=gen_data_t.names[k])

                    gen_vars.cost[local_t, k] += get_generator_cost_expression(
                        local_t=local_t,
                        k=k,
                        Sbase=Sbase,
                        gen_data_t=gen_data_t,
                        gen_vars=gen_vars,
                        prob=prob,
                        use_glsk_as_cost=use_glsk_as_cost,
                        quadratic_costs=quadratic_costs
                    )

                    if not skip_generation_limits:
                        prob.set_var_bounds(var=gen_vars.p[local_t, k],
                                            lb=gen_data_t.pmin[k] / Sbase,
                                            ub=gen_data_t.pmax[k] / Sbase)
                else:
                    # declare unit commitment vars
                    gen_vars.starting_up[local_t, k] = prob.add_bin(f"gen_starting_up_{local_t}_{k}")
                    gen_vars.producing[local_t, k] = prob.add_bin(f"gen_producing_{local_t}_{k}")
                    gen_vars.shutting_down[local_t, k] = prob.add_bin(f"gen_shutting_down_{local_t}_{k}")

                    gen_vars.cost[local_t, k] += get_generator_cost_expression(
                        local_t=local_t,
                        k=k,
                        Sbase=Sbase,
                        gen_data_t=gen_data_t,
                        gen_vars=gen_vars,
                        prob=prob,
                        use_glsk_as_cost=use_glsk_as_cost,
                        quadratic_costs=quadratic_costs,
                        producing_var=gen_vars.producing[local_t, k],
                        starting_up_var=gen_vars.starting_up[local_t, k],
                        shutting_down_var=gen_vars.shutting_down[local_t, k]
                    )

                    # power boundaries of the generator
                    if not skip_generation_limits:
                        prob.add_cst(
                            cst=gen_vars.p[local_t, k] >= (
                                    gen_data_t.pmin[k] / Sbase * gen_vars.producing[local_t, k]),
                            name=f"gen_geq_Pmin_{local_t}_{k}"
                        )
                        prob.add_cst(
                            cst=gen_vars.p[local_t, k] <= (
                                    gen_data_t.pmax[k] / Sbase * gen_vars.producing[local_t, k]),
                            name=f"gen_leq_Pmax_{local_t}_{k}"
                        )

                    if local_t is not None:
                        if local_t == 0:
                            # NOTE: Here, gen_data_t.active[k] represents the producing state at t-1
                            prob.add_cst(
                                cst=gen_vars.starting_up[local_t, k] - gen_vars.shutting_down[local_t, k] ==
                                    gen_vars.producing[local_t, k] - float(gen_data_t.active[k]),
                                name=f"binary_alg1_{local_t}_{k}"
                            )
                            prob.add_cst(
                                cst=gen_vars.starting_up[local_t, k] + gen_vars.shutting_down[local_t, k] <= 1,
                                name=f"binary_alg2_{local_t}_{k}"
                            )
                        else:
                            prob.add_cst(
                                cst=(gen_vars.starting_up[local_t, k] - gen_vars.shutting_down[local_t, k] ==
                                     gen_vars.producing[local_t, k] - gen_vars.producing[local_t - 1, k]),
                                name=f"binary_alg3_{local_t}_{k}"
                            )
                            prob.add_cst(
                                cst=gen_vars.starting_up[local_t, k] + gen_vars.shutting_down[local_t, k] <= 1,
                                name=f"binary_alg4_{local_t}_{k}"
                            )

                    if consider_time_up_down and local_t is not None:
                        up_window = get_min_time_window(time_array, local_t, gen_data_t.min_time_up[k])
                        if up_window:
                            prob.add_cst(
                                cst=sum(gen_vars.starting_up[tau, k] for tau in up_window) <= gen_vars.producing[
                                    local_t, k],
                                name=f"gen_min_up_{local_t}_{k}"
                            )

                        down_window = get_min_time_window(time_array, local_t, gen_data_t.min_time_down[k])
                        if down_window:
                            prob.add_cst(
                                cst=(sum(gen_vars.shutting_down[tau, k] for tau in down_window)
                                     <= 1 - gen_vars.producing[local_t, k]),
                                name=f"gen_min_down_{local_t}_{k}"
                            )

                # add the ramp constraints
                if ramp_constraints and local_t > 0 and not skip_generation_limits:
                    add_generator_ramp_constraints(local_t=local_t,
                                                   k=k,
                                                   Sbase=Sbase,
                                                   time_array=time_array,
                                                   gen_data_t=gen_data_t,
                                                   gen_vars=gen_vars,
                                                   prob=prob,
                                                   logger=logger)

            else:

                # NOTE: it is NOT dispatchable
                p = gen_data_t.p[k] / Sbase

                # the generator is not dispatchable at time step
                if p > 0:

                    gen_vars.shedding[local_t, k] = prob.add_var(
                        lb=0, ub=p,
                        name=f"gen_shedding_{local_t}_{k}"
                    )

                    gen_vars.p[local_t, k] = p - gen_vars.shedding[local_t, k]

                    if use_glsk_as_cost:
                        gen_vars.cost[local_t, k] += gen_data_t.shift_key[k] * gen_vars.shedding[local_t, k]
                    else:
                        gen_vars.cost[local_t, k] += gen_data_t.cost_1[k] * gen_vars.shedding[local_t, k]

                elif p < 0:
                    # the negative sign is because P is already negative here, to make it positive
                    gen_vars.shedding[local_t, k] = prob.add_var(
                        lb=0, ub=-p,
                        name=f"gen_shedding_{local_t}_{k}"
                    )

                    gen_vars.p[local_t, k] = p + gen_vars.shedding[local_t, k]

                    if use_glsk_as_cost:
                        gen_vars.cost[local_t, k] += gen_data_t.shift_key[k] * gen_vars.shedding[local_t, k]
                    else:
                        gen_vars.cost[local_t, k] += gen_data_t.cost_1[k] * gen_vars.shedding[local_t, k]

                else:
                    # the generation value is exactly zero
                    prob.set_var_bounds(var=gen_vars.p[local_t, k], lb=0.0, ub=0.0)

                gen_vars.producing[local_t, k] = 1
                gen_vars.shutting_down[local_t, k] = 0
                gen_vars.starting_up[local_t, k] = 0

                if gen_data_t.must_run[k]:
                    logger.add_warning("Ignoring must run, because it is not dispatchable",
                                       device_class="Generator",
                                       device=gen_data_t.names[k])

                gen_vars.cost[local_t, k] += get_generator_cost_expression(
                    local_t=local_t,
                    k=k,
                    Sbase=Sbase,
                    gen_data_t=gen_data_t,
                    gen_vars=gen_vars,
                    prob=prob,
                    use_glsk_as_cost=use_glsk_as_cost,
                    quadratic_costs=quadratic_costs
                )

            # add to the balance
            bus_vars.Pbalance[local_t, bus_idx] += gen_vars.p[local_t, k]

            # add to the generation injections in case of inter-area
            bus_vars.Pgen[local_t, bus_idx] += gen_vars.p[local_t, k]

        else:
            # the generator is not available at time step
            gen_vars.p[local_t, k] = 0.0  # there has not been any variable assigned to p[t, k] at this point

        # add to the objective function the total cost of the generator
        f_obj += gen_vars.cost[local_t, k]

    return f_obj


def add_linear_generation_redispatch_formulation(local_t: Union[int, None],
                                                 Sbase: float,
                                                 bus_vars: BusVars,
                                                 gen_data_t: GeneratorData,
                                                 gen_vars: GenerationVars,
                                                 prob: LpModel,
                                                 inter_aggregation_info: InterAggregationInfo,
                                                 quadratic_costs: bool,
                                                 skip_generation_limits: bool,
                                                 use_glsk_as_cost: bool,
                                                 logger: Logger) -> LpExp | float:
    """
    Add MIP generation redispatch formulation
    the main difference is that Pg = P + dP
    dP >= 0 for generators in A1 (sending),
    dP <= 0 for generators in A2 (receiving),
    :param local_t: time step
    :param Sbase: base power (100 MVA)
    :param bus_vars: BusVars
    :param gen_data_t: GeneratorData structure
    :param gen_vars: GenerationVars structure
    :param prob: LpModel
    :param inter_aggregation_info:
    :param quadratic_costs: enable the piecewise-linear quadratic cost approximation?
    :param skip_generation_limits: skip the generation limits?
    :param use_glsk_as_cost: if true, the GLSK values are used instead of the traditional costs
    :param logger: Logger object
    :return objective function
    """
    f_obj = 0.0

    # add generation stuff
    for k in range(gen_data_t.nelm):

        gen_vars.cost[local_t, k] = 0.0
        bus_idx = gen_data_t.bus_idx[k]

        if gen_data_t.active[k] and bus_idx > -1:

            if gen_data_t.dispatchable[k]:

                p_fix = gen_data_t.p[k] / Sbase

                if inter_aggregation_info.is_from(bus_idx):
                    # declare active power var (limits will be applied later)
                    gen_vars.p[local_t, k] = prob.add_var(-1e20, 1e20, f"gen_p_{local_t}_{k}")
                    gen_vars.dp[local_t, k] = prob.add_var(0, 1e20, f"gen_dp_{local_t}_{k}")

                    prob.add_cst(
                        cst=gen_vars.p[local_t, k] == p_fix + gen_vars.dp[local_t, k],  # dp must be positive
                        name=f"gen_p_up_{local_t}_{k}"
                    )

                    # NOTE: Must run is the same as this, so we skip it
                    if gen_data_t.must_run[k]:
                        logger.add_warning(
                            msg="Must run has no further effects since unit commitment is deactivated",
                            device_class="Generator",
                            device=gen_data_t.names[k]
                        )

                    gen_vars.cost[local_t, k] += get_generator_cost_expression(
                        local_t=local_t,
                        k=k,
                        Sbase=Sbase,
                        gen_data_t=gen_data_t,
                        gen_vars=gen_vars,
                        prob=prob,
                        use_glsk_as_cost=use_glsk_as_cost,
                        quadratic_costs=quadratic_costs
                    )

                    if not skip_generation_limits:
                        prob.set_var_bounds(var=gen_vars.p[local_t, k],
                                            lb=gen_data_t.pmin[k] / Sbase,
                                            ub=gen_data_t.pmax[k] / Sbase)

                elif inter_aggregation_info.is_to(bus_idx):
                    # declare active power var (limits will be applied later)
                    gen_vars.p[local_t, k] = prob.add_var(-1e20, 1e20, f"gen_p_{local_t}_{k}")
                    gen_vars.dp[local_t, k] = prob.add_var(-1e20, 0, f"gen_dp_{local_t}_{k}")

                    prob.add_cst(
                        cst=gen_vars.p[local_t, k] == p_fix + gen_vars.dp[local_t, k],  # dp must be negative
                        name=f"gen_p_down_{local_t}_{k}"
                    )

                    # NOTE: Must run is the same as this, so we skip it
                    if gen_data_t.must_run[k]:
                        logger.add_warning(
                            msg="Must run has no further effects since unit commitment is deactivated",
                            device_class="Generator",
                            device=gen_data_t.names[k]
                        )

                    gen_vars.cost[local_t, k] += get_generator_cost_expression(
                        local_t=local_t,
                        k=k,
                        Sbase=Sbase,
                        gen_data_t=gen_data_t,
                        gen_vars=gen_vars,
                        prob=prob,
                        use_glsk_as_cost=use_glsk_as_cost,
                        quadratic_costs=quadratic_costs
                    )

                    if not skip_generation_limits:
                        prob.set_var_bounds(var=gen_vars.p[local_t, k],
                                            lb=gen_data_t.pmin[k] / Sbase,
                                            ub=gen_data_t.pmax[k] / Sbase)
                else:
                    # same as not dispatchable, but we don't add shedding
                    gen_vars.p[local_t, k] = gen_data_t.p[k] / Sbase

                # is invested for already
                gen_vars.invested[local_t, k] = 1

            else:

                # NOTE: it is NOT dispatchable
                p = gen_data_t.p[k] / Sbase

                # the generator is not dispatchable at time step
                if p > 0:

                    gen_vars.shedding[local_t, k] = prob.add_var(
                        lb=0, ub=p,
                        name=f"gen_shedding_{local_t}_{k}"
                    )

                    gen_vars.p[local_t, k] = p - gen_vars.shedding[local_t, k]

                    if use_glsk_as_cost:
                        gen_vars.cost[local_t, k] += gen_data_t.shift_key[k] * gen_vars.shedding[local_t, k]
                    else:
                        gen_vars.cost[local_t, k] += gen_data_t.cost_1[k] * gen_vars.shedding[local_t, k]

                elif p < 0:
                    # the negative sign is because P is already negative here, to make it positive
                    gen_vars.shedding[local_t, k] = prob.add_var(
                        lb=0, ub=-p,
                        name=f"gen_shedding_{local_t}_{k}"
                    )

                    gen_vars.p[local_t, k] = p + gen_vars.shedding[local_t, k]

                    if use_glsk_as_cost:
                        gen_vars.cost[local_t, k] += gen_data_t.shift_key[k] * gen_vars.shedding[local_t, k]
                    else:
                        gen_vars.cost[local_t, k] += gen_data_t.cost_1[k] * gen_vars.shedding[local_t, k]

                else:
                    # the generation value is exactly zero
                    prob.set_var_bounds(var=gen_vars.p[local_t, k], lb=0.0, ub=0.0)

                gen_vars.producing[local_t, k] = 1
                gen_vars.shutting_down[local_t, k] = 0
                gen_vars.starting_up[local_t, k] = 0

                if gen_data_t.must_run[k]:
                    logger.add_warning("Ignoring must run, because it is not dispatchable",
                                       device_class="Generator",
                                       device=gen_data_t.names[k])

                gen_vars.cost[local_t, k] += get_generator_cost_expression(
                    local_t=local_t,
                    k=k,
                    Sbase=Sbase,
                    gen_data_t=gen_data_t,
                    gen_vars=gen_vars,
                    prob=prob,
                    use_glsk_as_cost=use_glsk_as_cost,
                    quadratic_costs=quadratic_costs
                )

            # add to the balance
            bus_vars.Pbalance[local_t, bus_idx] += gen_vars.p[local_t, k]

            # add to the generation injections in case of inter-area
            bus_vars.Pgen[local_t, bus_idx] += gen_vars.p[local_t, k]

        else:
            # the generator is not available at time step
            gen_vars.p[local_t, k] = 0.0  # there has not been any variable assigned to p[t, k] at this point

        # add to the objective function the total cost of the generator
        f_obj += gen_vars.cost[local_t, k]

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
                                   energy_0: Vec,
                                   global_t: Union[int, None] = None):
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
    :param global_t: global time index, used to keep the first interval consistent across grouped runs
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

            # The battery energy recurrence is shared by both dispatchable and fixed-power
            # operation modes, so compute the modeled interval once before the dispatchability
            # split and reuse it in both paths.
            dt: float = get_model_step_hours(time_array=time_array, local_t=t, global_t=global_t)

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
                    # energy falls when discharging (p_pos) and rises when charging (p_neg)
                    prob.add_cst(cst=(batt_vars.e[t, k] == batt_vars.e[t - 1, k]
                                      + dt * (batt_data_t.charge_efficiency[k] * p_neg
                                              - p_pos / batt_data_t.discharge_efficiency[k])),
                                 name=join("batt_energy_", [t, k], "_"))
                else:
                    # tie the first modeled interval to the provided initial energy
                    prob.add_cst(cst=(batt_vars.e[t, k] == energy_0[k] / Sbase
                                      + dt * (batt_data_t.charge_efficiency[k] * p_neg
                                              - p_pos / batt_data_t.discharge_efficiency[k])),
                                 name=join("batt_energy_", [t, k], "_"))

            else:

                # it is NOT dispatchable

                # Operational cost (linear...)
                f_obj += (batt_data_t.cost_1[k] * p_pos) + batt_data_t.cost_0[k]

                p: float = batt_data_t.p[k] / Sbase

                # the generator is not dispatchable at time step
                if p > 0:
                    # Positive fixed power means battery discharge, so the charging branch must
                    # stay at zero. This keeps the energy balance physically consistent.
                    prob.set_var_bounds(var=p_pos, lb=0, ub=p)
                    prob.set_var_bounds(var=p_neg, lb=0, ub=0)

                    batt_vars.shedding[t, k] = prob.add_var(0, p, join("bat_shedding_", [t, k], "_"))

                    prob.add_cst(
                        cst=batt_vars.p[t, k] == batt_data_t.p[k] / Sbase - batt_vars.shedding[t, k],
                        name=join("batt==PB-PBslack", [t, k], "_"))

                    f_obj += batt_data_t.cost_1[k] * batt_vars.shedding[t, k]

                elif p < 0:
                    # the negative sign is because P is already negative here
                    # Negative fixed power means battery charge, so the discharge branch must
                    # stay at zero. This prevents fake simultaneous charge/discharge flows.
                    prob.set_var_bounds(var=p_pos, lb=0, ub=0)
                    prob.set_var_bounds(var=p_neg, lb=0, ub=-p)

                    batt_vars.shedding[t, k] = prob.add_var(lb=0,
                                                            ub=-p,
                                                            name=join("bat_shedding_", [t, k], "_"))

                    prob.add_cst(
                        cst=batt_vars.p[t, k] == batt_data_t.p[k] / Sbase + batt_vars.shedding[t, k],
                        name=join("batt==PB+PBslack", [t, k], "_"))

                    f_obj += batt_data_t.cost_1[k] * batt_vars.shedding[t, k]

                else:
                    # Zero fixed power means neither charge nor discharge branch can move.
                    prob.set_var_bounds(var=p_pos, lb=0, ub=0)
                    prob.set_var_bounds(var=p_neg, lb=0, ub=0)

                batt_vars.producing[t, k] = 1
                batt_vars.shutting_down[t, k] = 0
                batt_vars.starting_up[t, k] = 0

                # The battery energy state must exist for every active battery, even when the
                # power is fixed by the profile. Otherwise a later dispatchable step cannot
                # reference a valid previous energy state.
                batt_vars.e[t, k] = prob.add_var(batt_data_t.e_min[k] / Sbase,
                                                 batt_data_t.e_max[k] / Sbase,
                                                 join("batt_e_", [t, k], "_"))

                if t > 0:
                    # The same signed power split is reused here: p_pos discharges the battery
                    # and p_neg charges it, so the state-of-charge continuity is preserved.
                    prob.add_cst(cst=(batt_vars.e[t, k] == batt_vars.e[t - 1, k]
                                      + dt * (batt_data_t.charge_efficiency[k] * p_neg
                                              - p_pos / batt_data_t.discharge_efficiency[k])),
                                 name=join("batt_energy_", [t, k], "_"))
                else:
                    # The first modeled interval must also carry the energy state forward from
                    # the provided initial condition, even if dispatch is disabled here.
                    prob.add_cst(cst=(batt_vars.e[t, k] == energy_0[k] / Sbase
                                      + dt * (batt_data_t.charge_efficiency[k] * p_neg
                                              - p_pos / batt_data_t.discharge_efficiency[k])),
                                 name=join("batt_energy_", [t, k], "_"))

            # add to the balance
            bus_vars.Pbalance[t, bus_idx] += batt_vars.p[t, k]

            # add to the net injections
            bus_vars.Pinj[t, bus_idx] += batt_vars.p[t, k]

            # add to the generation injections in case of inter-area
            bus_vars.Pgen[t, bus_idx] += batt_vars.p[t, k]

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
        nodal_capacity_vars.P[t, k] = prob.add_var(lb=0.0,
                                                   ub=9999.9,
                                                   name=join("nodal_capacity_", [t, k], "_"))

        f_obj += -100 * nodal_capacity_vars.P[t, k]

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
            bus_vars.Pbalance[t, bus_idx] += -load_vars.p[t, k]

            # add to the injections
            bus_vars.Pinj[t, bus_idx] += -load_vars.p[t, k]

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
                                    inf=1e20,
                                    add_losses_approximation: bool = False):
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
    :param add_losses_approximation: If true the distribution factors losses approximation is used
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
                if (ctrl_branch_data_t.tap_phase_control_mode[m] == TapPhaseControl.Pf.idx() or
                        ctrl_branch_data_t.tap_phase_control_mode[m] == TapPhaseControl.Pt.idx()):

                    # Phase shifter under control, so define as a variable
                    branch_vars.tap_angles[t, m] = prob.add_var(lb=ctrl_branch_data_t.tap_angle_min[m],
                                                                ub=ctrl_branch_data_t.tap_angle_max[m],
                                                                name=join("tap_ang_", [t, m], "_"))

                    branch_vars.flows[t, m] = bk * (bus_vars.Va[t, fr] -
                                                    bus_vars.Va[t, to] -
                                                    branch_vars.tap_angles[t, m])

                elif ctrl_branch_data_t.tap_angle[m] != 0.0:

                    # The device carries a phase shift that the user imposed
                    branch_vars.tap_angles[t, m] = ctrl_branch_data_t.tap_angle[m]

                    branch_vars.flows[t, m] = bk * (bus_vars.Va[t, fr] -
                                                    bus_vars.Va[t, to] -
                                                    branch_vars.tap_angles[t, m])

                else:  # rest of the branches, with no phase shift
                    branch_vars.flows[t, m] = bk * (bus_vars.Va[t, fr] - bus_vars.Va[t, to])

            # power injected and subtracted due to the phase shift
            bus_vars.Pbalance[t, fr] += - branch_vars.flows[t, m]
            bus_vars.Pbalance[t, to] += branch_vars.flows[t, m]

            if add_losses_approximation:
                # declare the abs flow LPVar
                branch_vars.z_flows[t, m] = prob.add_var(lb=0,
                                                         ub=inf,
                                                         name=join("z_flow_", [t, m], "_"))

                # zij ≥ Fij
                prob.add_cst(cst=branch_vars.flows[t, m] <= branch_vars.z_flows[t, m],
                             name=join("z_flow_u_lim_", [t, m]))

                # zij ≥ -Fij
                prob.add_cst(cst=-branch_vars.flows[t, m] <= branch_vars.z_flows[t, m],
                             name=join("z_flow_l_lim_", [t, m]))

                # add to the objective (αij =rij * ∣Fij0∣/V2)
                # insetad of the rates, the literature suggests an absolute initial value of the flow
                V = bus_data_t.Vnom[branch_data_t.F[m]]
                if V > 0.0:
                    factor = branch_data_t.R[m] * branch_data_t.rates[m] / (V ** 2)
                else:
                    factor = branch_data_t.R[m]

                # store the values for later retrieval
                branch_vars.losses[t, m] = branch_vars.z_flows[t, m] * factor

                # add the losses to the objective
                f_obj += branch_vars.losses[t, m]

                # divide the losses contribution equally among the from and to buses as new loads
                l_inj = 0.5 * branch_vars.losses[t, m]
                bus_vars.Pbalance[t, fr] += - l_inj
                bus_vars.Pbalance[t, to] += - l_inj

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


def pmode3_formulation_impr(prob: LpModel,
                            elm_idx: int,
                            t_idx: int,
                            m: float,
                            rate: float,
                            P0: float,
                            droop: float,
                            theta_f: LpVar,
                            theta_t: LpVar,
                            base_name: str,
                            logger: Logger):
    """
    Formulation for HVDC link with three operating regions using big-M and binary variables.
    :param prob:
    :param elm_idx:
    :param t_idx:
    :param m:
    :param rate:
    :param P0:
    :param droop:
    :param theta_f:
    :param theta_t:
    :param base_name:
    :param logger:
    :return:
    """

    # Ensure droop is not zero or too small to avoid division issues
    if abs(droop) < 1e-5:
        logger.add_warning("droop below threshold set to 1",
                           device=f"HVDC line {elm_idx}",
                           value=droop,
                           expected_value="abs(droop) < 1e-5")
        droop = 1.0

    # Variables
    flow = prob.add_var(
        lb=-rate,
        ub=rate,
        name=f"{base_name}_flow_{t_idx}_{m}"
    )
    z1 = prob.add_int(lb=0, ub=1, name=f"{base_name}_z1_{t_idx}_{m}")
    z2 = prob.add_int(lb=0, ub=1, name=f"{base_name}_z2_{t_idx}_{m}")
    z3 = prob.add_int(lb=0, ub=1, name=f"{base_name}_z3_{t_idx}_{m}")

    # Constants
    delta = theta_f - theta_t
    delta_low = (-rate - P0) / droop
    delta_high = (rate - P0) / droop
    M = 20 * rate  # Big-M as per note; may need adjustment for angle constraints

    # Exactly one region active
    prob.add_cst(z1 + z2 + z3 >= 1, name=f"one_region_ge_{t_idx}_{m}")
    prob.add_cst(z1 + z2 + z3 <= 1, name=f"one_region_le_{t_idx}_{m}")

    # Region constraints
    # Region 1 (z1=1): saturated at -rate, delta <= delta_low
    prob.add_cst(delta <= delta_low + M * (1 - z1), name=f"region1_le_{t_idx}_{m}")

    # Region 2 (z2=1): droop, delta_low <= delta <= delta_high
    prob.add_cst(delta >= delta_low - M * (1 - z2), name=f"region2_ge_{t_idx}_{m}")
    prob.add_cst(delta <= delta_high + M * (1 - z2), name=f"region2_le_{t_idx}_{m}")

    # Region 3 (z3=1): saturated at +rate, delta >= delta_high
    prob.add_cst(delta >= delta_high - M * (1 - z3), name=f"region3_ge_{t_idx}_{m}")

    # Power constraints
    # Region 1: flow = -rate when z1=1
    prob.add_cst(flow >= -rate - M * (1 - z1), name=f"power1_ge_{t_idx}_{m}")
    prob.add_cst(flow <= -rate + M * (1 - z1), name=f"power1_le_{t_idx}_{m}")

    # Region 2: flow = P0 + droop * (theta_f - theta_t) when z2=1
    prob.add_cst(flow - (P0 + droop * delta) >= -M * (1 - z2), name=f"power2_ge_{t_idx}_{m}")
    prob.add_cst(flow - (P0 + droop * delta) <= M * (1 - z2), name=f"power2_le_{t_idx}_{m}")

    # Region 3: flow = rate when z3=1
    prob.add_cst(flow >= rate - M * (1 - z3), name=f"power3_ge_{t_idx}_{m}")
    prob.add_cst(flow <= rate + M * (1 - z3), name=f"power3_le_{t_idx}_{m}")

    return flow


def add_linear_hvdc_formulation(t: int,
                                Sbase: float,
                                hvdc_data_t: HvdcData,
                                hvdc_vars: HvdcVars,
                                bus_vars: BusVars,
                                prob: LpModel,
                                logger: Logger):
    """

    :param t:
    :param Sbase:
    :param hvdc_data_t:
    :param hvdc_vars:
    :param bus_vars:
    :param prob:
    :param logger:
    :return:
    """
    f_obj = 0.0
    for m in range(hvdc_data_t.nelm):

        fr = hvdc_data_t.F[m]
        to = hvdc_data_t.T[m]
        hvdc_vars.rates[t, m] = hvdc_data_t.rates[m]

        if hvdc_data_t.active[m]:

            if hvdc_data_t.control_mode_int[m] == HvdcControlType.type_0_free.idx():

                # use improved pmode3 formulation with three operating regions
                P0 = hvdc_data_t.Pset[m] / Sbase

                # convert MW/deg to pu/rad
                droop = hvdc_data_t.get_angle_droop_in_pu_rad_at(m, Sbase)
                if droop == 0.0:
                    # avoid division by zero in pmode3_formulation_impr
                    droop = 1e-20

                rate = hvdc_data_t.rates[m] / Sbase

                hvdc_vars.flows[t, m] = pmode3_formulation_impr(
                    prob=prob,
                    elm_idx=m,
                    t_idx=t,
                    m=m,
                    rate=rate,
                    P0=P0,
                    droop=droop,
                    theta_f=bus_vars.Va[t, fr],
                    theta_t=bus_vars.Va[t, to],
                    base_name="hvdc",
                    logger=logger
                )

                # add the injections matching the flow
                bus_vars.Pbalance[t, fr] += - hvdc_vars.flows[t, m]
                bus_vars.Pbalance[t, to] += hvdc_vars.flows[t, m]

            elif hvdc_data_t.control_mode_int[m] == HvdcControlType.type_1_Pset.idx():

                if hvdc_data_t.dispatchable[m]:

                    # declare the flow var
                    hvdc_vars.flows[t, m] = prob.add_var(lb=-hvdc_data_t.rates[m] / Sbase,
                                                         ub=hvdc_data_t.rates[m] / Sbase,
                                                         name=join("hvdc_flow_", [t, m], "_"))

                    # add the injections matching the flow
                    bus_vars.Pbalance[t, fr] += - hvdc_vars.flows[t, m]
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
                    bus_vars.Pbalance[t, fr] += - hvdc_vars.flows[t, m]
                    bus_vars.Pbalance[t, to] += hvdc_vars.flows[t, m]
            else:
                raise Exception('OPF: Unknown HVDC control mode {}'.format(hvdc_data_t.control_mode_int[m]))
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
            bus_vars.Pbalance[t, fr] += - vsc_vars.flows[t, m]
            bus_vars.Pbalance[t, to] += vsc_vars.flows[t, m]

            if (vsc_data_t.control1_int[m] == ConverterControlType.Vm_dc.idx() or
                    vsc_data_t.control2_int[m] == ConverterControlType.Vm_dc.idx()):
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
                            nodal_capacity_sign: float,
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
    :param nodal_capacity_sign: Sign of the nodal capacity (>0: gen, <0: load)
    :param capacity_nodes_idx: IntVec
    :param prob: LpModel
    :param logger: Logger
    """

    # Note: At this point, Pbalance has all the devices' power summed up inside (including branches)

    if len(capacity_nodes_idx) > 0:
        if nodal_capacity_sign >= 0:
            bus_vars.Pbalance[t_idx, capacity_nodes_idx] += nodal_capacity_vars.P[t_idx, :]
            bus_vars.Pinj[t_idx, capacity_nodes_idx] += nodal_capacity_vars.P[t_idx, :]
        else:
            bus_vars.Pbalance[t_idx, capacity_nodes_idx] -= nodal_capacity_vars.P[t_idx, :]
            bus_vars.Pinj[t_idx, capacity_nodes_idx] -= nodal_capacity_vars.P[t_idx, :]

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
        # Convert electrical output into water flow, or clamp to zero when the device data is invalid.
        coeff = get_hydro_power_to_flow_coeff(flow_rate=float(turbine_data.max_flow_rate[m]),
                                              efficiency=float(turbine_data.efficiency[m]),
                                              rated_power=float(generator_data.pmax[gen_idx]),
                                              sbase=Sbase,
                                              logger=logger,
                                              device_label='turbine')
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
        # Convert electrical consumption into pumped flow, or clamp to zero when the device data is invalid.
        coeff = get_hydro_power_to_flow_coeff(flow_rate=float(pump_data.max_flow_rate[m]),
                                              efficiency=1.0 / float(pump_data.efficiency[m]),
                                              rated_power=abs(float(generator_data.pmin[gen_idx])),
                                              sbase=Sbase,
                                              logger=logger,
                                              device_label='pump')
        pump_flow = (generator_vars.p[t, gen_idx] * coeff)
        # node_vars.flow_in[t, plant_idx] = pump_flow  # assume only 1 pump connected

        # if t > 0:
        inj_vars.flow[t, m + turbine_data.nelm] = - pump_flow
        prob.add_cst(cst=(node_vars.flow_in[t, plant_idx] == - pump_flow),
                     name=join("pump_river_", [t, m], "_"))

        if generator_data.pmax[gen_idx] > 0:
            logger.add_error(msg='Pump generator pmax > 0 is not possible',
                             value=generator_data.pmax[gen_idx])

        # f_obj += - pump_flow

    for m in range(p2x_data.nelm):
        gen_idx = p2x_data.generator_idx[m]

        # flow[m3/s] = pcons [pu] * max_flow [m3/s] * eff / (Pcons_max [MW] / Sbase [MW])
        # invert the efficiency compared to a turbine
        # pmin instead of pmax because the sign should be inverted (consuming instead of generating)
        # Convert electrical consumption into process flow, or clamp to zero when the device data is invalid.
        coeff = get_hydro_power_to_flow_coeff(flow_rate=float(p2x_data.max_flow_rate[m]),
                                              efficiency=1.0 / float(p2x_data.efficiency[m]),
                                              rated_power=abs(float(generator_data.pmin[gen_idx])),
                                              sbase=Sbase,
                                              logger=logger,
                                              device_label='p2x')
        p2x_flow = (generator_vars.p[t, gen_idx] * coeff)

        # if t > 0:
        node_vars.p2x_flow[t, p2x_data.plant_idx[m]] += - p2x_flow
        inj_vars.flow[t, m + turbine_data.nelm + pump_data.nelm] = - p2x_flow

        if generator_data.pmax[gen_idx] > 0:
            logger.add_error(msg='P2X generator pmax > 0 is not possible',
                             value=generator_data.pmax[gen_idx])

        # f_obj += - p2x_flow

    if time_global_tidx is not None:
        # constraints for the node level
        for m in range(node_data.nelm):
            if t == 0:
                dt = get_time_increment_seconds(time_array=time_array, idx=time_global_tidx)

                # Initialize level at fluid_level_0
                node_vars.water_balance[t, m] = prob.add_cst(cst=(node_vars.current_level[t, m] ==
                                                                   fluid_level_0[m]
                                                                   + dt * node_data.inflow[m]
                                                                   + dt * node_vars.flow_in[t, m]
                                                                   + dt * node_vars.p2x_flow[t, m]
                                                                   - dt * node_vars.spillage[t, m]
                                                                   - dt * node_vars.flow_out[t, m]),
                                                              name=join("nodal_balance_", [t, m], "_"))
            else:
                # Update the level according to the in and out flows as time passes
                dt = get_time_increment_seconds(time_array=time_array, idx=time_global_tidx)

                node_vars.water_balance[t, m] = prob.add_cst(cst=(node_vars.current_level[t, m] ==
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
                      dispatch_mode: OpfDispatchMode = OpfDispatchMode.Normal,
                      solver_type: MIPSolvers = MIPSolvers.HIGHS,
                      zonal_grouping: ZonalGrouping = ZonalGrouping.NoGrouping,
                      skip_generation_limits: bool = False,
                      consider_contingencies: bool = False,
                      contingency_groups_used: Union[List[ContingencyGroup], None] = None,
                      ramp_constraints: bool = False,
                      consider_time_up_down: bool = False,
                      area_spinning_reserve: bool = False,
                      quadratic_costs: bool = False,
                      lodf_threshold: float = 0.001,
                      inter_aggregation_info: InterAggregationInfo | None = None,
                      energy_0: Union[Vec, None] = None,
                      fluid_level_0: Union[Vec, None] = None,
                      nodal_capacity_sign: float = 1.0,
                      capacity_nodes_idx: Union[IntVec, None] = None,
                      use_glsk_as_cost: bool = False,
                      add_losses_approximation: bool = False,
                      logger: Logger = Logger(),
                      progress_text: Union[None, Callable[[str], None]] = None,
                      progress_func: Union[None, Callable[[float], None]] = None,
                      verbose: int = 0,
                      robust: bool = False,
                      mip_framework: MIPFramework = MIPFramework.PuLP) -> Tuple[OpfVars, LpModel]:
    """
    Formulate linear optimal power flow
    :param grid: MultiCircuit instance
    :param time_indices: Time indices (in the general scheme)
    :param dispatch_mode: OpfDispatchMode
    :param solver_type: MIP solver to use
    :param zonal_grouping: Zonal grouping?
    :param skip_generation_limits: Skip the generation limits?
    :param consider_contingencies: Consider the contingencies?
    :param contingency_groups_used: List of contingency groups to use
    :param ramp_constraints: Formulate ramp constraints?
    :param consider_time_up_down: Consider the time up/down?
    :param area_spinning_reserve: Area spinning reserve?
    :param quadratic_costs: Enable the piecewise-linear quadratic cost approximation?
    :param lodf_threshold: LODF threshold value to consider contingencies
    :param inter_aggregation_info: Inter rea (or country, etc) information
    :param energy_0: Vector of initial energy for batteries (size: Number of batteries)
    :param fluid_level_0: initial fluid level of the nodes
    :param nodal_capacity_sign: if > 0 the generation is maximized, if < 0 the load is maximized
    :param capacity_nodes_idx: Array of bus indices to optimize their nodal capacity for
    :param use_glsk_as_cost: If true the generators use the GLSK as dispatch values
    :param add_losses_approximation: If true the distribution factors losses approximation is used
    :param logger: logger instance
    :param progress_text: Text progress callback
    :param progress_func: Numerical progress callback
    :param verbose: verbosity level
    :param robust: Robust optimization?
    :param mip_framework: MIP framework to use
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
    bus_area_indices = grid.get_bus_area_indices()
    area_spinning_reserve_requirements = (
        build_area_spinning_reserve_requirement_matrix(grid=grid, time_indices=time_indices)
        if area_spinning_reserve else None
    )

    if dispatch_mode == OpfDispatchMode.InterAreaRedispatch:
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
    lp_model: LpModel = get_model_instance(tpe=mip_framework, solver_type=solver_type)
    logger.add_info(f"MIP Framework", value=lp_model.name)
    logger.add_info(f"MIP Solver", value=solver_type.value)

    # objective function
    f_obj: Union[LpExp, float] = 0.0

    for local_t_idx, global_t_idx in enumerate(time_indices):  # use time_indices = [None] to simulate the snapshot

        # time indices:
        # imagine that the complete VeraGrid DB time goes from 0 to 1000
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
            fill_gep=dispatch_mode == OpfDispatchMode.GenerationExpansionPlanning,
            logger=logger
        )

        indices = nc.get_simulation_indices()
        area_generator_indices = (
            nc.generator_data.get_dispatchable_active_indices_per_area(
                bus_area_indices=bus_area_indices,
                area_count=len(grid.areas)
            )
            if area_spinning_reserve else None
        )

        # formulate the bus angles ---------------------------------------------------------------------------------
        for k in range(nc.bus_data.nbus):
            # we declare Vm for DC buses and Va for AC buses
            if nc.bus_data.is_dc[k]:
                mip_vars.bus_vars.Vm[local_t_idx, k] = lp_model.add_var(
                    lb=nc.bus_data.Vmin[k],
                    ub=nc.bus_data.Vmax[k],
                    name=f"Vm_{local_t_idx}_{k}"
                )
            else:
                mip_vars.bus_vars.Va[local_t_idx, k] = lp_model.add_var(
                    lb=nc.bus_data.angle_min[k],
                    ub=nc.bus_data.angle_max[k],
                    name=f"Va_{local_t_idx}_{k}"
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

        # formulate batteries energy
        if local_t_idx == 0 and energy_0 is None:
            # declare the initial energy of the batteries
            energy_0 = nc.battery_data.soc_0 * nc.battery_data.enom  # in MWh here

        if dispatch_mode == OpfDispatchMode.Normal:

            f_obj += add_linear_simple_generation_formulation(
                local_t=local_t_idx,
                Sbase=nc.Sbase,
                time_array=grid.time_profile,
                bus_vars=mip_vars.bus_vars,
                gen_data_t=nc.generator_data,
                gen_vars=mip_vars.gen_vars,
                prob=lp_model,
                ramp_constraints=ramp_constraints,
                consider_time_up_down=consider_time_up_down,
                area_spinning_reserve=area_spinning_reserve,
                quadratic_costs=quadratic_costs,
                skip_generation_limits=skip_generation_limits,
                use_glsk_as_cost=use_glsk_as_cost,
                logger=logger
            )

            f_obj += add_linear_battery_formulation(
                t=local_t_idx,
                Sbase=nc.Sbase,
                time_array=grid.time_profile,
                bus_vars=mip_vars.bus_vars,
                batt_data_t=nc.battery_data,
                batt_vars=mip_vars.batt_vars,
                prob=lp_model,
                unit_commitment=False,
                ramp_constraints=ramp_constraints,
                skip_generation_limits=skip_generation_limits,
                generation_expansion_planning=False,
                energy_0=energy_0,
                global_t=global_t_idx
            )

            if area_spinning_reserve:
                add_area_spinning_reserve_formulation(
                    local_t=local_t_idx,
                    Sbase=nc.Sbase,
                    gen_data_t=nc.generator_data,
                    gen_vars=mip_vars.gen_vars,
                    prob=lp_model,
                    area_generator_indices=area_generator_indices,
                    area_requirements_mw=area_spinning_reserve_requirements[local_t_idx, :]
                )

        elif dispatch_mode == OpfDispatchMode.UnitCommitment:

            f_obj += add_linear_generation_unit_commitment_formulation(
                local_t=local_t_idx,
                Sbase=nc.Sbase,
                time_array=grid.time_profile,
                bus_vars=mip_vars.bus_vars,
                gen_data_t=nc.generator_data,
                gen_vars=mip_vars.gen_vars,
                prob=lp_model,
                ramp_constraints=ramp_constraints,
                consider_time_up_down=consider_time_up_down,
                area_spinning_reserve=area_spinning_reserve,
                quadratic_costs=quadratic_costs,
                skip_generation_limits=skip_generation_limits,
                use_glsk_as_cost=use_glsk_as_cost,
                logger=logger
            )

            f_obj += add_linear_battery_formulation(
                t=local_t_idx,
                Sbase=nc.Sbase,
                time_array=grid.time_profile,
                bus_vars=mip_vars.bus_vars,
                batt_data_t=nc.battery_data,
                batt_vars=mip_vars.batt_vars,
                prob=lp_model,
                unit_commitment=True,
                ramp_constraints=ramp_constraints,
                skip_generation_limits=skip_generation_limits,
                generation_expansion_planning=False,
                energy_0=energy_0,
                global_t=global_t_idx
            )

            if area_spinning_reserve:
                add_area_spinning_reserve_formulation(
                    local_t=local_t_idx,
                    Sbase=nc.Sbase,
                    gen_data_t=nc.generator_data,
                    gen_vars=mip_vars.gen_vars,
                    prob=lp_model,
                    area_generator_indices=area_generator_indices,
                    area_requirements_mw=area_spinning_reserve_requirements[local_t_idx, :]
                )

        elif dispatch_mode == OpfDispatchMode.NodalCapacity:
            f_obj += add_linear_simple_generation_formulation(
                local_t=local_t_idx,
                Sbase=nc.Sbase,
                time_array=grid.time_profile,
                bus_vars=mip_vars.bus_vars,
                gen_data_t=nc.generator_data,
                gen_vars=mip_vars.gen_vars,
                prob=lp_model,
                ramp_constraints=ramp_constraints,
                consider_time_up_down=consider_time_up_down,
                area_spinning_reserve=area_spinning_reserve,
                quadratic_costs=quadratic_costs,
                skip_generation_limits=skip_generation_limits,
                use_glsk_as_cost=use_glsk_as_cost,
                logger=logger
            )

            f_obj += add_linear_battery_formulation(
                t=local_t_idx,
                Sbase=nc.Sbase,
                time_array=grid.time_profile,
                bus_vars=mip_vars.bus_vars,
                batt_data_t=nc.battery_data,
                batt_vars=mip_vars.batt_vars,
                prob=lp_model,
                unit_commitment=False,
                ramp_constraints=ramp_constraints,
                skip_generation_limits=skip_generation_limits,
                generation_expansion_planning=False,
                energy_0=energy_0,
                global_t=global_t_idx
            )

            if area_spinning_reserve:
                add_area_spinning_reserve_formulation(
                    local_t=local_t_idx,
                    Sbase=nc.Sbase,
                    gen_data_t=nc.generator_data,
                    gen_vars=mip_vars.gen_vars,
                    prob=lp_model,
                    area_generator_indices=area_generator_indices,
                    area_requirements_mw=area_spinning_reserve_requirements[local_t_idx, :]
                )

        elif dispatch_mode == OpfDispatchMode.GenerationExpansionPlanning:
            f_obj += add_linear_generation_expansion_planning_formulation(
                local_t=local_t_idx,
                Sbase=nc.Sbase,
                time_array=grid.time_profile,
                bus_vars=mip_vars.bus_vars,
                gen_data_t=nc.generator_data,
                gen_vars=mip_vars.gen_vars,
                prob=lp_model,
                ramp_constraints=ramp_constraints,
                quadratic_costs=quadratic_costs,
                skip_generation_limits=skip_generation_limits,
                use_glsk_as_cost=use_glsk_as_cost,
                logger=logger
            )

            f_obj += add_linear_battery_formulation(
                t=local_t_idx,
                Sbase=nc.Sbase,
                time_array=grid.time_profile,
                bus_vars=mip_vars.bus_vars,
                batt_data_t=nc.battery_data,
                batt_vars=mip_vars.batt_vars,
                prob=lp_model,
                unit_commitment=False,
                ramp_constraints=ramp_constraints,
                skip_generation_limits=skip_generation_limits,
                generation_expansion_planning=True,
                energy_0=energy_0,
                global_t=global_t_idx
            )

            if area_spinning_reserve:
                add_area_spinning_reserve_formulation(
                    local_t=local_t_idx,
                    Sbase=nc.Sbase,
                    gen_data_t=nc.generator_data,
                    gen_vars=mip_vars.gen_vars,
                    prob=lp_model,
                    area_generator_indices=area_generator_indices,
                    area_requirements_mw=area_spinning_reserve_requirements[local_t_idx, :]
                )

        elif dispatch_mode == OpfDispatchMode.InterAreaRedispatch:
            f_obj += add_linear_generation_redispatch_formulation(
                local_t=local_t_idx,
                Sbase=nc.Sbase,
                bus_vars=mip_vars.bus_vars,
                gen_data_t=nc.generator_data,
                gen_vars=mip_vars.gen_vars,
                prob=lp_model,
                inter_aggregation_info=inter_aggregation_info,
                quadratic_costs=quadratic_costs,
                skip_generation_limits=skip_generation_limits,
                use_glsk_as_cost=use_glsk_as_cost,
                logger=logger
            )

            f_obj += add_linear_battery_formulation(
                t=local_t_idx,
                Sbase=nc.Sbase,
                time_array=grid.time_profile,
                bus_vars=mip_vars.bus_vars,
                batt_data_t=nc.battery_data,
                batt_vars=mip_vars.batt_vars,
                prob=lp_model,
                unit_commitment=False,
                ramp_constraints=ramp_constraints,
                skip_generation_limits=skip_generation_limits,
                generation_expansion_planning=False,
                energy_0=energy_0,
                global_t=global_t_idx
            )
        else:
            raise ValueError(f"dispatch mode not supported {dispatch_mode}")

        # formulate nodal capacity -------------------------------------------------------------------------------------
        if dispatch_mode == OpfDispatchMode.NodalCapacity:
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
                prob=lp_model,
                logger=logger
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
                inf=1e20,
                add_losses_approximation=add_losses_approximation
            )

            # formulate nodes ------------------------------------------------------------------------------------------

            add_linear_node_balance(
                t_idx=local_t_idx,
                vd=indices.vd,
                bus_data=nc.bus_data,
                bus_vars=mip_vars.bus_vars,
                nodal_capacity_vars=mip_vars.nodal_capacity_vars,
                nodal_capacity_sign=nodal_capacity_sign,
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
            if dispatch_mode == OpfDispatchMode.InterAreaRedispatch:

                # maximize the power at the from buses
                for i in inter_aggregation_info.idx_bus_from:
                    f_obj += - mip_vars.bus_vars.Pgen[local_t_idx, i]

                # minimize the power at the to buses
                for i in inter_aggregation_info.idx_bus_to:
                    f_obj += mip_vars.bus_vars.Pgen[local_t_idx, i]

                for k, branch, sense in inter_area_branches:
                    # we want to maximize, hence the minus sign
                    f_obj += mip_vars.branch_vars.flows[local_t_idx, k] * (- sense)

                for k, branch, sense in inter_area_hvdc:
                    # we want to maximize, hence the minus sign
                    f_obj += mip_vars.hvdc_vars.flows[local_t_idx, k] * (- sense)

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

    status = lp_model.solve(robust=robust,
                            show_logs=verbose > 0,
                            progress_text=progress_text)
    # Preserve the solver's diagnostics even if export or extraction fails.
    logger += lp_model.logger

    # gather the results
    logger.add_info(msg="Status", value=lp_model.status2string(status))

    if status == lp_model.OPTIMAL:
        logger.add_info("Objective function", value=lp_model.fobj_value())
        mip_vars.acceptable_solution = True
    else:
        logger.add_error("The problem does not have an optimal solution.")
        mip_vars.acceptable_solution = False
        try:
            lp_file_name = os.path.join(opf_file_path(), f"{grid.name} opf debug.lp")
            lp_model.save_model(file_name=lp_file_name)
            logger.add_info("Debug LP model saved", value=lp_file_name)
        except Exception as error:
            logger.add_warning("Could not save debug LP model", value=str(error))

    # convert the lp vars to their values
    vars_v = mip_vars.get_values(Sbase=grid.Sbase,
                                 model=lp_model,
                                 gen_emissions_rates_matrix=gen_emissions_rates_matrix,
                                 gen_fuel_rates_matrix=gen_fuel_rates_matrix,
                                 gen_tech_shares_matrix=gen_tech_shares_matrix,
                                 batt_tech_shares_matrix=batt_tech_shares_matrix)

    # lp_model.save_model('nodal_opf.lp')
    return vars_v, lp_model
