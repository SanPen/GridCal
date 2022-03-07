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
from GridCal.Engine.basic_structures import MIPSolvers
from GridCal.Engine.Core.time_series_opf_data import OpfTimeCircuit
from GridCal.Engine.Simulations.OPF.opf_templates import OpfTimeSeries


class OpfSimpleTimeSeries(OpfTimeSeries):

    def __init__(self, numerical_circuit: OpfTimeCircuit, start_idx, end_idx, solver_type: MIPSolvers = MIPSolvers.CBC,
                 text_prog=None, prog_func=None):
        """
        DC time series linear optimal power flow
        :param numerical_circuit: NumericalCircuit instance
        :param start_idx: start index of the time series
        :param end_idx: end index of the time series
        :param solver_type: MIP solver_type to use
        :param batteries_energy_0: initial state of the batteries, if None the default values are taken
        """
        OpfTimeSeries.__init__(self, numerical_circuit=numerical_circuit, start_idx=start_idx, end_idx=end_idx,
                               solver_type=solver_type)

        self.text_prog = text_prog

        self.prog_func = prog_func

        # build the formulation
        self.problem = None

    def solve(self, msg=False):
        """

        :param msg:
        :return:
        """
        nc = self.numerical_circuit

        # general indices
        n = nc.nbus
        m = nc.nbr
        ng = nc.ngen
        nb = nc.nbatt
        nl = nc.nload
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
        Pg_max = nc.generator_pmax / Sbase
        Pg_min = nc.generator_pmin / Sbase
        P_profile = nc.generator_p[a:b, :] / Sbase
        cost_g = nc.generator_cost[a:b, :]
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
                self.prog_func((i+1) / nt * 100.0)

        # Assign variables to keep
        # transpose them to be in the format of GridCal: time, device
        self.theta = theta
        self.Pg = Pg
        self.Pb = Pb
        self.Pl = Pl
        self.E = E

        self.Pinj = self.numerical_circuit.Sbus.transpose().real
        self.hvdc_flow = np.zeros((nt, self.numerical_circuit.nhvdc))
        self.hvdc_slacks = np.zeros((nt, self.numerical_circuit.nhvdc))
        self.phase_shift = np.zeros((nt, m))

        self.load_shedding = np.zeros((nt, nl))
        self.s_from = np.zeros((nt, m))
        self.s_to = np.zeros((nt, m))
        self.overloads = np.zeros((nt, m))
        self.rating = nc.branch_rates[a:b, :] / Sbase
        self.nodal_restrictions = np.zeros((nt, n))

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
        return self.s_from / self.rating.T

    def get_branch_power_from(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.s_from * self.numerical_circuit.Sbase

    def get_battery_power(self):
        """
        return the battery dispatch (time, device)
        :return: 2D array
        """
        return self.Pb * self.numerical_circuit.Sbase

    def get_battery_energy(self):
        """
        return the battery energy (time, device)
        :return: 2D array
        """
        return self.E * self.numerical_circuit.Sbase

    def get_generator_power(self):
        """
        return the generator dispatch (time, device)
        :return: 2D array
        """
        return self.Pg * self.numerical_circuit.Sbase

    def get_load_shedding(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.load_shedding * self.numerical_circuit.Sbase

    def get_load_power(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.Pl * self.numerical_circuit.Sbase

    def get_shadow_prices(self):
        """
        Extract values fro the 2D array of LP variables
        :return: 2D numpy array
        """
        return self.nodal_restrictions


if __name__ == '__main__':

    from GridCal.Engine import *

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'

    main_circuit = FileOpen(fname).open()

    # get the power flow options from the GUI
    solver = SolverType.Simple_OPF
    mip_solver = MIPSolvers.CBC
    grouping = TimeGrouping.Daily
    pf_options = PowerFlowOptions()

    options = OptimalPowerFlowOptions(solver=solver,
                                      time_grouping=grouping,
                                      mip_solver=mip_solver,
                                      power_flow_options=pf_options)

    start = 0
    end = len(main_circuit.time_profile)

    # create the OPF time series instance
    # if non_sequential:
    optimal_power_flow_time_series = OptimalPowerFlowTimeSeries(grid=main_circuit,
                                                                options=options,
                                                                start_=start,
                                                                end_=end)

    optimal_power_flow_time_series.run()

    v = optimal_power_flow_time_series.results.voltage
    print('Angles\n', np.angle(v))

    l = optimal_power_flow_time_series.results.loading
    print('Branch loading\n', l)

    g = optimal_power_flow_time_series.results.generator_power
    print('Gen power\n', g)

    pr = optimal_power_flow_time_series.results.shadow_prices
    print('Nodal prices \n', pr)

    import pandas as pd
    pd.DataFrame(optimal_power_flow_time_series.results.loading).to_excel('opf_loading.xlsx')