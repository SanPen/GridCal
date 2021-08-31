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


class OptimalNetTransferCapacity(DriverTemplate):
    name = 'Optimal net power capacity'
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

        problem = OpfNTC(numerical_circuit,
                         area_from_bus_idx=self.options.area_from_bus_idx,
                         area_to_bus_idx=self.options.area_to_bus_idx,
                         solver_type=self.options.mip_solver)
        # Solve
        problem.solve()

        # get the branch Sf (it is used more than one time)
        Sbr = problem.get_branch_power()
        # ld = problem.get_load_shedding()
        # ld[ld == None] = 0
        # bt = problem.get_battery_power()
        # bt[bt == None] = 0
        gn = problem.get_generator_power()
        gn[gn == None] = 0

        Sbus = problem.get_power_injections()

        # pack the results
        self.results = OptimalPowerFlowResults(bus_names=numerical_circuit.bus_data.bus_names,
                                               branch_names=numerical_circuit.branch_data.branch_names,
                                               load_names=numerical_circuit.load_data.load_names,
                                               generator_names=numerical_circuit.generator_data.generator_names,
                                               battery_names=numerical_circuit.battery_data.battery_names,
                                               Sbus=Sbus,
                                               voltage=problem.get_voltage(),
                                               load_shedding=np.zeros((numerical_circuit.nload, 1)),
                                               generator_shedding=np.zeros_like(gn),
                                               battery_power=np.zeros((numerical_circuit.nbatt, 1)),
                                               controlled_generation_power=gn,
                                               Sf=Sbr,
                                               overloads=problem.get_overloads(),
                                               loading=problem.get_loading(),
                                               converged=bool(problem.converged()),
                                               bus_types=numerical_circuit.bus_types)

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
