# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np

from GridCalEngine.Simulations.PowerFlow.power_flow_ts_driver import PowerFlowTimeSeriesResults
from GridCalEngine.Devices.multi_circuit import MultiCircuit


class TimeSeriesResultsAnalysis:
    """
    TimeSeriesResultsAnalysis
    """

    def __init__(self, grid: MultiCircuit, results: PowerFlowTimeSeriesResults):
        """
        Constructor
        :param grid: MultiCircuit instance
        :param results: TimeSeriesResults instance
        """
        self.grid = grid

        self.res = results

        m = results.Sf.shape[1]
        n = results.S.shape[1]

        self.branch_overload_frequency = np.zeros(m)
        self.bus_under_voltage_frequency = np.zeros(n)
        self.bus_over_voltage_frequency = np.zeros(n)

        self.branch_overload_accumulated = np.zeros(m, dtype=complex)
        self.bus_under_voltage_accumulated = np.zeros(n, dtype=complex)
        self.bus_over_voltage_accumulated = np.zeros(n, dtype=complex)

        self.buses_selected_for_storage_frequency = np.zeros(n)

        self.branches_selected_for_reactance_compensation = np.zeros(m)

        self.__run__()

    def __run__(self):
        """
        Run the analysis
        Returns:

        """

        """
        Optimal storage locations are those nodes where there
        are voltage problems and those nodes receiving the flow
        of current in case of overloads for the time series
        simulation.

            Returns:
        """

        nt, n = self.res.S.shape

        self.buses_selected_for_storage_frequency = np.zeros(n)

        Vmax = np.zeros(n)
        Vmin = np.zeros(n)
        for i, bus in enumerate(self.grid.buses):
            Vmax[i] = bus.Vmax
            Vmin[i] = bus.Vmin

        F, T = self.grid.get_branch_FT(add_vsc=False, add_hvdc=False, add_switch=True)

        rates = self.grid.get_branch_rates_prof()

        for t in range(nt):
            bus_voltage = np.abs(self.res.voltage[t])

            branch_loading = np.abs(self.res.loading[t])

            buses_over = np.where(bus_voltage > Vmax)[0]

            buses_under = np.where(bus_voltage < Vmin)[0]

            branches_over = np.where(branch_loading > 1.0)[0]

            # get the buses from the selected Branches
            flow_dir = self.res.Sf[t, branches_over].real

            branches_w_from = np.where(flow_dir > 0)[0]
            branches_w_to = np.where(flow_dir < 0)[0]

            buses_f = F[branches_w_from]
            buses_t = T[branches_w_to]

            # Branches
            self.branch_overload_frequency[branches_over] += 1
            self.bus_under_voltage_frequency[buses_under] += 1
            self.bus_over_voltage_frequency[buses_over] += 1

            inc_loading = self.res.Sf[t, branches_over] - rates[t, branches_over]
            inc_over = bus_voltage[buses_over] - Vmax[buses_over]
            inc_under = Vmin[buses_under] - bus_voltage[buses_under]

            self.branch_overload_accumulated[branches_over] += inc_loading
            self.bus_under_voltage_accumulated[buses_under] += inc_under
            self.bus_over_voltage_accumulated[buses_over] += inc_over

            # buses for storage
            self.buses_selected_for_storage_frequency[buses_over] += 1
            self.buses_selected_for_storage_frequency[buses_under] += 1
            self.buses_selected_for_storage_frequency[buses_f] += 1
            self.buses_selected_for_storage_frequency[buses_t] += 1
