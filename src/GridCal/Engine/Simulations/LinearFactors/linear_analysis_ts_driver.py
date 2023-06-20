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
import time
import pandas as pd
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve, factorized
from typing import Dict, Union, List
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.numerical_circuit import NumericalCircuit
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Simulations.LinearFactors.linear_analysis import LinearAnalysis
from GridCal.Engine.Simulations.LinearFactors.linear_analysis_driver import LinearAnalysisOptions, LinearAnalysisResults
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Core.numerical_circuit import compile_numerical_circuit_at
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.Simulations.driver_template import TimeSeriesDriverTemplate


class LinearAnalysisTimeSeriesResults(ResultsTemplate):

    def __init__(
            self,
            n: int,
            m: int,
            time_array: np.ndarray,
            bus_names: np.ndarray,
            bus_types: np.ndarray,
            branch_names: np.ndarray
    ):
        """
        TimeSeriesResults constructor
        :param n: number of buses
        :param m: number of branches
        :param time_array: time array
        :param bus_names: bus names array
        :param bus_types: bus types array
        :param branch_names: branch names array
        """
        ResultsTemplate.__init__(
            self,
            name='Linear Analysis time series',
            available_results=[
                ResultTypes.BusActivePower,
                ResultTypes.BranchActivePowerFrom,
                ResultTypes.BranchLoading
            ],
            data_variables=[
                'bus_names',
                'bus_types',
                'time',
                'branch_names',
                'voltage',
                'S',
                'Sf',
                'loading',
                'losses'
            ]
        )

        self.m: int = m
        self.n: int = n
        self.nt: int = len(time_array)

        self.time: np.ndarray = time_array

        self.bus_names: np.ndarray = bus_names
        self.branch_names: np.ndarray = branch_names
        self.bus_types: np.ndarray = bus_types

        self.voltage: np.ndarray = np.ones((self.nt, n), dtype=float)
        self.S: np.ndarray = np.zeros((self.nt, n), dtype=float)
        self.Sf: np.ndarray = np.zeros((self.nt, m), dtype=float)
        self.loading: np.ndarray = np.zeros((self.nt, m), dtype=float)
        self.losses: np.ndarray = np.zeros((self.nt, m), dtype=float)

        self.topological_dict: Dict[int, List[int]] = dict()
        self.results: Dict[int, LinearAnalysisResults] = dict()
        self.reports: Dict[str, ResultsTable] = dict()

    def apply_new_time_series_rates(self, nc: NumericalCircuit):
        rates = nc.Rates.T
        self.loading = self.Sf / (rates + 1e-9)

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {
            'V': self.voltage.tolist(),
            'P': self.S.real.tolist(),
            'Q': self.S.imag.tolist(),
            'Sbr_real': self.Sf.real.tolist(),
            'Sbr_imag': self.Sf.imag.tolist(),
            'loading': np.abs(self.loading).tolist()
        }
        return data

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """
        Get ResultsModel instance
        :param result_type:
        :return: ResultsModel instance
        """

        if result_type == ResultTypes.BusActivePower:
            labels = self.bus_names
            data = self.S
            y_label = '(MW)'
            title = 'Bus active power '

        elif result_type == ResultTypes.BranchActivePowerFrom:
            labels = self.branch_names
            data = self.Sf.real
            y_label = '(MW)'
            title = 'Branch power '

        elif result_type == ResultTypes.BranchLoading:
            labels = self.branch_names
            data = self.loading * 100
            y_label = '(%)'
            title = 'Branch loading '

        elif result_type == ResultTypes.BranchLosses:
            labels = self.branch_names
            data = self.losses
            y_label = '(MVA)'
            title = 'Branch losses'

        elif result_type == ResultTypes.BusVoltageModule:
            labels = self.bus_names
            data = self.voltage
            y_label = '(p.u.)'
            title = 'Bus voltage'

        else:
            raise Exception('Result type not understood:' + str(result_type))

        if self.time is not None:
            index = self.time
        else:
            index = list(range(data.shape[0]))

        # assemble model
        return ResultsTable(
            data=data,
            index=index,
            columns=labels,
            title=title,
            ylabel=y_label,
            units=y_label
        )


