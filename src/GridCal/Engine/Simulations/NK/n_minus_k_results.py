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
import numpy as np
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Gui.GuiFunctions import ResultsModel


class NMinusKResults:

    def __init__(self, n, m, bus_names, branch_names, bus_types):
        """
        TimeSeriesResults constructor
        @param n: number of buses
        @param m: number of branches
        @param nt: number of time steps
        """

        self.name = 'N-1'

        self.bus_types = np.zeros(n, dtype=int)

        self.branch_names = branch_names

        self.bus_names = bus_names

        self.bus_types = bus_types

        self.voltage = np.ones((m, n), dtype=complex)

        self.S = np.zeros((m, n), dtype=complex)

        self.Sbranch = np.zeros((m, m), dtype=complex)

        self.loading = np.zeros((m, m), dtype=complex)

        self.otdf = np.zeros((m, m))

        self.available_results = [ResultTypes.OTDF,
                                  ResultTypes.BusActivePower,
                                  ResultTypes.BranchActivePowerFrom,
                                  ResultTypes.BranchLoading]

    def get_steps(self):
        return

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
                'loading': np.abs(self.loading).tolist()}
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

    def mdl(self, result_type: ResultTypes):
        """
        Plot the results
        :param result_type:
        :return:
        """

        index = self.branch_names

        if result_type == ResultTypes.BusVoltageModule:
            data = np.abs(self.voltage)
            y_label = '(p.u.)'
            title = 'Bus voltage '
            labels = self.bus_names
            # index = self.branch_names

        elif result_type == ResultTypes.BusVoltageAngle:
            data = np.angle(self.voltage, deg=True)
            y_label = '(Deg)'
            title = 'Bus voltage '
            labels = self.bus_names
            # index = self.branch_names

        elif result_type == ResultTypes.BusActivePower:
            data = self.S.real
            y_label = '(MW)'
            title = 'Bus active power '
            labels = self.bus_names
            # index = self.branch_names

        elif result_type == ResultTypes.BranchActivePowerFrom:
            data = self.Sbranch.real
            y_label = 'MW'
            title = 'Branch active power '
            labels = ['# ' + x for x in self.branch_names]
            # index = self.branch_names

        elif result_type == ResultTypes.BranchLoading:
            data = self.loading.real * 100
            y_label = '(%)'
            title = 'Branch loading '
            labels = ['# ' + x for x in self.branch_names]
            # index = self.branch_names

        elif result_type == ResultTypes.OTDF:
            data = self.otdf
            y_label = 'Per unit'
            labels = ['# ' + x for x in self.branch_names]

            title = 'OTDF'
        else:
            raise Exception('Result type not understood:' + str(result_type))

        # assemble model
        mdl = ResultsModel(data=data,
                           index=index,
                           columns=labels,
                           title=title,
                           ylabel=y_label)
        return mdl

