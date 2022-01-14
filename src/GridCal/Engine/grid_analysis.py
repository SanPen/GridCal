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
import numpy as np


from GridCal.Engine.Simulations.PowerFlow.time_series_driver import TimeSeriesResults
from GridCal.Engine.Core.time_series_pf_data import TimeCircuit


class TimeSeriesResultsAnalysis:

    def __init__(self, numerical_circuit: TimeCircuit, results: TimeSeriesResults):
        """
        Constructor
        :param numerical_circuit: TimeCircuit instance
        :param results: TimeSeriesResults instance
        """
        self.numerical_circuit = numerical_circuit

        self.res = results

        self.branch_overload_frequency = np.zeros(self.res.m)
        self.bus_under_voltage_frequency = np.zeros(self.res.n)
        self.bus_over_voltage_frequency = np.zeros(self.res.n)

        self.branch_overload_accumulated = np.zeros(self.res.m, dtype=complex)
        self.bus_under_voltage_accumulated = np.zeros(self.res.n, dtype=complex)
        self.bus_over_voltage_accumulated = np.zeros(self.res.n, dtype=complex)

        self.buses_selected_for_storage_frequency = np.zeros(self.res.n)

        self.__run__()

    def __run__(self):
        """
        Run the analysis
        Returns:

        """


        '''
        Optimal storage locations are those nodes where there
        are voltage problems and those nodes receiving the flow
        of current in case of overloads for the time series
        simulation.

            Returns:
        '''

        self.buses_selected_for_storage_frequency = np.zeros(self.res.n)

        rates = self.numerical_circuit.Rates.T

        for t in range(self.res.nt):

            bus_voltage = np.abs(self.res.voltage[t])

            branch_loading = np.abs(self.res.loading[t])

            buses_over = np.where(bus_voltage > self.numerical_circuit.bus_data.Vmax)[0]

            buses_under = np.where(bus_voltage < self.numerical_circuit.bus_data.Vmin)[0]

            branches_over = np.where(branch_loading > 1.0)[0]

            # get the buses from the selected branches
            flow_dir = self.res.Sf[t, branches_over].real

            branches_w_from = np.where(flow_dir > 0)[0]
            branches_w_to = np.where(flow_dir < 0)[0]

            buses_f = self.numerical_circuit.F[branches_w_from]
            buses_t = self.numerical_circuit.T[branches_w_to]

            # branches
            self.branch_overload_frequency[branches_over] += 1
            self.bus_under_voltage_frequency[buses_under] += 1
            self.bus_over_voltage_frequency[buses_over] += 1

            inc_loading = self.res.Sf[t, branches_over] - rates[t, branches_over]
            inc_over = bus_voltage[buses_over] - self.numerical_circuit.bus_data.Vmax[buses_over]
            inc_under = self.numerical_circuit.bus_data.Vmin[buses_under] - bus_voltage[buses_under]

            self.branch_overload_accumulated[branches_over] += inc_loading
            self.bus_under_voltage_accumulated[buses_under] += inc_under
            self.bus_over_voltage_accumulated[buses_over] += inc_over

            # buses for storage
            self.buses_selected_for_storage_frequency[buses_over] += 1
            self.buses_selected_for_storage_frequency[buses_under] += 1
            self.buses_selected_for_storage_frequency[buses_f] += 1
            self.buses_selected_for_storage_frequency[buses_t] += 1
