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
from enum import Enum
import pandas as pd
import numpy as np
import time

from GridCal.Engine.basic_structures import TimeGrouping, MIPSolvers
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.OPF.ntc_opf import OpfNTC, GenerationNtcFormulation, get_inter_areas_branches
from GridCal.Engine.Core.snapshot_opf_data import compile_snapshot_opf_circuit
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.driver_template import DriverTemplate
from GridCal.Engine.Simulations.LinearFactors.linear_analysis import LinearAnalysis
from GridCal.Engine.Simulations.ATC.available_transfer_capacity_driver import compute_alpha, AvailableTransferMode
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.Simulations.ContingencyAnalysis.contingency_analysis_driver import ContingencyAnalysisDriver, ContingencyAnalysisOptions
# from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
# from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Devices.enumerations import TransformerControlType, HvdcControlType
from GridCal.Engine.basic_structures import SolverType
from GridCal.Engine.basic_structures import Logger

try:
    from ortools.linear_solver import pywraplp
except ModuleNotFoundError:
    print('ORTOOLS not found :(')

########################################################################################################################
# Optimal Power flow classes
########################################################################################################################


class OptimalNetTransferCapacityOptions:

    def __init__(self,
                 area_from_bus_idx,
                 area_to_bus_idx,
                 verbose=False,
                 grouping: TimeGrouping = TimeGrouping.NoGrouping,
                 mip_solver=MIPSolvers.CBC,
                 generation_formulation: GenerationNtcFormulation = GenerationNtcFormulation.Proportional,
                 monitor_only_sensitive_branches=True,
                 monitor_only_ntc_rule_branches=False,
                 branch_sensitivity_threshold=0.05,
                 skip_generation_limits=True,
                 perform_previous_checks=False,
                 dispatch_all_areas=False,
                 tolerance=1e-2,
                 sensitivity_dT=100.0,
                 sensitivity_mode: AvailableTransferMode = AvailableTransferMode.InstalledPower,
                 weight_power_shift=1e0,
                 weight_generation_cost=1e-2,
                 with_solution_checks=True,
                 time_limit_ms=1e4,
                 max_report_elements=0,
                 consider_contingencies=True,
                 consider_hvdc_contingencies=False,
                 consider_gen_contingencies=False,
                 generation_contingency_threshold=0,
                 match_gen_load=True,
                 trm=0,
                 ntc_load_rule=0,
                 n1_consideration=True):
        """

        :param area_from_bus_idx:
        :param area_to_bus_idx:
        :param verbose:
        :param grouping:
        :param mip_solver:
        :param generation_formulation:
        :param monitor_only_sensitive_branches:
        :param branch_sensitivity_threshold:
        :param skip_generation_limits:
        :param consider_contingencies:
        :param tolerance:
        :param sensitivity_dT:
        :param sensitivity_mode:
        :param weight_power_shift:
        :param weight_generation_cost:
        :param with_solution_checks:
        :param time_limit_ms:
        :param max_report_elements:
        :param generation_contingency_threshold:
        :param trm:
        :param ntc_load_rule:
        :param n1_consideration:
        """
        self.verbose = verbose

        self.grouping = grouping

        self.mip_solver = mip_solver

        self.area_from_bus_idx = area_from_bus_idx

        self.area_to_bus_idx = area_to_bus_idx

        self.generation_formulation = generation_formulation

        self.monitor_only_sensitive_branches = monitor_only_sensitive_branches
        self.monitor_only_ntc_load_rule_branches = monitor_only_ntc_rule_branches

        self.branch_sensitivity_threshold = branch_sensitivity_threshold

        self.skip_generation_limits = skip_generation_limits

        self.dispatch_all_areas = dispatch_all_areas

        self.tolerance = tolerance

        self.sensitivity_dT = sensitivity_dT

        self.sensitivity_mode = sensitivity_mode

        self.perform_previous_checks = perform_previous_checks

        self.weight_power_shift = weight_power_shift
        self.weight_generation_cost = weight_generation_cost

        self.consider_contingencies = consider_contingencies
        self.consider_hvdc_contingencies = consider_hvdc_contingencies
        self.consider_gen_contingencies = consider_gen_contingencies
        self.generation_contingency_threshold = generation_contingency_threshold

        self.with_solution_checks = with_solution_checks
        self.time_limit_ms = time_limit_ms
        self.max_report_elements = max_report_elements

        self.match_gen_load = match_gen_load

        self.trm = trm
        self.ntc_load_rule = ntc_load_rule
        self.n1_consideration = n1_consideration


