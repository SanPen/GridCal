# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.
from enum import Enum
import numpy as np
import time

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.basic_structures import TimeGrouping, MIPSolvers
from GridCal.Engine.Simulations.OPF.opf_results import OptimalPowerFlowResults
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.OPF.ntc_opf import OpfNTC, GenerationNtcFormulation
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from GridCal.Engine.Core.snapshot_opf_data import compile_snapshot_opf_circuit
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.driver_template import DriverTemplate
from GridCal.Engine.Simulations.LinearFactors.linear_analysis import LinearAnalysis
from GridCal.Engine.Simulations.ATC.available_transfer_capacity_driver import compute_alpha, AvailableTransferMode
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Simulations.results_template import ResultsTemplate

########################################################################################################################
# Optimal Power flow classes
########################################################################################################################


class OptimalNetTransferCapacityOptions:

    def __init__(self, area_from_bus_idx, area_to_bus_idx,
                 verbose=False,
                 grouping: TimeGrouping = TimeGrouping.NoGrouping,
                 mip_solver=MIPSolvers.CBC,
                 generation_formulation: GenerationNtcFormulation = GenerationNtcFormulation.Optimal,
                 monitor_only_sensitive_branches=False,
                 branch_sensitivity_threshold=0.01,
                 skip_generation_limits=False,
                 consider_contingencies=True,
                 maximize_exchange_flows=True,
                 tolerance=1e-2,
                 sensitivity_dT=100.0,
                 sensitivity_mode: AvailableTransferMode = AvailableTransferMode.InstalledPower,
                 weight_power_shift=1e0,
                 weight_generation_cost=1e-2,
                 weight_generation_delta=1e0,
                 weight_kirchoff=1e5,
                 weight_overloads=1e5,
                 weight_hvdc_control=1e0
                 ):
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
        :param weight_generation_delta:
        :param weight_kirchoff:
        :param weight_overloads:
        :param weight_hvdc_control:
        """
        self.verbose = verbose

        self.grouping = grouping

        self.mip_solver = mip_solver

        self.area_from_bus_idx = area_from_bus_idx

        self.area_to_bus_idx = area_to_bus_idx

        self.generation_formulation = generation_formulation

        self.monitor_only_sensitive_branches = monitor_only_sensitive_branches

        self.branch_sensitivity_threshold = branch_sensitivity_threshold

        self.skip_generation_limits = skip_generation_limits

        self.consider_contingencies = consider_contingencies

        self.maximize_exchange_flows = maximize_exchange_flows

        self.tolerance = tolerance

        self.sensitivity_dT = sensitivity_dT

        self.sensitivity_mode = sensitivity_mode

        self.weight_power_shift = weight_power_shift
        self.weight_generation_cost = weight_generation_cost
        self.weight_generation_delta = weight_generation_delta
        self.weight_kirchoff = weight_kirchoff
        self.weight_overloads = weight_overloads
        self.weight_hvdc_control = weight_hvdc_control


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

    def __init__(self, bus_names, branch_names, load_names, generator_names, battery_names, hvdc_names,
                 Sbus=None, voltage=None, load_shedding=None, generator_shedding=None,
                 battery_power=None, controlled_generation_power=None,
                 Sf=None, contingency_flows=None, contingency_loading=None,
                 overloads=None, loading=None, losses=None, converged=None, bus_types=None,
                 hvdc_flow=None, hvdc_slacks=None, hvdc_loading=None, node_slacks=None, phase_shift=None,
                 generation_delta=None, generation_delta_slacks=None,
                 inter_area_branches=list(), inter_area_hvdc=list(), alpha=None):

        ResultsTemplate.__init__(self,
                                 name='OPF',
                                 available_results=[ResultTypes.BusVoltageModule,
                                                    ResultTypes.BusVoltageAngle,
                                                    ResultTypes.BranchPower,
                                                    ResultTypes.BranchLoading,
                                                    ResultTypes.BranchOverloads,
                                                    ResultTypes.ContingencyFlows,
                                                    ResultTypes.ContingencyLoading,
                                                    ResultTypes.BranchTapAngle,
                                                    ResultTypes.HvdcPowerFrom,
                                                    ResultTypes.HvdcOverloads,
                                                    ResultTypes.NodeSlacks,
                                                    ResultTypes.BatteryPower,
                                                    ResultTypes.ControlledGeneratorPower,
                                                    ResultTypes.GenerationDelta,
                                                    ResultTypes.GenerationDeltaSlacks,
                                                    ResultTypes.AvailableTransferCapacityAlpha,
                                                    ResultTypes.InterAreaExchange
                                                    ],

                                 data_variables=['bus_names',
                                                 'branch_names',
                                                 'load_names',
                                                 'generator_names',
                                                 'battery_names',
                                                 'Sbus',
                                                 'voltage',
                                                 'load_shedding',
                                                 'generator_shedding',
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

        self.inter_area_branches = inter_area_branches

        self.inter_area_hvdc = inter_area_hvdc

        self.generation_delta = generation_delta

        self.generation_delta_slacks = generation_delta_slacks

        self.Sbus = Sbus

        self.voltage = voltage

        self.node_slacks = node_slacks

        self.load_shedding = load_shedding

        self.Sf = Sf

        self.contingency_flows = contingency_flows

        self.contingency_loading = contingency_loading

        self.hvdc_Pf = hvdc_flow
        self.hvdc_loading = hvdc_loading
        self.hvdc_slacks = hvdc_slacks

        self.phase_shift = phase_shift

        self.bus_types = bus_types

        self.overloads = overloads

        self.loading = loading

        self.losses = losses

        self.battery_power = battery_power

        self.generator_shedding = generator_shedding

        self.generator_power = controlled_generation_power

        self.converged = converged

        self.alpha = alpha

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

        self.load_shedding = np.zeros(n, dtype=float)

        self.Sf = np.zeros(m, dtype=complex)

        self.loading = np.zeros(m, dtype=complex)

        self.overloads = np.zeros(m, dtype=complex)

        self.losses = np.zeros(m, dtype=complex)

        self.converged = list()

        self.plot_bars_limit = 100

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

        elif result_type == ResultTypes.ContingencyFlows:
            labels = self.branch_names
            columns = labels
            y = np.abs(self.contingency_flows)
            y_label = '(MW)'
            title = result_type.value[0]

        elif result_type == ResultTypes.ContingencyLoading:
            labels = self.branch_names
            columns = labels
            y = np.abs(self.contingency_loading)
            y_label = '(%)'
            title = result_type.value[0]

        elif result_type == ResultTypes.BranchLosses:
            labels = self.branch_names
            y = self.losses.real
            y_label = '(MW)'
            title = 'Branch losses'

        elif result_type == ResultTypes.NodeSlacks:
            labels = self.bus_names
            y = self.node_slacks
            y_label = '(MW)'
            title = result_type.value[0]

        elif result_type == ResultTypes.GenerationDeltaSlacks:
            labels = self.generator_names
            y = self.generation_delta_slacks
            y_label = '(MW)'
            title = result_type.value[0]

        elif result_type == ResultTypes.ControlledGeneratorPower:
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

        elif result_type == ResultTypes.HvdcOverloads:
            labels = self.hvdc_names
            y = self.hvdc_slacks
            y_label = '(MW)'
            title = result_type.value[0]

        elif result_type == ResultTypes.AvailableTransferCapacityAlpha:
            labels = self.branch_names
            y = self.alpha
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

            y = np.array(y)
            labels = np.array(labels)
            y_label = '(MW)'
            title = result_type.value

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


class OptimalNetTransferCapacity(DriverTemplate):
    name = 'Optimal net transfer capacity'
    tpe = SimulationTypes.OPF_NTC_run

    def __init__(self, grid: MultiCircuit, options: OptimalNetTransferCapacityOptions, pf_options: PowerFlowOptions):
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

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return list()

    def compute_exchange_sensitivity(self, linear, numerical_circuit):

        # compute the branch exchange sensitivity (alpha)
        alpha = compute_alpha(ptdf=linear.PTDF,
                              P0=numerical_circuit.Sbus.real,
                              Pinstalled=numerical_circuit.bus_installed_power,
                              idx1=self.options.area_from_bus_idx,
                              idx2=self.options.area_to_bus_idx,
                              bus_types=numerical_circuit.bus_types.astype(np.int),
                              dT=self.options.sensitivity_dT,
                              mode=self.options.sensitivity_mode.value)

        return alpha

    def opf(self):
        """
        Run a power flow for every circuit
        @return: OptimalPowerFlowResults object
        """
        self.progress_text.emit('Compiling...')

        numerical_circuit = compile_snapshot_opf_circuit(circuit=self.grid,
                                                         apply_temperature=self.pf_options.apply_temperature_correction,
                                                         branch_tolerance_mode=self.pf_options.branch_impedance_tolerance_mode)

        self.progress_text.emit('Running linear analysis...')

        # declare the linear analysis
        linear = LinearAnalysis(grid=self.grid,
                                distributed_slack=False,
                                correct_values=False)
        linear.run()

        # sensitivities
        if self.options.monitor_only_sensitive_branches:
            alpha = self.compute_exchange_sensitivity(linear, numerical_circuit)
        else:
            alpha = np.ones(numerical_circuit.nbr)

        # islands = numerical_circuit.split_into_islands(ignore_single_node_islands=True)
        # for island in islands:

        self.progress_text.emit('Formulating NTC OPF...')

        # DDefine the problem
        problem = OpfNTC(numerical_circuit,
                         area_from_bus_idx=self.options.area_from_bus_idx,
                         area_to_bus_idx=self.options.area_to_bus_idx,
                         alpha=alpha,
                         LODF=linear.LODF,
                         solver_type=self.options.mip_solver,
                         generation_formulation=self.options.generation_formulation,
                         monitor_only_sensitive_branches=self.options.monitor_only_sensitive_branches,
                         branch_sensitivity_threshold=self.options.branch_sensitivity_threshold,
                         skip_generation_limits=self.options.skip_generation_limits,
                         consider_contingencies=self.options.consider_contingencies,
                         maximize_exchange_flows=self.options.maximize_exchange_flows,
                         tolerance=self.options.tolerance,
                         weight_power_shift=self.options.weight_power_shift,
                         weight_generation_cost=self.options.weight_generation_cost,
                         weight_generation_delta=self.options.weight_generation_delta,
                         weight_kirchoff=self.options.weight_kirchoff,
                         weight_overloads=self.options.weight_overloads,
                         weight_hvdc_control=self.options.weight_hvdc_control,
                         logger=self.logger
                         )
        # Solve
        self.progress_text.emit('Solving NTC OPF...')
        converged = problem.solve()
        err = problem.error()

        if not converged:
            self.logger.add_error('Did not converge', 'NTC OPF', str(err), self.options.tolerance)

        # pack the results
        self.results = OptimalNetTransferCapacityResults(bus_names=numerical_circuit.bus_data.bus_names,
                                                         branch_names=numerical_circuit.branch_data.branch_names,
                                                         load_names=numerical_circuit.load_data.load_names,
                                                         generator_names=numerical_circuit.generator_data.generator_names,
                                                         battery_names=numerical_circuit.battery_data.battery_names,
                                                         hvdc_names=numerical_circuit.hvdc_data.names,
                                                         Sbus=problem.get_power_injections(),
                                                         voltage=problem.get_voltage(),
                                                         load_shedding=np.zeros((numerical_circuit.nload, 1)),
                                                         generator_shedding=np.zeros((numerical_circuit.ngen, 1)),
                                                         battery_power=np.zeros((numerical_circuit.nbatt, 1)),
                                                         controlled_generation_power=problem.get_generator_power(),
                                                         Sf=problem.get_branch_power(),
                                                         contingency_flows=problem.get_contingency_flows(),
                                                         contingency_loading=problem.get_contingency_loading(),
                                                         overloads=problem.get_overloads(),
                                                         loading=problem.get_loading(),
                                                         converged=bool(converged),
                                                         bus_types=numerical_circuit.bus_types,
                                                         hvdc_flow=problem.get_hvdc_flow(),
                                                         hvdc_loading=problem.get_hvdc_loading(),
                                                         hvdc_slacks=problem.get_hvdc_slacks(),
                                                         node_slacks=problem.get_node_slacks(),
                                                         phase_shift=problem.get_phase_angles(),
                                                         generation_delta=problem.get_generator_delta(),
                                                         generation_delta_slacks=problem.get_generator_delta_slacks(),
                                                         inter_area_branches=problem.inter_area_branches,
                                                         inter_area_hvdc=problem.inter_area_hvdc,
                                                         alpha=alpha,
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
