# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import numpy as np

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.basic_structures import CxVec
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults, PowerFlowOptions
from VeraGridEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults
from VeraGridEngine.Simulations.ShortCircuitStudies.short_circuit_worker import (short_circuit_ph3,
                                                                                 short_circuit_unbalanced,
                                                                                 short_circuit_abc)
from VeraGridEngine.Simulations.ShortCircuitStudies.short_circuit_results import ShortCircuitResults
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Devices import Line, Bus
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.ShortCircuitStudies.short_circuit_options import ShortCircuitOptions
from VeraGridEngine.enumerations import FaultType, SimulationTypes, MethodShortCircuit, PhasesShortCircuit
from VeraGridEngine.Devices.types import BRANCH_TYPES


class ShortCircuitDriver(DriverTemplate):
    name = 'Short Circuit'
    tpe = SimulationTypes.ShortCircuit_run

    def __init__(self, grid: MultiCircuit,
                 options: ShortCircuitOptions | None,
                 pf_options: PowerFlowOptions | None,
                 pf_results: PowerFlowResults | None,
                 opf_results: OptimalPowerFlowResults | None = None):
        """
        ShortCircuitDriver class constructor
        :param grid: MultiCircuit Object
        :param options: ShortCircuitOptions
        :param pf_options: PowerFlowOptions
        :param pf_results: PowerFlowResults
        :param opf_results: OptimalPowerFlowResults
        """
        assert isinstance(pf_results, PowerFlowResults)
        DriverTemplate.__init__(self, grid=grid)

        self.pf_results: PowerFlowResults | None = pf_results
        self.pf_options: PowerFlowOptions | None = pf_options
        self.opf_results: OptimalPowerFlowResults | None = opf_results

        # Options to use
        self.options: ShortCircuitOptions | None = options

        # declare an empty results object
        n = grid.get_bus_number()
        self.results: ShortCircuitResults = ShortCircuitResults(
            n=n,
            m=grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True),
            n_hvdc=grid.get_hvdc_number(),
            bus_names=grid.get_bus_names(),
            branch_names=grid.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True),
            hvdc_names=grid.get_hvdc_names(),
            bus_types=np.ones(n),
            area_names=grid.get_area_names()
        )

        self.logger = Logger()

        self.__cancel__ = False

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
    def single_short_circuit(nc: NumericalCircuit,
                             Vpf: CxVec,
                             Zf: complex,
                             island_bus_index: int,
                             fault_type: FaultType,
                             method: MethodShortCircuit,
                             phases: PhasesShortCircuit,
                             Spf: CxVec) -> ShortCircuitResults:
        """
        Run a short circuit simulation for a single island
        :param calculation_inputs:
        :param Vpf: Power flow voltage vector applicable to the island
        :param Zf: Short circuit impedance vector applicable to the island
        :param island_bus_index: bus index where the fault happens
        :param fault_type: FaultType
        @return: short circuit results
        """
        adm = nc.get_admittance_matrices()
        # compute Zbus
        # is dense, so no need to store it as sparse
        if adm.Ybus.shape[0] > 1:
            if method == MethodShortCircuit.sequences:
                if fault_type == FaultType.ph3:
                    return short_circuit_ph3(nc=nc,
                                             Vpf=Vpf[nc.bus_data.original_idx],
                                             Zf=Zf,
                                             bus_index=island_bus_index)

                elif fault_type in [FaultType.LG, FaultType.LL, FaultType.LLG]:
                    return short_circuit_unbalanced(nc=nc,
                                                    Vpf=Vpf[nc.bus_data.original_idx],
                                                    Zf=Zf,
                                                    bus_index=island_bus_index,
                                                    fault_type=fault_type)

                else:
                    raise Exception('Unknown fault type!')

            elif method == MethodShortCircuit.phases:

                if fault_type in (FaultType.LLL, FaultType.ph3):
                    if phases != PhasesShortCircuit.abc:
                        raise Exception(
                            f"The selected short-circuit type is inconsistent with the phases involved: {fault_type.name} must include all three phases (abc).")

                elif fault_type in (FaultType.LL, FaultType.LLG):
                    if phases not in (PhasesShortCircuit.ab, PhasesShortCircuit.bc, PhasesShortCircuit.ca):
                        raise Exception(
                            f"The selected short-circuit type is inconsistent with the phases involved: {fault_type.name} must be between two valid phases (ab, bc, or ca).")

                elif fault_type == FaultType.LG:
                    if phases not in (PhasesShortCircuit.a, PhasesShortCircuit.b, PhasesShortCircuit.c):
                        raise Exception(
                            f"The selected short-circuit type is inconsistent with the phases involved: {fault_type.name} must be on a single valid phase (a, b or c).")

                # Short-circuit simulation:
                return short_circuit_abc(nc=nc,
                                          Vpf=Vpf,
                                          Zf=Zf,
                                          bus_index=island_bus_index,
                                          fault_type=fault_type,
                                          method = method,
                                          phases = phases,
                                          Spf=Spf)

            else:
                raise Exception('Short-circuit calculation method is unknown!')


        # if we get here, no short circuit was done, so declare empty results and exit --------------------------------
        nbus = adm.Ybus.shape[0]
        nbr = nc.nbr

        # voltage, Sf, loading, losses, error, converged, Qpv
        results = ShortCircuitResults(n=nc.nbus,
                                      m=nc.nbr,
                                      n_hvdc=nc.nhvdc,
                                      bus_names=nc.bus_data.names,
                                      branch_names=nc.passive_branch_data.names,
                                      hvdc_names=nc.hvdc_data.names,
                                      bus_types=nc.bus_data.bus_types,
                                      area_names=None)

        results.Sbus = nc.get_power_injections_pu()
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
            branch = self.grid.get_branches(add_hvdc=False, add_vsc=False, add_switch=True)[self.options.branch_index]
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
        if self.options.method == MethodShortCircuit.phases:
            nc = compile_numerical_circuit_at(circuit=grid,
                                              t_idx=None,
                                              apply_temperature=self.pf_options.apply_temperature_correction,
                                              branch_tolerance_mode=self.pf_options.branch_impedance_tolerance_mode,
                                              opf_results=self.opf_results,
                                              logger=self.logger,
                                              fill_three_phase=True
                                              )
        else:
            nc = compile_numerical_circuit_at(circuit=grid,
                                              t_idx=None,
                                              apply_temperature=self.pf_options.apply_temperature_correction,
                                              branch_tolerance_mode=self.pf_options.branch_impedance_tolerance_mode,
                                              opf_results=self.opf_results,
                                              logger=self.logger,
                                              fill_three_phase=False
                                              )

        calculation_inputs = nc.split_into_islands(
            ignore_single_node_islands=self.pf_options.ignore_single_node_islands
        )

        results = ShortCircuitResults(n=nc.nbus,
                                      m=nc.nbr,
                                      n_hvdc=nc.nhvdc,
                                      bus_names=nc.bus_data.names,
                                      branch_names=nc.passive_branch_data.names,
                                      hvdc_names=nc.hvdc_data.names,
                                      bus_types=nc.bus_data.bus_types)

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
                    res = self.single_short_circuit(nc=island,
                                                    Vpf=self.pf_results.voltage[island.bus_data.original_idx],
                                                    Zf=Zf[island.bus_data.original_idx],
                                                    island_bus_index=island_bus_index,
                                                    fault_type=self.options.fault_type)  # TODO fill missing arguments

                    # merge results
                    results.apply_from_island(res, island.bus_data.original_idx,
                                              island.passive_branch_data.original_idx)

        else:  # single island

            res = self.single_short_circuit(nc=calculation_inputs[0],
                                            Vpf=self.pf_results.voltage,
                                            Zf=Zf,
                                            island_bus_index=self.options.bus_index,
                                            fault_type=self.options.fault_type,
                                            method=self.options.method,
                                            phases=self.options.phases,
                                            Spf=self.pf_results.Sbus
                                            )

            # merge results
            results.apply_from_island(res, calculation_inputs[0].bus_data.original_idx,
                                      calculation_inputs[0].passive_branch_data.original_idx)

        results.sc_type = self.options.fault_type
        results.sc_bus_index = self.options.bus_index

        # expand voltages if there was a bus topology reduction
        if nc.topology_performed:
            results.voltage = nc.propagate_bus_result(results.voltage)
            results.voltage1 = nc.propagate_bus_result(results.voltage1)
            results.voltage0 = nc.propagate_bus_result(results.voltage0)
            results.voltage2 = nc.propagate_bus_result(results.voltage2)

        self.results = results
        self._is_running = False
        self.toc()
