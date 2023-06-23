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
from GridCal.Engine.basic_structures import Logger
import GridCal.ThirdParty.ortools.ortools_extra as pl
from GridCal.Engine.Core.Devices.enumerations import TransformerControlType, ConverterControlType, HvdcControlType, \
    GenerationNtcFormulation


def join(init: str, vals: List[int], sep="_"):
    """
    Generate naming string
    :param init: initial string
    :param vals: concatenation of indices
    :param sep: separator
    :return: naming string
    """
    return init + sep.join([str(x) for x in vals])


class GenerationVars:

    def __init__(self, nt, ng):
        """
        GenerationVars structure
        :param nt: Number of time steps
        :param ng: Number og generators
        """
        self.p = np.zeros((nt, ng), dtype=object)
        self.shedding = np.zeros((nt, ng), dtype=object)
        self.producing = np.zeros((nt, ng), dtype=object)
        self.starting_up = np.zeros((nt, ng), dtype=object)
        self.shutting_down = np.zeros((nt, ng), dtype=object)


class BatteryVars(GenerationVars):

    def __init__(self, nt, nb):
        GenerationVars.__init__(self, nt=nt, ng=nb)
        self.e = np.zeros((nt, nb), dtype=object)


def add_linear_generation_formulation(t: Union[int, None],
                                      Sbase: float,
                                      time_array: List[int],
                                      gen_data_t: GeneratorData,
                                      gen: GenerationVars,
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
    :param gen: GenerationVars structure
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
                    f_obj += gen_data_t.cost_1[k] * gen.p[t, k] + gen_data_t.cost_0[k] * gen.producing[t, k]

                    # start-up cost
                    f_obj += gen_data_t.startup_cost[k] * gen.starting_up[t, k]

                    # power boundaries of the generator
                    if not skip_generation_limits:
                        prob.Add(gen.p[t, k] >= (
                                gen_data_t.availability[k] * gen_data_t.pmin[k] / Sbase * gen.producing[t, k]),
                                 join("gen>=Pmin", [t, k], "_"))
                        prob.Add(gen.p[t, k] <= (
                                gen_data_t.availability[k] * gen_data_t.pmax[k] / Sbase * gen.producing[t, k]),
                                 join("gen<=Pmax", [t, k], "_"))

                    if t is not None:
                        if t == 0:
                            prob.Add(gen.starting_up[t, k] - gen.shutting_down[t, k] == gen.producing[t, k] - float(
                                gen_data_t.active[k]),
                                     join("binary_alg1_", [t, k], "_"))
                            prob.Add(gen.starting_up[t, k] + gen.shutting_down[t, k] <= 1,
                                     join("binary_alg2_", [t, k], "_"))
                        else:
                            prob.Add(
                                gen.starting_up[t, k] - gen.shutting_down[t, k] == gen.producing[t, k] - gen.producing[
                                    t - 1, k],
                                join("binary_alg3_", [t, k], "_"))
                            prob.Add(gen.starting_up[t, k] + gen.shutting_down[t, k] <= 1,
                                     join("binary_alg4_", [t, k], "_"))
                else:
                    # No unit commitment

                    # Operational cost (linear...)
                    f_obj += (gen_data_t.cost_1[k] * gen.p[t, k]) + gen_data_t.cost_0[k]

                    # power boundaries of the generator
                    if not skip_generation_limits:
                        gen.p[t, k].SetLb(gen_data_t.availability[k] * gen_data_t.pmin[k] / Sbase)
                        gen.p[t, k].SetUb(gen_data_t.availability[k] * gen_data_t.pmax[k] / Sbase)

                # add the ramp constraints
                if ramp_constraints and t is not None:
                    if t > 0:
                        if gen_data_t.ramp_up[k] < gen_data_t.pmax[k] and gen_data_t.ramp_down[k] < gen_data_t.pmax[k]:
                            # if the ramp is actually sufficiently restrictive...
                            dt = (time_array[t] - time_array[t - 1]) / 3600.0  # time increment in hours

                            # - ramp_down · dt <= P(t) - P(t-1) <= ramp_up · dt
                            prob.Add(-gen_data_t.ramp_down[k] / Sbase * dt <= gen.p[t, k] - gen.p[t - 1, k])
                            prob.Add(gen.p[t, k] - gen.p[t - 1, k] <= gen_data_t.ramp_up[k] / Sbase * dt)
            else:

                # it is NOT dispatchable

                # Operational cost (linear...)
                f_obj += (gen_data_t.cost_1[k] * gen.p[t, k]) + gen_data_t.cost_0[k]

                # the generator is not dispatchable at time step
                if gen_data_t.p[k] > 0:
                    prob.Add(gen.p[t, k] == gen_data_t.p[k] / Sbase - gen.shedding[t, k],
                             join("gen==PG-PGslack", [t, k], "_"))
                    gen.shedding[t, k].SetLb(0.0)
                    gen.shedding[t, k].SetUb(gen_data_t.p[k] / Sbase)
                else:
                    prob.Add(gen.p[t, k] == gen_data_t.p[k] / Sbase + gen.shedding[t, k],
                             join("gen==PG+PGslack", [t, k], "_"))
                    gen.shedding[t, k].SetLb(0.0)
                    gen.shedding[t, k].SetUb(
                        -gen_data_t.p[k] / Sbase)  # the negative sign is because P is already negative here

                gen.producing[t, k].SetBounds(0.0, 0.0)
                gen.shutting_down[t, k].SetBounds(0.0, 0.0)
                gen.starting_up[t, k].SetBounds(0.0, 0.0)

        else:
            # the generator is not available at time step
            gen.p[t, k].SetBounds(0.0, 0.0)


def add_linear_battery_formulation(t: Union[int, None],
                                   Sbase: float,
                                   time_array: List[int],
                                   batt_data_t: BatteryData,
                                   batt: BatteryVars,
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
    :param batt: BatteryVars structure
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
                    f_obj += batt_data_t.cost_1[k] * batt.p[t, k] + batt_data_t.cost_0[k] * batt.producing[t, k]

                    # start-up cost
                    f_obj += batt_data_t.startup_cost[k] * batt.starting_up[t, k]

                    # power boundaries of the generator
                    if not skip_generation_limits:
                        prob.Add(batt.p[t, k] >= (
                                batt_data_t.availability[k] * batt_data_t.pmin[k] / Sbase * batt.producing[t, k]),
                                 join("batt>=Pmin", [t, k], "_"))
                        prob.Add(batt.p[t, k] <= (
                                batt_data_t.availability[k] * batt_data_t.pmax[k] / Sbase * batt.producing[t, k]),
                                 join("batt<=Pmax", [t, k], "_"))

                    if t is not None:
                        if t == 0:
                            prob.Add(batt.starting_up[t, k] - batt.shutting_down[t, k] == batt.producing[t, k] - float(
                                batt_data_t.active[k]),
                                     join("binary_alg1_", [t, k], "_"))
                            prob.Add(batt.starting_up[t, k] + batt.shutting_down[t, k] <= 1,
                                     join("binary_alg2_", [t, k], "_"))
                        else:
                            prob.Add(
                                batt.starting_up[t, k] - batt.shutting_down[t, k] == batt.producing[t, k] - batt.producing[
                                    t - 1, k],
                                join("binary_alg3_", [t, k], "_"))
                            prob.Add(batt.starting_up[t, k] + batt.shutting_down[t, k] <= 1,
                                     join("binary_alg4_", [t, k], "_"))
                else:
                    # No unit commitment

                    # Operational cost (linear...)
                    f_obj += (batt_data_t.cost_1[k] * batt.p[t, k]) + batt_data_t.cost_0[k]

                    # power boundaries of the generator
                    if not skip_generation_limits:
                        batt.p[t, k].SetLb(batt_data_t.availability[k] * batt_data_t.pmin[k] / Sbase)
                        batt.p[t, k].SetUb(batt_data_t.availability[k] * batt_data_t.pmax[k] / Sbase)

                if t is not None:
                    if t > 0:
                        dt = (time_array[t] - time_array[t - 1]) / 3600.0  # time increment in hours

                        # add the ramp constraints
                        if ramp_constraints:
                            if batt_data_t.ramp_up[k] < batt_data_t.pmax[k] and batt_data_t.ramp_down[k] < batt_data_t.pmax[k]:
                                # if the ramp is actually sufficiently restrictive...
                                # - ramp_down · dt <= P(t) - P(t-1) <= ramp_up · dt
                                prob.Add(-batt_data_t.ramp_down[k] / Sbase * dt <= batt.p[t, k] - batt.p[t - 1, k])
                                prob.Add(batt.p[t, k] - batt.p[t - 1, k] <= batt_data_t.ramp_up[k] / Sbase * dt)

                        # set the energy  value Et = E(t - 1) + dt * Pb / eff
                        batt.e[t, k].SetBounds(batt_data_t.Emin[k] / Sbase, batt_data_t.Emax[k] / Sbase)
                        prob.Add(batt.e[t, k] == batt.e[t-1, k] + dt * batt_data_t.efficiency[k] * batt.p[t, k])

            else:

                # it is NOT dispatchable

                # Operational cost (linear...)
                f_obj += (batt_data_t.cost_1[k] * batt.p[t, k]) + batt_data_t.cost_0[k]

                # the generator is not dispatchable at time step
                if batt_data_t.p[k] > 0:
                    prob.Add(batt.p[t, k] == batt_data_t.p[k] / Sbase - batt.shedding[t, k],
                             join("batt==PB-PBslack", [t, k], "_"))
                    batt.shedding[t, k].SetLb(0.0)
                    batt.shedding[t, k].SetUb(batt_data_t.p[k] / Sbase)
                else:
                    prob.Add(batt.p[t, k] == batt_data_t.p[k] / Sbase + batt.shedding[t, k],
                             join("batt==PB+PBslack", [t, k], "_"))
                    batt.shedding[t, k].SetLb(0.0)
                    batt.shedding[t, k].SetUb(
                        -batt_data_t.p[k] / Sbase)  # the negative sign is because P is already negative here

                batt.producing[t, k].SetBounds(0.0, 0.0)
                batt.shutting_down[t, k].SetBounds(0.0, 0.0)
                batt.starting_up[t, k].SetBounds(0.0, 0.0)

        else:
            # the generator is not available at time step
            batt.p[t, k].SetBounds(0.0, 0.0)


class OpfDcTimeSeries:

    def __init__(self, grid: MultiCircuit,
                 time_indices: np.ndarray,
                 solver_type: MIPSolvers = MIPSolvers.CBC,
                 zonal_grouping: ZonalGrouping = ZonalGrouping.NoGrouping,
                 skip_generation_limits=False,
                 consider_contingencies=False,
                 LODF=None,
                 lodf_tolerance=0.001,
                 maximize_inter_area_flow=False,
                 buses_areas_1=None,
                 buses_areas_2=None):
        """
        DC time series linear optimal power flow
        :param grid: MultiCircuit instance
        :param start_idx: start index of the time series
        :param end_idx: end index of the time series
        :param solver_type: MIP solver_type to use
        :param zonal_grouping:
        :param skip_generation_limits:
        :param consider_contingencies:
        :param LODF:
        :param lodf_tolerance:
        :param maximize_inter_area_flow:
        :param buses_areas_1:
        :param buses_areas_2:
        """

        self.logger = Logger()

        self.grid: MultiCircuit = grid
        self.time_indices = time_indices
        self.solver_type = solver_type

        nt = len(time_indices) if len(time_indices) > 0 else 1
        n = grid.get_bus_number()
        nbr = grid.get_branch_number_wo_hvdc()
        ng = grid.get_generators_number()
        nb = grid.get_batteries_number()
        nl = grid.get_calculation_loads_number()
        n_hvdc = grid.get_hvdc_number()

        self.theta = np.zeros((nt, n))
        self.Pinj = np.zeros((nt, n))
        self.nodal_restrictions = np.zeros((nt, n), dtype=object)

        self.Pg = np.zeros((nt, ng))
        self.gen_shedding = np.zeros((nt, ng))

        self.Pb = np.zeros((nt, nb))
        self.E = np.zeros((nt, nb))

        self.Pl = np.zeros((nt, nl))
        self.load_shedding = np.zeros((nt, nl))

        self.hvdc_flow = np.zeros(nt, n_hvdc)

        self.phase_shift = np.zeros((nt, nbr))
        self.s_from = np.zeros((nt, nbr))
        self.s_to = np.zeros((nt, nbr))
        self.overloads = np.zeros((nt, nbr))
        self.rating = grid.get_branch_rates_prof_wo_hvdc()

        self.contingency_flows_list = list()
        self.contingency_indices_list = list()  # [(t, m, c), ...]
        self.contingency_flows_slacks_list = list()

        self.zonal_grouping = zonal_grouping
        self.skip_generation_limits = skip_generation_limits
        self.consider_contingencies = consider_contingencies
        self.LODF = LODF
        self.lodf_tolerance = lodf_tolerance

        self.maximize_inter_area_flow = maximize_inter_area_flow
        self.buses_areas_1: List[int] = buses_areas_1
        self.buses_areas_2: List[int] = buses_areas_2

    def formulate_step(self, t_idx):

        nc = compile_numerical_circuit_at(self.grid, t_idx=t_idx)

    def formulate(self, batteries_energy_0=None):
        """
        Formulate the DC OPF time series in the non-sequential fashion (all to the solver_type at once)
        :param batteries_energy_0: initial energy state of the batteries (if none, the default is taken)
        :return: PuLP Problem instance
        """

        if len(self.time_indices) == 0:
            self.formulate_step(t_idx=None)
        else:
            for t_idx in self.time_indices:
                self.formulate_step(t_idx=t_idx)

    def extract_list(self, lst):
        val = np.zeros(len(lst))
        for i in range(val.shape[0]):
            if isinstance(lst[i], int) or isinstance(lst[i], float):
                val[i] = lst[i]
            else:
                val[i] = lst[i].value()
        return val

    def get_voltage(self):
        """
        return the complex voltages (time, device)
        :return: 2D array
        """
        angles = self.extract2D(self.theta)
        return np.ones_like(angles) * np.exp(-1j * angles)

    def get_overloads(self):
        """
        return the branch overloads (time, device)
        :return: 2D array
        """
        return self.extract2D(self.overloads)

    def get_loading(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract2D(self.s_from, make_abs=False) / (self.rating + 1e-20)

    def get_power_injections(self):
        """
        return the branch overloads (time, device)
        :return: 2D array
        """
        return self.extract2D(self.Pinj) * self.numerical_circuit.Sbase

    def get_phase_shifts(self):
        """
        return the branch phase_shifts (time, device)
        :return: 2D array
        """
        return self.extract2D(self.phase_shift)

    def get_hvdc_flows(self):
        """
        return the branch overloads (time, device)
        :return: 2D array
        """
        return self.extract2D(self.hvdc_flow) * self.numerical_circuit.Sbase

    def get_branch_power_from(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract2D(self.s_from, make_abs=False) * self.numerical_circuit.Sbase

    def get_branch_power_to(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract2D(self.s_to, make_abs=False) * self.numerical_circuit.Sbase

    def get_battery_power(self):
        """
        return the battery dispatch (time, device)
        :return: 2D array
        """
        return self.extract2D(self.Pb) * self.numerical_circuit.Sbase

    def get_battery_energy(self):
        """
        return the battery energy (time, device)
        :return: 2D array
        """
        return self.extract2D(self.E) * self.numerical_circuit.Sbase

    def get_generator_power(self):
        """
        return the generator dispatch (time, device)
        :return: 2D array
        """
        return self.extract2D(self.Pg) * self.numerical_circuit.Sbase

    def get_load_shedding(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.extract2D(self.load_shedding) * self.numerical_circuit.Sbase

    def get_load_power(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.extract2D(self.Pl) * self.numerical_circuit.Sbase

    def get_contingency_flows_list(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.extract_list(self.contingency_flows_list) * self.numerical_circuit.Sbase

    def get_contingency_flows_slacks_list(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.extract_list(self.contingency_flows_slacks_list) * self.numerical_circuit.Sbase

    def get_shadow_prices(self):
        """
        Extract values fro the 2D array of LP variables
        :return: 2D numpy array
        """
        val = np.zeros(self.nodal_restrictions.shape)
        for i, j in product(range(val.shape[0]), range(val.shape[1])):
            if self.nodal_restrictions[i, j] is not None:
                if self.nodal_restrictions[i, j].pi is not None:
                    val[i, j] = - self.nodal_restrictions[i, j].pi
        return val.transpose()
