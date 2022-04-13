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
import numpy as np
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Simulations.results_template import ResultsTemplate


class ContingencyAnalysisResults(ResultsTemplate):

    def __init__(self, nbus, nbr, bus_names, branch_names, bus_types):
        """
        TimeSeriesResults constructor
        @param nbus: number of buses
        @param nbr: number of branches
        """
        ResultsTemplate.__init__(self,
                                 name='Contingency Analysis Results',
                                 available_results=[ResultTypes.OTDF,
                                                    ResultTypes.BusActivePower,
                                                    ResultTypes.BranchActivePowerFrom,
                                                    ResultTypes.BranchLoading],
                                 data_variables=['bus_types',
                                                 'branch_names',
                                                 'bus_names',
                                                 'voltage',
                                                 'S',
                                                 'Sf',
                                                 'loading',
                                                 'otdf'])

        self.branch_names = branch_names

        self.bus_names = bus_names

        self.bus_types = bus_types

        self.voltage = np.ones((nbr, nbus), dtype=complex)

        self.S = np.zeros((nbr, nbus), dtype=complex)

        self.Sf = np.zeros((nbr, nbr), dtype=complex)

        self.loading = np.zeros((nbr, nbr), dtype=complex)

        self.otdf = np.zeros((nbr, nbr))

    def apply_new_rates(self, nc: "SnapshotData"):
        rates = nc.Rates
        self.loading = self.Sf / (rates + 1e-9)

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

            title = 'LODF'
        else:
            raise Exception('Result type not understood:' + str(result_type))

        # assemble model
        mdl = ResultsTable(data=data,
                           index=index,
                           columns=labels,
                           title=title,
                           ylabel=y_label)
        return mdl

