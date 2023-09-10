# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
import time
import numpy as np
from typing import Union
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis
from GridCalEngine.Simulations.driver_types import SimulationTypes
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Core.Compilers.circuit_to_bentayga import BENTAYGA_AVAILABLE, bentayga_linear_matrices
from GridCalEngine.Core.Compilers.circuit_to_newton_pa import NEWTON_PA_AVAILABLE, newton_pa_linear_matrices
import GridCalEngine.basic_structures as bs
from GridCalEngine.Simulations.LinearFactors.linear_analysis_results import LinearAnalysisResults
from GridCalEngine.Simulations.LinearFactors.linear_analysis_options import LinearAnalysisOptions


class LinearAnalysisDriver(DriverTemplate):
    name = 'Linear analysis'
    tpe = SimulationTypes.LinearAnalysis_run

    def __init__(self, grid: MultiCircuit,
                 options: LinearAnalysisOptions,
                 engine: bs.EngineType = bs.EngineType.GridCal):
        """
        Linear analysis driver constructor
        :param grid: MultiCircuit instance
        :param options: LinearAnalysisOptions instance
        :param engine: EngineType enum
        """
        DriverTemplate.__init__(self, grid=grid)

        # Options to use
        self.options: LinearAnalysisOptions = options

        self.engine: bs.EngineType = engine

        # Results
        self.results: Union[LinearAnalysisResults, None] = None

        self.all_solved: bool = True

    def run(self):
        """
        Run thread
        """
        start = time.time()
        self.progress_text.emit('Analyzing')
        self.progress_signal.emit(0)

        bus_names = self.grid.get_bus_names()
        br_names = self.grid.get_branches_wo_hvdc_names()
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
        if self.engine == bs.EngineType.Bentayga and not BENTAYGA_AVAILABLE:
            self.engine = bs.EngineType.GridCal
            self.logger.add_warning('Failed, back to GridCal')

        if self.engine == bs.EngineType.NewtonPA and not NEWTON_PA_AVAILABLE:
            self.engine = bs.EngineType.GridCal
            self.logger.add_warning('Failed, back to GridCal')

        if self.engine == bs.EngineType.GridCal:
            nc = compile_numerical_circuit_at(circuit=self.grid)
            analysis = LinearAnalysis(
                numerical_circuit=nc,
                distributed_slack=self.options.distribute_slack,
                correct_values=self.options.correct_values)

            analysis.run()
            self.logger += analysis.logger
            self.results.bus_names = analysis.numerical_circuit.bus_names
            self.results.branch_names = analysis.numerical_circuit.branch_names
            self.results.bus_types = analysis.numerical_circuit.bus_data.bus_types
            self.results.PTDF = analysis.PTDF
            self.results.LODF = analysis.LODF

            # compose the HVDC power Injections
            bus_dict = self.grid.get_bus_index_dict()
            nbus = len(self.grid.buses)

            # TODO: Use the function from HvdcData instead of the one from MultiCircuit
            Shvdc, Losses_hvdc, Pf_hvdc, Pt_hvdc, loading_hvdc, n_free = nc.hvdc_data.get_power(Sbase=nc.Sbase,
                                                                                                theta=np.zeros(nbus))
            self.results.Sf = analysis.get_flows(analysis.numerical_circuit.Sbus.real + Shvdc)
            self.results.loading = self.results.Sf / (analysis.numerical_circuit.branch_rates + 1e-20)
            self.results.Sbus = analysis.numerical_circuit.Sbus.real

        elif self.engine == bs.EngineType.Bentayga:

            lin_mat = bentayga_linear_matrices(circuit=self.grid, distributed_slack=self.options.distribute_slack)
            self.results.PTDF = lin_mat.PTDF
            self.results.LODF = lin_mat.LODF
            self.results.Sf = lin_mat.get_flows(lin_mat.Pbus * self.grid.Sbase)
            self.results.loading = self.results.Sf / (lin_mat.rates + 1e-20)
            self.results.Sbus = lin_mat.Pbus * self.grid.Sbase

        elif self.engine == bs.EngineType.NewtonPA:

            lin_mat = newton_pa_linear_matrices(circuit=self.grid, distributed_slack=self.options.distribute_slack)
            self.results.PTDF = lin_mat.PTDF
            self.results.LODF = lin_mat.LODF
            self.results.Sbus = self.grid.get_Pbus()
            rates = self.grid.get_branch_rates_wo_hvdc()
            self.results.Sf = np.dot(lin_mat.PTDF, self.results.Sbus)
            self.results.loading = self.results.Sf / (rates + 1e-20)

        end = time.time()
        self.elapsed = end - start

    def get_steps(self):
        """
        Get variations list of strings
        """
        if self.results is not None:
            return [v for v in self.results.bus_names]
        else:
            return list()
