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

from GridCalEngine.basic_structures import ZonalGrouping
from GridCalEngine.basic_structures import MIPSolvers
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Core.Devices.Aggregation.area import Area
from GridCalEngine.Core.DataStructures.numerical_circuit import NumericalCircuit, compile_numerical_circuit_at
from GridCalEngine.Core.DataStructures.generator_data import GeneratorData
from GridCalEngine.Core.DataStructures.battery_data import BatteryData
from GridCalEngine.Core.DataStructures.load_data import LoadData
from GridCalEngine.Core.DataStructures.branch_data import BranchData
from GridCalEngine.Core.DataStructures.hvdc_data import HvdcData
from GridCalEngine.Core.DataStructures.bus_data import BusData
from GridCalEngine.basic_structures import Logger, Vec, IntVec, DateVec
from GridCalEngine.Utils.MIP.selected_interface import LpExp, LpVar, LpModel, lpDot, set_var_bounds, join
from GridCalEngine.enumerations import TransformerControlType, HvdcControlType
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis, LinearMultiContingency, \
    LinearMultiContingencies


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
            if abs(multi_contingency.ptdf_factors[m, i]) >= threshold:
                res += multi_contingency.ptdf_factors[m, i] * multi_contingency.injections_factor[i] * injections[c]

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
        self.theta = np.zeros((nt, n_elm), dtype=object)
        self.Pcalc = np.zeros((nt, n_elm), dtype=object)
        self.branch_injections = np.zeros((nt, n_elm), dtype=object)
        self.kirchhoff = np.zeros((nt, n_elm), dtype=object)
        self.shadow_prices = np.zeros((nt, n_elm), dtype=float)

    def get_values(self, Sbase: float, model: LpModel) -> "BusVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: BusVars
        """
        nt, n_elm = self.theta.shape
        data = BusVars(nt=nt, n_elm=n_elm)

        data.shadow_prices = self.shadow_prices

        for t in range(nt):
            for i in range(n_elm):
                data.theta[t, i] = model.get_value(self.theta[t, i])
                data.Pcalc[t, i] = model.get_value(self.Pcalc[t, i])
                data.branch_injections[t, i] = model.get_value(self.branch_injections[t, i]) * Sbase
                data.shadow_prices[t, i] = model.get_dual_value(self.kirchhoff[t, i])

        # format the arrays aproprietly
        data.theta = data.theta.astype(float, copy=False)
        data.Pcalc = data.Pcalc.astype(float, copy=False)
        data.branch_injections = data.branch_injections.astype(float, copy=False)

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

        self.p = np.zeros((nt, n_elm), dtype=float)  # to be filled (no vars)

    def get_values(self, Sbase: float, model: LpModel) -> "LoadVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
        :return: LoadVars
        """
        nt, n_elm = self.shedding.shape
        data = LoadVars(nt=nt, n_elm=n_elm)

        data.p = self.p * Sbase  # this is data already, so make a refference copy

        for t in range(nt):
            for i in range(n_elm):
                data.shedding[t, i] = model.get_value(self.shedding[t, i]) * Sbase

        # format the arrays aproprietly
        data.shedding = data.shedding.astype(float, copy=False)

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

    def get_values(self, Sbase: float, model: LpModel) -> "GenerationVars":
        """
        Return an instance of this class where the arrays content are not LP vars but their value
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

        # format the arrays aproprietly
        data.p = data.p.astype(float, copy=False)
        data.shedding = data.shedding.astype(float, copy=False)
        data.producing = data.producing.astype(int, copy=False)
        data.starting_up = data.starting_up.astype(int, copy=False)
        data.shutting_down = data.shutting_down.astype(int, copy=False)

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

    def get_values(self, Sbase: float, model: LpModel) -> "BatteryVars":
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

            # format the arrays aproprietly
            data.p = data.p.astype(float, copy=False)
            data.e = data.e.astype(float, copy=False)
            data.shedding = data.shedding.astype(float, copy=False)
            data.producing = data.producing.astype(int, copy=False)
            data.starting_up = data.starting_up.astype(int, copy=False)
            data.shutting_down = data.shutting_down.astype(int, copy=False)

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

        for i in range(len(self.contingency_flow_data)):
            t, m, c, var, neg_slack, pos_slack = self.contingency_flow_data[i]
            self.contingency_flow_data[i] = (t, m, c,
                                             model.get_value(var),
                                             model.get_value(neg_slack),
                                             model.get_value(pos_slack))

        # format the arrays aproprietly
        data.flows = data.flows.astype(float, copy=False)
        data.flow_slacks_pos = data.flow_slacks_pos.astype(float, copy=False)
        data.flow_slacks_neg = data.flow_slacks_neg.astype(float, copy=False)
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

        # format the arrays aproprietly
        data.flows = data.flows.astype(float, copy=False)

        data.loading = data.flows / (data.rates + 1e-20)

        return data


class OpfVars:
    """
    Structure to host the opf variables
    """

    def __init__(self, nt: int, nbus: int, ng: int, nb: int, nl: int, nbr: int, n_hvdc: int):
        """
        Constructor
        :param nt: number of time steps
        :param nbus: number of nodes
        :param ng: number of generators
        :param nb: number of batteries
        :param nl: number of loads
        :param nbr: number of branches
        :param n_hvdc: number of HVDC
        """
        self.nt = nt
        self.nbus = nbus
        self.ng = ng
        self.nb = nb
        self.nl = nl
        self.nbr = nbr
        self.n_hvdc = n_hvdc

        self.acceptable_solution = False

        self.bus_vars = BusVars(nt=nt, n_elm=nbus)
        self.load_vars = LoadVars(nt=nt, n_elm=nl)
        self.gen_vars = GenerationVars(nt=nt, n_elm=ng)
        self.batt_vars = BatteryVars(nt=nt, n_elm=nb)
        self.branch_vars = BranchVars(nt=nt, n_elm=nbr)
        self.hvdc_vars = HvdcVars(nt=nt, n_elm=n_hvdc)

    def get_values(self, Sbase: float, model: LpModel) -> "OpfVars":
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
                       n_hvdc=self.n_hvdc)
        data.bus_vars = self.bus_vars.get_values(Sbase, model)
        data.load_vars = self.load_vars.get_values(Sbase, model)
        data.gen_vars = self.gen_vars.get_values(Sbase, model)
        data.batt_vars = self.batt_vars.get_values(Sbase, model)
        data.branch_vars = self.branch_vars.get_values(Sbase, model)
        data.hvdc_vars = self.hvdc_vars.get_values(Sbase, model)

        data.acceptable_solution = self.acceptable_solution
        return data


def add_linear_generation_formulation(t: Union[int, None],
                                      Sbase: float,
                                      time_array: DateVec,
                                      gen_data_t: GeneratorData,
                                      gen_vars: GenerationVars,
                                      prob: LpModel,
                                      unit_commitment: bool,
                                      ramp_constraints: bool,
                                      skip_generation_limits: bool):
    """
    Add MIP generation formulation
    :param t: time step
    :param Sbase: base power (100 MVA)
    :param time_array: complete time array
    :param gen_data_t: GeneratorData structure
    :param gen_vars: GenerationVars structure
    :param prob: ORTools problem
    :param unit_commitment: formulate unit commitment?
    :param ramp_constraints: formulate ramp constraints?
    :param skip_generation_limits: skip the generation limits?
    :return objective function
    """
    f_obj = 0.0
    for k in range(gen_data_t.nelm):

        if gen_data_t.active[k]:

            # declare active power var (limits will be applied later)
            gen_vars.p[t, k] = prob.add_var(-1e20, 1e20, join("gen_p_", [t, k], "_"))

            if gen_data_t.dispatchable[k]:

                if unit_commitment:

                    # declare unit commitment vars
                    gen_vars.starting_up[t, k] = prob.add_int(0, 1,
                                                              join("gen_starting_up_", [t, k], "_"))
                    gen_vars.producing[t, k] = prob.add_int(0, 1,
                                                            join("gen_producing_", [t, k], "_"))
                    gen_vars.shutting_down[t, k] = prob.add_int(0, 1,
                                                                join("gen_shutting_down_", [t, k], "_"))

                    # operational cost (linear...)
                    f_obj += gen_data_t.cost_1[k] * gen_vars.p[t, k] + gen_data_t.cost_0[k] * gen_vars.producing[t, k]

                    # start-up cost
                    f_obj += gen_data_t.startup_cost[k] * gen_vars.starting_up[t, k]

                    # power boundaries of the generator
                    if not skip_generation_limits:
                        prob.add_cst(
                            cst=gen_vars.p[t, k] >= (
                                    gen_data_t.availability[k] * gen_data_t.pmin[k] / Sbase * gen_vars.producing[t, k]),
                            name=join("gen>=Pmin", [t, k], "_"))
                        prob.add_cst(
                            cst=gen_vars.p[t, k] <= (
                                    gen_data_t.availability[k] * gen_data_t.pmax[k] / Sbase * gen_vars.producing[t, k]),
                            name=join("gen<=Pmax", [t, k], "_"))

                    if t is not None:
                        if t == 0:
                            prob.add_cst(
                                cst=gen_vars.starting_up[t, k] - gen_vars.shutting_down[t, k] ==
                                    gen_vars.producing[t, k] - float(gen_data_t.active[k]),
                                name=join("binary_alg1_", [t, k], "_")
                            )
                            prob.add_cst(
                                cst=gen_vars.starting_up[t, k] + gen_vars.shutting_down[t, k] <= 1,
                                name=join("binary_alg2_", [t, k], "_")
                            )
                        else:
                            prob.add_cst(
                                cst=gen_vars.starting_up[t, k] - gen_vars.shutting_down[t, k] ==
                                    gen_vars.producing[t, k] - gen_vars.producing[t - 1, k],
                                name=join("binary_alg3_", [t, k], "_")
                            )
                            prob.add_cst(
                                cst=gen_vars.starting_up[t, k] + gen_vars.shutting_down[t, k] <= 1,
                                name=join("binary_alg4_", [t, k], "_")
                            )
                else:
                    # No unit commitment

                    # Operational cost (linear...)
                    f_obj += (gen_data_t.cost_1[k] * gen_vars.p[t, k]) + gen_data_t.cost_0[k]

                    if not skip_generation_limits:
                        set_var_bounds(var=gen_vars.p[t, k],
                                       lb=gen_data_t.availability[k] * gen_data_t.pmin[k] / Sbase,
                                       ub=gen_data_t.availability[k] * gen_data_t.pmax[k] / Sbase)

                # add the ramp constraints
                if ramp_constraints and t is not None:
                    if t > 0:
                        if gen_data_t.ramp_up[k] < gen_data_t.pmax[k] and gen_data_t.ramp_down[k] < gen_data_t.pmax[k]:
                            # if the ramp is actually sufficiently restrictive...
                            dt = (time_array[t] - time_array[t - 1]).seconds / 3600.0  # time increment in hours

                            # - ramp_down · dt <= P(t) - P(t-1) <= ramp_up · dt
                            prob.add_cst(
                                cst=-gen_data_t.ramp_down[k] / Sbase * dt <= gen_vars.p[t, k] - gen_vars.p[t - 1, k])
                            prob.add_cst(
                                cst=gen_vars.p[t, k] - gen_vars.p[t - 1, k] <= gen_data_t.ramp_up[k] / Sbase * dt)
            else:

                # it is NOT dispatchable
                p = gen_data_t.p[k] / Sbase

                # Operational cost (linear...)
                f_obj += (gen_data_t.cost_1[k] * gen_vars.p[t, k]) + gen_data_t.cost_0[k]

                # the generator is not dispatchable at time step
                if p > 0:

                    gen_vars.shedding[t, k] = prob.add_var(0, p, join("gen_shedding_", [t, k], "_"))

                    prob.add_cst(
                        cst=gen_vars.p[t, k] == gen_data_t.p[k] / Sbase - gen_vars.shedding[t, k],
                        name=join("gen==PG-PGslack", [t, k], "_"))

                    f_obj += gen_data_t.cost_1[k] * gen_vars.shedding[t, k]

                elif p < 0:
                    # the negative sign is because P is already negative here, to make it positive
                    gen_vars.shedding[t, k] = prob.add_var(0, -p, join("gen_shedding_", [t, k], "_"))

                    prob.add_cst(
                        cst=gen_vars.p[t, k] == p + gen_vars.shedding[t, k],
                        name=join("gen==PG+PGslack", [t, k], "_"))

                    f_obj += gen_data_t.cost_1[k] * gen_vars.shedding[t, k]

                else:
                    # the generation value is exactly zero, pass
                    pass

                gen_vars.producing[t, k] = 1
                gen_vars.shutting_down[t, k] = 0
                gen_vars.starting_up[t, k] = 0

        else:
            # the generator is not available at time step
            gen_vars.p[t, k] = 0.0

    return f_obj


def add_linear_battery_formulation(t: Union[int, None],
                                   Sbase: float,
                                   time_array: DateVec,
                                   batt_data_t: BatteryData,
                                   batt_vars: BatteryVars,
                                   prob: LpModel,
                                   unit_commitment: bool,
                                   ramp_constraints: bool,
                                   skip_generation_limits: bool,
                                   energy_0: Vec):
    """
    Add MIP generation formulation
    :param t: time step, if None we assume single time step
    :param Sbase: base power (100 MVA)
    :param time_array: complete time array
    :param batt_data_t: BatteryData structure
    :param batt_vars: BatteryVars structure
    :param prob: ORTools problem
    :param unit_commitment: formulate unit commitment?
    :param ramp_constraints: formulate ramp constraints?
    :param skip_generation_limits: skip the generation limits?
    :param energy_0: initial value of the energy stored
    :return objective function
    """
    f_obj = 0.0
    for k in range(batt_data_t.nelm):

        if batt_data_t.active[k]:

            # declare active power var (limits will be applied later)
            batt_vars.p[t, k] = prob.add_var(0, 1e20, join("batt_p_", [t, k], "_"))

            if batt_data_t.dispatchable[k]:

                if unit_commitment:

                    # declare unit commitment vars
                    batt_vars.starting_up[t, k] = prob.add_int(0, 1, join("bat_starting_up_", [t, k], "_"))
                    batt_vars.producing[t, k] = prob.add_int(0, 1, join("bat_producing_", [t, k], "_"))
                    batt_vars.shutting_down[t, k] = prob.add_int(0, 1, join("bat_shutting_down_", [t, k], "_"))

                    # operational cost (linear...)
                    f_obj += batt_data_t.cost_1[k] * batt_vars.p[t, k] + batt_data_t.cost_0[k] * batt_vars.producing[
                        t, k]

                    # start-up cost
                    f_obj += batt_data_t.startup_cost[k] * batt_vars.starting_up[t, k]

                    # power boundaries of the generator
                    if not skip_generation_limits:
                        prob.add_cst(
                            cst=batt_vars.p[t, k] >= (
                                    batt_data_t.availability[k] * batt_data_t.pmin[k] / Sbase * batt_vars.producing[
                                t, k]),
                            name=join("batt>=Pmin", [t, k], "_"))
                        prob.add_cst(
                            cst=batt_vars.p[t, k] <= (
                                    batt_data_t.availability[k] * batt_data_t.pmax[k] / Sbase * batt_vars.producing[
                                t, k]),
                            name=join("batt<=Pmax", [t, k], "_"))

                    if t is not None:
                        if t == 0:
                            prob.add_cst(
                                cst=batt_vars.starting_up[t, k] - batt_vars.shutting_down[t, k] ==
                                    batt_vars.producing[t, k] - float(batt_data_t.active[k]),
                                name=join("binary_alg1_", [t, k], "_"))
                            prob.add_cst(
                                cst=batt_vars.starting_up[t, k] + batt_vars.shutting_down[t, k] <= 1,
                                name=join("binary_alg2_", [t, k], "_"))
                        else:
                            prob.add_cst(
                                cst=batt_vars.starting_up[t, k] - batt_vars.shutting_down[t, k] ==
                                    batt_vars.producing[t, k] - batt_vars.producing[t - 1, k],
                                name=join("binary_alg3_", [t, k], "_"))
                            prob.add_cst(
                                cst=batt_vars.starting_up[t, k] + batt_vars.shutting_down[t, k] <= 1,
                                name=join("binary_alg4_", [t, k], "_"))
                else:
                    # No unit commitment

                    # Operational cost (linear...)
                    f_obj += (batt_data_t.cost_1[k] * batt_vars.p[t, k]) + batt_data_t.cost_0[k]

                    # power boundaries of the generator
                    if not skip_generation_limits:
                        set_var_bounds(var=batt_vars.p[t, k],
                                       lb=batt_data_t.availability[k] * batt_data_t.pmin[k] / Sbase,
                                       ub=batt_data_t.availability[k] * batt_data_t.pmax[k] / Sbase)

                # compute the time increment in hours
                dt = (time_array[t] - time_array[t - 1]).seconds / 3600.0

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
                    prob.add_cst(cst=batt_vars.e[t, k] ==
                                     batt_vars.e[t - 1, k] + dt * batt_data_t.efficiency[k] * batt_vars.p[t, k],
                                 name=join("batt_energy_", [t, k], "_"))
                else:
                    # set the initial energy value
                    batt_vars.e[t, k] = energy_0[k] / Sbase

            else:

                # it is NOT dispatchable

                # Operational cost (linear...)
                f_obj += (batt_data_t.cost_1[k] * batt_vars.p[t, k]) + batt_data_t.cost_0[k]

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
                    batt_vars.shedding[t, k] = prob.add_var(0,
                                                            -p,
                                                            join("bat_shedding_", [t, k], "_"))

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

        else:
            # the generator is not available at time step
            batt_vars.p[t, k] = 0.0

    return f_obj


def add_linear_load_formulation(t: Union[int, None],
                                Sbase: float,
                                load_data_t: LoadData,
                                load_vars: LoadVars,
                                prob: LpModel):
    """
    Add MIP generation formulation
    :param t: time step, if None we assume single time step
    :param Sbase: base power (100 MVA)
    :param load_data_t: BatteryData structure
    :param load_vars: BatteryVars structure
    :param prob: ORTools problem
    :return objective function
    """
    f_obj = 0.0
    for k in range(load_data_t.nelm):

        if load_data_t.active[k]:

            # store the load
            load_vars.p[t, k] = load_data_t.S[k].real / Sbase

            if load_vars.p[t, k] > 0.0:

                # assign load shedding variable
                load_vars.shedding[t, k] = prob.add_var(lb=0,
                                                        ub=load_vars.p[t, k],
                                                        name=join("load_shedding_", [t, k], "_"))

                # minimize the load shedding
                f_obj += load_data_t.cost[k] * load_vars.shedding[t, k]
            else:
                # the load is negative, won't shed?
                load_vars.shedding[t, k] = 0.0

        else:
            # the load is not available at time step
            load_vars.shedding[t, k] = 0.0

    return f_obj


def add_linear_branches_formulation(t: int,
                                    Sbase: float,
                                    branch_data_t: BranchData,
                                    branch_vars: BranchVars,
                                    bus_vars: BusVars,
                                    prob: LpModel,
                                    inf=1e20):
    """
    Formulate the branches
    :param t: time index
    :param Sbase: base power (100 MVA)
    :param branch_data_t: BranchData
    :param branch_vars: BranchVars
    :param bus_vars: BusVars
    :param prob: OR problem
    :param inf: number considered infinte
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
                branch_vars.tap_angles[t, m] = prob.add_var(lb=branch_data_t.tap_angle_min[m],
                                                            ub=branch_data_t.tap_angle_max[m],
                                                            name=join("tap_ang_", [t, m], "_"))

                # is a phase shifter device (like phase shifter transformer or VSC with P control)
                flow_ctr = branch_vars.flows[t, m] == bk * (
                        bus_vars.theta[t, fr] - bus_vars.theta[t, to] + branch_vars.tap_angles[t, m])
                prob.add_cst(cst=flow_ctr, name=join("Branch_flow_set_with_ps_", [t, m], "_"))

                # power injected and subtracted due to the phase shift
                bus_vars.branch_injections[t, fr] = -bk * branch_vars.tap_angles[t, m]
                bus_vars.branch_injections[t, to] = bk * branch_vars.tap_angles[t, m]

            else:  # rest of the branches
                # is a phase shifter device (like phase shifter transformer or VSC with P control)
                flow_ctr = branch_vars.flows[t, m] == bk * (bus_vars.theta[t, fr] - bus_vars.theta[t, to])
                prob.add_cst(cst=flow_ctr, name=join("Branch_flow_set_", [t, m], "_"))

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

                # add to the objective function
                f_obj += branch_data_t.overload_cost[m] * branch_vars.flow_slacks_pos[t, m]
                f_obj += branch_data_t.overload_cost[m] * branch_vars.flow_slacks_neg[t, m]

    return f_obj


