# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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

import numpy as np
from typing import Union, List
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.basic_structures import CxVec
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults, PowerFlowOptions
from GridCalEngine.Simulations.ShortCircuitStudies.short_circuit_worker import (short_circuit_ph3,
                                                                                short_circuit_unbalanced)
from GridCalEngine.Simulations.ShortCircuitStudies.short_circuit_results import ShortCircuitResults
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Devices import Line, Bus
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Simulations.ShortCircuitStudies.short_circuit_options import ShortCircuitOptions
from GridCalEngine.enumerations import FaultType, SimulationTypes
from GridCalEngine.Devices.types import BRANCH_TYPES


class ShortCircuitDriver(DriverTemplate):
    name = 'Short Circuit'
    tpe = SimulationTypes.ShortCircuit_run

    def __init__(self, grid: MultiCircuit,
                 options: ShortCircuitOptions,
                 pf_options: PowerFlowOptions,
                 pf_results: PowerFlowResults,
                 opf_results=None):
        """
        ShortCircuitDriver class constructor
        :param grid: MultiCircuit Object
        :param options: ShortCircuitOptions
        :param pf_options: PowerFlowOptions
        :param pf_results: PowerFlowResults
        :param opf_results: OptimalPowerFlowResults
        """
        DriverTemplate.__init__(self, grid=grid)

        # power flow results
        self.pf_results = pf_results

        self.pf_options = pf_options

        self.opf_results = opf_results

        # Options to use
        self.options = options

        # declare an empty results object
        self.results: ShortCircuitResults = ShortCircuitResults(n=0,
                                                                m=0,
                                                                n_hvdc=0,
                                                                bus_names=np.empty(0),
                                                                branch_names=np.empty(0),
                                                                hvdc_names=np.empty(0),
                                                                bus_types=np.empty(0),
                                                                area_names=None)

        self.logger = Logger()

        self.__cancel__ = False

        self._is_running = False

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return list()

    @staticmethod
    def compile_zf(grid: MultiCircuit):
        """
        Compose the fault impedance
        :param grid: MultiCircuit instance
        :return:
        """
        # compile the buses short circuit impedance array
        n = len(grid.buses)
        Zf = np.zeros(n, dtype=complex)
        for i in range(n):
            Zf[i] = grid.buses[i].get_fault_impedance()

        return Zf

    @staticmethod
    def split_branch(branch: BRANCH_TYPES, fault_position: float, r_fault: float, x_fault: float):
        """
        Split a branch by a given distance
        :param branch: Branch of a circuit
        :param fault_position: per unit distance measured from the "from" bus (0 ~ 1)
        :param r_fault: Fault resistance in p.u.
        :param x_fault: Fault reactance in p.u.
        :return: the two new Branches and the mid short circuited bus
        """

        assert (0.0 < fault_position < 1.0)

        r = branch.R
        x = branch.X
        g = branch.G
        b = branch.B

        # deactivate the current branch
        branch.active = False

        # Each of the Branches will have the proportional impedance
        # Bus_from           Middle_bus            Bus_To
        # o----------------------o--------------------o
        #   >-------- x -------->|
        #   (x: distance measured in per unit (0~1)

        middle_bus = Bus()

        # set the bus fault impedance
        middle_bus.Zf = complex(r_fault, x_fault)

        br1 = Line(bus_from=branch.bus_from,
                   bus_to=middle_bus,
                   r=r * fault_position,
                   x=x * fault_position,
                   b=b * fault_position)

        br2 = Line(bus_from=middle_bus,
                   bus_to=branch.bus_to,
                   r=r * (1 - fault_position),
                   x=x * (1 - fault_position),
                   b=b * (1 - fault_position))

        return br1, br2, middle_bus

    @staticmethod
    def single_short_circuit(calculation_inputs: NumericalCircuit,
                             Vpf: CxVec,
                             Zf: complex,
                             island_bus_index: int,
                             fault_type: FaultType) -> ShortCircuitResults:
        """
        Run a short circuit simulation for a single island
        :param calculation_inputs:
        :param Vpf: Power flow voltage vector applicable to the island
        :param Zf: Short circuit impedance vector applicable to the island
        :param island_bus_index: bus index where the fault happens
        :param fault_type: FaultType
        @return: short circuit results
        """
        # compute Zbus
        # is dense, so no need to store it as sparse
        if calculation_inputs.Ybus.shape[0] > 1:
            if fault_type == FaultType.ph3:
                return short_circuit_ph3(calculation_inputs=calculation_inputs,
                                         Vpf=Vpf[calculation_inputs.original_bus_idx],
                                         Zf=Zf,
                                         bus_index=island_bus_index)

            elif fault_type in [FaultType.LG, FaultType.LL, FaultType.LLG]:
                return short_circuit_unbalanced(calculation_inputs=calculation_inputs,
                                                Vpf=Vpf[calculation_inputs.original_bus_idx],
                                                Zf=Zf,
                                                bus_index=island_bus_index,
                                                fault_type=fault_type)

            else:
                raise Exception('Unknown fault type!')

        # if we get here, no short circuit was done, so declare empty results and exit --------------------------------
        nbus = calculation_inputs.Ybus.shape[0]
        nbr = calculation_inputs.nbr

        # voltage, Sf, loading, losses, error, converged, Qpv
        results = ShortCircuitResults(n=calculation_inputs.nbus,
                                      m=calculation_inputs.nbr,
                                      n_hvdc=calculation_inputs.nhvdc,
                                      bus_names=calculation_inputs.bus_names,
                                      branch_names=calculation_inputs.branch_names,
                                      hvdc_names=calculation_inputs.hvdc_names,
                                      bus_types=calculation_inputs.bus_types,
                                      area_names=None)

        results.Sbus = calculation_inputs.Sbus
        results.voltage = np.zeros(nbus, dtype=complex)
        results.Sf = np.zeros(nbr, dtype=complex)
        results.If = np.zeros(nbr, dtype=complex)
        results.losses = np.zeros(nbr, dtype=complex)
        results.SCpower = np.zeros(nbus, dtype=complex)

        return results

    def run(self):
        """
        Run a power flow for every circuit
        @return:
        """
        self.tic()
        self._is_running = True
        if self.options.mid_line_fault:

            # if there are branch indices where to perform short circuits, modify the grid accordingly

            grid = self.grid.copy()

            sc_bus_index = list()

            # modify the grid by inserting a mid-line short circuit bus
            branch = self.grid.get_branches_wo_hvdc()[self.options.branch_index]
            br1, br2, middle_bus = self.split_branch(branch=branch,
                                                     fault_position=self.options.branch_fault_locations,
                                                     r_fault=self.options.branch_fault_r,
                                                     x_fault=self.options.branch_fault_x)

            grid.add_line(br1)
            grid.add_line(br2)
            grid.add_bus(middle_bus)
            sc_bus_index.append(len(grid.buses) - 1)

        else:
            grid = self.grid

        # Compile the grid
        numerical_circuit = compile_numerical_circuit_at(circuit=grid,
                                                         t_idx=None,
                                                         apply_temperature=self.pf_options.apply_temperature_correction,
                                                         branch_tolerance_mode=self.pf_options.branch_impedance_tolerance_mode,
                                                         opf_results=self.opf_results,
                                                         logger=self.logger)

        calculation_inputs = numerical_circuit.split_into_islands(
            ignore_single_node_islands=self.pf_options.ignore_single_node_islands)

        results = ShortCircuitResults(n=numerical_circuit.nbus,
                                      m=numerical_circuit.nbr,
                                      n_hvdc=numerical_circuit.nhvdc,
                                      bus_names=numerical_circuit.bus_names,
                                      branch_names=numerical_circuit.branch_names,
                                      hvdc_names=numerical_circuit.hvdc_names,
                                      bus_types=numerical_circuit.bus_types)

        results.bus_types = numerical_circuit.bus_types

        Zf = self.compile_zf(grid)

        if len(calculation_inputs) > 1:  # multi-island

            for i, island in enumerate(calculation_inputs):

                # the options give the bus index counting all the grid, however
                # for the calculation we need the bus index in the island scheme.
                # Hence, we need to convert it, and if the global bus index is not
                # in the island, do not perform any calculation
                reverse_bus_index = {b: i for i, b in enumerate(island.bus_data.original_idx)}

                island_bus_index = reverse_bus_index.get(self.options.bus_index, None)

                if island_bus_index is not None:
                    res = self.single_short_circuit(calculation_inputs=island,
                                                    Vpf=self.pf_results.voltage[island.bus_data.original_idx],
                                                    Zf=Zf[island.bus_data.original_idx],
                                                    island_bus_index=island_bus_index,
                                                    fault_type=self.options.fault_type)

                    # merge results
                    results.apply_from_island(res, island.bus_data.original_idx, island.branch_data.original_idx)

        else:  # single island

            res = self.single_short_circuit(calculation_inputs=calculation_inputs[0],
                                            Vpf=self.pf_results.voltage,
                                            Zf=Zf,
                                            island_bus_index=self.options.bus_index,
                                            fault_type=self.options.fault_type)

            # merge results
            results.apply_from_island(res, calculation_inputs[0].original_bus_idx,
                                      calculation_inputs[0].original_branch_idx)

        results.sc_type = self.options.fault_type
        results.sc_bus_index = self.options.bus_index

        self.results = results
        self.grid.short_circuit_results = results
        self._is_running = False
        self.toc()

    def isRunning(self):
        return self._is_running