class OptimalNetTransferCapacityResults(ResultsTemplate):
    """
    OPF results.

    Arguments:

        **Sbus**: bus power injections

        **voltage**: bus voltages

        **load_shedding**: load shedding values

        **Sf**: branch power values

        **overloads**: branch overloading values

        **loading**: branch loading values

        **losses**: branch losses

        **converged**: converged?
    """

    def __init__(self, bus_names, branch_names, load_names, generator_names, battery_names,
                 hvdc_names, trm, ntc_load_rule, branch_control_modes, hvdc_control_modes,
                 Sbus=None, voltage=None, battery_power=None, controlled_generation_power=None, Sf=None, loading=None,
                 losses=None, solved=None, bus_types=None, hvdc_flow=None, hvdc_loading=None, hvdc_angle_slack=None,
                 phase_shift=None, generation_delta=None, inter_area_branches=list(), inter_area_hvdc=list(),
                 alpha=None, alpha_n1=None, rates=None, monitor=None, contingency_branch_flows_list=None,
                 contingency_branch_indices_list=None, contingency_generation_flows_list=None,
                 contingency_generation_indices_list=None, contingency_hvdc_flows_list=None,
                 contingency_hvdc_indices_list=None, contingency_rates=None, branch_ntc_load_rule=None,
                 area_from_bus_idx=None, area_to_bus_idx=None, contingency_branch_alpha_list=None,
                 contingency_generation_alpha_list=None, contingency_hvdc_alpha_list=None, structural_ntc=None,
                 sbase=None):

        ResultsTemplate.__init__(self,
                                 name='OPF',
                                 available_results=[ResultTypes.BusVoltageModule,
                                                    ResultTypes.BusVoltageAngle,
                                                    ResultTypes.BranchPower,
                                                    ResultTypes.BranchLoading,
                                                    ResultTypes.BranchTapAngle,

                                                    ResultTypes.ContingencyFlowsReport,
                                                    ResultTypes.ContingencyFlowsBranchReport,
                                                    ResultTypes.ContingencyFlowsGenerationReport,
                                                    ResultTypes.ContingencyFlowsHvdcReport,

                                                    ResultTypes.HvdcPowerFrom,
                                                    ResultTypes.BatteryPower,
                                                    ResultTypes.GeneratorPower,
                                                    ResultTypes.GenerationDelta,

                                                    ResultTypes.AvailableTransferCapacityAlpha,
                                                    ResultTypes.AvailableTransferCapacityAlphaN1,

                                                    ResultTypes.InterAreaExchange],

                                 data_variables=['bus_names',
                                                 'branch_names',
                                                 'load_names',
                                                 'generator_names',
                                                 'battery_names',
                                                 'Sbus',
                                                 'voltage',
                                                 'Sf',
                                                 'bus_types',
                                                 'overloads',
                                                 'loading',
                                                 'battery_power',
                                                 'generator_power',
                                                 'converged'])

        self.bus_names = bus_names
        self.branch_names = branch_names
        self.load_names = load_names
        self.generator_names = generator_names
        self.battery_names = battery_names
        self.hvdc_names = hvdc_names

        self.trm = trm
        self.ntc_load_rule = ntc_load_rule

        self.hvdc_control_modes = hvdc_control_modes
        self.branch_control_modes = branch_control_modes

        self.inter_area_branches = inter_area_branches
        self.inter_area_hvdc = inter_area_hvdc

        self.area_from_bus_idx = area_from_bus_idx
        self.area_to_bus_idx = area_to_bus_idx

        self.generation_delta = generation_delta

        self.Sbus = Sbus

        self.voltage = voltage

        self.Sf = Sf

        self.hvdc_Pf = hvdc_flow
        self.hvdc_loading = hvdc_loading
        self.hvdc_angle_slack = hvdc_angle_slack

        self.phase_shift = phase_shift

        self.bus_types = bus_types

        self.loading = loading

        self.losses = losses

        self.battery_power = battery_power

        self.generator_power = controlled_generation_power

        self.solved = solved

        self.alpha = alpha
        self.alpha_n1 = alpha_n1

        self.monitor = monitor

        self.contingency_branch_flows_list = contingency_branch_flows_list
        self.contingency_branch_indices_list = contingency_branch_indices_list  # [(t, m, c), ...]
        self.contingency_branch_alpha_list = contingency_branch_alpha_list

        self.contingency_generation_flows_list = contingency_generation_flows_list
        self.contingency_generation_indices_list = contingency_generation_indices_list  # [(t, m, c), ...]
        self.contingency_generation_alpha_list = contingency_generation_alpha_list

        self.contingency_hvdc_flows_list = contingency_hvdc_flows_list
        self.contingency_hvdc_indices_list = contingency_hvdc_indices_list  # [(t, m, c), ...]
        self.contingency_hvdc_alpha_list = contingency_hvdc_alpha_list

        self.rates = rates
        self.contingency_rates = contingency_rates

        self.branch_ntc_load_rule = branch_ntc_load_rule

        self.structural_ntc = structural_ntc

        self.sbase = sbase

        self.plot_bars_limit = 100

    def apply_new_rates(self, nc: "SnapshotData"):
        rates = nc.Rates
        self.loading = self.Sf / (rates + 1e-9)

    def initialize(self, n, m):
        """
        Initialize the arrays
        @param n: number of buses
        @param m: number of branches
        @return:
        """
        self.Sbus = np.zeros(n, dtype=complex)

        self.voltage = np.zeros(n, dtype=complex)

        self.Sf = np.zeros(m, dtype=complex)

        self.loading = np.zeros(m, dtype=complex)

        self.losses = np.zeros(m, dtype=complex)

        self.converged = list()

        self.plot_bars_limit = 100

    def get_exchange_power(self):
        y = list()

        for (k, sign) in self.inter_area_branches:
            y.append([self.Sf[k] * sign])

        for (k, sign) in self.inter_area_hvdc:
            y.append([self.hvdc_Pf[k] * sign])

        return np.array(y).sum()

    def get_contingency_report(self, max_report_elements=0):

        l1, c1, y1 = self.get_contingency_branch_report()
        l2, c2, y2 = self.get_contingency_generation_report()
        l3, c3, y3 = self.get_contingency_hvdc_report()

        # group all contingency reports
        labels = l1 + l2 + l3
        columns = c1
        y = np.concatenate((y1, y2, y3), axis=0)

        if len(y.shape) == 2:
            # sort by column value
            sort_idx = columns.index('Contingency flow (%)')
            idx = np.flip(np.argsort(np.abs(y[:, sort_idx].astype(float))))
            y = y[idx, :]
            y = np.array(y, dtype=object)
        else:
            y = np.zeros((0, len(columns)), dtype=object)

        # curtail report
        if max_report_elements > 0:
            y = y[:max_report_elements, :]
            labels = labels[:max_report_elements]

        return labels, columns, y

    def get_base_report(self, max_report_elements=0):

        labels = self.branch_names
        y = list()

        trm = self.trm
        ttc = np.floor(self.get_exchange_power())
        ntc = ttc - trm

        monitor_idx = np.where(self.monitor)[0]
        for m in monitor_idx:
            maczt = ntc * np.abs(self.alpha[m]) / self.rates[m]
            y.append([np.round(ttc, 0),
                      trm,
                      np.round(ntc, 0),
                      np.round(maczt * 100, 2),
                      np.round(self.branch_ntc_load_rule[m], 2),
                      self.branch_names[m],
                      np.round(self.Sf[m].real, 2),
                      np.round(self.Sf[m] / self.rates[m] * 100, 2),
                      self.rates[m],
                      self.alpha[m]])

        y = np.array(y, dtype=object)
        columns = ['TTC',
                   'TRM',
                   'NTC',
                   'MACZT (%)',
                   'NTC Load Rule',
                   'Branch',
                   'Flow (MW)',
                   'Load (%)',
                   'Rate',
                   'Alpha']

        # Add inter area branches, shifter and hvdc data into report
        y, columns = self.add_inter_area_branches_data(y=y, columns=columns)
        y, columns = self.add_hvdc_data(y=y, columns=columns)
        y, columns = self.add_shifter_data(y=y, columns=columns)

        # sort by column value
        sort_idx = columns.index('Load (%)')
        idx = np.flip(np.argsort(np.abs(y[:, sort_idx].astype(float))))
        y = y[idx, :]

        # curtail report
        if max_report_elements > 0:
            y = y[:max_report_elements, :]
            labels = labels[:max_report_elements]

        return labels, columns, y

    def get_controled_shifters_as_pt(self):
        shifter_idx = np.where(self.branch_control_modes == TransformerControlType.Pt)
        shifter_names = self.branch_names[shifter_idx]

        return shifter_names, shifter_idx


    def get_contingency_branch_report(self, max_report_elements=0):
        labels = list()
        y = list()

        ttc = self.get_exchange_power()
        trm = self.trm
        ntc = ttc - trm

        for (m, c), contingency_flow, alpha_n1 in zip(self.contingency_branch_indices_list,
                                                      self.contingency_branch_flows_list,
                                                      self.contingency_branch_alpha_list):
            if contingency_flow != 0.0:
                maczt = ntc * np.abs(alpha_n1) / self.rates[m]
                y.append((np.round(ttc, 0),
                          trm,
                          np.round(ntc, 0),
                          np.round(maczt * 100, 2),
                          np.round(self.branch_ntc_load_rule[m], 2),
                          self.branch_names[m],
                          self.branch_names[c],
                          np.round(contingency_flow, 2),
                          np.round(self.Sf[m], 2),
                          self.contingency_rates[m],
                          self.rates[m],
                          np.round(contingency_flow / self.contingency_rates[m] * 100, 2),
                          np.round(self.Sf[m] / self.rates[m] * 100, 2),
                          self.alpha[m],
                          alpha_n1,
                          self.structural_ntc,
                          'Branch',
                          m, c))
                labels.append(len(y))

        columns = ['TTC',
                   'TRM',
                   'NTC',
                   'MACZT (%)',
                   'NTC Load Rule',
                   'Monitored',
                   'Contingency',
                   'Contingency flow (MW)',
                   'Base flow (MW)',
                   'Contingency rates (MW)',
                   'Base rates (MW)',
                   'Contingency flow (%)',
                   'Base flow (%)',
                   'Alpha N',
                   'Alpha N-1',
                   'Structural NTC',
                   'Contingency type',
                   'Monitored idx',
                   'Contingency idx',
                   ]

        y = np.array(y, dtype=object)

        # Add inter area branches, shifter and hvdc data into report
        y, columns = self.add_inter_area_branches_data(y=y, columns=columns)
        y, columns = self.add_hvdc_data(y=y, columns=columns)
        y, columns = self.add_shifter_data(y=y, columns=columns)

        if len(y.shape) == 2:
            # sort by column value
            sort_idx = columns.index('Contingency flow (%)')
            idx = np.flip(np.argsort(np.abs(y[:, sort_idx].astype(float))))
            y = y[idx, :]
            y = np.array(y, dtype=object)
        else:
            y = np.zeros((0, len(columns)), dtype=object)

        # curtail report
        if max_report_elements > 0:
            y = y[:max_report_elements, :]
            labels = labels[:max_report_elements]

        return labels, columns, y

    def get_contingency_generation_report(self, max_report_elements=0):
        labels = list()
        y = list()

        ttc = self.get_exchange_power()
        trm = self.trm
        ntc = ttc - trm

        for (m, c), contingency_flow, alpha_n1 in zip(self.contingency_generation_indices_list,
                                                      self.contingency_generation_flows_list,
                                                      self.contingency_generation_alpha_list):
            if contingency_flow != 0.0:
                maczt = ntc * np.abs(alpha_n1) / self.rates[m]
                y.append((np.round(ttc, 0),
                          trm,
                          np.round(ntc, 0),
                          np.round(maczt * 100, 2),
                          np.round(self.branch_ntc_load_rule[m], 2),
                          self.branch_names[m],
                          self.generator_names[c],
                          np.round(contingency_flow, 2),
                          np.round(self.Sf[m], 2),
                          self.contingency_rates[m],
                          self.rates[m],
                          np.round(contingency_flow / self.contingency_rates[m] * 100, 2),
                          np.round(self.Sf[m] / self.rates[m] * 100, 2),
                          self.alpha[m],
                          alpha_n1,
                          self.structural_ntc,
                          'Generation',
                          m, c))
                labels.append(len(y))

        columns = ['TTC',
                   'TRM',
                   'NTC',
                   'MACZT (%)',
                   'NTC Load Rule',
                   'Monitored',
                   'Contingency',
                   'Contingency flow (MW)',
                   'Base flow (MW)',
                   'Contingency rates (MW)',
                   'Base rates (MW)',
                   'Contingency flow (%)',
                   'Base flow (%)',
                   'Alpha N',
                   'Alpha N-1',
                   'Structural NTC',
                   'Contingency Type',
                   'Monitored idx',
                   'Contingency idx']

        y = np.array(y, dtype=object)

        # Add inter area branches, shifter and hvdc data into report
        y, columns = self.add_inter_area_branches_data(y=y, columns=columns)
        y, columns = self.add_hvdc_data(y=y, columns=columns)
        y, columns = self.add_shifter_data(y=y, columns=columns)

        if len(y.shape) == 2:
            # sort by column value
            sort_idx = columns.index('Contingency flow (%)')
            idx = np.flip(np.argsort(np.abs(y[:, sort_idx].astype(float))))
            y = y[idx, :]
            y = np.array(y, dtype=object)
        else:
            y = np.zeros((0, len(columns)), dtype=object)

        # curtail report
        if max_report_elements > 0:
            y = y[:max_report_elements, :]
            labels = labels[:max_report_elements]

        return labels, columns, y

    def get_contingency_hvdc_report(self, max_report_elements=0):
        labels = list()
        y = list()

        ttc = self.get_exchange_power()
        trm = self.trm
        ntc = ttc - trm

        for (m, c), contingency_flow, alpha_n1 in zip(self.contingency_hvdc_indices_list,
                                                      self.contingency_hvdc_flows_list,
                                                      self.contingency_hvdc_alpha_list):
            if contingency_flow != 0.0:
                maczt = ntc * np.abs(alpha_n1) / self.rates[m]
                y.append((np.round(ttc, 0),
                          trm,
                          np.round(ntc, 0),
                          np.round(maczt * 100, 2),
                          np.round(self.branch_ntc_load_rule[m], 2),
                          self.branch_names[m],
                          self.hvdc_names[c],
                          np.round(contingency_flow, 2),
                          np.round(self.Sf[m], 2),
                          self.contingency_rates[m],
                          self.rates[m],
                          np.round(contingency_flow / self.contingency_rates[m] * 100, 2),
                          np.round(self.Sf[m] / self.rates[m] * 100, 2),
                          self.alpha[m],
                          alpha_n1,
                          self.structural_ntc,
                          'Hvdc',
                          m, c))
                labels.append(len(y))

        columns = ['TTC',
                   'TRM',
                   'NTC',
                   'MACZT (%)',
                   'NTC Load Rule',
                   'Monitored',
                   'Contingency',
                   'Contingency flow (MW)',
                   'Base flow (MW)',
                   'Contingency rates (MW)',
                   'Base rates (MW)',
                   'Contingency flow (%)',
                   'Base flow (%)',
                   'Alpha N',
                   'Alpha N-1',
                   'Structural NTC',
                   'Contingency Type',
                   'Monitored idx',
                   'Contingency idx']

        y = np.array(y, dtype=object)

        # Add shifter and hvdc data into report
        y, columns = self.add_inter_area_branches_data(y=y, columns=columns)
        y, columns = self.add_hvdc_data(y=y, columns=columns)
        y, columns = self.add_shifter_data(y=y, columns=columns)

        if len(y.shape) == 2:
            # sort by column value
            sort_idx = columns.index('Contingency flow (%)')
            idx = np.flip(np.argsort(np.abs(y[:, sort_idx].astype(float))))
            y = y[idx, :]
            y = np.array(y, dtype=object)
        else:
            y = np.zeros((0, len(columns)), dtype=object)

        # curtail report
        if max_report_elements > 0:
            y = y[:max_report_elements, :]
            labels = labels[:max_report_elements]

        return labels, columns, y

    def add_inter_area_branches_data(self, y, columns):
        """
        Add inter area branches data into y, columns from report
        :param y:
        :param columns:
        :return:
        """
        inter_area_idx = [idx for (idx, name) in self.inter_area_branches]
        inter_area_names = self.branch_names[inter_area_idx]
        inter_area_data = np.array([self.Sf[inter_area_idx]] * y.shape[0])

        if len(y.shape) == 2:
            y = np.concatenate((y, inter_area_data), axis=1)

        columns = columns + [name for name in inter_area_names]

        return y, columns

    def add_shifter_data(self, y, columns):
        """
        Add shifter data into y, columns from report
        :param y:
        :param columns:
        :return:
        """

        shifter_names, shifter_idx = self.get_controled_shifters_as_pt()
        shifter_data = np.array([self.phase_shift[shifter_idx]] * y.shape[0])

        if len(y.shape) == 2:
            y = np.concatenate((y, shifter_data), axis=1)

        columns = columns + [name for name in shifter_names]

        return y, columns

    def add_hvdc_data(self, y, columns):
        """
        Add hvdc data into y, columns from report
        :param y:
        :param columns:
        :return:
        """

        hvdc_data = np.array([self.hvdc_Pf] * y.shape[0])
        hvdc_angles = np.array([self.hvdc_angle_slack] * y.shape[0])

        if len(y.shape) == 2:
            y = np.concatenate((y, hvdc_data, hvdc_angles), axis=1)

        columns = columns + [name for name in self.hvdc_names] + ['Slack angle ' + name for name in self.hvdc_names]

        return y, columns

    def make_report(self, path_out=None):
        """

         :param path_out:
         :return:
         """

        print('NTC is', self.get_exchange_power(), 'MW')

        labels, columns, data = self.get_contingency_report()

        df = pd.DataFrame(data=data, columns=columns, index=labels)

        # print result dataframe
        print('\n\n')
        print(df)

        # Save file
        if path_out:
            df.to_csv(path_out, index=False)

    def mdl(self, result_type) -> "ResultsTable":
        """
        Plot the results
        :param result_type: type of results (string)
        :return: DataFrame of the results (or None if the result was not understood)
        """

        columns = [result_type.value[0]]

        if result_type == ResultTypes.BusVoltageModule:
            labels = self.bus_names
            y = np.abs(self.voltage)
            y_label = '(p.u.)'
            title = 'Bus voltage module'

        elif result_type == ResultTypes.BusVoltageAngle:
            labels = self.bus_names
            y = np.angle(self.voltage)
            y_label = '(Radians)'
            title = 'Bus voltage angle'

        elif result_type == ResultTypes.BranchPower:
            labels = self.branch_names
            y = self.Sf.real
            y_label = '(MW)'
            title = 'Branch power'

        elif result_type == ResultTypes.BusPower:
            labels = self.bus_names
            y = self.Sbus.real
            y_label = '(MW)'
            title = 'Bus power'

        elif result_type == ResultTypes.BranchLoading:
            labels = self.branch_names
            y = self.loading * 100.0
            y_label = '(%)'
            title = 'Branch loading'

        elif result_type == ResultTypes.BranchOverloads:
            labels = self.branch_names
            y = np.abs(self.overloads)
            y_label = '(MW)'
            title = 'Branch overloads'

        elif result_type == ResultTypes.BranchLosses:
            labels = self.branch_names
            y = self.losses.real
            y_label = '(MW)'
            title = 'Branch losses'

        elif result_type == ResultTypes.BranchTapAngle:
            labels = self.branch_names
            y = np.rad2deg(self.phase_shift)
            y_label = '(deg)'
            title = result_type.value[0]

        # elif result_type == ResultTypes.BranchTapAngleRad:
        #    labels = self.branch_names
        #    y = self.phase_shift
        #    y_label = '(rad)'
        #    title = result_type.value[0]

        elif result_type == ResultTypes.GeneratorPower:
            labels = self.generator_names
            y = self.generator_power
            y_label = '(MW)'
            title = 'Controlled generators power'

        elif result_type == ResultTypes.BatteryPower:
            labels = self.battery_names
            y = self.battery_power
            y_label = '(MW)'
            title = 'Battery power'

        elif result_type == ResultTypes.HvdcPowerFrom:
            labels = self.hvdc_names
            y = self.hvdc_Pf
            y_label = '(MW)'
            title = result_type.value[0]

        # elif result_type == ResultTypes.HvdcPmode3Slack:
        #    labels = self.hvdc_names
        #    y = self.hvdc_angle_slack
        #    y_label = '(rad)'
        #    title = result_type.value[0]

        elif result_type == ResultTypes.AvailableTransferCapacityAlpha:
            labels = self.branch_names
            y = self.alpha
            y_label = '(p.u.)'
            title = result_type.value[0]

        elif result_type == ResultTypes.AvailableTransferCapacityAlphaN1:
            labels = self.branch_names
            y = self.alpha_n1
            y_label = '(p.u.)'
            title = result_type.value[0]

        elif result_type == ResultTypes.GenerationDelta:
            labels = self.generator_names
            y = self.generation_delta
            y_label = '(MW)'
            title = result_type.value[0]

        elif result_type == ResultTypes.InterAreaExchange:
            labels = list()
            y = list()

            for (k, sign) in self.inter_area_branches:
                labels.append(self.branch_names[k])
                y.append([self.Sf[k] * sign])

            for (k, sign) in self.inter_area_hvdc:
                labels.append(self.hvdc_names[k])
                y.append([self.hvdc_Pf[k] * sign])

            y.append([np.array(y).sum()])
            y = np.array(y)
            labels = np.array(labels + ['Total'])
            y_label = '(MW)'
            title = result_type.value[0]

        elif result_type == ResultTypes.ContingencyFlowsReport:
            labels, columns, y = self.get_contingency_report()
            y_label = ''
            title = result_type.value[0]

        elif result_type == ResultTypes.ContingencyFlowsBranchReport:
            labels, columns, y = self.get_contingency_branch_report()
            y_label = ''
            title = result_type.value[0]

        elif result_type == ResultTypes.ContingencyFlowsGenerationReport:
            labels, columns, y = self.get_contingency_generation_report()
            y_label = ''
            title = result_type.value[0]

        elif result_type == ResultTypes.ContingencyFlowsHvdcReport:
            labels, columns, y = self.get_contingency_hvdc_report()
            y_label = ''
            title = result_type.value[0]

        else:
            labels = []
            y = np.zeros(0)
            y_label = '(MW)'
            title = 'Battery power'

        mdl = ResultsTable(data=y,
                           index=labels,
                           columns=columns,
                           title=title,
                           ylabel=y_label,
                           xlabel='',
                           units=y_label)
        return mdl

