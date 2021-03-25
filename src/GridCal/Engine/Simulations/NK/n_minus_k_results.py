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
from GridCal.Engine.Simulations.results_model import ResultsModel


class NMinusKResults:

    def __init__(self, n, m, bus_names, branch_names, bus_types):
        """
        TimeSeriesResults constructor
        @param n: number of buses
        @param m: number of branches
        """

        self.name = 'N-1'

        self.bus_types = np.zeros(n, dtype=int)

        self.branch_names = branch_names

        self.bus_names = bus_names

        self.bus_types = bus_types

        self.voltage = np.ones((m, n), dtype=complex)

        self.S = np.zeros((m, n), dtype=complex)

        self.Sf = np.zeros((m, m), dtype=complex)

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
                'Sbr_real': self.Sf.real.tolist(),
                'Sbr_imag': self.Sf.imag.tolist(),
                'loading': np.abs(self.loading).tolist()}
        return data

    def save(self, fname):
        """
        Export as json
        """
        with open(fname, "w") as output_file:
            json_str = json.dumps(self.get_results_dict())
            output_file.write(json_str)

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
            data = self.Sf.real
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