def add_linear_branches_contingencies_formulation(t_idx: int,
                                                  Sbase: float,
                                                  branch_data_t: BranchData,
                                                  branch_vars: BranchVars,
                                                  bus_vars: BusVars,
                                                  prob: LpModel,
                                                  linear_multicontingencies: LinearMultiContingencies):
    """
    Formulate the branches
    :param t_idx: time index
    :param Sbase: base power (100 MVA)
    :param branch_data_t: BranchData
    :param branch_vars: BranchVars
    :param bus_vars: BusVars
    :param prob: OR problem
    :param linear_multicontingencies: LinearMultiContingencies
    :return objective function
    """
    f_obj = 0.0
    for c, contingency in enumerate(linear_multicontingencies.multi_contingencies):

        # compute the contingency flow (Lp expression)
        contingency_flows = contingency.get_lp_contingency_flows(base_flow=branch_vars.flows[t_idx, :],
                                                                 injections=bus_vars.Pcalc[t_idx, :])

        for m, contingency_flow in enumerate(contingency_flows):

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
                                vars_bus: BusVars,
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
            hvdc_vars.flows[t, m] = prob.add_var(-hvdc_data_t.rate[m] / Sbase, hvdc_data_t.rate[m] / Sbase,
                                                 name=join("hvdc_flow_", [t, m], "_"))

            if hvdc_data_t.control_mode[m] == HvdcControlType.type_0_free:

                # set the flow based on the angular difference
                P0 = hvdc_data_t.Pset[m] / Sbase
                prob.add_cst(cst=hvdc_vars.flows[t, m] ==
                                 P0 + hvdc_data_t.angle_droop[m] * (vars_bus.theta[t, fr] - vars_bus.theta[t, to]),
                             name=join("hvdc_flow_cst_", [t, m], "_"))

                # add the injections matching the flow
                vars_bus.branch_injections[t, fr] -= hvdc_vars.flows[t, m]
                vars_bus.branch_injections[t, to] += hvdc_vars.flows[t, m]

            elif hvdc_data_t.control_mode[m] == HvdcControlType.type_1_Pset:

                if hvdc_data_t.dispatchable[m]:

                    # add the injections matching the flow
                    vars_bus.branch_injections[t, fr] -= hvdc_vars.flows[t, m]
                    vars_bus.branch_injections[t, to] += hvdc_vars.flows[t, m]

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
                    vars_bus.branch_injections[t, fr] -= hvdc_vars.flows[t, m]
                    vars_bus.branch_injections[t, to] += hvdc_vars.flows[t, m]
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
                            generator_data: GeneratorData,
                            battery_data: BatteryData,
                            load_data: LoadData,
                            bus_vars: BusVars,
                            gen_vars: GenerationVars,
                            batt_vars: BatteryVars,
                            load_vars: LoadVars,
                            prob: LpModel):
    """
    Add the kirchoff nodal equality
    :param t_idx: time step
    :param Bbus: susceptance matrix (complete)
    :param vd: List of slack node indices
    :param bus_data: BusData
    :param generator_data: GeneratorData
    :param battery_data: BatteryData
    :param load_data: LoadData
    :param bus_vars: BusVars
    :param gen_vars: GenerationVars
    :param batt_vars: BatteryVars
    :param load_vars: LoadVars
    :param prob: LpModel
    :param logger: Logger
    """
    B = Bbus.tocsc()

    P_esp = bus_vars.branch_injections[t_idx, :]
    P_esp += lpDot(generator_data.C_bus_elm.tocsc(),
                   gen_vars.p[t_idx, :] - gen_vars.shedding[t_idx, :])
    P_esp += lpDot(battery_data.C_bus_elm.tocsc(),
                   batt_vars.p[t_idx, :] - batt_vars.shedding[t_idx, :])
    P_esp += lpDot(load_data.C_bus_elm.tocsc(),
                   load_vars.shedding[t_idx, :] - load_vars.p[t_idx, :])

    # calculate the linear nodal inyection
    bus_vars.Pcalc[t_idx, :] = lpDot(B, bus_vars.theta[t_idx, :])

    # add the equality restrictions
    for k in range(bus_data.nbus):
        bus_vars.kirchhoff[t_idx, k] = prob.add_cst(
            cst=bus_vars.Pcalc[t_idx, k] == P_esp[k],
            name=join("kirchoff_", [t_idx, k], "_")
        )

    for i in vd:
        set_var_bounds(var=bus_vars.theta[t_idx, i], lb=0.0, ub=0.0)