class OptimalNetTransferCapacityDriver(DriverTemplate):
    name = 'Optimal net transfer capacity'
    tpe = SimulationTypes.OPF_NTC_run

    def __init__(self, grid: MultiCircuit, options: OptimalNetTransferCapacityOptions, pf_options: "PowerFlowOptions"):
        """
        PowerFlowDriver class constructor
        @param grid: MultiCircuit Object
        @param options: OPF options
        """
        DriverTemplate.__init__(self, grid=grid)

        # Options to use
        self.options = options
        self.pf_options = pf_options

        self.all_solved = True

        self.logger = Logger()

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return list()

    def compute_exchange_sensitivity(self, linear, numerical_circuit, with_n1=True):

        # compute the branch exchange sensitivity (alpha)
        alpha, alpha_n1 = compute_alpha(
            ptdf=linear.PTDF,
            lodf=linear.LODF,
            P0=numerical_circuit.Sbus.real,
            Pinstalled=numerical_circuit.installed_power,
            Pgen=numerical_circuit.generator_data.get_injections_per_bus()[:, 0].real,
            Pload=numerical_circuit.load_data.get_injections_per_bus()[:, 0].real,
            idx1=self.options.area_from_bus_idx,
            idx2=self.options.area_to_bus_idx,
            dT=self.options.sensitivity_dT,
            mode=self.options.sensitivity_mode.value,
            with_n1=with_n1)

        return alpha, alpha_n1

    def opf(self):
        """
        Run a power flow for every circuit
        @return: OptimalPowerFlowResults object
        """

        self.progress_text.emit('Compiling...')

        contingency_flows_list = list()
        contingency_indices_list = list()
        contingency_gen_flows_list = list()
        contingency_gen_indices_list = list()
        contingency_hvdc_flows_list = list()
        contingency_hvdc_indices_list = list()

        contingency_branch_alpha_list = list()
        contingency_generation_alpha_list = list()
        contingency_hvdc_alpha_list = list()

        numerical_circuit = compile_snapshot_opf_circuit(
            circuit=self.grid,
            apply_temperature=self.pf_options.apply_temperature_correction,
            branch_tolerance_mode=self.pf_options.branch_impedance_tolerance_mode)

        self.progress_text.emit('Running linear analysis...')

        # declare the linear analysis
        linear = LinearAnalysis(
            grid=self.grid,
            distributed_slack=False,
            correct_values=False)

        linear.run()

        # sensitivities
        if self.options.monitor_only_sensitive_branches:
            alpha, alpha_n1 = self.compute_exchange_sensitivity(
                linear=linear,
                numerical_circuit=numerical_circuit,
                with_n1=self.options.n1_consideration)
        else:
            alpha = np.ones(numerical_circuit.nbr)
            alpha_n1 = np.ones((numerical_circuit.nbr, numerical_circuit.nbr))

        base_problems = False
        if self.options.perform_previous_checks:

            # run dc power flow ----------------------------------------------------------------------------------------
            self.progress_text.emit('Pre-solving base state (DC power flow)...')
            from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver, PowerFlowOptions
            pf_options = PowerFlowOptions(solver_type=SolverType.DC)
            pf_drv = PowerFlowDriver(grid=self.grid, options=pf_options)
            pf_drv.run()
            indices = np.where(np.abs(pf_drv.results.loading.real) >= 1.0)
            for m in zip(indices[0]):
                if numerical_circuit.branch_data.monitor_loading[m] and \
                   alpha[m] >= self.options.branch_sensitivity_threshold:

                    elm_name = '{0}'.format(numerical_circuit.branch_names[m])

                    self.logger.add_error('Base overload', elm_name, pf_drv.results.loading[m].real * 100, 100)
                    base_problems = True

            # run contingency analysis ---------------------------------------------------------------------------------
            if self.options.consider_contingencies:
                self.progress_text.emit('Pre-solving base state (Contingency analysis)...')
                options = ContingencyAnalysisOptions(
                    distributed_slack=False,
                    use_provided_flows=True,
                    Pf=pf_drv.results.Sf.real)
                cnt_drv = ContingencyAnalysisDriver(grid=self.grid, options=options)
                cnt_drv.run()
                indices = np.where(np.abs(cnt_drv.results.loading.real) >= 1.0)

                for m, c in zip(indices[0], indices[1]):
                    if numerical_circuit.branch_data.monitor_loading[m] and \
                       numerical_circuit.branch_data.contingency_enabled[c] and \
                       alpha[m] >= self.options.branch_sensitivity_threshold:

                        elm_name = '{0} @ {1}'.format(
                            numerical_circuit.branch_names[m],
                            numerical_circuit.branch_names[c])

                        self.logger.add_error(
                            'Base contingency overload',
                            elm_name, cnt_drv.results.loading[m, c].real * 100,
                            100)

                        contingency_flows_list.append(cnt_drv.results.Sf[m, c].real)
                        contingency_indices_list.append((m, c))
                        contingency_branch_alpha_list.append(alpha_n1[m, c])
                        base_problems = True
        else:
            pass

        if base_problems:

            # get the inter-area branches and their sign
            inter_area_branches = get_inter_areas_branches(
                nbr=numerical_circuit.nbr,
                F=numerical_circuit.branch_data.F,
                T=numerical_circuit.branch_data.T,
                buses_areas_1=self.options.area_from_bus_idx,
                buses_areas_2=self.options.area_to_bus_idx)

            inter_area_hvdc = get_inter_areas_branches(
                nbr=numerical_circuit.nhvdc,
                F=numerical_circuit.hvdc_data.get_bus_indices_f(),
                T=numerical_circuit.hvdc_data.get_bus_indices_t(),
                buses_areas_1=self.options.area_from_bus_idx,
                buses_areas_2=self.options.area_to_bus_idx)

            # pack the results
            self.results = OptimalNetTransferCapacityResults(
                bus_names=numerical_circuit.bus_data.names,
                branch_names=numerical_circuit.branch_data.names,
                load_names=numerical_circuit.load_data.names,
                generator_names=numerical_circuit.generator_data.names,
                battery_names=numerical_circuit.battery_data.names,
                hvdc_names=numerical_circuit.hvdc_data.names,
                trm=self.trm,
                ntc_load_rule=self.ntc_load_rule,
                Sbus=numerical_circuit.Sbus.real,
                voltage=pf_drv.results.voltage,
                battery_power=np.zeros((numerical_circuit.nbatt, 1)),
                controlled_generation_power=numerical_circuit.generator_data.p,
                Sf=pf_drv.results.Sf.real,
                loading=pf_drv.results.loading.real,
                solved=False,
                bus_types=numerical_circuit.bus_types,
                hvdc_flow=pf_drv.results.hvdc_Pt,
                hvdc_loading=pf_drv.results.hvdc_loading,
                phase_shift=pf_drv.results.theta,
                generation_delta=np.zeros(numerical_circuit.ngen),
                inter_area_branches=inter_area_branches,
                inter_area_hvdc=inter_area_hvdc,
                alpha=alpha,
                contingency_branch_flows_list=contingency_flows_list,
                contingency_branch_indices_list=contingency_indices_list,
                contingency_branch_alpha_list=contingency_branch_alpha_list,
                contingency_generation_flows_list=contingency_gen_flows_list,
                contingency_generation_indices_list=contingency_gen_indices_list,
                contingency_generation_alpha_list=list(),
                contingency_hvdc_flows_list=contingency_hvdc_flows_list,
                contingency_hvdc_indices_list=contingency_hvdc_indices_list,
                contingency_hvdc_alpha_list=list(),
                rates=numerical_circuit.branch_data.rates[:, 0],
                contingency_rates=numerical_circuit.branch_data.contingency_rates[:, 0],
                area_from_bus_idx=self.options.area_from_bus_idx,
                area_to_bus_idx=self.options.area_to_bus_idx
            )
        else:
            self.progress_text.emit('Formulating NTC OPF...')

            # Define the problem
            problem = OpfNTC(
                numerical_circuit=numerical_circuit,
                area_from_bus_idx=self.options.area_from_bus_idx,
                area_to_bus_idx=self.options.area_to_bus_idx,
                alpha=alpha,
                alpha_n1=alpha_n1,
                LODF=linear.LODF,
                PTDF=linear.PTDF,
                solver_type=self.options.mip_solver,
                generation_formulation=self.options.generation_formulation,
                monitor_only_sensitive_branches=self.options.monitor_only_sensitive_branches,
                monitor_only_ntc_load_rule_branches=self.options.monitor_only_ntc_load_rule_branches,
                branch_sensitivity_threshold=self.options.branch_sensitivity_threshold,
                skip_generation_limits=self.options.skip_generation_limits,
                dispatch_all_areas=self.options.dispatch_all_areas,
                tolerance=self.options.tolerance,
                weight_power_shift=self.options.weight_power_shift,
                weight_generation_cost=self.options.weight_generation_cost,
                consider_contingencies=self.options.consider_contingencies,
                consider_hvdc_contingencies=self.options.consider_hvdc_contingencies,
                consider_gen_contingencies=self.options.consider_gen_contingencies,
                generation_contingency_threshold=self.options.generation_contingency_threshold,
                match_gen_load=self.options.match_gen_load,
                ntc_load_rule=self.options.ntc_load_rule,
                logger=self.logger)

            # Solve
            self.progress_text.emit('Solving NTC OPF...')
            problem.formulate()
            solved = problem.solve(
                with_solution_checks=self.options.with_solution_checks,
                time_limit_ms=self.options.time_limit_ms)

            err = problem.error()

            if not solved:

                if problem.status == pywraplp.Solver.FEASIBLE:
                    self.logger.add_error(
                        'Feasible solution, not optimal',
                        'NTC OPF',
                        str(err),
                        self.options.tolerance)

                if problem.status == pywraplp.Solver.INFEASIBLE:
                    self.logger.add_error(
                        'Unfeasible solution',
                        'NTC OPF',
                        str(err),
                        self.options.tolerance)

                if problem.status == pywraplp.Solver.UNBOUNDED:
                    self.logger.add_error(
                        'Proved unbounded',
                        'NTC OPF',
                        str(err),
                        self.options.tolerance)

                if problem.status == pywraplp.Solver.ABNORMAL:
                    self.logger.add_error(
                        'Abnormal solution, some error happens',
                        'NTC OPF',
                        str(err),
                        self.options.tolerance)

                if problem.status == pywraplp.Solver.NOT_SOLVED:
                    self.logger.add_error(
                        'Not solved, maybe timeout occurs',
                        'NTC OPF',
                        str(err),
                        self.options.tolerance)

            self.logger += problem.logger

            # pack the results
            self.results = OptimalNetTransferCapacityResults(
                bus_names=numerical_circuit.bus_data.names,
                branch_names=numerical_circuit.branch_data.names,
                load_names=numerical_circuit.load_data.names,
                generator_names=numerical_circuit.generator_data.names,
                battery_names=numerical_circuit.battery_data.names,
                hvdc_names=numerical_circuit.hvdc_data.names,
                trm=self.options.trm,
                ntc_load_rule=self.options.ntc_load_rule,
                branch_control_modes=numerical_circuit.branch_data.control_mode,
                hvdc_control_modes=numerical_circuit.hvdc_data.control_mode,
                Sbus=problem.get_power_injections(),
                voltage=problem.get_voltage(),
                battery_power=np.zeros((numerical_circuit.nbatt, 1)),
                controlled_generation_power=problem.get_generator_power(),
                Sf=problem.get_branch_power_from(),
                loading=problem.get_loading(),
                solved=bool(solved),
                bus_types=numerical_circuit.bus_types,
                hvdc_flow=problem.get_hvdc_flow(),
                hvdc_loading=problem.get_hvdc_loading(),
                phase_shift=problem.get_phase_angles(),
                generation_delta=problem.get_generator_delta(),
                hvdc_angle_slack=problem.get_hvdc_angle_slacks(),
                inter_area_branches=problem.inter_area_branches,
                inter_area_hvdc=problem.inter_area_hvdc,
                alpha=alpha,
                monitor=problem.monitor,
                contingency_branch_flows_list=problem.get_contingency_flows_list(),
                contingency_branch_indices_list=problem.contingency_indices_list,
                contingency_branch_alpha_list=problem.contingency_branch_alpha_list,
                contingency_generation_flows_list=problem.get_contingency_gen_flows_list(),
                contingency_generation_indices_list=problem.contingency_gen_indices_list,
                contingency_generation_alpha_list=problem.contingency_generation_alpha_list,
                contingency_hvdc_flows_list=problem.get_contingency_hvdc_flows_list(),
                contingency_hvdc_indices_list=problem.contingency_hvdc_indices_list,
                contingency_hvdc_alpha_list=problem.contingency_hvdc_alpha_list,
                branch_ntc_load_rule=problem.get_branch_ntc_load_rule(),
                rates=numerical_circuit.branch_data.rates[:, 0],
                contingency_rates=numerical_circuit.branch_data.contingency_rates[:, 0],
                area_from_bus_idx=self.options.area_from_bus_idx,
                area_to_bus_idx=self.options.area_to_bus_idx,
                structural_ntc=problem.structural_ntc,
                sbase=numerical_circuit.Sbase
            )

        self.progress_text.emit('Done!')

        return self.results

    def run(self):
        """

        :return:
        """
        start = time.time()
        self.opf()
        end = time.time()
        self.elapsed = end - start