class LinearAnalysisTimeSeriesDriver(TimeSeriesDriverTemplate):
    name = 'Linear analysis time series'
    tpe = SimulationTypes.LinearAnalysis_TS_run

    def __init__(
            self,
            grid: MultiCircuit,
            options: LinearAnalysisOptions,
            start_: int = 0,
            end_: Union[int, None] = None,
            use_clustering: bool = False,
    ):
        """
        TimeSeries constructor
        :param grid: MultiCircuit instance
        :param options: LinearAnalysisOptions instance
        :param start_: first time index to consider
        :param end_: last time index to consider
        """
        TimeSeriesDriverTemplate.__init__(
            self,
            grid=grid,
            start_=start_,
            end_=end_,
            use_clustering=use_clustering,
        )

        self.options: LinearAnalysisOptions = options

        # self.nc_dict: Union[Dict[int, NumericalCircuit], None] = None
        self.drivers: Dict[int, LinearAnalysis] = dict()
        self.results: Dict[int, LinearAnalysisTimeSeriesResults] = dict()

    def get_steps(self):
        """
        Get time steps list of strings
        """

        return [l.strftime('%d-%m-%Y %H:%M') for l in self.indices]

    def run(self, with_flows=True, with_nx=False):
        """
        Run the time series analysis
        :param with_flows: Boolean to compute flows for time series
        :param with_nx: Boolean to compute LODF-nx sensibilities
        :return: LinearAnalysisTimeSeriesResults instance
        """

        tm_ = time.time()

        self.progress_text.emit('Computing TS linear analysis...')

        self.__cancel__ = False

        time_indices = self.get_time_indices()

        if self.use_clustering:
            self.apply_cluster_indices()

        self.indices = pd.to_datetime(self.grid.time_profile[time_indices])

        self.results = LinearAnalysisTimeSeriesResults(
            n=self.grid.get_bus_number(),
            m=self.grid.get_branch_number_wo_hvdc(),
            time_array=self.grid.time_profile[time_indices],
            bus_names=self.grid.get_bus_names(),
            bus_types=self.grid.get_bus_default_types(),
            branch_names=self.grid.get_branches_wo_hvdc_names(),
        )
        # Compute bus injections
        Sbus = self.grid.get_Sbus() / self.grid.Sbase

        # Initialize branch flows
        Sf = np.zeros(shape=(len(time_indices), self.grid.get_branch_number_wo_hvdc()), dtype=float)

        # Compute different topologies to consider
        self.set_topologic_groups()

        contingency_dict = self.grid.get_contingencies_dict()
        branch_dict = self.grid.get_branches_dict()


        for it, t in enumerate(self.topologic_groups.keys()):

            self.progress_text.emit('Processing topology group ' + str(self.grid.time_profile[t]))
            self.progress_signal.emit((it + 1) / len(self.topologic_groups.keys()) * 100)

            # time indices with same topology
            t_idx = self.topologic_groups[t]

            nc = compile_numerical_circuit_at(
                circuit=self.grid,
                t_idx=t,
            )

            driver_ = LinearAnalysis(
                numerical_circuit=nc,
                distributed_slack=True,
                correct_values=False,
            )

            driver_.run()

            if with_flows:
                Sf[t_idx, :] = driver_.get_flows(Sbus=Sbus[t_idx, :])

            if with_nx:
                driver_.lodf_nx = driver_.make_lodfnx(
                    lodf=driver_.LODF,
                    contingencies_dict=contingency_dict,
                    branches_dict=branch_dict
                )

            # store main linear drivers
            self.drivers[t] = driver_

        # Store results
        self.results.Sbus = Sbus
        self.results.Sf = Sf
        self.results.loading = Sf / (self.grid.get_branch_rates_wo_hvdc()[time_indices, :] + 1e-9)
        self.elapsed = time.time() - tm_

