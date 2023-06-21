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

"""
This file implements a DC-OPF for time series
That means that solves the OPF problem for a complete time series at once
"""
import numpy as np
from typing import List, Union
from GridCal.Engine.Core.multi_circuit import MultiCircuit


class OpfSimpleTimeSeries:

    def __init__(self,  grid: MultiCircuit,
                 time_indices: List[int],):
        """
        DC time series linear optimal power flow
        :param grid: NumericalCircuit instance
        """

        # build the formulation
        self.grid = grid

        nt = len(time_indices) if len(time_indices) > 0 else 1
        n = grid.get_bus_number()
        nbr = grid.get_branch_number_wo_hvdc()
        ng = grid.get_generators_number()
        nb = grid.get_batteries_number()
        nl = grid.get_calculation_loads_number()
        n_hvdc = grid.get_hvdc_number()

        self.theta = np.zeros((nt, n))
        self.Pinj = np.zeros((nt, n))
        self.nodal_restrictions = np.zeros((nt, n))

        self.Pg = np.zeros((nt, ng))

        self.Pb = np.zeros((nt, nb))
        self.E = np.zeros((nt, nb))

        self.Pl = np.zeros((nt, nl))
        self.load_shedding = np.zeros((nt, nl))

        self.hvdc_flow = np.zeros((nt, n_hvdc))
        self.hvdc_slacks = np.zeros((nt, n_hvdc))

        self.phase_shift = np.zeros((nt, nbr))
        self.s_from = np.zeros((nt, nbr))
        self.s_to = np.zeros((nt, nbr))
        self.overloads = np.zeros((nt, nbr))
        self.rating = grid.get_branch_rates_prof_wo_hvdc() / grid.Sbase

    def solve(self, msg=False):
        """

        :param msg:
        :return:
        """
        nc = self.numerical_circuit

        # general indices
        n = nc.nbus
        m = nc.nelm
        ng = nc.nelm
        nb = nc.nbatt
        nl = nc.nelm
        nt = self.end_idx - self.start_idx
        a = self.start_idx
        b = self.end_idx
        Sbase = nc.Sbase

        # battery
        # Capacity = nc.battery_Enom / Sbase
        # minSoC = nc.battery_min_soc
        # maxSoC = nc.battery_max_soc
        # if batteries_energy_0 is None:
        #     SoC0 = nc.battery_soc_0
        # else:
        #     SoC0 = (batteries_energy_0 / Sbase) / Capacity
        # Pb_max = nc.battery_pmax / Sbase
        # Pb_min = nc.battery_pmin / Sbase
        # Efficiency = (nc.battery_discharge_efficiency + nc.battery_charge_efficiency) / 2.0
        # cost_b = nc.battery_cost_profile[a:b, :].transpose()

        # generator
        Pg_max = nc.pmax / Sbase
        Pg_min = nc.pmin / Sbase
        P_profile = nc.generator_p[a:b, :] / Sbase
        cost_g = nc.cost_1[a:b, :]
        enabled_for_dispatch = nc.generator_active

        # load
        Pl = np.zeros((nt, nl))
        Pg = np.zeros((nt, ng))
        Pb = np.zeros((nt, nb))
        E = np.zeros((nt, nb))
        theta = np.zeros((nt, n))
        for i, t in enumerate(range(a, b)):

            # generator share:
            Pavail = (Pg_max * nc.generator_active[:, t])
            Gshare = Pavail / Pavail.sum()

            Pl[i] = (nc.load_active[:, t] * nc.load_s.real[:, t]) / Sbase

            Pg[i] = Pl[i].sum() * Gshare

            if self.text_prog is not None:
                self.text_prog('Solving ' + str(nc.time_array[t]))
            if self.prog_func is not None:
                self.prog_func((i + 1) / nt * 100.0)

        # Assign variables to keep
        # transpose them to be in the format of GridCal: time, device
        self.theta = theta
        self.Pg = Pg
        self.Pb = Pb
        self.Pl = Pl
        self.E = E

        self.Pinj = self.numerical_circuit.Sbus.transpose().real
        self.hvdc_flow = np.zeros((nt, self.numerical_circuit.nelm))
        self.hvdc_slacks = np.zeros((nt, self.numerical_circuit.nelm))
        self.phase_shift = np.zeros((nt, m))

        self.load_shedding = np.zeros((nt, nl))
        self.s_from = np.zeros((nt, m))
        self.s_to = np.zeros((nt, m))
        self.overloads = np.zeros((nt, m))
        self.rating = nc.branch_rates[a:b, :] / Sbase
        self.nodal_restrictions = np.zeros((nt, n))

        return True

    def get_voltage(self):
        """
        return the complex voltages (time, device)
        :return: 2D array
        """
        return np.ones_like(self.theta) * np.exp(-1j * self.theta)

    def get_overloads(self):
        """
        return the branch overloads (time, device)
        :return: 2D array
        """
        return self.overloads

    def get_loading(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.s_from / (self.rating + 1e-9)

    def get_branch_power_from(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.s_from * self.grid.Sbase

    def get_battery_power(self):
        """
        return the battery dispatch (time, device)
        :return: 2D array
        """
        return self.Pb * self.grid.Sbase

    def get_battery_energy(self):
        """
        return the battery energy (time, device)
        :return: 2D array
        """
        return self.E * self.grid.Sbase

    def get_generator_power(self):
        """
        return the generator dispatch (time, device)
        :return: 2D array
        """
        return self.Pg * self.grid.Sbase

    def get_load_shedding(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.load_shedding * self.grid.Sbase

    def get_load_power(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.Pl * self.grid.Sbase

    def get_shadow_prices(self):
        """
        Extract values fro the 2D array of LP variables
        :return: 2D numpy array
        """
        return self.nodal_restrictions
