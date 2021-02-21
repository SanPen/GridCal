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
from PySide2.QtCore import QThread, Signal

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.basic_structures import TimeGrouping, MIPSolvers
from GridCal.Engine.Simulations.OPF.opf_results import OptimalPowerFlowResults
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.OPF.ac_opf import OpfAc
from GridCal.Engine.Simulations.OPF.dc_opf import OpfDc
from GridCal.Engine.Simulations.OPF.simple_dispatch import OpfSimple
from GridCal.Engine.basic_structures import SolverType
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from GridCal.Engine.Core.snapshot_opf_data import compile_snapshot_opf_circuit

########################################################################################################################
# Optimal Power flow classes
########################################################################################################################


class OptimalPowerFlowOptions:

    def __init__(self, verbose=False,
                 solver: SolverType = SolverType.DC_OPF,
                 grouping: TimeGrouping = TimeGrouping.NoGrouping,
                 mip_solver=MIPSolvers.CBC,
                 faster_less_accurate=False,
                 power_flow_options=None, bus_types=None):
        """
        Optimal power flow options
        :param verbose:
        :param solver: OPF solver type
        :param grouping:
        :param mip_solver:
        :param faster_less_accurate:
        :param power_flow_options:
        :param bus_types:
        """
        self.verbose = verbose

        self.solver = solver

        self.grouping = grouping

        self.mip_solver = mip_solver

        self.faster_less_accurate = faster_less_accurate

        self.power_flow_options = power_flow_options

        self.bus_types = bus_types


class OptimalPowerFlow(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    name = 'Optimal power flow'

    def __init__(self, grid: MultiCircuit, options: OptimalPowerFlowOptions, pf_options: PowerFlowOptions):
        """
        PowerFlowDriver class constructor
        @param grid: MultiCircuit Object
        @param options: OPF options
        """
        QThread.__init__(self)

        # Grid to run a power flow in
        self.grid = grid

        # Options to use
        self.options = options

        self.pf_options = pf_options

        # OPF results
        self.results = None

        # set cancel state
        self.__cancel__ = False

        self.all_solved = True

        self.elapsed = 0.0

        self.logger = Logger()

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

        if self.options.solver == SolverType.DC_OPF:
            # DC optimal power flow
            problem = OpfDc(numerical_circuit=numerical_circuit, solver=self.options.mip_solver)

        elif self.options.solver == SolverType.AC_OPF:
            # AC optimal power flow
            problem = OpfAc(numerical_circuit=numerical_circuit, solver=self.options.mip_solver)

        elif self.options.solver == SolverType.Simple_OPF:
            # simplistic dispatch
            problem = OpfSimple(numerical_circuit=numerical_circuit)

        else:
            raise Exception('Solver not recognized ' + str(self.options.solver))

        # Solve
        problem.solve()

        # get the branch flows (it is used more than one time)
        Sbr = problem.get_branch_power()
        ld = problem.get_load_shedding()
        ld[ld == None] = 0
        bt = problem.get_battery_power()
        bt[bt == None] = 0
        gn = problem.get_generator_power()
        gn[gn == None] = 0

        # pack the results
        self.results = OptimalPowerFlowResults(bus_names=numerical_circuit.bus_data.bus_names,
                                               branch_names=numerical_circuit.branch_data.branch_names,
                                               load_names=numerical_circuit.load_data.load_names,
                                               generator_names=numerical_circuit.generator_data.generator_names,
                                               battery_names=numerical_circuit.battery_data.battery_names,
                                               Sbus=None,
                                               voltage=problem.get_voltage(),
                                               load_shedding=ld,
                                               generation_shedding=np.zeros_like(gn),
                                               battery_power=bt,
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

    def cancel(self):
        self.__cancel__ = True

