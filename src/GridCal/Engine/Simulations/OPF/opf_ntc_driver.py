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
from GridCal.Engine.Simulations.OPF.ntc_opf import OpfNTC
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from GridCal.Engine.Core.snapshot_opf_data import compile_snapshot_opf_circuit
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.driver_template import DriverTemplate

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
                 mip_solver=MIPSolvers.CBC):
        """
        Optimal power flow options
        :param verbose:
        :param grouping:
        :param mip_solver:
        """
        self.verbose = verbose

        self.grouping = grouping

        self.mip_solver = mip_solver

        self.area_from_bus_idx = area_from_bus_idx

        self.area_to_bus_idx = area_to_bus_idx



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
                 Sf=None, overloads=None, loading=None, losses=None, converged=None, bus_types=None,
                 hvdc_flow=None, hvdc_slacks=None, hvdc_loading=None, node_slacks=None, phase_shift=None, generation_delta=None,
                 inter_area_branches=list(), inter_area_hvdc=list()):

        ResultsTemplate.__init__(self,
                                 name='OPF',
                                 available_results=[ResultTypes.BusVoltageModule,
                                                    ResultTypes.BusVoltageAngle,
                                                    ResultTypes.BranchPower,
                                                    ResultTypes.BranchLoading,
                                                    ResultTypes.BranchOverloads,
                                                    ResultTypes.LoadShedding,
                                                    ResultTypes.ControlledGeneratorShedding,
                                                    ResultTypes.ControlledGeneratorPower,
                                                    ResultTypes.BatteryPower,

                                                    ResultTypes.HvdcPowerFrom,
                                                    ResultTypes.HvdcOverloads,
                                                    ResultTypes.BranchTapAngle,
                                                    ResultTypes.GenerationDelta,
                                                    ResultTypes.InterAreaExchange],

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

        self.Sbus = Sbus

        self.voltage = voltage

        self.node_slacks = node_slacks

        self.load_shedding = load_shedding

        self.Sf = Sf

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

        self.plot_bars_limit = 100

    def apply_new_rates(self, nc: "SnapshotData"):
        rates = nc.Rates
        self.loading = self.Sf / (rates + 1e-9)

    def copy(self):
        """
        Return a copy of this
        @return:
        """
        return OptimalPowerFlowResults(bus_names=self.bus_names,
                                       branch_names=self.branch_names,
                                       load_names=self.load_names,
                                       generator_names=self.generator_names,
                                       battery_names=self.battery_names,
                                       Sbus=self.Sbus,
                                       voltage=self.voltage,
                                       load_shedding=self.load_shedding,
                                       Sf=self.Sf,
                                       overloads=self.overloads,
                                       loading=self.loading,
                                       generator_shedding=self.generator_shedding,
                                       battery_power=self.battery_power,
                                       controlled_generation_power=self.generator_power,
                                       converged=self.converged)

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

        elif result_type == ResultTypes.LoadShedding:
            labels = self.load_names
            y = self.load_shedding
            y_label = '(MW)'
            title = 'Load shedding'

        elif result_type == ResultTypes.ControlledGeneratorShedding:
            labels = self.generator_names
            y = self.generator_shedding
            y_label = '(MW)'
            title = 'Controlled generator shedding'

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
            title = result_type.value

        elif result_type == ResultTypes.HvdcOverloads:
            labels = self.hvdc_names
            y = self.hvdc_slacks
            y_label = '(MW)'
            title = result_type.value

        elif result_type == ResultTypes.BranchTapAngle:
            labels = self.branch_names
            y = self.phase_shift
            y_label = '(rad)'
            title = result_type.value

        elif result_type == ResultTypes.GenerationDelta:
            labels = self.generator_names
            y = self.generation_delta
            y_label = '(MW)'
            title = result_type.value

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
                           columns=[result_type.value[0]],
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

    def opf(self):
        """
        Run a power flow for every circuit
        @return: OptimalPowerFlowResults object
        """

        numerical_circuit = compile_snapshot_opf_circuit(circuit=self.grid,
                                                         apply_temperature=self.pf_options.apply_temperature_correction,
                                                         branch_tolerance_mode=self.pf_options.branch_impedance_tolerance_mode)

        # islands = numerical_circuit.split_into_islands(ignore_single_node_islands=True)
        # for island in islands:

        island = numerical_circuit

        problem = OpfNTC(island,
                         area_from_bus_idx=self.options.area_from_bus_idx,
                         area_to_bus_idx=self.options.area_to_bus_idx,
                         solver_type=self.options.mip_solver)
        # Solve
        problem.solve()

        # pack the results
        self.results = OptimalNetTransferCapacityResults(bus_names=island.bus_data.bus_names,
                                                         branch_names=island.branch_data.branch_names,
                                                         load_names=island.load_data.load_names,
                                                         generator_names=island.generator_data.generator_names,
                                                         battery_names=island.battery_data.battery_names,
                                                         hvdc_names=island.hvdc_data.names,
                                                         Sbus=problem.get_power_injections(),
                                                         voltage=problem.get_voltage(),
                                                         load_shedding=np.zeros((island.nload, 1)),
                                                         generator_shedding=np.zeros((island.ngen, 1)),
                                                         battery_power=np.zeros((island.nbatt, 1)),
                                                         controlled_generation_power=problem.get_generator_power(),
                                                         Sf=problem.get_branch_power(),
                                                         overloads=problem.get_overloads(),
                                                         loading=problem.get_loading(),
                                                         converged=bool(problem.converged()),
                                                         bus_types=island.bus_types,
                                                         hvdc_flow=problem.get_hvdc_flow(),
                                                         hvdc_loading=problem.get_hvdc_loading(),
                                                         hvdc_slacks=problem.get_hvdc_slacks(),
                                                         node_slacks=problem.get_node_slacks(),
                                                         phase_shift=problem.get_phase_angles(),
                                                         generation_delta=problem.get_generator_delta(),
                                                         inter_area_branches=problem.inter_area_branches,
                                                         inter_area_hvdc=problem.inter_area_hvdc
                                                         )

        return self.results

    def run(self):
        """

        :return:
        """
        start = time.time()
        self.opf()
        end = time.time()
        self.elapsed = end - start
        self.progress_text.emit('Done!')
        self.done_signal.emit()