if __name__ == '__main__':

    import GridCal.Engine.basic_structures as bs
    import GridCal.Engine.Devices as dev
    from GridCal.Engine.Simulations.ATC.available_transfer_capacity_driver import AvailableTransferMode
    from GridCal.Engine import FileOpen, LinearAnalysis

    folder = r'\\mornt4\DESRED\DPE-Planificacion\Plan 2021_2026\_0_TRABAJO\5_Plexos_PSSE\Peninsula\_2026_TRABAJO\Vesiones con alegaciones\Anexo II\TYNDP 2022\5GW\Con N-x\merged\GridCal'
    fname = folder + r'\ES-PTv2--FR v4_ts_5k_PMODE1.gridcal'
    path_out = folder + r'\ES-PTv2--FR v4_ts_5k_PMODE1.csv'

    circuit = FileOpen(fname).open()

    areas_from_idx = [0]
    areas_to_idx = [1]

    areas_from = [circuit.areas[i] for i in areas_from_idx]
    areas_to = [circuit.areas[i] for i in areas_to_idx]

    compatible_areas = True
    for a1 in areas_from:
        if a1 in areas_to:
            compatible_areas = False
            print("The area from '{0}' is in the list of areas to. This cannot be.".format(a1.name),
                  'Incompatible areas')

    for a2 in areas_to:
        if a2 in areas_from:
            compatible_areas = False
            print("The area to '{0}' is in the list of areas from. This cannot be.".format(a2.name),
                  'Incompatible areas')

    lst_from = circuit.get_areas_buses(areas_from)
    lst_to = circuit.get_areas_buses(areas_to)
    lst_br = circuit.get_inter_areas_branches(areas_from, areas_to)
    lst_br_hvdc = circuit.get_inter_areas_hvdc_branches(areas_from, areas_to)

    idx_from = np.array([i for i, bus in lst_from])
    idx_to = np.array([i for i, bus in lst_to])
    idx_br = np.array([i for i, bus, sense in lst_br])
    sense_br = np.array([sense for i, bus, sense in lst_br])
    idx_hvdc_br = np.array([i for i, bus, sense in lst_br_hvdc])
    sense_hvdc_br = np.array([sense for i, bus, sense in lst_br_hvdc])

    if len(idx_from) == 0:
        print('The area "from" has no buses!')

    if len(idx_to) == 0:
        print('The area "to" has no buses!')

    if len(idx_br) == 0:
        print('There are no inter-area branches!')


    options = OptimalNetTransferCapacityOptions(
        area_from_bus_idx=idx_from,
        area_to_bus_idx=idx_to,
        mip_solver=bs.MIPSolvers.CBC,
        generation_formulation=dev.GenerationNtcFormulation.Proportional,
        monitor_only_sensitive_branches=True,
        branch_sensitivity_threshold=0.05,
        skip_generation_limits=True,
        consider_contingencies=True,
        consider_gen_contingencies=True,
        consider_hvdc_contingencies=True,
        dispatch_all_areas=False,
        generation_contingency_threshold=1000,
        tolerance=1e-2,
        sensitivity_dT=100.0,
        sensitivity_mode=AvailableTransferMode.InstalledPower,
        # todo: checkear si queremos el ptdf por potencia generada
        perform_previous_checks=False,
        weight_power_shift=1e5,
        weight_generation_cost=1e2,
        with_solution_checks=False,
        time_limit_ms=1e4,
        max_report_elements=5)

    print('Running optimal net transfer capacity...')


    # set optimal net transfer capacity driver instance
    circuit.set_state(t=1)
    driver = OptimalNetTransferCapacityDriver(
        grid=circuit,
        options=options,
        pf_options=PowerFlowOptions(solver_type=SolverType.DC))
    driver.run()

    driver.results.make_report(path_out=path_out)
    # driver.results.make_report()

