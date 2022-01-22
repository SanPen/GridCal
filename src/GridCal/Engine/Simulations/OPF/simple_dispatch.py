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
from GridCal.Engine.Core.snapshot_opf_data import SnapshotOpfData
from GridCal.Engine.Simulations.OPF.opf_templates import Opf
from GridCal.ThirdParty.pulp import *


class OpfSimple(Opf):

    def __init__(self, numerical_circuit: SnapshotOpfData):
        """
        DC time series linear optimal power flow
        :param numerical_circuit: NumericalCircuit instance
        """
        Opf.__init__(self, numerical_circuit=numerical_circuit)

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
        # Pg_min = nc.generator_pmin / Sbase
        # P_profile = nc.generator_power_profile[a:b, :] / Sbase
        # cost_g = nc.generator_cost_profile[a:b, :]
        # enabled_for_dispatch = nc.generator_active_prof

        # load
        Pl = np.zeros(nl)
        Pg = np.zeros(ng)
        Pb = np.zeros(nb)
        E = np.zeros(nb)
        theta = np.zeros(n)

        # generator share:
        Pavail = Pg_max * nc.generator_active
        Gshare = Pavail / Pavail.sum()

        Pl = (nc.load_active * nc.load_s.real) / Sbase

        Pg = Pl.sum() * Gshare

        # Assign variables to keep
        # transpose them to be in the format of GridCal: time, device
        self.theta = theta
        self.Pg = Pg
        self.Pb = Pb
        self.Pl = Pl
        self.E = E

        self.Pinj = self.numerical_circuit.Sbus.transpose().real
        self.hvdc_flow = np.zeros(self.numerical_circuit.nhvdc)
        self.hvdc_slacks = np.zeros(self.numerical_circuit.nhvdc)
        self.phase_shift = np.zeros(m)

        self.load_shedding = np.zeros(nl)
        self.s_from = np.zeros(m)
        self.s_to = np.zeros(m)
        self.overloads = np.zeros(m)
        self.rating = nc.branch_rates / Sbase
        self.nodal_restrictions = np.zeros(n)

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
    from GridCal.Engine.basic_structures import BranchImpedanceMode
    from GridCal.Engine.IO.file_handler import FileOpen
    from GridCal.Engine.Core.snapshot_opf_data import compile_snapshot_opf_circuit

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv (2 islands).gridcal'

    main_circuit = FileOpen(fname).open()

    main_circuit.buses[3].controlled_generators[0].enabled_dispatch = False

    numerical_circuit_ = compile_snapshot_opf_circuit(circuit=main_circuit,
                                                      apply_temperature=False,
                                                      branch_tolerance_mode=BranchImpedanceMode.Specified)

    problem = OpfSimple(numerical_circuit=numerical_circuit_)

    print('Solving...')
    status = problem.solve()

    print("Status:", status)

    v = problem.get_voltage()
    print('Angles\n', np.angle(v))

    l = problem.get_loading()
    print('Branch loading\n', l)

    g = problem.get_generator_power()
    print('Gen power\n', g)

    pr = problem.get_shadow_prices()
    print('Nodal prices \n', pr)

    pass
