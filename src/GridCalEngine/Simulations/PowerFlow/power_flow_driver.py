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
from __future__ import annotations
import numpy as np
from typing import Union, List, TYPE_CHECKING
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Compilers.circuit_to_bentayga import (BENTAYGA_AVAILABLE, bentayga_pf,
                                                         translate_bentayga_pf_results)
from GridCalEngine.Compilers.circuit_to_newton_pa import (NEWTON_PA_AVAILABLE, newton_pa_pf,
                                                          translate_newton_pa_pf_results)
from GridCalEngine.Compilers.circuit_to_pgm import PGM_AVAILABLE, pgm_pf
from GridCalEngine.enumerations import EngineType, SimulationTypes

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCalEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults


class PowerFlowDriver(DriverTemplate):
    name = 'Power Flow'
    tpe = SimulationTypes.PowerFlow_run

    """
    Power flow wrapper to use with Qt
    """

    def __init__(self, grid: MultiCircuit,
                 options: Union[PowerFlowOptions, None] = None,
                 opf_results: Union[OptimalPowerFlowResults, None] = None,
                 engine: EngineType = EngineType.GridCal):
        """
        PowerFlowDriver class constructor
        :param grid: MultiCircuit instance
        :param options: PowerFlowOptions instance (optional)
        :param opf_results: OptimalPowerFlowResults instance (optional)
        :param engine: EngineType (i.e. EngineType.GridCal) (optional)
        """

        DriverTemplate.__init__(self, grid=grid, engine=engine)

        # Options to use
        self.options: PowerFlowOptions = PowerFlowOptions() if options is None else options

        self.opf_results: Union[OptimalPowerFlowResults, None] = opf_results

        self.results = PowerFlowResults(n=0,
                                        m=0,
                                        n_hvdc=0,
                                        bus_names=np.empty(0, dtype=object),
                                        branch_names=np.empty(0, dtype=object),
                                        hvdc_names=np.empty(0, dtype=object),
                                        bus_types=np.empty(0))

        self.convergence_reports = list()

        self.__cancel__ = False

    def get_steps(self) -> List[str]:
        """

        :return:
        """
        return list()

    def add_report(self):
        """
        Add a report of the results (in-place)
        """
        vm = np.abs(self.results.voltage)
        for i, bus in enumerate(self.grid.buses):
            if vm[i] > bus.Vmax:
                self.logger.add_warning("Overvoltage",
                                        device=bus.name,
                                        value=vm[i],
                                        expected_value=bus.Vmax)
            elif vm[i] < bus.Vmin:
                self.logger.add_warning("Undervoltage",
                                        device=bus.name,
                                        value=vm[i],
                                        expected_value=bus.Vmin)

        loading = np.abs(self.results.loading)
        branches = self.grid.get_branches_wo_hvdc()
        for i, branch in enumerate(branches):
            if loading[i] > 1.0:
                self.logger.add_warning("Overload",
                                        device=branch.name,
                                        value=loading[i] * 100.0,
                                        expected_value=100.0)

    def run(self) -> None:
        """
        Pack run_pf for the QThread
        """
        self.tic()
        if self.engine == EngineType.NewtonPA and not NEWTON_PA_AVAILABLE:
            self.engine = EngineType.GridCal
            self.logger.add_warning('Failed back to GridCal')

        if self.engine == EngineType.Bentayga and not BENTAYGA_AVAILABLE:
            self.engine = EngineType.GridCal
            self.logger.add_warning('Failed back to GridCal')

        if self.engine == EngineType.PGM and not PGM_AVAILABLE:
            self.engine = EngineType.GridCal
            self.logger.add_warning('Failed back to GridCal')

        if self.engine == EngineType.GridCal:
            self.results = multi_island_pf(multi_circuit=self.grid,
                                           t=None,
                                           options=self.options,
                                           opf_results=self.opf_results,
                                           logger=self.logger)
            self.convergence_reports = self.results.convergence_reports

        elif self.engine == EngineType.NewtonPA:

            res = newton_pa_pf(circuit=self.grid, pf_opt=self.options, time_series=False)

            self.results = PowerFlowResults(n=self.grid.get_bus_number(),
                                            m=self.grid.get_branch_number_wo_hvdc(),
                                            n_hvdc=self.grid.get_hvdc_number(),
                                            bus_names=res.bus_names,
                                            branch_names=res.branch_names,
                                            hvdc_names=res.hvdc_names,
                                            bus_types=res.bus_types)

            self.results = translate_newton_pa_pf_results(self.grid, res)
            self.results.area_names = [a.name for a in self.grid.areas]
            self.convergence_reports = self.results.convergence_reports

        elif self.engine == EngineType.Bentayga:

            res = bentayga_pf(self.grid, self.options, time_series=False)

            self.results = PowerFlowResults(n=self.grid.get_bus_number(),
                                            m=self.grid.get_branch_number_wo_hvdc(),
                                            n_hvdc=self.grid.get_hvdc_number(),
                                            bus_names=res.names,
                                            branch_names=res.names,
                                            hvdc_names=res.hvdc_names,
                                            bus_types=res.bus_types)

            self.results = translate_bentayga_pf_results(self.grid, res)
            self.results.area_names = [a.name for a in self.grid.areas]
            self.convergence_reports = self.results.convergence_reports

        elif self.engine == EngineType.PGM:

            self.results = pgm_pf(self.grid, self.options, logger=self.logger)
            self.results.area_names = [a.name for a in self.grid.areas]

        else:
            raise Exception('Engine ' + self.engine.value + ' not implemented for ' + self.name)

        # fill F, T, Areas, etc...
        self.results.fill_circuit_info(self.grid)

        self.toc()

        for convergence_report in self.results.convergence_reports:
            n = len(convergence_report.error_)
            for i in range(n):
                self.logger.add_info(msg=f"Method {convergence_report.methods_[i]}",
                                     device=f"Converged",
                                     value=convergence_report.converged_[i],
                                     expected_value="True")
                self.logger.add_info(msg=f"Method {convergence_report.methods_[i]}",
                                     device="Elapsed (s)",
                                     value=convergence_report.elapsed_[i])
                self.logger.add_info(msg=f"Method {convergence_report.methods_[i]}",
                                     device="Error (p.u.)",
                                     value=convergence_report.error_[i],
                                     expected_value=self.options.tolerance)
                self.logger.add_info(msg=f"Method {convergence_report.methods_[i]}",
                                     device="Iterations",
                                     value=convergence_report.iterations_[i],
                                     expected_value=self.options.max_iter)

        if self.options.generate_report:
            self.add_report()
