# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import numpy as np
from typing import Union, TYPE_CHECKING

from numba.cuda.cudadrv.nvvm import nvvm_result

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Compilers.circuit_to_bentayga import BENTAYGA_AVAILABLE, bentayga_linear_matrices
from GridCalEngine.Compilers.circuit_to_newton_pa import NEWTON_PA_AVAILABLE, newton_pa_linear_matrices
from GridCalEngine.enumerations import EngineType, SimulationTypes
from GridCalEngine.Simulations.LinearFactors.linear_analysis_results import LinearAnalysisResults
from GridCalEngine.Simulations.LinearFactors.linear_analysis_options import LinearAnalysisOptions
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCalEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults


class LinearAnalysisDriver(DriverTemplate):
    name = 'Linear analysis'
    tpe = SimulationTypes.LinearAnalysis_run

    def __init__(self, grid: MultiCircuit,
                 options: Union[LinearAnalysisOptions, None] = None,
                 engine: EngineType = EngineType.GridCal,
                 opf_results: Union[OptimalPowerFlowResults, None] = None):
        """
        Linear analysis driver constructor
        :param grid: MultiCircuit instance
        :param options: LinearAnalysisOptions instance
        :param engine: EngineType enum
        """
        DriverTemplate.__init__(self, grid=grid)

        # Options to use
        self.options: LinearAnalysisOptions = LinearAnalysisOptions() if options is None else options

        self.engine: EngineType = engine

        self.opf_results = opf_results

        # Results
        self.results: LinearAnalysisResults = LinearAnalysisResults(n_br=self.grid.get_branch_number_wo_hvdc(),
                                                                    n_bus=self.grid.get_bus_number(),
                                                                    br_names=self.grid.get_branch_names_wo_hvdc(),
                                                                    bus_names=self.grid.get_bus_names(),
                                                                    bus_types=np.ones(self.grid.get_bus_number()))

        self.all_solved: bool = True

    def run(self):
        """
        Run thread
        """
        self.tic()
        self.report_text('Analyzing')
        self.report_progress(0)

        bus_names = self.grid.get_bus_names()
        br_names = self.grid.get_branch_names_wo_hvdc()
        bus_types = np.ones(len(bus_names), dtype=int)
        try:
            self.results = LinearAnalysisResults(
                n_br=len(br_names),
                n_bus=len(bus_names),
                br_names=br_names,
                bus_names=bus_names,
                bus_types=bus_types
            )

        except MemoryError as e:
            self.logger.add_error(str(e))
            return

        # Run Analysis
        if self.engine == EngineType.Bentayga and not BENTAYGA_AVAILABLE:
            self.engine = EngineType.GridCal
            self.logger.add_warning('Failed, back to GridCal')

        if self.engine == EngineType.NewtonPA and not NEWTON_PA_AVAILABLE:
            self.engine = EngineType.GridCal
            self.logger.add_warning('Failed, back to GridCal')

        if self.engine == EngineType.GridCal:

            nc: NumericalCircuit = compile_numerical_circuit_at(
                circuit=self.grid,
                t_idx=None,
                opf_results=self.opf_results,
                logger=self.logger
            )

            analysis = LinearAnalysis(
                numerical_circuit=nc,
                distributed_slack=self.options.distribute_slack,
                correct_values=self.options.correct_values
            )

            self.logger += analysis.logger
            self.results.bus_names = nc.bus_data.names
            self.results.branch_names = nc.passive_branch_data.names
            self.results.bus_types = nc.bus_data.bus_types
            self.results.PTDF = analysis.PTDF
            self.results.LODF = analysis.LODF

            # compose the HVDC power Injections
            bus_dict = self.grid.get_bus_index_dict()
            nbus = len(self.grid.buses)

            Shvdc, Losses_hvdc, Pf_hvdc, Pt_hvdc, loading_hvdc, n_free = nc.hvdc_data.get_power(Sbase=nc.Sbase,
                                                                                                theta=np.zeros(nbus))
            Sbus = nc.get_power_injections_pu()
            Pbus_pu = Sbus.real + Shvdc
            self.results.Sbus = Pbus_pu * nc.Sbase
            self.results.Sf = analysis.get_flows(Pbus_pu) * nc.Sbase
            self.results.loading = self.results.Sf / (nc.passive_branch_data.rates + 1e-20)

        elif self.engine == EngineType.Bentayga:

            lin_mat = bentayga_linear_matrices(circuit=self.grid, distributed_slack=self.options.distribute_slack)
            self.results.PTDF = lin_mat.PTDF
            self.results.LODF = lin_mat.LODF
            self.results.Sf = lin_mat.get_flows(lin_mat.Pbus * self.grid.Sbase)
            self.results.loading = self.results.Sf / (lin_mat.rates + 1e-20)
            self.results.Sbus = lin_mat.Pbus * self.grid.Sbase

        elif self.engine == EngineType.NewtonPA:

            lin_mat = newton_pa_linear_matrices(circuit=self.grid, distributed_slack=self.options.distribute_slack)
            self.results.PTDF = lin_mat.PTDF
            self.results.LODF = lin_mat.LODF
            # TODO: figure this out
            self.results.Sbus = self.grid.get_Pbus()
            rates = self.grid.get_branch_rates_wo_hvdc()
            self.results.Sf = np.dot(lin_mat.PTDF, self.results.Sbus)
            self.results.loading = self.results.Sf / (rates + 1e-20)

        self.toc()

    def get_steps(self):
        """
        Get variations list of strings
        """
        if self.results is not None:
            return [v for v in self.results.bus_names]
        else:
            return list()
