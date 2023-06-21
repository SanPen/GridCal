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

import json
import pandas as pd
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve, factorized
import time

from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Simulations.LinearFactors.linear_analysis import LinearAnalysis
from GridCal.Engine.Simulations.LinearFactors.linear_analysis_options import LinearAnalysisOptions
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Core.numerical_circuit import compile_numerical_circuit_at
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCal.Engine.Simulations.LinearFactors.linear_analysis_ts_results import LinearAnalysisTimeSeriesResults



class LinearAnalysisTimeSeries(TimeSeriesDriverTemplate):
    name = 'Linear analysis time series'
    tpe = SimulationTypes.LinearAnalysis_TS_run

    def __init__(self, grid: MultiCircuit, options: LinearAnalysisOptions, start_=0, end_=None):
        """
        TimeSeries constructor
        @param grid: MultiCircuit instance
        @param options: LinearAnalysisOptions instance
        """
        TimeSeriesDriverTemplate.__init__(self, grid=grid, start_=start_, end_=end_)

        self.options = options

        self.results: LinearAnalysisTimeSeriesResults = None

        self.ptdf_driver = LinearAnalysis(grid=self.grid, distributed_slack=self.options.distribute_slack)

    def get_steps(self):
        """
        Get time steps list of strings
        """

        return [l.strftime('%d-%m-%Y %H:%M') for l in self.indices]

    def run(self):
        """
        Run the time series simulation
        @return:
        """
        self.__cancel__ = False
        a = time.time()

        if self.end_ is None:
            self.end_ = len(self.grid.time_profile)
        time_indices = np.arange(self.start_, self.end_ + 1)

        self.results = LinearAnalysisTimeSeriesResults(n=self.grid.get_bus_number(),
                                                       m=self.grid.get_branch_number_wo_hvdc(),
                                                       time_array=self.grid.time_profile[time_indices],
                                                       bus_names=self.grid.get_bus_names(),
                                                       bus_types=self.grid.get_bus_default_types(),
                                                       branch_names=self.grid.get_branches_wo_hvdc_names())

        self.indices = pd.to_datetime(self.grid.time_profile[time_indices])

        self.progress_text.emit('Computing PTDF...')
        linear_analysis = LinearAnalysis(grid=self.grid,
                                         distributed_slack=self.options.distribute_slack,
                                         correct_values=self.options.correct_values)
        linear_analysis.run()

        self.progress_text.emit('Computing branch flows...')

        Pbus_0 = self.grid.get_Sbus_prof().T[:, time_indices]
        self.results.Sf = linear_analysis.get_flows_time_series(Pbus_0)

        # compute post process
        self.results.loading = self.results.Sf / (self.grid.get_branch_rates_prof_wo_hvdc()[time_indices, :] + 1e-9)
        self.results.S = Pbus_0.T

        self.elapsed = time.time() - a

