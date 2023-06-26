# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
from itertools import product
from typing import List, Union, Dict
from ortools.linear_solver import pywraplp
from GridCal.Engine.basic_structures import ZonalGrouping
from GridCal.Engine.basic_structures import MIPSolvers
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.numerical_circuit import NumericalCircuit, compile_numerical_circuit_at
from GridCal.Engine.Core.DataStructures.generator_data import GeneratorData
from GridCal.Engine.Core.DataStructures.battery_data import BatteryData
from GridCal.Engine.Core.DataStructures.load_data import LoadData
from GridCal.Engine.Core.DataStructures.branch_data import BranchData
from GridCal.Engine.Core.DataStructures.hvdc_data import HvdcData
from GridCal.Engine.basic_structures import Logger, Mat, Vec, IntVec
import GridCal.ThirdParty.ortools.ortools_extra as pl
from GridCal.Engine.Core.Devices.enumerations import TransformerControlType, ConverterControlType, HvdcControlType, \
    GenerationNtcFormulation
from GridCal.Engine.Simulations.LinearFactors.linear_analysis import LinearAnalysis


def join(init: str, vals: List[int], sep="_"):
    """
    Generate naming string
    :param init: initial string
    :param vals: concatenation of indices
    :param sep: separator
    :return: naming string
    """
    return init + sep.join([str(x) for x in vals])


class BusVars:
    """
    Struct to store the bus related vars
    """

    def __init__(self, nt, n_elm):
        """
        BusVars structure
        :param nt: Number of time steps
        :param n_elm: Number of branches
        """
        self.theta = np.zeros((nt, n_elm), dtype=object)
        self.Pinj_tau = np.zeros((nt, n_elm), dtype=object)


class LoadVars:
    """
    Struct to store the load related vars
    """

    def __init__(self, nt, n_elm):
        """
        LoadVars structure
        :param nt: Number of time steps
        :param n_elm: Number of branches
        """
        self.shedding = np.zeros((nt, n_elm), dtype=object)


class GenerationVars:
    """
    Struct to store the generation vars
    """

    def __init__(self, nt, n_elm):
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


class BatteryVars(GenerationVars):
    """
    struct extending the generation vars to handle the battery vars
    """

    def __init__(self, nt, n_elm):
        """
        BatteryVars structure
        :param nt: Number of time steps
        :param n_elm: Number of branches
        """
        GenerationVars.__init__(self, nt=nt, n_elm=n_elm)
        self.e = np.zeros((nt, n_elm), dtype=object)


class BranchVars:
    """
    Struct to store the branch related vars
    """

    def __init__(self, nt, n_elm):
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


class HvdcVars:
    """
    Struct to store the generation vars
    """

    def __init__(self, nt, n_elm):
        """
        GenerationVars structure
        :param nt: Number of time steps
        :param n_elm: Number of branches
        """
        self.flows = np.zeros((nt, n_elm), dtype=object)