def run_linear_opf_ts(grid: MultiCircuit,
                      time_indices: Union[IntVec, None],
                      solver_type: MIPSolvers = MIPSolvers.CBC,
                      zonal_grouping: ZonalGrouping = ZonalGrouping.NoGrouping,
                      skip_generation_limits: bool = False,
                      consider_contingencies: bool = False,
                      unit_Commitment: bool = False,
                      ramp_constraints: bool = False,
                      lodf_threshold: float = 0.001,
                      maximize_inter_area_flow: bool = False,
                      areas_from: List[Area] = None,
                      areas_to: List[Area] = None,
                      energy_0: Union[Vec, None] = None,
                      logger: Logger = Logger(),
                      progress_text: Union[None, Callable[[str], None]] = None,
                      progress_func: Union[None, Callable[[float], None]] = None,
                      export_model_fname: Union[None, str] = None) -> OpfVars:
    """
    Run linear optimal power flow
    :param grid: MultiCircuit instance
    :param time_indices: Time indices (in the general scheme)
    :param solver_type: MIP solver to use
    :param zonal_grouping: Zonal grouping?
    :param skip_generation_limits: Skip the generation limits?
    :param consider_contingencies: Consider the contingencies?
    :param unit_Commitment: Formulate unit commitment?
    :param ramp_constraints: Formulate ramp constraints?
    :param lodf_threshold:
    :param maximize_inter_area_flow:
    :param areas_from:
    :param areas_to:
    :param energy_0:
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

    if maximize_inter_area_flow:
        inter_area_branches = grid.get_inter_areas_branches(a1=areas_from, a2=areas_to)
        inter_area_hvdc = grid.get_inter_areas_hvdc_branches(a1=areas_from, a2=areas_to)
    else:
        inter_area_branches = list()
        inter_area_hvdc = list()

    # declare structures of LP vars
    mip_vars = OpfVars(nt=nt, nbus=n, ng=ng, nb=nb, nl=nl, nbr=nbr, n_hvdc=n_hvdc)

    # create the MIP problem object
    lp_model: LpModel = LpModel(solver_type)

    # objective function
    f_obj = 0.0

    for t_idx, t in enumerate(time_indices):  # use time_indices = [None] to simulate the snapshot

        # compile the circuit at the master time index ------------------------------------------------------------
        # note: There are very little chances of simplifying this step and experience shows
        #       it is not worth the effort, so compile every time step
        nc: NumericalCircuit = compile_numerical_circuit_at(circuit=grid,
                                                            t_idx=t,  # yes, this is not a bug
                                                            bus_dict=bus_dict,
                                                            areas_dict=areas_dict)

        # formulate the bus angles ---------------------------------------------------------------------------------
        for k in range(nc.bus_data.nbus):
            mip_vars.bus_vars.theta[t_idx, k] = lp_model.add_var(lb=nc.bus_data.angle_min[k],
                                                                 ub=nc.bus_data.angle_max[k],
                                                                 name=join("th_", [t_idx, k], "_"))

        # formulate loads ------------------------------------------------------------------------------------------
        f_obj += add_linear_load_formulation(t=t_idx,
                                             Sbase=nc.Sbase,
                                             load_data_t=nc.load_data,
                                             load_vars=mip_vars.load_vars,
                                             prob=lp_model)

        # formulate generation -------------------------------------------------------------------------------------
        f_obj += add_linear_generation_formulation(t=t_idx,
                                                   Sbase=nc.Sbase,
                                                   time_array=grid.time_profile,
                                                   gen_data_t=nc.generator_data,
                                                   gen_vars=mip_vars.gen_vars,
                                                   prob=lp_model,
                                                   unit_commitment=unit_Commitment,
                                                   ramp_constraints=ramp_constraints,
                                                   skip_generation_limits=skip_generation_limits)

        # formulate batteries --------------------------------------------------------------------------------------
        if t_idx == 0 and energy_0 is None:
            # declare the initial energy of the batteries
            energy_0 = nc.battery_data.soc_0 * nc.battery_data.enom  # in MWh here

        f_obj += add_linear_battery_formulation(t=t_idx,
                                                Sbase=nc.Sbase,
                                                time_array=grid.time_profile,
                                                batt_data_t=nc.battery_data,
                                                batt_vars=mip_vars.batt_vars,
                                                prob=lp_model,
                                                unit_commitment=unit_Commitment,
                                                ramp_constraints=ramp_constraints,
                                                skip_generation_limits=skip_generation_limits,
                                                energy_0=energy_0)

        # if no zonal grouping, all the grid is considered...
        if zonal_grouping == ZonalGrouping.NoGrouping:

            # formulate hvdc -------------------------------------------------------------------------------------------
            f_obj += add_linear_hvdc_formulation(t=t_idx,
                                                 Sbase=nc.Sbase,
                                                 hvdc_data_t=nc.hvdc_data,
                                                 hvdc_vars=mip_vars.hvdc_vars,
                                                 vars_bus=mip_vars.bus_vars,
                                                 prob=lp_model)

            # formulate branches ---------------------------------------------------------------------------------------
            f_obj += add_linear_branches_formulation(t=t_idx,
                                                     Sbase=nc.Sbase,
                                                     branch_data_t=nc.branch_data,
                                                     branch_vars=mip_vars.branch_vars,
                                                     bus_vars=mip_vars.bus_vars,
                                                     prob=lp_model,
                                                     inf=1e20)

            # formulate nodes ------------------------------------------------------------------------------------------
            add_linear_node_balance(t_idx=t_idx,
                                    Bbus=nc.Bbus,
                                    vd=nc.vd,
                                    bus_data=nc.bus_data,
                                    generator_data=nc.generator_data,
                                    battery_data=nc.battery_data,
                                    load_data=nc.load_data,
                                    bus_vars=mip_vars.bus_vars,
                                    gen_vars=mip_vars.gen_vars,
                                    batt_vars=mip_vars.batt_vars,
                                    load_vars=mip_vars.load_vars,
                                    prob=lp_model)

            # add branch contingencies ---------------------------------------------------------------------------------
            if consider_contingencies:
                # The contingencies formulation uses the total nodal injection stored in bus_vars,
                # hence this step goes before the add_linear_node_balance function

                # compute the PTDF and LODF
                ls = LinearAnalysis(numerical_circuit=nc, distributed_slack=False, correct_values=True)
                ls.run()

                # Compute the more generalistic contingency structures
                mctg = LinearMultiContingencies(grid=grid)
                mctg.update(lodf=ls.LODF, ptdf=ls.PTDF, threshold=lodf_threshold)

                # formulate the contingencies
                f_obj += add_linear_branches_contingencies_formulation(t_idx=t_idx,
                                                                       Sbase=nc.Sbase,
                                                                       branch_data_t=nc.branch_data,
                                                                       branch_vars=mip_vars.branch_vars,
                                                                       bus_vars=mip_vars.bus_vars,
                                                                       prob=lp_model,
                                                                       linear_multicontingencies=mctg)

            # add inter area branch flow maximization ------------------------------------------------------------------
            if maximize_inter_area_flow:

                for branches_list in [inter_area_branches, inter_area_hvdc]:
                    for k, branch, sense in branches_list:
                        # we want to maximize, hence the minus sign
                        f_obj += mip_vars.branch_vars.flows[t_idx, k] * (- sense)

        elif zonal_grouping == ZonalGrouping.All:
            # this is the copper plate approach
            pass

        # production equals demand -------------------------------------------------------------------------------------
        lp_model.add_cst(cst=(lp_model.sum(mip_vars.gen_vars.p[t_idx, :]) +
                              lp_model.sum(mip_vars.batt_vars.p[t_idx, :]) >=
                              mip_vars.load_vars.p[t_idx, :].sum() - mip_vars.load_vars.shedding[t_idx].sum()),
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
        logger.add_info("Objective function", value=lp_model.fobj_value())
        mip_vars.acceptable_solution = True
    else:
        logger.add_error("The problem does not have an optimal solution.")
        mip_vars.acceptable_solution = False
        lp_file_name = grid.name + "_debug.lp"
        lp_model.save_model(file_name=lp_file_name)
        logger.add_info("Debug LP model saved", value=lp_file_name)

    vars_v = mip_vars.get_values(grid.Sbase, model=lp_model)

    # add the model logger to the main logger
    logger += lp_model.logger

    return vars_v
