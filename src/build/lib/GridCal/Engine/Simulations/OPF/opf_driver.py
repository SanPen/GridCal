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
from typing import List, Dict, Tuple, Any
import numpy as np
import time

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.basic_structures import TimeGrouping, MIPSolvers, ZonalGrouping
from GridCal.Engine.Simulations.OPF.opf_results import OptimalPowerFlowResults
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.OPF.ac_opf import OpfAc
from GridCal.Engine.Simulations.OPF.dc_opf import OpfDc
from GridCal.Engine.Simulations.OPF.simple_dispatch import OpfSimple
from GridCal.Engine.basic_structures import SolverType
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from GridCal.Engine.Core.snapshot_opf_data import compile_snapshot_opf_circuit
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.driver_template import DriverTemplate

########################################################################################################################
# Optimal Power flow classes
########################################################################################################################


class OptimalPowerFlowOptions:

    def __init__(self, verbose=False,
                 solver: SolverType = SolverType.DC_OPF,
                 time_grouping: TimeGrouping = TimeGrouping.NoGrouping,
                 zonal_grouping: ZonalGrouping = ZonalGrouping.NoGrouping,
                 mip_solver=MIPSolvers.CBC,
                 faster_less_accurate=False,
                 power_flow_options=None,
                 bus_types=None,
                 consider_contingencies=False,
                 skip_generation_limits=False,
                 tolerance=1.0,
                 LODF=None,
                 lodf_tolerance=0.001,
                 maximize_flows=False,
                 area_from_bus_idx: List = None,
                 area_to_bus_idx: List = None):
        """
        Optimal power flow options
        :param verbose:
        :param solver:
        :param time_grouping:
        :param zonal_grouping:
        :param mip_solver:
        :param faster_less_accurate:
        :param power_flow_options:
        :param bus_types:
        :param consider_contingencies:
        :param skip_generation_limits:
        :param tolerance:
        :param LODF:
        :param lodf_tolerance:
        :param maximize_flows:
        :param area_from_bus_idx:
        :param area_to_bus_idx:
        """
        self.verbose = verbose

        self.solver = solver

        self.grouping = time_grouping

        self.mip_solver = mip_solver

        self.faster_less_accurate = faster_less_accurate

        self.power_flow_options = power_flow_options

        self.bus_types = bus_types

        self.zonal_grouping = zonal_grouping

        self.skip_generation_limits = skip_generation_limits

        self.consider_contingencies = consider_contingencies

        self.LODF = LODF

        self.tolerance = tolerance

        self.lodf_tolerance = lodf_tolerance

        self.maximize_flows = maximize_flows

        self.area_from_bus_idx = area_from_bus_idx

        self.area_to_bus_idx = area_to_bus_idx


class OptimalPowerFlow(DriverTemplate):
    name = 'Optimal power flow'
    tpe = SimulationTypes.OPF_run

    def __init__(self, grid: MultiCircuit, options: OptimalPowerFlowOptions, pf_options: PowerFlowOptions):
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

        if self.options.solver == SolverType.DC_OPF:
            # DC optimal power flow
            problem = OpfDc(numerical_circuit=numerical_circuit,
                            solver_type=self.options.mip_solver,
                            zonal_grouping=self.options.zonal_grouping,
                            skip_generation_limits=self.options.skip_generation_limits,
                            consider_contingencies=self.options.consider_contingencies,
                            LODF=self.options.LODF,
                            lodf_tolerance=self.options.lodf_tolerance,
                            maximize_inter_area_flow=self.options.maximize_flows,
                            buses_areas_1=self.options.area_from_bus_idx,
                            buses_areas_2=self.options.area_to_bus_idx
                            )

        elif self.options.solver == SolverType.AC_OPF:
            # AC optimal power flow
            problem = OpfAc(numerical_circuit=numerical_circuit, solver_type=self.options.mip_solver)

        elif self.options.solver == SolverType.Simple_OPF:
            # simplistic dispatch
            problem = OpfSimple(numerical_circuit=numerical_circuit)

        else:
            raise Exception('Solver not recognized ' + str(self.options.solver))

        # Solve
        problem.formulate()
        problem.solve()

        # get the branch Sf (it is used more than one time)
        ld = problem.get_load_shedding()
        ld[ld == None] = 0
        bt = problem.get_battery_power()
        bt[bt == None] = 0
        gn = problem.get_generator_power()
        gn[gn == None] = 0

        hvdc_power = problem.get_hvdc_flows()
        hvdc_loading = hvdc_power / (numerical_circuit.hvdc_data.rate[:, 0] + 1e-20)

        # pack the results
        self.results = OptimalPowerFlowResults(bus_names=numerical_circuit.bus_data.bus_names,
                                               branch_names=numerical_circuit.branch_data.branch_names,
                                               load_names=numerical_circuit.load_data.load_names,
                                               generator_names=numerical_circuit.generator_data.generator_names,
                                               battery_names=numerical_circuit.battery_data.battery_names,
                                               Sbus=problem.get_power_injections(),
                                               voltage=problem.get_voltage(),
                                               load_shedding=ld,
                                               hvdc_names=numerical_circuit.hvdc_names,
                                               hvdc_power=hvdc_power,
                                               hvdc_loading=hvdc_loading,
                                               phase_shift=problem.get_phase_shifts(),
                                               bus_shadow_prices=problem.get_shadow_prices(),
                                               generator_shedding=np.zeros_like(gn),
                                               battery_power=bt,
                                               controlled_generation_power=gn,
                                               Sf=problem.get_branch_power_from(),
                                               St=problem.get_branch_power_to(),
                                               overloads=problem.get_overloads(),
                                               loading=problem.get_loading(),
                                               contingency_flows_list=problem.get_contingency_flows_list(),
                                               contingency_indices_list=problem.contingency_indices_list,
                                               contingency_flows_slacks_list=problem.get_contingency_flows_slacks_list(),
                                               rates=numerical_circuit.branch_data.branch_rates[:, 0],
                                               contingency_rates=numerical_circuit.branch_data.branch_contingency_rates[:, 0],
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