def add_linear_generation_formulation(t: Union[int, None],
                                      Sbase: float,
                                      time_array: List[int],
                                      gen_data_t: GeneratorData,
                                      gen_vars: GenerationVars,
                                      prob: pywraplp.Solver,
                                      f_obj: pywraplp.LinearConstraint,
                                      unit_commitment: bool,
                                      ramp_constraints: bool,
                                      skip_generation_limits: bool):
    """
    Add MIP generation formulation
    :param t: time step, if None we assume single time step
    :param Sbase: base power (100 MVA)
    :param time_array: complete time array
    :param gen_data_t: GeneratorData structure
    :param gen_vars: GenerationVars structure
    :param prob: ORTools problem
    :param f_obj: objective function
    :param unit_commitment: formulate unit commitment?
    :param ramp_constraints: formulate ramp constraints?
    :param skip_generation_limits: skip the generation limits?
    """

    for k in range(gen_data_t.nelm):

        if gen_data_t.active[k]:

            if gen_data_t.dispatchable[k]:

                if unit_commitment:

                    # operational cost (linear...)
                    f_obj += gen_data_t.cost_1[k] * gen_vars.p[t, k] + gen_data_t.cost_0[k] * gen_vars.producing[t, k]

                    # start-up cost
                    f_obj += gen_data_t.startup_cost[k] * gen_vars.starting_up[t, k]

                    # power boundaries of the generator
                    if not skip_generation_limits:
                        prob.Add(gen_vars.p[t, k] >= (
                                gen_data_t.availability[k] * gen_data_t.pmin[k] / Sbase * gen_vars.producing[t, k]),
                                 join("gen>=Pmin", [t, k], "_"))
                        prob.Add(gen_vars.p[t, k] <= (
                                gen_data_t.availability[k] * gen_data_t.pmax[k] / Sbase * gen_vars.producing[t, k]),
                                 join("gen<=Pmax", [t, k], "_"))

                    if t is not None:
                        if t == 0:
                            prob.Add(gen_vars.starting_up[t, k] - gen_vars.shutting_down[t, k] == gen_vars.producing[t, k] - float(
                                gen_data_t.active[k]),
                                     join("binary_alg1_", [t, k], "_"))
                            prob.Add(gen_vars.starting_up[t, k] + gen_vars.shutting_down[t, k] <= 1,
                                     join("binary_alg2_", [t, k], "_"))
                        else:
                            prob.Add(
                                gen_vars.starting_up[t, k] - gen_vars.shutting_down[t, k] == gen_vars.producing[t, k] - gen_vars.producing[
                                    t - 1, k],
                                join("binary_alg3_", [t, k], "_"))
                            prob.Add(gen_vars.starting_up[t, k] + gen_vars.shutting_down[t, k] <= 1,
                                     join("binary_alg4_", [t, k], "_"))
                else:
                    # No unit commitment

                    # Operational cost (linear...)
                    f_obj += (gen_data_t.cost_1[k] * gen_vars.p[t, k]) + gen_data_t.cost_0[k]

                    # power boundaries of the generator
                    if not skip_generation_limits:
                        gen_vars.p[t, k].SetLb(gen_data_t.availability[k] * gen_data_t.pmin[k] / Sbase)
                        gen_vars.p[t, k].SetUb(gen_data_t.availability[k] * gen_data_t.pmax[k] / Sbase)

                # add the ramp constraints
                if ramp_constraints and t is not None:
                    if t > 0:
                        if gen_data_t.ramp_up[k] < gen_data_t.pmax[k] and gen_data_t.ramp_down[k] < gen_data_t.pmax[k]:
                            # if the ramp is actually sufficiently restrictive...
                            dt = (time_array[t] - time_array[t - 1]) / 3600.0  # time increment in hours

                            # - ramp_down · dt <= P(t) - P(t-1) <= ramp_up · dt
                            prob.Add(-gen_data_t.ramp_down[k] / Sbase * dt <= gen_vars.p[t, k] - gen_vars.p[t - 1, k])
                            prob.Add(gen_vars.p[t, k] - gen_vars.p[t - 1, k] <= gen_data_t.ramp_up[k] / Sbase * dt)
            else:

                # it is NOT dispatchable

                # Operational cost (linear...)
                f_obj += (gen_data_t.cost_1[k] * gen_vars.p[t, k]) + gen_data_t.cost_0[k]

                # the generator is not dispatchable at time step
                if gen_data_t.p[k] > 0:
                    prob.Add(gen_vars.p[t, k] == gen_data_t.p[k] / Sbase - gen_vars.shedding[t, k],
                             join("gen==PG-PGslack", [t, k], "_"))
                    gen_vars.shedding[t, k].SetLb(0.0)
                    gen_vars.shedding[t, k].SetUb(gen_data_t.p[k] / Sbase)
                else:
                    prob.Add(gen_vars.p[t, k] == gen_data_t.p[k] / Sbase + gen_vars.shedding[t, k],
                             join("gen==PG+PGslack", [t, k], "_"))
                    gen_vars.shedding[t, k].SetLb(0.0)
                    gen_vars.shedding[t, k].SetUb(
                        -gen_data_t.p[k] / Sbase)  # the negative sign is because P is already negative here

                gen_vars.producing[t, k].SetBounds(0.0, 0.0)
                gen_vars.shutting_down[t, k].SetBounds(0.0, 0.0)
                gen_vars.starting_up[t, k].SetBounds(0.0, 0.0)

        else:
            # the generator is not available at time step
            gen_vars.p[t, k].SetBounds(0.0, 0.0)


