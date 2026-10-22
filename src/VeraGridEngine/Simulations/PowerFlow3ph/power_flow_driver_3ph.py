# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import numpy as np
from typing import Union, List, TYPE_CHECKING
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_worker_3ph import multi_island_pf_3ph
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Compilers.Gslv.activation import GSLV_AVAILABLE, GSLV_UNAVAILABLE_REASON
from VeraGridEngine.Compilers.Gslv.Simulations.power_flow_3ph import (
    gslv_pf_3ph,
    translate_gslv_pf_3ph_results,
)
from VeraGridEngine.enumerations import EngineType, SimulationTypes

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGridEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults


class PowerFlowDriver3Ph(DriverTemplate):
    __slots__ = (
        "options",
        "opf_results",
        "convergence_reports",
    )

    name = 'Power flow 3ph'
    tpe = SimulationTypes.PowerFlow3ph_run

    """
    Power flow wrapper
    """

    def __init__(self, grid: MultiCircuit,
                 options: Union[PowerFlowOptions, None] = None,
                 opf_results: Union[OptimalPowerFlowResults, None] = None,
                 engine: EngineType = EngineType.VeraGrid) -> None:
        """
        PowerFlowDriver class constructor
        :param grid: MultiCircuit instance
        :param options: PowerFlowOptions instance (optional)
        :param opf_results: OptimalPowerFlowResults instance (optional)
        :param engine: EngineType (i.e., EngineType.VeraGrid) (optional)
        """

        DriverTemplate.__init__(self, grid=grid, engine=engine)

        # Options to use
        self.options: PowerFlowOptions = PowerFlowOptions() if options is None else options

        self.opf_results: Union[OptimalPowerFlowResults, None] = opf_results

        self.results: PowerFlowResults3Ph = PowerFlowResults3Ph(
            n=self.grid.get_bus_number(),
            m=self.grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True),
            n_hvdc=self.grid.get_hvdc_number(),
            n_vsc=self.grid.get_vsc_number(),
            n_gen=self.grid.get_generation_like_number(),
            n_batt=self.grid.get_batteries_number(),
            n_sh=self.grid.get_shunt_like_device_number(),
            n_load=self.grid.get_load_like_device_number(),
            bus_names=self.grid.get_bus_names(),
            branch_names=self.grid.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True),
            hvdc_names=self.grid.get_hvdc_names(),
            vsc_names=self.grid.get_vsc_names(),
            gen_names=self.grid.get_generation_like_names(),
            batt_names=self.grid.get_battery_names(),
            sh_names=self.grid.get_shunt_like_devices_names(),
            load_names=self.grid.get_load_like_devices_names(),
            bus_types=np.ones(self.grid.get_bus_number())
        )

        self.convergence_reports: List = list()

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

        for vm, phase in [(np.abs(self.results.voltage_A), "A"),
                          (np.abs(self.results.voltage_B), "B"),
                          (np.abs(self.results.voltage_C), "C")]:

            for i, bus in enumerate(self.grid.buses):
                if vm[i] > bus.Vmax:
                    self.logger.add_warning("Overvoltage",
                                            device=f"{bus.name} - {phase}",
                                            value=vm[i],
                                            expected_value=bus.Vmax)
                elif vm[i] < bus.Vmin:
                    self.logger.add_warning("Undervoltage",
                                            device=f"{bus.name} - {phase}",
                                            value=vm[i],
                                            expected_value=bus.Vmin)

        for loading, phase in [(np.abs(self.results.loading_A), "A"),
                               (np.abs(self.results.loading_B), "B"),
                               (np.abs(self.results.loading_C), "C")]:

            branches = self.grid.get_branches(add_vsc=False, add_hvdc=False, add_switch=True)
            for i, branch in enumerate(branches):
                if loading[i] > 1.0:
                    self.logger.add_warning("Overload",
                                            device=f"{branch.name} - {phase}",
                                            value=loading[i] * 100.0,
                                            expected_value=100.0)

    def run(self) -> None:
        """
        Pack run_pf for the QThread
        """
        self.tic()
        self.report_text("Compiling and configuring...")

        # The three-phase driver can only stay on GSLV when that engine is present.
        if self.engine == EngineType.GSLV and not GSLV_AVAILABLE:
            self.engine = EngineType.VeraGrid
            self.logger.add_warning(f'GSLV unavailable: {GSLV_UNAVAILABLE_REASON}; falling back to VeraGrid')
        else:
            pass

        if self.engine == EngineType.VeraGrid:

            # There is a different worker for 3-phase calculations
            self.results = multi_island_pf_3ph(multi_circuit=self.grid,
                                               t=None,
                                               options=self.options,
                                               opf_results=self.opf_results,
                                               logger=self.logger)

            self.convergence_reports = self.results.convergence_reports

        elif self.engine == EngineType.GSLV:
            # Native GSLV solves the explicit NABC formulation, then the result is
            # translated back into the VeraGrid three-phase results container.
            gslv_results = gslv_pf_3ph(
                circuit=self.grid,
                pf_opt=self.options,
                t_idx=None,
                logger=self.logger,
            )
            self.results = translate_gslv_pf_3ph_results(self.grid, gslv_results)
            self.convergence_reports = self.results.convergence_reports

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
