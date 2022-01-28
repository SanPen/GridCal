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
from enum import Enum
from typing import List, Dict, Tuple
import numpy as np
from GridCal.Engine.Core.time_series_opf_data import OpfTimeCircuit
from GridCal.Engine.Simulations.OPF.opf_templates import OpfTimeSeries, MIPSolvers
from GridCal.Engine.Devices.enumerations import TransformerControlType, ConverterControlType, HvdcControlType, \
    GenerationNtcFormulation
from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Simulations.OPF.ntc_opf import validate_generator_limits, validate_generator_to_increase, \
    validate_generator_to_decrease, formulate_angles, formulate_objective, formulate_contingency, \
    formulate_branches_flow, formulate_hvdc_flow, formulate_node_balance, formulate_power_injections, \
    formulate_proportional_generation, formulate_optimal_generation, check_proportional_generation, \
    check_contingency, check_hvdc_flow, check_branches_flow, check_node_balance, check_power_injections, \
    check_optimal_generation, lpDot, lpExpand, extract, save_lp, get_generators_per_areas, get_inter_areas_branches

try:
    from ortools.linear_solver import pywraplp
except ModuleNotFoundError:
    print('ORTOOLS not found :(')

import pandas as pd
from scipy.sparse.csc import csc_matrix


class OpfNTC_ts(OpfTimeSeries):

    def __init__(self,
                 numerical_circuit: OpfTimeCircuit,
                 start_idx,
                 end_idx,
                 area_from_bus_idx,
                 area_to_bus_idx,
                 alpha,
                 LODF,
                 solver_type: MIPSolvers = MIPSolvers.CBC,
                 generation_formulation: GenerationNtcFormulation = GenerationNtcFormulation.Proportional,
                 monitor_only_sensitive_branches=False,
                 branch_sensitivity_threshold=0.01,
                 skip_generation_limits=True,
                 consider_contingencies=True,
                 maximize_exchange_flows=True,
                 dispatch_all_areas=False,
                 tolerance=1e-2,
                 weight_power_shift=1e5,
                 weight_generation_cost=1e5,
                 weight_generation_delta=1e5,
                 weight_kirchoff=1e5,
                 weight_overloads=1e5,
                 weight_hvdc_control=1e0,
                 logger: Logger = None):
        """
        DC time series linear optimal power flow
        :param numerical_circuit:  NumericalCircuit instance
        :param start_idx: start index of the time series
        :param end_idx: end index of the time series
        :param area_from_bus_idx:  indices of the buses of the area 1
        :param area_to_bus_idx: indices of the buses of the area 2
        :param alpha: Array of branch sensitivities to the exchange
        :param LODF: LODF matrix
        :param solver_type: MIP solver_type to use
        :param generation_formulation: type of generation formulation
        :param monitor_only_sensitive_branches: Monitor the loading of only the sensitive branches?
        :param branch_sensitivity_threshold: branch sensitivity used to filter out the branches whose sensitivity is under the threshold
        :param skip_generation_limits: Skip the generation limits?
        :param consider_contingencies: Consider contingencies?
        :param maximize_exchange_flows: Maximize the exchange flow?
        :param tolerance: Solution tolerance
        :param weight_power_shift: Power shift maximization weight
        :param weight_generation_cost: Generation cost minimization weight
        :param weight_generation_delta: Generation delta slacks minimization
        :param weight_kirchoff: (unused)
        :param weight_overloads: Branch overload minimization weight
        :param weight_hvdc_control: HVDC control mismatch minimization weight
        :param logger: logger instance
        :param t: time index
        """

        self.start_idx = start_idx
        self.end_idx = end_idx
        self.solver = solver_type

        self.area_from_bus_idx = area_from_bus_idx

        self.area_to_bus_idx = area_to_bus_idx

        self.generation_formulation = generation_formulation

        self.monitor_only_sensitive_branches = monitor_only_sensitive_branches

        self.branch_sensitivity_threshold = branch_sensitivity_threshold

        self.skip_generation_limits = skip_generation_limits

        self.consider_contingencies = consider_contingencies

        self.maximize_exchange_flows = maximize_exchange_flows

        self.dispatch_all_areas = dispatch_all_areas

        self.tolerance = tolerance

        self.alpha = alpha

        self.LODF = LODF

        self.weight_power_shift = weight_power_shift
        self.weight_generation_cost = weight_generation_cost
        self.weight_generation_delta = weight_generation_delta
        self.weight_kirchoff = weight_kirchoff
        self.weight_overloads = weight_overloads
        self.weight_hvdc_control = weight_hvdc_control

        self.inf = 99999999999999

        # results
        self.gen_a1_idx = None
        self.gen_a2_idx = None
        self.all_slacks = None
        self.all_slacks_sum = None
        self.Pg_delta = None
        self.area_balance_slack = None
        self.generation_delta_slacks = None
        self.Pinj = None
        self.hvdc_flow = None
        self.hvdc_slacks = None
        self.phase_shift = None
        self.inter_area_branches = None
        self.inter_area_hvdc = None

        self.logger = logger

        # this builds the formulation right away
        OpfTimeSeries.__init__(self,
                               numerical_circuit=numerical_circuit,
                               start_idx=self.start_idx,
                               end_idx=self.end_idx,
                               solver_type=self.solver,
                               ortools=True)

    def formulate(self, add_slacks=True, t=0):
        """
        Formulate the Net Transfer Capacity problem
        :param t: time index
        :return:
        """

        self.inf = self.solver.infinity()

        # general indices
        n = self.numerical_circuit.nbus
        m = self.numerical_circuit.nbr
        ng = self.numerical_circuit.ngen
        nb = self.numerical_circuit.nbatt
        nl = self.numerical_circuit.nload
        nt = self.end_idx - self.start_idx
        a = self.start_idx
        b = self.end_idx
        Sbase = self.numerical_circuit.Sbase

        # battery
        Pb_max = self.numerical_circuit.battery_pmax / Sbase
        Pb_min = self.numerical_circuit.battery_pmin / Sbase
        cost_b = self.numerical_circuit.battery_cost[:, t]
        Cbat = self.numerical_circuit.battery_data.C_bus_batt.tocsc()

        # generator
        Pg_max = self.numerical_circuit.generator_pmax / Sbase
        Pg_min = self.numerical_circuit.generator_pmin / Sbase
        Pg_fix = self.numerical_circuit.generator_data.get_effective_generation()[:, t] / Sbase
        Cgen = self.numerical_circuit.generator_data.C_bus_gen.tocsc()

        if self.skip_generation_limits:
            print('Skipping generation limits')
            Pg_max = self.inf * np.ones(self.numerical_circuit.ngen)
            Pg_min = -self.inf * np.ones(self.numerical_circuit.ngen)

        # load
        Pl_fix = self.numerical_circuit.load_data.get_effective_load().real[:, t] / Sbase

        # modify Pg_fix until it is identical to Pload
        total_load = Pl_fix.sum()
        total_gen = Pg_fix.sum()
        diff = total_gen - total_load
        Pg_fix -= diff * (Pg_fix / total_gen)

        # branch
        branch_ratings = self.numerical_circuit.branch_rates[:, t] / Sbase
        alpha_abs = np.abs(self.alpha)

        # --------------------------------------------------------------------------------------------------------------
        # Formulate the problem
        # --------------------------------------------------------------------------------------------------------------

        # get the inter-area branches and their sign
        inter_area_branches = get_inter_areas_branches(
            nbr=m,
            F=self.numerical_circuit.branch_data.F,
            T=self.numerical_circuit.branch_data.T,
            buses_areas_1=self.area_from_bus_idx,
            buses_areas_2=self.area_to_bus_idx)

        inter_area_hvdc = get_inter_areas_branches(
            nbr=self.numerical_circuit.nhvdc,
            F=self.numerical_circuit.hvdc_data.get_bus_indices_f(),
            T=self.numerical_circuit.hvdc_data.get_bus_indices_t(),
            buses_areas_1=self.area_from_bus_idx,
            buses_areas_2=self.area_to_bus_idx)

        # formulate the generation
        if self.generation_formulation == GenerationNtcFormulation.Optimal:

            generation, generation_delta, gen_a1_idx, gen_a2_idx, power_shift, dgen1, gen_cost,  delta_slack_1, \
            delta_slack_2 = formulate_optimal_generation(
                solver=self.solver,
                generator_active=self.numerical_circuit.generator_data.generator_active[:,t],
                dispatchable=self.numerical_circuit.generator_data.generator_dispatchable,
                generator_cost=self.numerical_circuit.generator_data.generator_cost[:, t],
                generator_names=self.numerical_circuit.generator_data.generator_names,
                Sbase=self.numerical_circuit.Sbase,
                logger=self.logger,
                inf=self.inf,
                ngen=ng,
                Cgen=Cgen,
                Pgen=Pg_fix,
                Pmax=Pg_max,
                Pmin=Pg_min,
                a1=self.area_from_bus_idx,
                a2=self.area_to_bus_idx,
                dispatch_all_areas=self.dispatch_all_areas)

            load_cost = self.numerical_circuit.load_data.load_cost[:, t]

        elif self.generation_formulation == GenerationNtcFormulation.Proportional:

            generation, generation_delta, gen_a1_idx, gen_a2_idx, power_shift, dgen1, gen_cost, delta_slack_1, \
            delta_slack_2 = formulate_proportional_generation(
                solver=self.solver,
                generator_active=self.numerical_circuit.generator_data.generator_active[:, t],
                generator_dispatchable=self.numerical_circuit.generator_data.generator_dispatchable,
                generator_cost=self.numerical_circuit.generator_data.generator_cost[:, t],
                generator_names=self.numerical_circuit.generator_data.generator_names,
                Sbase=self.numerical_circuit.Sbase,
                logger=self.logger,
                inf=self.inf,
                ngen=ng,
                Cgen=Cgen,
                Pgen=Pg_fix,
                Pmax=Pg_max,
                Pmin=Pg_min,
                a1=self.area_from_bus_idx,
                a2=self.area_to_bus_idx)

            load_cost = np.ones(self.numerical_circuit.nload)

        else:
            raise Exception('Unknown generation mode')

        # add the angles
        theta = formulate_angles(
            solver=self.solver,
            nbus=self.numerical_circuit.nbus,
            vd=self.numerical_circuit.vd,
            bus_names=self.numerical_circuit.bus_data.bus_names,
            angle_min=self.numerical_circuit.bus_data.angle_min,
            angle_max=self.numerical_circuit.bus_data.angle_max,
            logger=self.logger)

        # formulate the power injections
        Pinj, load_shedding = formulate_power_injections(
            solver=self.solver,
            Cgen=Cgen,
            generation=generation,
            Cload=self.numerical_circuit.load_data.C_bus_load,
            load_active=self.numerical_circuit.load_data.load_active[:, t],
            load_power=Pl_fix,
            Sbase=self.numerical_circuit.Sbase)

        # formulate the flows
        flow_f, overload1, overload2, tau, monitor = formulate_branches_flow(
            solver=self.solver,
            nbr=self.numerical_circuit.nbr,
            Rates=self.numerical_circuit.Rates[:, t],
            Sbase=self.numerical_circuit.Sbase,
            branch_active=self.numerical_circuit.branch_active[:, t],
            branch_names=self.numerical_circuit.branch_names,
            branch_dc=self.numerical_circuit.branch_data.branch_dc,
            theta=self.numerical_circuit.branch_data.theta[:, t],
            theta_min=self.numerical_circuit.branch_data.theta_min,
            theta_max=self.numerical_circuit.branch_data.theta_max,
            control_mode=self.numerical_circuit.branch_data.control_mode,
            R=self.numerical_circuit.branch_data.R,
            X=self.numerical_circuit.branch_data.X,
            F=self.numerical_circuit.F,
            T=self.numerical_circuit.T,
            inf=self.inf,
            monitor_loading=self.numerical_circuit.branch_data.monitor_loading,
            branch_sensitivity_threshold=self.branch_sensitivity_threshold,
            monitor_only_sensitive_branches=self.monitor_only_sensitive_branches,
            angles=theta,
            alpha_abs=alpha_abs,
            logger=self.logger)

        # formulate the contingencies
        if self.consider_contingencies:
            n1flow_f, n1overload1, n1overload2, con_br_idx = formulate_contingency(
                solver=self.solver,
                ContingencyRates=self.numerical_circuit.ContingencyRates[:, t],
                Sbase=self.numerical_circuit.Sbase,
                branch_names=self.numerical_circuit.branch_names,
                contingency_enabled_indices=self.numerical_circuit.branch_data.get_contingency_enabled_indices(),
                LODF=self.LODF,
                F=self.numerical_circuit.F,
                T=self.numerical_circuit.T,
                inf=self.inf,
                branch_sensitivity_threshold=self.branch_sensitivity_threshold,
                flow_f=flow_f,
                monitor=monitor,
                replacement_value=0,
                logger=self.logger)
        else:
            n1overload1 = list()
            n1overload2 = list()
            con_br_idx = list()
            n1flow_f = list()

        # formulate the HVDC flows
        hvdc_flow_f, hvdc_overload1, hvdc_overload2, hvdc_control1, hvdc_control2 = formulate_hvdc_flow(
            solver=self.solver,
            nhvdc=self.numerical_circuit.nhvdc,
            names=self.numerical_circuit.hvdc_names,
            rate=self.numerical_circuit.hvdc_data.rate[:, t],
            angles=theta,
            active=self.numerical_circuit.hvdc_data.active[:, t],
            Pt=self.numerical_circuit.hvdc_data.Pt[:, t],
            angle_droop=self.numerical_circuit.hvdc_data.get_angle_droop_in_pu_rad(Sbase)[:, t],
            control_mode=self.numerical_circuit.hvdc_data.control_mode,
            dispatchable=self.numerical_circuit.hvdc_data.dispatchable,
            F=self.numerical_circuit.hvdc_data.get_bus_indices_f(),
            T=self.numerical_circuit.hvdc_data.get_bus_indices_t(),
            Pinj=Pinj,
            Sbase=self.numerical_circuit.Sbase,
            inf=self.inf,
            logger=self.logger)

        # formulate the node power balance
        node_balance = formulate_node_balance(
            solver=self.solver,
            Bbus=self.numerical_circuit.Bbus,
            angles=theta,
            Pinj=Pinj,
            bus_active=self.numerical_circuit.bus_data.bus_active[:, t],
            bus_names=self.numerical_circuit.bus_data.bus_names)

        # formulate the objective
        self.all_slacks_sum, self.all_slacks = formulate_objective(
            solver=self.solver,
            inter_area_branches=inter_area_branches,
            flows_f=flow_f,
            overload1=overload1,
            overload2=overload2,
            n1overload1=n1overload1,
            n1overload2=n1overload2,
            inter_area_hvdc=inter_area_hvdc,
            hvdc_flow_f=hvdc_flow_f,
            hvdc_overload1=hvdc_overload1,
            hvdc_overload2=hvdc_overload2,
            hvdc_control1=hvdc_control1,
            hvdc_control2=hvdc_control2,
            power_shift=power_shift,
            dgen1=dgen1,
            gen_cost=gen_cost[gen_a1_idx],
            generation_delta=generation_delta[gen_a1_idx],
            delta_slack_1=delta_slack_1,
            delta_slack_2=delta_slack_2,
            weight_power_shift=self.weight_power_shift,
            maximize_exchange_flows=self.maximize_exchange_flows,
            weight_generation_cost=self.weight_generation_cost,
            weight_generation_delta=self.weight_generation_delta,
            weight_overloads=self.weight_overloads,
            weight_hvdc_control=self.weight_hvdc_control,
            load_shedding=load_shedding,
            load_cost=load_cost)

        # Assign variables to keep
        # transpose them to be in the format of GridCal: time, device
        self.theta = theta
        self.Pg = generation
        self.Pg_delta = generation_delta
        self.area_balance_slack = power_shift
        self.generation_delta_slacks = delta_slack_1 - delta_slack_2

        self.load_shedding = load_shedding

        self.gen_a1_idx = gen_a1_idx
        self.gen_a2_idx = gen_a2_idx

        # self.Pb = Pb
        self.Pl = Pl_fix
        self.Pinj = Pinj
        # self.load_shedding = load_slack
        self.s_from = flow_f
        self.s_to = - flow_f
        self.n1flow_f = n1flow_f
        self.contingency_br_idx = con_br_idx

        self.hvdc_flow = hvdc_flow_f
        self.hvdc_slacks = hvdc_overload1 - hvdc_overload2

        self.overloads = overload1 - overload2
        self.rating = branch_ratings
        self.phase_shift = tau
        self.nodal_restrictions = node_balance

        self.inter_area_branches = inter_area_branches
        self.inter_area_hvdc = inter_area_hvdc

        # n1flow_f, n1overload1, n1overload2, con_br_idx
        self.contingency_flows_list = n1flow_f
        self.contingency_indices_list = con_br_idx  # [(t, m, c), ...]
        self.contingency_flows_slacks_list = n1overload1

        return self.solver

    def check(self, t=0):
        """
        Formulate the Net Transfer Capacity problem
        param t: time index
        :return:
        """
        # time index
        # t = 0

        # general indices
        n = self.numerical_circuit.nbus
        m = self.numerical_circuit.nbr
        ng = self.numerical_circuit.ngen
        nb = self.numerical_circuit.nbatt
        nl = self.numerical_circuit.nload
        Sbase = self.numerical_circuit.Sbase

        # battery
        Pb_max = self.numerical_circuit.battery_pmax / Sbase
        Pb_min = self.numerical_circuit.battery_pmin / Sbase
        cost_b = self.numerical_circuit.battery_cost
        Cbat = self.numerical_circuit.battery_data.C_bus_batt.tocsc()

        # generator
        Pg_fix = self.numerical_circuit.generator_data.get_effective_generation()[:, t] / Sbase
        Pg_max = self.numerical_circuit.generator_pmax / Sbase
        Cgen = self.numerical_circuit.generator_data.C_bus_gen.tocsc()

        if self.skip_generation_limits:
            print('Skipping generation limits')
            Pg_max = self.inf * np.ones(self.numerical_circuit.ngen)
            Pg_min = -self.inf * np.ones(self.numerical_circuit.ngen)

        # load
        Pl_fix = self.numerical_circuit.load_data.get_effective_load().real[:, t] / Sbase

        # branch
        alpha_abs = np.abs(self.alpha)

        # check that the slacks are 0
        if self.all_slacks is not None:
            for var_array in self.all_slacks:
                for var in var_array:
                    if isinstance(var, float) or isinstance(var, int):
                        val = var
                    else:
                        val = var.solution_value()

                    if abs(val) > 0:
                        self.logger.add_divergence(
                            'Slack variable is over the tolerance', var.name(), val, 0
                        )

        # check variables
        for var in self.solver.variables():

            if var.solution_value() > var.Ub():
                self.logger.add_divergence(
                    'Variable over the upper bound', var.name(), var.solution_value(), var.Ub()
                )
            if var.solution_value() < var.Lb():
                self.logger.add_divergence(
                    'Variable under the lower bound', var.name(), var.solution_value(), var.Lb()
                )

        # formulate the generation
        if self.generation_formulation == GenerationNtcFormulation.Optimal:

            check_optimal_generation(
                generator_active=self.numerical_circuit.generator_data.generator_active[:, t],
                dispatchable=self.numerical_circuit.generator_data.generator_dispatchable,
                generator_names=self.numerical_circuit.generator_data.generator_names,
                Cgen=Cgen,
                Pgen=Pg_fix,
                a1=self.area_from_bus_idx,
                a2=self.area_to_bus_idx,
                generation=self.extract(self.Pg),
                delta=self.extract(self.Pg_delta),
                logger=self.logger
            )

        elif self.generation_formulation == GenerationNtcFormulation.Proportional:

            check_proportional_generation(
                generator_active=self.numerical_circuit.generator_data.generator_active[:, t],
                generator_dispatchable=self.numerical_circuit.generator_data.generator_dispatchable,
                generator_cost=self.numerical_circuit.generator_data.generator_cost[:, t],
                generator_names=self.numerical_circuit.generator_data.generator_names,
                Sbase=self.numerical_circuit.Sbase,
                Cgen=Cgen,
                Pgen=Pg_fix,
                Pmax=Pg_max,
                Pmin=Pg_min,
                a1=self.area_from_bus_idx,
                a2=self.area_to_bus_idx,
                generation=self.extract(self.Pg),
                delta=self.extract(self.Pg_delta),
                power_shift=self.area_balance_slack.solution_value(),
                logger=self.logger)
        else:
            raise Exception('Unknown generation mode')

        monitor = check_branches_flow(
            nbr=self.numerical_circuit.nbr,
            Rates=self.numerical_circuit.Rates[:, t],
            Sbase=self.numerical_circuit.Sbase,
            branch_active=self.numerical_circuit.branch_active[:, t],
            branch_names=self.numerical_circuit.branch_names,
            branch_dc=self.numerical_circuit.branch_data.branch_dc,
            control_mode=self.numerical_circuit.branch_data.control_mode,
            R=self.numerical_circuit.branch_data.R,
            X=self.numerical_circuit.branch_data.X,
            F=self.numerical_circuit.F,
            T=self.numerical_circuit.T,
            monitor_loading=self.numerical_circuit.branch_data.monitor_loading,
            branch_sensitivity_threshold=self.branch_sensitivity_threshold,
            monitor_only_sensitive_branches=self.monitor_only_sensitive_branches,
            angles=self.extract(self.theta),
            alpha_abs=alpha_abs,
            logger=self.logger,
            flow_f=self.extract(self.s_from),
            tau=self.extract(self.phase_shift))

        check_contingency(
            ContingencyRates=self.numerical_circuit.ContingencyRates[:, t],
            Sbase=self.numerical_circuit.Sbase,
            branch_names=self.numerical_circuit.branch_names,
            contingency_enabled_indices=self.numerical_circuit.branch_data.get_contingency_enabled_indices(),
            LODF=self.LODF,
            F=self.numerical_circuit.F,
            T=self.numerical_circuit.T,
            branch_sensitivity_threshold=self.branch_sensitivity_threshold,
            flow_f=self.extract(self.s_from),
            monitor=monitor,
            logger=self.logger)

        check_hvdc_flow(
            nhvdc=self.numerical_circuit.nhvdc,
            names=self.numerical_circuit.hvdc_names,
            rate=self.numerical_circuit.hvdc_data.rate[:, t],
            angles=self.extract(self.theta),
            active=self.numerical_circuit.hvdc_data.active[:, t],
            Pt=self.numerical_circuit.hvdc_data.Pset[:, t],
            angle_droop=self.numerical_circuit.hvdc_data.get_angle_droop_in_pu_rad(Sbase)[:, t],
            control_mode=self.numerical_circuit.hvdc_data.control_mode,
            dispatchable=self.numerical_circuit.hvdc_data.dispatchable,
            F=self.numerical_circuit.hvdc_data.get_bus_indices_f(),
            T=self.numerical_circuit.hvdc_data.get_bus_indices_t(),
            Sbase=self.numerical_circuit.Sbase,
            flow_f=self.extract(self.hvdc_flow),
            logger=self.logger)

        Pinj = check_power_injections(
            load_power=Pl_fix,
            Cgen=Cgen,
            generation=self.extract(self.Pg),
            Cload=self.numerical_circuit.load_data.C_bus_load,
            load_shedding=self.extract(self.load_shedding))

        check_node_balance(
            Bbus=self.numerical_circuit.Bbus,
            angles=self.extract(self.theta),
            Pinj=Pinj,
            bus_active=self.numerical_circuit.bus_data.bus_active[:, t],
            bus_names=self.numerical_circuit.bus_data.bus_names,
            logger=self.logger)

    def save_lp(self, file_name="ntc_opf_problem.lp"):
        """
        Save problem in LP format
        :param file_name: name of the file (.lp or .mps supported)
        """
        save_lp(self.solver, file_name)

    def solve(self, with_checks=True):
        """
        Call ORTools to solve the problem
        """
        self.status = self.solver.Solve()

        converged = self.converged()

        self.save_lp('ntc_opf.lp')

        # check the solution
        if not converged and with_checks:
            self.check()

        return converged

    def error(self):
        """
        Compute total error
        :return: total error
        """
        if self.status == pywraplp.Solver.OPTIMAL:
            return self.all_slacks_sum.solution_value()
        else:
            return 99999

    def converged(self):
        return abs(self.error()) < self.tolerance

    @staticmethod
    def extract(arr, make_abs=False):  # override this method to call ORTools instead of PuLP
        """
        Extract values fro the 1D array of LP variables
        :param arr: 1D array of LP variables
        :param make_abs: substitute the result by its abs value
        :return: 1D numpy array
        """

        if isinstance(arr, list):
            arr = np.array(arr)

        val = np.zeros(arr.shape)
        for i in range(val.shape[0]):
            if isinstance(arr[i], float) or isinstance(arr[i], int):
                val[i] = arr[i]
            else:
                val[i] = arr[i].solution_value()
        if make_abs:
            val = np.abs(val)

        return val

    def get_contingency_flows_list(self):
        """
        Square matrix of contingency flows (n branch, n contingency branch)
        :return:
        """

        x = np.zeros(len(self.contingency_flows_list))

        for i in range(len(self.contingency_flows_list)):
            try:
                x[i] = self.contingency_flows_list[i].solution_value() * self.numerical_circuit.Sbase
            except AttributeError:
                x[i] = float(self.contingency_flows_list[i]) * self.numerical_circuit.Sbase

        return x

    def get_contingency_flows_slacks_list(self):
        """
        Square matrix of contingency flows (n branch, n contingency branch)
        :return:
        """

        x = np.zeros(len(self.n1flow_f))

        for i in range(len(self.n1flow_f)):
            try:
                x[i] = self.contingency_flows_list[i].solution_value() * self.numerical_circuit.Sbase
            except AttributeError:
                x[i] = float(self.contingency_flows_slacks_list[i]) * self.numerical_circuit.Sbase

        return x

    def get_contingency_loading(self):
        """
        Square matrix of contingency flows (n branch, n contingency branch)
        :return:
        """

        x = np.zeros(len(self.n1flow_f))

        for i in range(len(self.n1flow_f)):
            try:
                x[i] = self.n1flow_f[i].solution_value() * self.numerical_circuit.Sbase / (self.rating[i] + 1e-20)
            except AttributeError:
                x[i] = float(self.n1flow_f[i]) * self.numerical_circuit.Sbase / (self.rating[i] + 1e-20)

        return x

    def get_power_injections(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.Pinj, make_abs=False) * self.numerical_circuit.Sbase

    def get_generator_delta(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        x = self.extract(self.Pg_delta, make_abs=False) * self.numerical_circuit.Sbase
        x[self.gen_a2_idx] *= -1  # this is so that the deltas in the receiving area appear negative in the final vector
        return x

    def get_generator_delta_slacks(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.generation_delta_slacks, make_abs=False) * self.numerical_circuit.Sbase

    def get_phase_angles(self):
        """
        Get the phase shift solution
        :return:
        """
        return self.extract(self.phase_shift, make_abs=False)

    def get_hvdc_flow(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.hvdc_flow, make_abs=False) * self.numerical_circuit.Sbase

    def get_hvdc_loading(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(
            self.hvdc_flow, make_abs=False
        ) * self.numerical_circuit.Sbase / self.numerical_circuit.hvdc_data.rate[:, 0]

    def get_hvdc_slacks(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.hvdc_slacks, make_abs=False) * self.numerical_circuit.Sbase

