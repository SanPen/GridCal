# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

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
from GridCalEngine.Compilers.circuit_to_gslv import (GSLV_AVAILABLE, gslv_pf, translate_gslv_pf_results)
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

        self.results = PowerFlowResults(n=self.grid.get_bus_number(),
                                        m=self.grid.get_branch_number_wo_hvdc(),
                                        n_hvdc=self.grid.get_hvdc_number(),
                                        n_vsc=self.grid.get_vsc_number(),
                                        n_gen=self.grid.get_generation_like_number(),
                                        n_batt=self.grid.get_batteries_number(),
                                        n_sh=self.grid.get_shunt_like_device_number(),
                                        bus_names=self.grid.get_bus_names(),
                                        branch_names=self.grid.get_branch_names_wo_hvdc(),
                                        hvdc_names=self.grid.get_hvdc_names(),
                                        vsc_names=self.grid.get_vsc_names(),
                                        gen_names=self.grid.get_generation_like_names(),
                                        batt_names=self.grid.get_battery_names(),
                                        sh_names=self.grid.get_shunt_like_devices_names(),
                                        bus_types=np.ones(self.grid.get_bus_number()))

        self.convergence_reports = list()

        self.__cancel__ = False

    def get_steps(self) -> List[str]:
        """

        :return:
        """
        return list()

    def add_report(self) -> None:
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

        for i, elm in enumerate(self.grid.generators):
            if not (elm.Qmin <= self.results.gen_q[i] <= elm.Qmax):
                self.logger.add_warning("Generator Q out of bounds",
                                        device=elm.name,
                                        value=self.results.gen_q[i],
                                        expected_value=f"[{elm.Qmin}, {elm.Qmax}]", )

        for i, elm in enumerate(self.grid.batteries):
            if not (elm.Qmin <= self.results.battery_q[i] <= elm.Qmax):
                self.logger.add_warning("Battery Q out of bounds",
                                        device=elm.name,
                                        value=self.results.battery_q[i],
                                        expected_value=f"[{elm.Qmin}, {elm.Qmax}]", )

    def run(self) -> None:
        """
        Pack run_pf for the QThread
        """
        self.tic()
        if self.engine == EngineType.GSLV and not GSLV_AVAILABLE:
            self.engine = EngineType.GridCal
            self.logger.add_warning('Failed back to GridCal')

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
                                            n_vsc=self.grid.get_vsc_number(),
                                            n_gen=self.grid.get_generators_number(),
                                            n_batt=self.grid.get_batteries_number(),
                                            n_sh=self.grid.get_shunt_like_device_number(),
                                            bus_names=res.bus_names,
                                            branch_names=res.branch_names,
                                            hvdc_names=res.hvdc_names,
                                            vsc_names=self.grid.get_vsc_names(),
                                            gen_names=self.grid.get_generator_names(),
                                            batt_names=self.grid.get_battery_names(),
                                            sh_names=self.grid.get_shunt_like_devices_names(),
                                            bus_types=res.bus_types)

            self.results = translate_newton_pa_pf_results(self.grid, res)
            self.results.area_names = [a.name for a in self.grid.areas]
            self.convergence_reports = self.results.convergence_reports

        elif self.engine == EngineType.GSLV:

            res = gslv_pf(circuit=self.grid, pf_opt=self.options, time_series=False)

            self.results = PowerFlowResults(n=self.grid.get_bus_number(),
                                            m=self.grid.get_branch_number_wo_hvdc(),
                                            n_hvdc=self.grid.get_hvdc_number(),
                                            n_vsc=self.grid.get_vsc_number(),
                                            n_gen=self.grid.get_generators_number(),
                                            n_batt=self.grid.get_batteries_number(),
                                            n_sh=self.grid.get_shunt_like_device_number(),
                                            bus_names=res.bus_names,
                                            branch_names=res.branch_names,
                                            hvdc_names=res.hvdc_names,
                                            vsc_names=self.grid.get_vsc_names(),
                                            gen_names=self.grid.get_generator_names(),
                                            batt_names=self.grid.get_battery_names(),
                                            sh_names=self.grid.get_shunt_like_devices_names(),
                                            bus_types=res.bus_types)

            self.results = translate_gslv_pf_results(self.grid, res)
            self.results.area_names = [a.name for a in self.grid.areas]
            self.convergence_reports = self.results.convergence_reports

        elif self.engine == EngineType.Bentayga:

            res = bentayga_pf(self.grid, self.options, time_series=False)

            self.results = PowerFlowResults(n=self.grid.get_bus_number(),
                                            m=self.grid.get_branch_number_wo_hvdc(),
                                            n_hvdc=self.grid.get_hvdc_number(),
                                            n_vsc=self.grid.get_vsc_number(),
                                            n_gen=self.grid.get_generators_number(),
                                            n_batt=self.grid.get_batteries_number(),
                                            n_sh=self.grid.get_shunt_like_device_number(),
                                            bus_names=res.names,
                                            branch_names=res.names,
                                            hvdc_names=res.hvdc_names,
                                            vsc_names=self.grid.get_vsc_names(),
                                            gen_names=self.grid.get_generator_names(),
                                            batt_names=self.grid.get_battery_names(),
                                            sh_names=self.grid.get_shunt_like_devices_names(),
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
                                     device_property=f"Converged",
                                     value=convergence_report.converged_[i],
                                     expected_value="True")
                self.logger.add_info(msg=f"Method {convergence_report.methods_[i]}",
                                     device_property="Elapsed (s)",
                                     value='{:.4f}'.format(convergence_report.elapsed_[i]))
                self.logger.add_info(msg=f"Method {convergence_report.methods_[i]}",
                                     device_property="Error (p.u.)",
                                     value='{:.4e}'.format(convergence_report.error_[i]),
                                     expected_value=f"<{self.options.tolerance}")
                self.logger.add_info(msg=f"Method {convergence_report.methods_[i]}",
                                     device_property="Iterations",
                                     value=convergence_report.iterations_[i],
                                     expected_value=f"<{self.options.max_iter}")

        if self.options.generate_report:
            self.add_report()
