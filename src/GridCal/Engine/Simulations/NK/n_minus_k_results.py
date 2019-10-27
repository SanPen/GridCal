# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import json
import pandas as pd
import numpy as np
import time
import multiprocessing
from matplotlib import pyplot as plt

from PySide2.QtCore import QThread, Signal

from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Gui.GuiFunctions import ResultsModel


class NMinusKResults(PowerFlowResults):

    def __init__(self, n, m, nt, time_array=None, states=None):
        """
        TimeSeriesResults constructor
        @param n: number of buses
        @param m: number of branches
        @param nt: number of time steps
        """
        PowerFlowResults.__init__(self)

        self.name = 'N-1'

        self.nt = nt
        self.m = m
        self.n = n

        self.time = time_array

        self.states = states

        self.bus_types = np.zeros(n, dtype=int)

        self.branch_names = None

        if nt > 0:
            self.voltage = np.zeros((nt, n), dtype=complex)

            self.S = np.zeros((nt, n), dtype=complex)

            self.Sbranch = np.zeros((nt, m), dtype=complex)

            self.Ibranch = np.zeros((nt, m), dtype=complex)

            self.Vbranch = np.zeros((nt, m), dtype=complex)

            self.loading = np.zeros((nt, m), dtype=complex)

            self.losses = np.zeros((nt, m), dtype=complex)

            self.flow_direction = np.zeros((nt, m), dtype=float)

            self.error = np.zeros(nt)

            self.converged = np.ones(nt, dtype=bool)  # guilty assumption

            self.overloads = [None] * nt

            self.overvoltage = [None] * nt

            self.undervoltage = [None] * nt

            self.overloads_idx = [None] * nt

            self.overvoltage_idx = [None] * nt

            self.undervoltage_idx = [None] * nt

            self.buses_useful_for_storage = [None] * nt

        else:
            self.voltage = None

            self.S = None

            self.Sbranch = None

            self.Ibranch = None

            self.Vbranch = None

            self.loading = None

            self.losses = None

            self.flow_direction = None

            self.error = None

            self.converged = None

            self.overloads = None

            self.overvoltage = None

            self.undervoltage = None

            self.overloads_idx = None

            self.overvoltage_idx = None

            self.undervoltage_idx = None

            self.buses_useful_for_storage = None

        self.otdf = np.zeros((m, m))

        self.available_results = [ResultTypes.OTDF,
                                  ResultTypes.BusVoltageModule,
                                  ResultTypes.BusVoltageAngle,
                                  ResultTypes.BusActivePower,
                                  ResultTypes.BusReactivePower,
                                  ResultTypes.BranchPower,
                                  ResultTypes.BranchCurrent,
                                  ResultTypes.BranchLoading,
                                  ResultTypes.BranchLosses,
                                  ResultTypes.BranchVoltage,
                                  ResultTypes.BranchAngles,
                                  ResultTypes.OTDFSimulationError]

    def set_at(self, t, results: PowerFlowResults):
        """
        Set the results at the step t
        @param t: time index
        @param results: PowerFlowResults instance
        """

        self.voltage[t, :] = results.voltage

        self.S[t, :] = results.Sbus

        self.Sbranch[t, :] = results.Sbranch

        self.Ibranch[t, :] = results.Ibranch

        self.Vbranch[t, :] = results.Vbranch

        self.loading[t, :] = results.loading

        self.losses[t, :] = results.losses

        self.flow_direction[t, :] = results.flow_direction

        self.error[t] = max(results.error)

        self.converged[t] = min(results.converged)

        self.overloads[t] = results.overloads

        self.overvoltage[t] = results.overvoltage

        self.undervoltage[t] = results.undervoltage

        self.overloads_idx[t] = results.overloads_idx

        self.overvoltage_idx[t] = results.overvoltage_idx

        self.undervoltage_idx[t] = results.undervoltage_idx

        self.buses_useful_for_storage[t] = results.buses_useful_for_storage

    def get_steps(self):
        return

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

    def apply_from_island(self, results, b_idx, br_idx, t_index, grid_idx):
        """
        Apply results from another island circuit to the circuit results represented here
        @param results: PowerFlowResults
        @param b_idx: bus original indices
        @param br_idx: branch original indices
        @return:
        """

        # bus results
        if self.voltage.shape == results.voltage.shape:
            self.voltage = results.voltage
            self.S = results.S
        else:
            self.voltage[np.ix_(t_index, b_idx)] = results.voltage
            self.S[np.ix_(t_index, b_idx)] = results.S

        # branch results
        if self.Sbranch.shape == results.Sbranch.shape:
            self.Sbranch = results.Sbranch

            self.Ibranch = results.Ibranch

            self.Vbranch = results.Vbranch

            self.loading = results.loading

            self.losses = results.losses

            self.flow_direction = results.flow_direction
        else:
            self.Sbranch[np.ix_(t_index, br_idx)] = results.Sbranch

            self.Ibranch[np.ix_(t_index, br_idx)] = results.Ibranch

            self.Vbranch[np.ix_(t_index, br_idx)] = results.Vbranch

            self.loading[np.ix_(t_index, br_idx)] = results.loading

            self.losses[np.ix_(t_index, br_idx)] = results.losses

            self.flow_direction[np.ix_(t_index, br_idx)] = results.flow_direction

        if (results.error > self.error[t_index]).any():
            self.error[t_index] += results.error

        self.converged[t_index] = self.converged[t_index] * results.converged

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'Vm': np.abs(self.voltage).tolist(),
                'Va': np.angle(self.voltage).tolist(),
                'P': self.S.real.tolist(),
                'Q': self.S.imag.tolist(),
                'Sbr_real': self.Sbranch.real.tolist(),
                'Sbr_imag': self.Sbranch.imag.tolist(),
                'Ibr_real': self.Ibranch.real.tolist(),
                'Ibr_imag': self.Ibranch.imag.tolist(),
                'loading': np.abs(self.loading).tolist(),
                'losses': np.abs(self.losses).tolist()}
        return data

    def save(self, fname):
        """
        Export as json
        """

        with open(fname, "wb") as output_file:
            json_str = json.dumps(self.get_results_dict())
            output_file.write(json_str)

    def analyze(self):
        """
        Analyze the results
        @return:
        """
        branch_overload_frequency = np.zeros(self.m)
        bus_undervoltage_frequency = np.zeros(self.n)
        bus_overvoltage_frequency = np.zeros(self.n)
        buses_selected_for_storage_frequency = np.zeros(self.n)
        for i in range(self.nt):
            branch_overload_frequency[self.overloads_idx[i]] += 1
            bus_undervoltage_frequency[self.undervoltage_idx[i]] += 1
            bus_overvoltage_frequency[self.overvoltage_idx[i]] += 1
            buses_selected_for_storage_frequency[self.buses_useful_for_storage[i]] += 1

        return branch_overload_frequency, bus_undervoltage_frequency, bus_overvoltage_frequency, \
                buses_selected_for_storage_frequency

    def mdl(self, result_type: ResultTypes, indices=None, names=None):
        """
        Plot the results
        :param result_type:
        :param ax:
        :param indices:
        :param names:
        :return:
        """

        if indices is None:
            indices = np.array(range(len(names)))

        if len(indices) > 0:

            labels = names[indices]

            if result_type == ResultTypes.BusVoltageModule:
                data = np.abs(self.voltage[indices + 1])
                y_label = '(p.u.)'
                title = 'Bus voltage '

            elif result_type == ResultTypes.BusVoltageAngle:
                data = np.angle(self.voltage[indices + 1], deg=True)
                y_label = '(Deg)'
                title = 'Bus voltage '

            elif result_type == ResultTypes.BusActivePower:
                data = self.S[indices + 1].real
                y_label = '(MW)'
                title = 'Bus active power '

            elif result_type == ResultTypes.BusReactivePower:
                data = self.S[indices + 1].imag
                y_label = '(MVAr)'
                title = 'Bus reactive power '

            elif result_type == ResultTypes.BranchPower:
                data = self.Sbranch[indices + 1]
                y_label = '(MVA)'
                title = 'Branch power '

            elif result_type == ResultTypes.BranchCurrent:
                data = self.Ibranch[indices + 1]
                y_label = '(kA)'
                title = 'Branch current '

            elif result_type == ResultTypes.BranchLoading:
                data = self.loading[indices + 1] * 100
                y_label = '(%)'
                title = 'Branch loading '

            elif result_type == ResultTypes.BranchLosses:
                data = self.losses[indices + 1]
                y_label = '(MVA)'
                title = 'Branch losses'

            elif result_type == ResultTypes.BranchVoltage:
                data = np.abs(self.Vbranch[indices + 1])
                y_label = '(p.u.)'
                title = result_type.value[0]

            elif result_type == ResultTypes.BranchAngles:
                data = np.angle(self.Vbranch[indices + 1], deg=True)
                y_label = '(deg)'
                title = result_type.value[0]

            elif result_type == ResultTypes.BatteryPower:
                data = np.zeros_like(self.losses[indices + 1])
                y_label = '$\Delta$ (MVA)'
                title = 'Battery power'

            elif result_type == ResultTypes.OTDFSimulationError:
                data = self.error[indices + 1]
                y_label = 'Per unit power'
                labels = [y_label]
                title = 'Error'

            elif result_type == ResultTypes.OTDF:
                data = self.otdf[indices, :]
                y_label = 'Per unit'
                labels = [y_label]
                title = 'OTDF'

                # assemble model
                mdl = ResultsModel(data=data, index=self.branch_names[indices],
                                   columns=self.branch_names, title=title, ylabel=y_label)
                return mdl
            else:
                raise Exception('Result type not understood:' + str(result_type))

            index = self.branch_names[indices]

            # assemble model
            mdl = ResultsModel(data=data, index=index, columns=labels, title=title, ylabel=y_label)
            return mdl

        else:
            return None