def add_linear_battery_formulation(t: Union[int, None],
                                   Sbase: float,
                                   time_array: List[int],
                                   batt_data_t: BatteryData,
                                   batt_vars: BatteryVars,
                                   prob: pywraplp.Solver,
                                   f_obj: pywraplp.LinearConstraint,
                                   unit_commitment: bool,
                                   ramp_constraints: bool,
                                   skip_generation_limits: bool):
    """
    Add MIP generation formulation
    :param t: time step, if None we assume single time step
    :param Sbase: base power (100 MVA)
    :param time_array: complete time array
    :param batt_data_t: BatteryData structure
    :param batt_vars: BatteryVars structure
    :param prob: ORTools problem
    :param f_obj: objective function
    :param unit_commitment: formulate unit commitment?
    :param ramp_constraints: formulate ramp constraints?
    :param skip_generation_limits: skip the generation limits?
    """

    for k in range(batt_data_t.nelm):

        if batt_data_t.active[k]:

            if batt_data_t.dispatchable[k]:

                if unit_commitment:

                    # operational cost (linear...)
                    f_obj += batt_data_t.cost_1[k] * batt_vars.p[t, k] + batt_data_t.cost_0[k] * batt_vars.producing[t, k]

                    # start-up cost
                    f_obj += batt_data_t.startup_cost[k] * batt_vars.starting_up[t, k]

                    # power boundaries of the generator
                    if not skip_generation_limits:
                        prob.Add(batt_vars.p[t, k] >= (
                                batt_data_t.availability[k] * batt_data_t.pmin[k] / Sbase * batt_vars.producing[t, k]),
                                 join("batt>=Pmin", [t, k], "_"))
                        prob.Add(batt_vars.p[t, k] <= (
                                batt_data_t.availability[k] * batt_data_t.pmax[k] / Sbase * batt_vars.producing[t, k]),
                                 join("batt<=Pmax", [t, k], "_"))

                    if t is not None:
                        if t == 0:
                            prob.Add(batt_vars.starting_up[t, k] - batt_vars.shutting_down[t, k] == batt_vars.producing[t, k] - float(
                                batt_data_t.active[k]),
                                     join("binary_alg1_", [t, k], "_"))
                            prob.Add(batt_vars.starting_up[t, k] + batt_vars.shutting_down[t, k] <= 1,
                                     join("binary_alg2_", [t, k], "_"))
                        else:
                            prob.Add(
                                batt_vars.starting_up[t, k] - batt_vars.shutting_down[t, k] == batt_vars.producing[t, k] -
                                batt_vars.producing[
                                    t - 1, k],
                                join("binary_alg3_", [t, k], "_"))
                            prob.Add(batt_vars.starting_up[t, k] + batt_vars.shutting_down[t, k] <= 1,
                                     join("binary_alg4_", [t, k], "_"))
                else:
                    # No unit commitment

                    # Operational cost (linear...)
                    f_obj += (batt_data_t.cost_1[k] * batt_vars.p[t, k]) + batt_data_t.cost_0[k]

                    # power boundaries of the generator
                    if not skip_generation_limits:
                        batt_vars.p[t, k].SetLb(batt_data_t.availability[k] * batt_data_t.pmin[k] / Sbase)
                        batt_vars.p[t, k].SetUb(batt_data_t.availability[k] * batt_data_t.pmax[k] / Sbase)

                if t is not None:
                    if t > 0:
                        dt = (time_array[t] - time_array[t - 1]) / 3600.0  # time increment in hours

                        # add the ramp constraints
                        if ramp_constraints:
                            if batt_data_t.ramp_up[k] < batt_data_t.pmax[k] and batt_data_t.ramp_down[k] < \
                                    batt_data_t.pmax[k]:
                                # if the ramp is actually sufficiently restrictive...
                                # - ramp_down · dt <= P(t) - P(t-1) <= ramp_up · dt
                                prob.Add(-batt_data_t.ramp_down[k] / Sbase * dt <= batt_vars.p[t, k] - batt_vars.p[t - 1, k])
                                prob.Add(batt_vars.p[t, k] - batt_vars.p[t - 1, k] <= batt_data_t.ramp_up[k] / Sbase * dt)

                        # set the energy  value Et = E(t - 1) + dt * Pb / eff
                        batt_vars.e[t, k].SetBounds(batt_data_t.e_min[k] / Sbase, batt_data_t.e_max[k] / Sbase)
                        prob.Add(batt_vars.e[t, k] == batt_vars.e[t - 1, k] + dt * batt_data_t.efficiency[k] * batt_vars.p[t, k])

            else:

                # it is NOT dispatchable

                # Operational cost (linear...)
                f_obj += (batt_data_t.cost_1[k] * batt_vars.p[t, k]) + batt_data_t.cost_0[k]

                # the generator is not dispatchable at time step
                if batt_data_t.p[k] > 0:
                    prob.Add(batt_vars.p[t, k] == batt_data_t.p[k] / Sbase - batt_vars.shedding[t, k],
                             join("batt==PB-PBslack", [t, k], "_"))
                    batt_vars.shedding[t, k].SetLb(0.0)
                    batt_vars.shedding[t, k].SetUb(batt_data_t.p[k] / Sbase)
                else:
                    prob.Add(batt_vars.p[t, k] == batt_data_t.p[k] / Sbase + batt_vars.shedding[t, k],
                             join("batt==PB+PBslack", [t, k], "_"))
                    batt_vars.shedding[t, k].SetLb(0.0)
                    batt_vars.shedding[t, k].SetUb(
                        -batt_data_t.p[k] / Sbase)  # the negative sign is because P is already negative here

                batt_vars.producing[t, k].SetBounds(0.0, 0.0)
                batt_vars.shutting_down[t, k].SetBounds(0.0, 0.0)
                batt_vars.starting_up[t, k].SetBounds(0.0, 0.0)

        else:
            # the generator is not available at time step
            batt_vars.p[t, k].SetBounds(0.0, 0.0)


