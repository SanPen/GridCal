# # GridCal
# # Copyright (C) 2022 Santiago Peñate Vera
# #
# # This program is free software; you can redistribute it and/or
# # modify it under the terms of the GNU Lesser General Public
# # License as published by the Free Software Foundation; either
# # version 3 of the License, or (at your option) any later version.
# #
# # This program is distributed in the hope that it will be useful,
# # but WITHOUT ANY WARRANTY; without even the implied warranty of
# # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# # Lesser General Public License for more details.
# #
# # You should have received a copy of the GNU Lesser General Public License
# # along with this program; if not, write to the Free Software Foundation,
# # Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
# import json
# import pandas as pd
# import numpy as np
# import scipy.sparse as sp
# from scipy.sparse.linalg import spsolve, factorized
# import time
# from typing import Union
# from GridCal.Engine.Simulations.result_types import ResultTypes
# from GridCal.Engine.Core.multi_circuit import MultiCircuit
# from GridCal.Engine.Core.numerical_circuit import NumericalCircuit
# from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
# from GridCal.Engine.Simulations.LinearFactors.linear_analysis import LinearAnalysisMultiCircuit
# from GridCal.Engine.Simulations.LinearFactors.linear_analysis_driver import LinearAnalysisOptions
# from GridCal.Engine.Simulations.results_table import ResultsTable
# from GridCal.Engine.Core.numerical_circuit import compile_numerical_circuit_at
# from GridCal.Engine.Simulations.driver_types import SimulationTypes
# from GridCal.Engine.Simulations.results_template import ResultsTemplate
# from GridCal.Engine.Simulations.driver_template import TimeSeriesDriverTemplate
#
#
# class LinearAnalysisTimeSeriesResults(ResultsTemplate):
#
#     def __init__(
#             self,
#             n: int,
#             m: int,
#             time_array: np.ndarray,
#             bus_names: np.ndarray,
#             bus_types: np.ndarray,
#             branch_names: np.ndarray
#     ):
#         """
#         TimeSeriesResults constructor
#         :param n: number of buses
#         :param m: number of branches
#         :param time_array: time array
#         :param bus_names: bus names array
#         :param bus_types: bus types array
#         :param branch_names: branch names array
#         """
#
#         ResultsTemplate.__init__(
#             self,
#             name='Linear Analysis time series',
#             available_results=[
#                 ResultTypes.BusActivePower,
#                 ResultTypes.BranchActivePowerFrom,
#                 ResultTypes.BranchLoading
#             ],
#             data_variables=[
#                 'bus_names',
#                 'bus_types',
#                 'time',
#                 'branch_names',
#                 'voltage',
#                 'S',
#                 'Sf',
#                 'loading',
#                 'losses'
#             ]
#         )
#
#         self.nt = len(time_array)
#         self.m = m
#         self.n = n
#         self.time = time_array
#
#         self.bus_names = bus_names
#
#         self.bus_types = bus_types
#
#         self.branch_names = branch_names
#
#         self.voltage = np.ones((self.nt, n), dtype=float)
#
#         self.S = np.zeros((self.nt, n), dtype=float)
#
#         self.Sf = np.zeros((self.nt, m), dtype=float)
#
#         self.loading = np.zeros((self.nt, m), dtype=float)
#
#         self.losses = np.zeros((self.nt, m), dtype=float)
#
#     def apply_new_time_series_rates(self, nc: NumericalCircuit):
#         rates = nc.Rates.T
#         self.loading = self.Sf / (rates + 1e-9)
#
#     def get_results_dict(self):
#         """
#         Returns a dictionary with the results sorted in a dictionary
#         :return: dictionary of 2D numpy arrays (probably of complex numbers)
#         """
#         data = {
#             'V': self.voltage.tolist(),
#             'P': self.S.real.tolist(),
#             'Q': self.S.imag.tolist(),
#             'Sbr_real': self.Sf.real.tolist(),
#             'Sbr_imag': self.Sf.imag.tolist(),
#             'loading': np.abs(self.loading).tolist()
#         }
#         return data
#
#     def mdl(self, result_type: ResultTypes) -> ResultsTable:
#         """
#         Get ResultsModel instance
#         :param result_type:
#         :return: ResultsModel instance
#         """
#
#         if result_type == ResultTypes.BusActivePower:
#             labels = self.bus_names
#             data = self.S
#             y_label = '(MW)'
#             title = 'Bus active power '
#
#         elif result_type == ResultTypes.BranchActivePowerFrom:
#             labels = self.branch_names
#             data = self.Sf.real
#             y_label = '(MW)'
#             title = 'Branch power '
#
#         elif result_type == ResultTypes.BranchLoading:
#             labels = self.branch_names
#             data = self.loading * 100
#             y_label = '(%)'
#             title = 'Branch loading '
#
#         elif result_type == ResultTypes.BranchLosses:
#             labels = self.branch_names
#             data = self.losses
#             y_label = '(MVA)'
#             title = 'Branch losses'
#
#         elif result_type == ResultTypes.BusVoltageModule:
#             labels = self.bus_names
#             data = self.voltage
#             y_label = '(p.u.)'
#             title = 'Bus voltage'
#
#         else:
#             raise Exception('Result type not understood:' + str(result_type))
#
#         if self.time is not None:
#             index = self.time
#         else:
#             index = list(range(data.shape[0]))
#
#         # assemble model
#         return ResultsTable(
#             data=data,
#             index=index,
#             columns=labels,
#             title=title,
#             ylabel=y_label,
#             units=y_label
#         )
#
#
# class LinearAnalysisTimeSeries(TimeSeriesDriverTemplate):
#     name = 'Linear analysis time series'
#     def __init__(
#             self,
#             grid: MultiCircuit,
#             options: LinearAnalysisOptions,
#             start_: int = 0,
#             end_: Union[int, None] = None,
#             use_clustering: bool = False,
#     ):
#         """
#         TimeSeries constructor
#         :param grid: MultiCircuit instance
#         :param options: LinearAnalysisOptions instance
#         :param start_: Integer. First time index to consider
#         :param end_: Integer. Last time index to consider. None for the last one.
#         :param use_clustering: Boolean. True to cluster time indices
#         """
#         """
#         TimeSeries constructor
#         @param grid: MultiCircuit instance
#         @param options: LinearAnalysisOptions instance
#         """
#         TimeSeriesDriverTemplate.__init__(
#             self,
#             grid=grid,
#             start_=start_,
#             end_=end_,
#             use_clustering=use_clustering,
#         )
#
#         self.options = options
#
#         self.results: LinearAnalysisTimeSeriesResults = None
#
#         self.ptdf_driver = LinearAnalysisMultiCircuit(
#             grid=self.grid,
#             distributed_slack=self.options.distribute_slack
#         )
#
#     tpe = SimulationTypes.LinearAnalysis_TS_run
#
#     def get_steps(self):
#         """
#         Get time steps list of strings
#         """
#
#         return [l.strftime('%d-%m-%Y %H:%M') for l in self.indices]
#
#     def run(self):
#         """
#         Run the time series simulation
#         @return:
#         """
#         self.__cancel__ = False
#         a = time.time()
#
#         if self.end_ is None:
#             self.end_ = len(self.grid.time_profile)
#         time_indices = np.arange(self.start_, self.end_ + 1)
#
#         ts_numeric_circuit = compile_numerical_circuit_at(self.grid)
#         self.results = LinearAnalysisTimeSeriesResults(
#             n=ts_numeric_circuit.nbus,
#             m=ts_numeric_circuit.nbr,
#             time_array=ts_numeric_circuit.time_array[time_indices],
#             bus_names=ts_numeric_circuit.bus_names,
#             bus_types=ts_numeric_circuit.bus_types,
#             branch_names=ts_numeric_circuit.branch_names
#         )
#
#         self.indices = pd.to_datetime(ts_numeric_circuit.time_array[time_indices])
#
#         self.progress_text.emit('Computing PTDF...')
#         linear_analysis = LinearAnalysisTimeSeries(
#             grid=self.grid,
#             options=self.options,
#             start_=self.start_,
#             end_=self.end_,
#             use_clustering=
#         )
#
#         linear_analysis = LinearAnalysisMultiCircuit(
#             grid=self.grid,
#             distributed_slack=self.options.distribute_slack,
#             correct_values=self.options.correct_values,
#         )
#         linear_analysis.run()
#
#         self.progress_text.emit('Computing branch flows...')
#
#         Pbus_0 = ts_numeric_circuit.Sbus.real[:, time_indices]
#         self.results.Sf = linear_analysis.get_flows_time_series(Pbus_0)
#
#         # compute post process
#         self.results.loading = self.results.Sf / (ts_numeric_circuit.Rates[:, time_indices].T + 1e-9)
#         self.results.S = Pbus_0.T
#
#         self.elapsed = time.time() - a
#
