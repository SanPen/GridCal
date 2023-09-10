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

import json
import pandas as pd
import numpy as np
from typing import Union
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCalEngine.Simulations.result_types import ResultTypes
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Core.DataStructures.numerical_circuit import NumericalCircuit


class PowerFlowTimeSeriesResults(PowerFlowResults):

    def __init__(
            self,
            n: int,
            m: int,
            n_hvdc: int,
            bus_names: np.ndarray,
            branch_names: np.ndarray,
            hvdc_names: np.ndarray,
            time_array: np.ndarray,
            bus_types: np.ndarray,
            area_names: Union[np.ndarray, None] = None,
            clustering_results=None):
        """
        TimeSeriesResults constructor
        :param n: number of buses
        :param m: number of Branches
        :param n_hvdc:
        :param bus_names:
        :param branch_names:
        :param hvdc_names:
        :param time_array:
        :param bus_types:
        """
        PowerFlowResults.__init__(
            self,
            n=n,
            m=m,
            n_hvdc=n_hvdc,
            bus_names=bus_names,
            branch_names=branch_names,
            hvdc_names=hvdc_names,
            bus_types=bus_types,
            area_names=area_names,
            clustering_results=clustering_results
        )

        self.data_variables.append('time')  # this is missing from the base class

        # results available (different from the base class)
        self.available_results = {
            ResultTypes.BusResults: [
                ResultTypes.BusVoltageModule,
                ResultTypes.BusVoltageAngle,
                ResultTypes.BusActivePower,
                ResultTypes.BusReactivePower
            ],
            ResultTypes.BranchResults: [
                ResultTypes.BranchActivePowerFrom,
                ResultTypes.BranchReactivePowerFrom,
                ResultTypes.BranchLoading,
                ResultTypes.BranchActiveLosses,
                ResultTypes.BranchReactiveLosses,
                ResultTypes.BranchActiveLossesPercentage,
                ResultTypes.BranchVoltage,
                ResultTypes.BranchAngles
            ],
            ResultTypes.HvdcResults: [
                ResultTypes.HvdcLosses,
                ResultTypes.HvdcPowerFrom,
                ResultTypes.HvdcPowerTo
            ],
            ResultTypes.AreaResults: [
                ResultTypes.InterAreaExchange,
                ResultTypes.ActivePowerFlowPerArea,
                ResultTypes.LossesPerArea,
                ResultTypes.LossesPercentPerArea
            ],
            ResultTypes.InfoResults: [
                ResultTypes.SimulationError
            ]
        }

        self.name = 'Time series'
        self.nt = len(time_array)
        self.m = m
        self.n = n

        # this is from the template
        self.time_array = time_array

        self.bus_types = np.zeros(n, dtype=int)

        self.voltage = np.zeros((self.nt, n), dtype=complex)

        self.S = np.zeros((self.nt, n), dtype=complex)

        self.Sf = np.zeros((self.nt, m), dtype=complex)

        self.St = np.zeros((self.nt, m), dtype=complex)

        self.Vbranch = np.zeros((self.nt, m), dtype=complex)

        self.loading = np.zeros((self.nt, m), dtype=complex)

        self.losses = np.zeros((self.nt, m), dtype=complex)

        self.hvdc_losses = np.zeros((self.nt, self.n_hvdc))

        self.hvdc_Pf = np.zeros((self.nt, self.n_hvdc))

        self.hvdc_Pt = np.zeros((self.nt, self.n_hvdc))

        self.hvdc_loading = np.zeros((self.nt, self.n_hvdc))

        self.error_values = np.zeros(self.nt)

        self.converged_values = np.ones(self.nt, dtype=bool)  # guilty assumption

    def apply_new_time_series_rates(self, nc: NumericalCircuit):
        """
        Recompute the loading with new rates
        :param nc: NumericalCircuit instance
        """
        self.loading = self.Sf / (nc.rates + 1e-9)

    def set_at(self, t, results: PowerFlowResults):
        """
        Set the results at the step t
        @param t: time index
        @param results: PowerFlowResults instance
        """

        self.voltage[t, :] = results.voltage

        self.S[t, :] = results.Sbus

        self.Sf[t, :] = results.Sf
        self.St[t, :] = results.St

        self.Vbranch[t, :] = results.Vbranch

        self.loading[t, :] = results.loading

        self.losses[t, :] = results.losses

        self.error_values[t] = results.error

        self.converged_values[t] = results.converged

    @staticmethod
    def merge_if(df, arr, ind, cols):
        """

        @param df:
        @param arr:
        @param ind:
        @param cols:
        @return:
        """
        obj = pd.DataFrame(data=arr, index=ind, columns=cols)
        if df is None:
            df = obj
        else:
            df = pd.concat([df, obj], axis=1)

        return df

    def apply_from_island(
            self,
            results: "PowerFlowResults",
            b_idx: np.ndarray,
            br_idx: np.ndarray,
            t_index: np.ndarray,
            grid_idx: np.ndarray
    ):
        """
        Apply results from another island circuit to the circuit results represented here
        :param results: PowerFlowResults
        :param b_idx: bus original indices
        :param br_idx: branch original indices
        :param t_index:
        :param grid_idx:
        :return:
        """

        # bus results
        if self.voltage.shape == results.voltage.shape:
            self.voltage = results.voltage
            self.S = results.S
        elif self.voltage.shape[0] == results.voltage.shape[0]:
            self.voltage[:, b_idx] = results.voltage
            self.S[:, b_idx] = results.S
        else:
            self.voltage[np.ix_(t_index, b_idx)] = results.voltage
            self.S[np.ix_(t_index, b_idx)] = results.S

        # branch results
        if self.Sf.shape == results.Sf.shape:
            self.Sf = results.Sf
            self.St = results.St

            self.Vbranch = results.Vbranch

            self.loading = results.loading

            self.losses = results.losses

            if (results.error_values > self.error_values).any():
                self.error_values += results.error_values

            self.converged_values = self.converged_values * results.converged_values

        elif self.Sf.shape[0] == results.Sf.shape[0]:
            self.Sf[:, br_idx] = results.Sf
            self.St[:, br_idx] = results.St

            self.Vbranch[:, br_idx] = results.Vbranch

            self.loading[:, br_idx] = results.loading

            self.losses[:, br_idx] = results.losses

            if (results.error_values > self.error_values).any():
                self.error_values += results.error_values

            self.converged_values = self.converged_values * results.converged_values
        else:
            self.Sf[np.ix_(t_index, br_idx)] = results.Sf
            self.St[np.ix_(t_index, br_idx)] = results.St

            self.Vbranch[np.ix_(t_index, br_idx)] = results.Vbranch

            self.loading[np.ix_(t_index, br_idx)] = results.loading

            self.losses[np.ix_(t_index, br_idx)] = results.losses

            if (results.error_values > self.error_values[t_index]).any():
                self.error_values[t_index] += results.error_values

            self.converged_values[t_index] = self.converged_values[t_index] * results.converged_values

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'Vm': np.abs(self.voltage).tolist(),
                'Va': np.angle(self.voltage).tolist(),
                'P': self.S.real.tolist(),
                'Q': self.S.imag.tolist(),
                'Sf_real': self.Sf.real.tolist(),
                'Sf_imag': self.Sf.imag.tolist(),
                'loading': np.abs(self.loading).tolist(),
                'losses_real': np.real(self.losses).tolist(),
                'losses_imag': np.imag(self.losses).tolist()}
        return data

    def to_json(self, fname):
        """
        Export as json
        """

        with open(fname, "wb") as output_file:
            json_str = json.dumps(self.get_results_dict())
            output_file.write(json_str)

    def get_ordered_area_names(self):
        na = len(self.area_names)
        x = [''] * (na * na)
        for i, a in enumerate(self.area_names):
            for j, b in enumerate(self.area_names):
                x[i * na + j] = a + '->' + b
        return x

    def get_inter_area_flows(self):

        na = len(self.area_names)
        nt = len(self.time_array)
        x = np.zeros((nt, na * na), dtype=complex)

        for f, t, flow in zip(self.F, self.T, self.Sf.T):
            a1 = self.bus_area_indices[f]
            a2 = self.bus_area_indices[t]
            if a1 != a2:
                x[:, a1 * na + a2] += flow
                x[:, a2 * na + a1] -= flow

        for f, t, flow in zip(self.hvdc_F, self.hvdc_T, self.hvdc_Pf.T):
            a1 = self.bus_area_indices[f]
            a2 = self.bus_area_indices[t]
            if a1 != a2:
                x[:, a1 * na + a2] += flow
                x[:, a2 * na + a1] -= flow

        return x

    def get_branch_values_per_area(self, branch_values: np.ndarray):

        na = len(self.area_names)
        nt = len(self.time_array)
        x = np.zeros((nt, na * na), dtype=branch_values.dtype)

        for f, t, val in zip(self.F, self.T, branch_values.T):
            a1 = self.bus_area_indices[f]
            a2 = self.bus_area_indices[t]
            x[:, a1 * na + a2] += val

        return x

    def get_hvdc_values_per_area(self, hvdc_values: np.ndarray):

        na = len(self.area_names)
        nt = len(self.time_array)
        x = np.zeros((nt, na * na), dtype=hvdc_values.dtype)

        for f, t, val in zip(self.hvdc_F, self.hvdc_T, hvdc_values.T):
            a1 = self.bus_area_indices[f]
            a2 = self.bus_area_indices[t]
            x[:, a1 * na + a2] += val

        return x

    def mdl(self, result_type: ResultTypes) -> "ResultsTable":
        """

        :param result_type:
        :return:
        """

        if result_type == ResultTypes.BusVoltageModule:
            labels = self.bus_names
            data = np.abs(self.voltage)
            y_label = '(p.u.)'
            title = 'Bus voltage '

        elif result_type == ResultTypes.BusVoltageAngle:
            labels = self.bus_names
            data = np.angle(self.voltage, deg=True)
            y_label = '(Deg)'
            title = 'Bus voltage '

        elif result_type == ResultTypes.BusActivePower:
            labels = self.bus_names
            data = self.S.real
            y_label = '(MW)'
            title = 'Bus active power '

        elif result_type == ResultTypes.BusReactivePower:
            labels = self.bus_names
            data = self.S.imag
            y_label = '(MVAr)'
            title = 'Bus reactive power '

        elif result_type == ResultTypes.BranchPower:
            labels = self.branch_names
            data = self.Sf
            y_label = '(MVA)'
            title = 'Branch power '

        elif result_type == ResultTypes.BranchActivePowerFrom:
            labels = self.branch_names
            data = self.Sf.real
            y_label = '(MW)'
            title = 'Branch power '

        elif result_type == ResultTypes.BranchReactivePowerFrom:
            labels = self.branch_names
            data = self.Sf.imag
            y_label = '(MVAr)'
            title = 'Branch power '

        elif result_type == ResultTypes.BranchLoading:
            labels = self.branch_names
            data = np.abs(self.loading) * 100
            y_label = '(%)'
            title = 'Branch loading '

        elif result_type == ResultTypes.BranchLosses:
            labels = self.branch_names
            data = self.losses
            y_label = '(MVA)'
            title = 'Branch losses'

        elif result_type == ResultTypes.BranchActiveLosses:
            labels = self.branch_names
            data = self.losses.real
            y_label = '(MW)'
            title = 'Branch losses'

        elif result_type == ResultTypes.BranchReactiveLosses:
            labels = self.branch_names
            data = self.losses.imag
            y_label = '(MVAr)'
            title = 'Branch losses'

        elif result_type == ResultTypes.BranchActiveLossesPercentage:
            labels = self.branch_names
            data = np.abs(self.losses.real) / np.abs(self.Sf.real + 1e-20) * 100.0
            y_label = '(%)'
            title = 'Branch losses percentage'

        elif result_type == ResultTypes.BranchVoltage:
            labels = self.branch_names
            data = np.abs(self.Vbranch)
            y_label = '(p.u.)'
            title = result_type.value[0]

        elif result_type == ResultTypes.BranchAngles:
            labels = self.branch_names
            data = np.angle(self.Vbranch, deg=True)
            y_label = '(deg)'
            title = result_type.value[0]

        elif result_type == ResultTypes.BatteryPower:
            labels = self.branch_names
            data = np.zeros_like(self.losses)
            y_label = '$\Delta$ (MVA)'
            title = 'Battery power'

        elif result_type == ResultTypes.SimulationError:
            data = self.error_values.reshape(-1, 1)
            y_label = 'p.u.'
            labels = ['Error']
            title = 'Error'

        elif result_type == ResultTypes.HvdcLosses:
            labels = self.hvdc_names
            data = self.hvdc_losses
            y_label = '(MW)'
            title = result_type.value

        elif result_type == ResultTypes.HvdcPowerFrom:
            labels = self.hvdc_names
            data = self.hvdc_Pf
            y_label = '(MW)'
            title = result_type.value

        elif result_type == ResultTypes.HvdcPowerTo:
            labels = self.hvdc_names
            data = self.hvdc_Pt
            y_label = '(MW)'
            title = result_type.value

        elif result_type == ResultTypes.InterAreaExchange:
            labels = self.get_ordered_area_names()
            data = self.get_inter_area_flows().real
            y_label = '(MW)'
            title = result_type.value[0]

        elif result_type == ResultTypes.LossesPercentPerArea:
            labels = self.get_ordered_area_names()
            Pf = self.get_branch_values_per_area(np.abs(self.Sf.real)) + self.get_hvdc_values_per_area(np.abs(self.hvdc_Pf))
            Pl = self.get_branch_values_per_area(np.abs(self.losses.real)) + self.get_hvdc_values_per_area(np.abs(self.hvdc_losses))

            data = Pl / (Pf + 1e-20) * 100.0
            y_label = '(%)'
            title = result_type.value[0]

        elif result_type == ResultTypes.LossesPerArea:
            labels = self.get_ordered_area_names()
            data = self.get_branch_values_per_area(np.abs(self.losses.real)) + self.get_hvdc_values_per_area(np.abs(self.hvdc_losses))

            y_label = '(MW)'
            title = result_type.value[0]

        elif result_type == ResultTypes.ActivePowerFlowPerArea:
            labels = self.get_ordered_area_names()
            data = self.get_branch_values_per_area(np.abs(self.Sf.real)) + self.get_hvdc_values_per_area(np.abs(self.hvdc_Pf))

            y_label = '(MW)'
            title = result_type.value[0]

        else:
            raise Exception('Result type not understood:' + str(result_type))

        if self.time_array is not None:
            index = pd.to_datetime(self.time_array)
        else:
            index = list(range(data.shape[0]))

        # assemble model
        mdl = ResultsTable(data=data, index=index, columns=labels, title=title, ylabel=y_label, units=y_label)
        return mdl