def add_linear_branches_formulation(t: int,
                                    Sbase: float,
                                    branch_data_t: BranchData,
                                    branch_vars: BranchVars,
                                    vars_bus: BusVars,
                                    prob: pywraplp.Solver,
                                    f_obj: pywraplp.LinearConstraint,
                                    add_contingencies: bool,
                                    LODF: Union[Mat, None],
                                    lodf_threshold: float,
                                    inf=1e20):
    """

    :param t:
    :param Sbase:
    :param branch_data_t:
    :param branch_vars:
    :param vars_bus:
    :param prob:
    :param f_obj:
    :param add_contingencies:
    :param LODF:
    :param lodf_threshold:
    :param inf:
    :return:
    """

    if add_contingencies:
        assert LODF is not None

    # for each branch
    for m in range(branch_data_t.nelm):
        fr = branch_data_t.F[m]
        to = branch_data_t.T[m]

        if branch_data_t.active[m]:

            # declare the flow LPVar
            branch_vars.flows[t, m] = prob.NumVar(lb=-inf, ub=inf, name=join("flow_", [t, m], "_"))

            # compute the branch susceptance
            if branch_data_t.X[m] == 0.0:
                if branch_data_t.R[m] != 0.0:
                    bk = -1.0 / branch_data_t.R[m]
                else:
                    bk = 1e-20
            else:
                bk = -1.0 / branch_data_t.X[m]

            # compute the flow
            if branch_data_t.control_mode[m] == TransformerControlType.Pt:

                # add angle
                branch_vars.tap_angles[t, m] = prob.NumVar(lb=branch_data_t.tap_angle_min[m],
                                                           ub=branch_data_t.tap_angle_max[m],
                                                           name=join("flow_", [t, m], "_"))

                # is a phase shifter device (like phase shifter transformer or VSC with P control)
                flow_ctr = branch_vars.flows[t, m] == bk * (
                        vars_bus.theta[t, fr] - vars_bus.theta[t, to] + branch_vars.tap_angles[t, m])
                prob.Add(flow_ctr, name=join("Branch_flow_set_with_ps_", [t, m], "_"))

                # power injected and subtracted due to the phase shift
                vars_bus.Pinj_tau[fr] = -bk * branch_vars.tap_angles[t, m]
                vars_bus.Pinj_tau[to] = bk * branch_vars.tap_angles[t, m]

            else:  # rest of the branches
                # is a phase shifter device (like phase shifter transformer or VSC with P control)
                flow_ctr = branch_vars.flows[t, m] == bk * (vars_bus.theta[t, fr] - vars_bus.theta[t, to])
                prob.Add(flow_ctr, name=join("Branch_flow_set_", [t, m], "_"))

            # add the flow constraint if monitored
            if branch_data_t.monitor_loading[m]:
                branch_vars.flow_slacks_pos[t, m] = prob.NumVar(0, inf, name=join("flow_slack_pos_", [t, m], "_"))
                branch_vars.flow_slacks_neg[t, m] = prob.NumVar(0, inf, name=join("flow_slack_neg_", [t, m], "_"))

                # add upper rate constraint
                branch_vars.flow_constraints_ub[t, m] = branch_vars.flows[t, m] + branch_vars.flow_slacks_pos[t, m] - branch_vars.flow_slacks_neg[
                    t, m] <= branch_data_t.rates[m] / Sbase
                prob.Add(branch_vars.flow_constraints_ub[t, m])

                # add lower rate constraint
                branch_vars.flow_constraints_lb[t, m] = branch_vars.flows[t, m] + branch_vars.flow_slacks_pos[t, m] - branch_vars.flow_slacks_neg[
                    t, m] >= -branch_data_t.rates[m] / Sbase
                prob.Add(branch_vars.flow_constraints_lb[t, m])

                # add to the objective function
                f_obj += branch_vars.flow_slacks_pos[t, m] - branch_vars.flow_slacks_neg[t, m]

                if add_contingencies:

                    for c in range(branch_data_t.nelm):

                        if abs(LODF[m, c]) > lodf_threshold:
                            # TODO : think about the contingencies integration here
                            pass


def add_linear_hvdc_formulation(t: int,
                                Sbase: float,
                                hvdc_data_t: HvdcData,
                                hvdc_vars: HvdcVars,
                                vars_bus: BusVars,
                                prob: pywraplp.Solver):
    """

    :param t:
    :param Sbase:
    :param hvdc_data_t:
    :param hvdc_vars:
    :param vars_bus:
    :param prob:
    :return:
    """
    for m in range(hvdc_data_t.nelm):

        fr = hvdc_data_t.F[m]
        to = hvdc_data_t.T[m]

        if hvdc_data_t.active[m]:

            # declare the flow var
            hvdc_vars.flows[t, m] = prob.NumVar(-hvdc_data_t.rate[m] / Sbase, hvdc_data_t.rate[m] / Sbase,
                                                name=join("hvdc_flow_", [t, m], "_"))

            if hvdc_data_t.control_mode[m] == HvdcControlType.type_0_free:

                # set the flow based on the angular difference
                P0 = hvdc_data_t.Pset[m] / Sbase
                prob.Add(hvdc_vars.flows[m, t] == P0 + hvdc_data_t.angle_droop[m] * (
                        vars_bus.theta[t, fr] - vars_bus.theta[t, to]),
                         name=join("hvdc_flow_cst_", [t, m], "_"))

                # add the injections matching the flow
                vars_bus.Pinj_tau[fr] -= hvdc_vars.flows[t, m]
                vars_bus.Pinj_tau[to] += hvdc_vars.flows[t, m]

            elif hvdc_data_t.control_mode[m] == HvdcControlType.type_1_Pset:

                if hvdc_data_t.dispatchable[m]:

                    # add the injections matching the flow
                    vars_bus.Pinj_tau[fr] -= hvdc_vars.flows[t, m]
                    vars_bus.Pinj_tau[to] += hvdc_vars.flows[t, m]

                else:

                    if hvdc_data_t.Pset[m] > hvdc_data_t.rate[m]:
                        P0 = hvdc_data_t.rate[m] / Sbase
                    elif hvdc_data_t.Pset[m] < -hvdc_data_t.rate[m]:
                        P0 = -hvdc_data_t.rate[m] / Sbase
                    else:
                        P0 = hvdc_data_t.Pset[m] / Sbase

                    hvdc_vars.flows[t, m].SetBounds(P0, P0)  # make the flow equal to P0

                    # add the injections matching the flow
                    vars_bus.Pinj_tau[fr] -= hvdc_vars.flows[t, m]
                    vars_bus.Pinj_tau[to] += hvdc_vars.flows[t, m]
            else:
                raise Exception('OPF: Unknown HVDC control mode {}'.format(hvdc_data_t.control_mode[m]))
        else:
            # not active, therefore the flow is exactly zero
            hvdc_vars.flows[t, m].SetBounds(0, 0)


class OpfDcTimeSeries:

    def __init__(self, circuit: MultiCircuit,
                 time_indices: IntVec,
                 solver_type: MIPSolvers = MIPSolvers.CBC,
                 zonal_grouping: ZonalGrouping = ZonalGrouping.NoGrouping,
                 skip_generation_limits=False,
                 consider_contingencies=False,
                 unit_Commitment=False,
                 ramp_constraints=False,
                 add_contingencies=False,
                 lodf_threshold=0.001,
                 maximize_inter_area_flow=False,
                 buses_areas_1=None,
                 buses_areas_2=None):
        self.logger = Logger()

        self.grid: MultiCircuit = circuit
        self.time_indices = time_indices
        self.solver_type = solver_type

        nt = len(time_indices) if len(time_indices) > 0 else 1
        n = circuit.get_bus_number()
        nbr = circuit.get_branch_number_wo_hvdc()
        ng = circuit.get_generators_number()
        nb = circuit.get_batteries_number()
        nl = circuit.get_calculation_loads_number()
        n_hvdc = circuit.get_hvdc_number()

        prob = pywraplp.Solver.CreateSolver("SCIP")

        bus_vars = BusVars(nt=nt, n_elm=n)
        load_vars = LoadVars(nt=nt, n_elm=nl)
        gen_vars = GenerationVars(nt=nt, n_elm=ng)
        batt_vars = BatteryVars(nt=nt, n_elm=nb)
        branch_vars = BranchVars(nt=nt, n_elm=nbr)
        hvdc_vars = HvdcVars(nt=nt, n_elm=n_hvdc)

        bus_dict = {bus: i for i, bus in enumerate(circuit.buses)}
        areas_dict = {elm: i for i, elm in enumerate(circuit.areas)}
        f_obj: pywraplp.LinearConstraint = 0

        for t_idx, t in enumerate(time_indices):  # use time_indices = [None] to simulate the snapshot

            # compile the circuit at the master time index -------------------------------------------------------------
            nc = compile_numerical_circuit_at(circuit=circuit,
                                              t_idx=t,  # yes, this is not a bug
                                              bus_dict=bus_dict,
                                              areas_dict=areas_dict)

            if add_contingencies:
                ls = LinearAnalysis(numerical_circuit=nc,
                                    distributed_slack=False,
                                    correct_values=True)
                ls.run(with_nx=False)
                LODF = ls.LODF
            else:
                LODF = None

            # formulate generation -------------------------------------------------------------------------------------
            add_linear_generation_formulation(t=t_idx,
                                              Sbase=nc.Sbase,
                                              time_array=circuit.time_profile,
                                              gen_data_t=nc.generator_data,
                                              gen_vars=gen_vars,
                                              prob=prob,
                                              f_obj=f_obj,
                                              unit_commitment=unit_Commitment,
                                              ramp_constraints=ramp_constraints,
                                              skip_generation_limits=skip_generation_limits)

            # formulate batteries --------------------------------------------------------------------------------------
            add_linear_battery_formulation(t=t_idx,
                                           Sbase=nc.Sbase,
                                           time_array=circuit.time_profile,
                                           batt_data_t=nc.battery_data,
                                           batt_vars=batt_vars,
                                           prob=prob,
                                           f_obj=f_obj,
                                           unit_commitment=unit_Commitment,
                                           ramp_constraints=ramp_constraints,
                                           skip_generation_limits=skip_generation_limits)

            # formulate branches ---------------------------------------------------------------------------------------
            add_linear_branches_formulation(t=t_idx,
                                            Sbase=nc.Sbase,
                                            branch_data_t=nc.branch_data,
                                            branch_vars=branch_vars,
                                            vars_bus=bus_vars,
                                            prob=prob,
                                            f_obj=f_obj,
                                            add_contingencies=add_contingencies,
                                            LODF=LODF,
                                            lodf_threshold=lodf_threshold,
                                            inf=1e20)

            # formulate hvdc -------------------------------------------------------------------------------------------
            add_linear_hvdc_formulation(t=t_idx,
                                        Sbase=nc.Sbase,
                                        hvdc_data_t=nc.hvdc_data,
                                        hvdc_vars=hvdc_vars,
                                        vars_bus=bus_vars,
                                        prob=prob)

            # production equals demand ---------------------------------------------------------------------------------
            P_load_bus: Vec = nc.load_data.get_linear_injections_per_bus() / nc.Sbase

            demand_t = P_load_bus.sum()
