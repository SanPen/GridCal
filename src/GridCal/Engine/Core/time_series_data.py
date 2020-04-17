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

import datetime
import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse import diags, hstack as hstack_s, vstack as vstack_s
from scipy.sparse.linalg import factorized
from scipy.sparse import csc_matrix
from typing import List, Dict

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Simulations.sparse_solve import get_sparse_type
from GridCal.Engine.Core.topology import Graph
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.Simulations.PowerFlow.jacobian_based_power_flow import Jacobian
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCal.Engine.Core.snapshot_data import SnapshotCircuit, SnapshotIsland

sparse = get_sparse_type()


def calc_islands(circuit: "SeriesIsland", bus_active, C_bus_bus, C_branch_bus, C_bus_gen, C_bus_batt,
                 nbus, nbr, time_idx=None, ignore_single_node_islands=False) -> List["SeriesIsland"]:
    """
    Partition the circuit in islands for the designated time intervals
    :param circuit: CalculationInputs instance with all the data regardless of the islands and the branch states
    :param C_bus_bus: bus-bus connectivity matrix
    :param C_branch_bus: branch-bus connectivity matrix
    :param C_bus_gen: gen-bus connectivity matrix
    :param C_bus_batt: battery-bus connectivity matrix
    :param nbus: number of buses
    :param nbr: number of branches
    :param time_idx: array with the time indices where this set of islands belongs to
                    (if None all the time series are kept)
    :param ignore_single_node_islands: Ignore the single node islands
    :return: list of CalculationInputs instances
    """
    # find the islands of the circuit
    g = Graph(C_bus_bus=sp.csc_matrix(C_bus_bus), C_branch_bus=sp.csc_matrix(C_branch_bus), bus_states=bus_active)
    islands = g.find_islands()

    # clear the list of circuits
    calculation_islands = list()

    # find the branches that belong to each island
    island_branches = list()

    if len(islands) > 1:

        # there are islands, pack the islands into sub circuits
        for island_bus_idx in islands:

            if ignore_single_node_islands and len(island_bus_idx) <= 1:
                keep = False
            else:
                keep = True

            if keep:
                # get the branch indices of the island
                island_br_idx = g.get_branches_of_the_island(island_bus_idx)
                island_br_idx = np.sort(island_br_idx)  # sort
                island_branches.append(island_br_idx)

                # indices of batteries and controlled generators that belong to this island
                gen_idx = np.where(C_bus_gen[island_bus_idx, :].sum(axis=0) > 0)[0]
                bat_idx = np.where(C_bus_batt[island_bus_idx, :].sum(axis=0) > 0)[0]

                # Get the island circuit (the bus types are computed automatically)
                # The island original indices are generated within the get_island function
                circuit_island = circuit.get_island(island_bus_idx, island_br_idx, gen_idx, bat_idx)

                circuit_island.trim_profiles(time_idx=time_idx)

                # store the island
                calculation_islands.append(circuit_island)

    else:
        # Only one island

        # compile bus types
        circuit.consolidate()

        # only one island, no need to split anything
        calculation_islands.append(circuit)

        island_bus_idx = np.arange(start=0, stop=nbus, step=1, dtype=int)
        island_br_idx = np.arange(start=0, stop=nbr, step=1, dtype=int)

        # set the indices in the island too
        circuit.original_bus_idx = island_bus_idx
        circuit.original_branch_idx = island_br_idx

        circuit.trim_profiles(time_idx=time_idx)

        # append a list with all the branch indices for completeness
        island_branches.append(island_br_idx)

    # return the list of islands
    return calculation_islands


class SeriesIsland(SnapshotIsland):
    """
    This class represents a SeriesData for a single island
    """

    def __init__(self, nbus, nbr, nhvdc, nvsc, ntime, nbat, nctrlgen, Sbase=100.0):

        SnapshotIsland.__init__(self, nbus, nbr, nhvdc, nvsc, nbat, nctrlgen, Sbase)

        self.ntime = ntime
        self.time_array = None

        self.Ysh_prof = np.zeros((nbus, ntime), dtype=complex)
        self.Sbus_prof = np.zeros((nbus, ntime), dtype=complex)
        self.Ibus_prof = np.zeros((nbus, ntime), dtype=complex)

        self.branch_rates_prof = np.zeros((ntime, nbr))

    def trim_profiles(self, time_idx):
        """
        Trims the profiles with the passed time indices and stores those time indices for later
        :param time_idx: array of time indices
        """
        self.original_time_idx = time_idx

        self.Ysh_prof = self.Ysh_prof[:, time_idx]
        self.Sbus_prof = self.Sbus_prof[:, time_idx]
        self.Ibus_prof = self.Ibus_prof[:, time_idx]
        self.branch_rates_prof = self.branch_rates_prof[time_idx, :]

    def get_island(self, bus_idx, branch_idx, gen_idx, bat_idx) -> "SeriesIsland":
        """
        Get a sub-island
        :param bus_idx: bus indices of the island
        :param branch_idx: branch indices of the island
        :return: CalculationInputs instance
        """
        obj = SeriesIsland(len(bus_idx), len(branch_idx), 0, 0, self.ntime, len(bat_idx), len(gen_idx))

        # remember the island original indices
        obj.original_bus_idx = bus_idx
        obj.original_branch_idx = branch_idx

        obj.Yf = self.Yf[np.ix_(branch_idx, bus_idx)]
        obj.Yt = self.Yt[np.ix_(branch_idx, bus_idx)]
        obj.Ybus = self.Ybus[np.ix_(bus_idx, bus_idx)]
        obj.Yseries = self.Yseries[np.ix_(bus_idx, bus_idx)]
        obj.B1 = self.B1[np.ix_(bus_idx, bus_idx)]
        obj.B2 = self.B2[np.ix_(bus_idx, bus_idx)]

        obj.Ysh = self.Ysh[bus_idx]
        obj.Sbus = self.Sbus[bus_idx]
        obj.Ibus = self.Ibus[bus_idx]
        obj.Vbus = self.Vbus[bus_idx]
        obj.types = self.types[bus_idx]
        obj.Qmin = self.Qmin[bus_idx]
        obj.Qmax = self.Qmax[bus_idx]
        obj.Vmin = self.Vmin[bus_idx]
        obj.Vmax = self.Vmax[bus_idx]
        obj.Sinstalled = self.Sinstalled[bus_idx]

        obj.F = self.F[branch_idx]
        obj.T = self.T[branch_idx]
        obj.branch_rates = self.branch_rates[branch_idx]
        obj.branch_rates_prof = self.branch_rates_prof[:, branch_idx]
        obj.bus_names = self.bus_names[bus_idx]
        obj.branch_names = self.branch_names[branch_idx]

        obj.Ysh_prof = self.Ysh_prof[bus_idx, :]
        obj.Sbus_prof = self.Sbus_prof[bus_idx, :]
        obj.Ibus_prof = self.Ibus_prof[bus_idx, :]

        obj.C_branch_bus_f = self.C_branch_bus_f[np.ix_(branch_idx, bus_idx)]
        obj.C_branch_bus_t = self.C_branch_bus_t[np.ix_(branch_idx, bus_idx)]

        obj.C_bus_load = self.C_bus_load[bus_idx, :]
        obj.C_bus_batt = self.C_bus_batt[bus_idx, :]
        obj.C_bus_sta_gen = self.C_bus_sta_gen[bus_idx, :]
        obj.C_bus_gen = self.C_bus_gen[bus_idx, :]
        obj.C_bus_shunt = self.C_bus_shunt[bus_idx, :]

        obj.is_bus_to_regulated = self.is_bus_to_regulated[branch_idx]
        obj.tap_position = self.tap_position[branch_idx]
        obj.min_tap = self.min_tap[branch_idx]
        obj.max_tap = self.max_tap[branch_idx]
        obj.tap_inc_reg_up = self.tap_inc_reg_up[branch_idx]
        obj.tap_inc_reg_down = self.tap_inc_reg_down[branch_idx]
        obj.vset = self.vset[branch_idx]
        obj.tap_ang = self.tap_ang[branch_idx]
        obj.tap_mod = self.tap_mod[branch_idx]

        obj.Ys = self.Ys
        obj.GBc = self.GBc
        obj.tap_f = self.tap_f
        obj.tap_t = self.tap_t

        obj.controlled_gen_pmin = self.controlled_gen_pmin[gen_idx]
        obj.controlled_gen_pmax = self.controlled_gen_pmax[gen_idx]
        obj.controlled_gen_enabled = self.controlled_gen_enabled[gen_idx]
        obj.controlled_gen_dispatchable = self.controlled_gen_dispatchable[gen_idx]
        obj.battery_pmin = self.battery_pmin[bat_idx]
        obj.battery_pmax = self.battery_pmax[bat_idx]
        obj.battery_Enom = self.battery_Enom[bat_idx]
        obj.battery_soc_0 = self.battery_soc_0[bat_idx]
        obj.battery_discharge_efficiency = self.battery_discharge_efficiency[bat_idx]
        obj.battery_charge_efficiency = self.battery_charge_efficiency[bat_idx]
        obj.battery_min_soc = self.battery_min_soc[bat_idx]
        obj.battery_max_soc = self.battery_max_soc[bat_idx]
        obj.battery_enabled = self.battery_enabled[bat_idx]
        obj.battery_dispatchable = self.battery_dispatchable[bat_idx]

        obj.consolidate()

        return obj

    def compute_branch_results(self, V) -> "PowerFlowResults":
        """
        Compute the branch magnitudes from the voltages
        :param V: Voltage vector solution in p.u.
        :return: PowerFlowResults instance
        """

        # declare circuit results
        data = PowerFlowResults(self.nbus, self.nbr)

        # copy the voltage
        data.V = V

        # power at the slack nodes
        data.Sbus = self.Sbus.copy()
        data.Sbus[self.ref] = V[self.ref] * np.conj(self.Ybus[self.ref, :].dot(V))

        # Reactive power at the pv nodes: keep the original P injection and set the calculated reactive power
        Q = (V[self.pv] * np.conj(self.Ybus[self.pv, :].dot(V))).imag

        data.Sbus[self.pv] = self.Sbus[self.pv].real + 1j * Q

        # Branches current, loading, etc
        data.If = self.Yf * V
        data.It = self.Yt * V
        data.Sf = self.C_branch_bus_f * V * np.conj(data.If)
        data.St = self.C_branch_bus_t * V * np.conj(data.It)

        # Branch losses in MVA
        data.losses = (data.Sf + data.St)

        # Branch current in p.u.
        data.Ibranch = np.maximum(data.If, data.It)

        # Branch power in MVA
        data.Sbranch = np.maximum(data.Sf, data.St)

        # Branch loading in p.u.
        data.loading = data.Sbranch / (self.branch_rates + 1e-9)

        return data

    def re_calc_admittance_matrices(self, tap_mod):
        """
        Recalculate the admittance matrices as the tap changes
        :param tap_mod: tap modules per bus
        :return: Nothing, the matrices are changed in-place
        """
        # here the branch_bus matrices do have the states embedded
        Cf = self.C_branch_bus_f
        Ct = self.C_branch_bus_t

        tap = tap_mod * np.exp(1.0j * self.tap_ang)

        # branch primitives in vector form
        Ytt = (self.Ys + self.GBc / 2.0) / (self.tap_t * self.tap_t)
        Yff = (self.Ys + self.GBc / 2.0) / (self.tap_f * self.tap_f * tap * np.conj(tap))
        Yft = - self.Ys / (self.tap_f * self.tap_t * np.conj(tap))
        Ytf = - self.Ys / (self.tap_t * self.tap_f * tap)

        # form the admittance matrices
        self.Yf = diags(Yff) * Cf + diags(Yft) * Ct
        self.Yt = diags(Ytf) * Cf + diags(Ytt) * Ct
        self.Ybus = csc_matrix(Cf.T * self.Yf + Ct.T * self.Yt + diags(self.Ysh))

        # branch primitives in vector form
        Ytts = self.Ys
        Yffs = Ytts / (tap * np.conj(tap))
        Yfts = - self.Ys / np.conj(tap)
        Ytfs = - self.Ys / tap

        # form the admittance matrices of the series elements
        Yfs = diags(Yffs) * Cf + diags(Yfts) * Ct
        Yts = diags(Ytfs) * Cf + diags(Ytts) * Ct
        self.Yseries = csc_matrix(Cf.T * Yfs + Ct.T * Yts)
        Gsh = self.GBc / 2.0
        self.Ysh += Cf.T * Gsh + Ct.T * Gsh

        X = (1 / self.Ys).imag
        b1 = 1.0 / (X + 1e-20)
        B1f = diags(-b1) * Cf + diags(-b1) * Ct
        B1t = diags(-b1) * Cf + diags(-b1) * Ct
        self.B1 = csc_matrix(Cf.T * B1f + Ct.T * B1t)

        b2 = b1 + self.GBc.imag  # B == GBc.imag
        b2_ff = -(b2 / (tap * np.conj(tap))).real
        b2_ft = -(b1 / np.conj(tap)).real
        b2_tf = -(b1 / tap).real
        b2_tt = - b2
        B2f = diags(b2_ff) * Cf + diags(b2_ft) * Ct
        B2t = diags(b2_tf) * Cf + diags(b2_tt) * Ct
        self.B2 = csc_matrix(Cf.T * B2f + Ct.T * B2t)

    def build_linear_ac_sys_mat(self):
        """
        Get the AC linear approximation matrices
        :return:
        """
        A11 = -self.Yseries.imag[np.ix_(self.pqpv, self.pqpv)]
        A12 = self.Ybus.real[np.ix_(self.pqpv, self.pq)]
        A21 = -self.Yseries.real[np.ix_(self.pq, self.pqpv)]
        A22 = -self.Ybus.imag[np.ix_(self.pq, self.pq)]

        A = vstack_s([hstack_s([A11, A12]),
                      hstack_s([A21, A22])], format="csc")

        # form the slack system matrix
        A11s = -self.Yseries.imag[np.ix_(self.ref, self.pqpv)]
        A12s = self.Ybus.real[np.ix_(self.ref, self.pq)]
        A_slack = hstack_s([A11s, A12s], format="csr")

        self.Asys = factorized(A)
        return A, A_slack

    def get_structure(self, structure_type) -> pd.DataFrame:
        """
        Get a DataFrame with the input.

        Arguments:

            **structure_type** (str): 'Vbus', 'Sbus', 'Ibus', 'Ybus', 'Yshunt', 'Yseries' or 'Types'

        Returns:

            pandas DataFrame

        """

        if structure_type == 'Vbus':

            df = pd.DataFrame(data=self.Vbus, columns=['Voltage (p.u.)'], index=self.bus_names)

        elif structure_type == 'Sbus':
            df = pd.DataFrame(data=self.Sbus, columns=['Power (p.u.)'], index=self.bus_names)

        elif structure_type == 'Ibus':
            df = pd.DataFrame(data=self.Ibus, columns=['Current (p.u.)'], index=self.bus_names)

        elif structure_type == 'Ybus':
            df = pd.DataFrame(data=self.Ybus.toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == 'Yshunt':
            df = pd.DataFrame(data=self.Ysh, columns=['Shunt admittance (p.u.)'], index=self.bus_names)

        elif structure_type == 'Yseries':
            df = pd.DataFrame(data=self.Yseries.toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == "B'":
            df = pd.DataFrame(data=self.B1.toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == "B''":
            df = pd.DataFrame(data=self.B2.toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == 'Types':
            df = pd.DataFrame(data=self.types, columns=['Bus types'], index=self.bus_names)

        elif structure_type == 'Qmin':
            df = pd.DataFrame(data=self.Qmin, columns=['Qmin'], index=self.bus_names)

        elif structure_type == 'Qmax':
            df = pd.DataFrame(data=self.Qmax, columns=['Qmax'], index=self.bus_names)

        elif structure_type == 'Jacobian':

            J = Jacobian(self.Ybus, self.Vbus, self.Ibus, self.pq, self.pqpv)

            """
            J11 = dS_dVa[array([pvpq]).T, pvpq].real
            J12 = dS_dVm[array([pvpq]).T, pq].real
            J21 = dS_dVa[array([pq]).T, pvpq].imag
            J22 = dS_dVm[array([pq]).T, pq].imag
            """
            npq = len(self.pq)
            npv = len(self.pv)
            npqpv = npq + npv
            cols = ['dS/dVa'] * npqpv + ['dS/dVm'] * npq
            rows = cols
            df = pd.DataFrame(data=J.toarray(), columns=cols, index=rows)

        else:

            raise Exception('PF input: structure type not found')

        return df

    def print(self, bus_names):
        """
        print in console
        :return:
        """
        df_bus = pd.DataFrame(
            np.c_[self.types, np.abs(self.Vbus), np.angle(self.Vbus), self.Vbus.real, self.Vbus.imag,
                  self.Sbus.real, self.Sbus.imag, self.Ysh.real, self.Ysh.imag],
            index=bus_names, columns=['Type', '|V|', 'angle', 're{V}', 'im{V}', 'P', 'Q', 'Gsh', 'Bsh'])
        # df_bus.sort_index(inplace=True)

        print('\nBus info\n', df_bus)

        if self.nbus < 100:
            print('\nYbus\n', pd.DataFrame(self.Ybus.todense(), columns=bus_names, index=bus_names))

        print('PQ:', self.pq)
        print('PV:', self.pv)
        print('REF:', self.ref)


class SeriesData(SnapshotCircuit):
    """
    This class represents the set of numerical inputs for simulations that require
    static values from the time series mode (power flow time series, monte carlo, PTDF time-series, etc.)
    """

    def __init__(self, n_bus, n_pi, n_hvdc, n_vsc, n_ld, n_gen, n_sta_gen, n_batt, n_sh, n_time,
                 idx_pi, idx_hvdc, idx_vsc, Sbase):
        """
        Topology constructor
        :param n_bus: number of nodes
        :param n_pi: number of branches
        :param n_ld: number of loads
        :param n_gen: number of generators
        :param n_sta_gen: number of generators
        :param n_batt: number of generators
        :param n_sh: number of shunts
        :param n_time: number of time_steps
        :param Sbase: circuit base power
        """

        SnapshotData.__init__(self,
                              n_bus=n_bus,
                              n_pi=n_pi,
                              n_hvdc=n_hvdc,
                              n_vsc=n_vsc,
                              n_ld=n_ld,
                              n_gen=n_gen,
                              n_sta_gen=n_sta_gen,
                              n_batt=n_batt,
                              n_sh=n_sh,
                              idx_pi=idx_pi,
                              idx_hvdc=idx_hvdc,
                              idx_vsc=idx_vsc,
                              Sbase=Sbase)

        # number of time steps
        self.ntime = n_time

        self.time_array = None

        # bus ----------------------------------------------------------------------------------------------------------
        self.bus_active_prof = np.zeros((n_time, n_bus), dtype=int)

        # branch -------------------------------------------------------------------------------------------------------
        self.branch_active_prof = np.zeros((n_time, n_pi), dtype=int)
        self.branch_rate_profile = np.zeros((n_time, n_pi), dtype=float)

        # pi model -----------------------------------------------------------------------------------------------------
        self.branch_temp_oper_prof = np.zeros((n_time, n_pi), dtype=float)
        self.branch_cost_profile = np.zeros((n_time, n_pi), dtype=float)

        # load ---------------------------------------------------------------------------------------------------------
        self.load_active_prof = np.zeros((n_time, n_ld), dtype=bool)
        self.load_cost_prof = np.zeros((n_time, n_ld), dtype=float)
        self.load_power_profile = np.zeros((n_time, n_ld), dtype=complex)
        self.load_current_profile = np.zeros((n_time, n_ld), dtype=complex)
        self.load_admittance_profile = np.zeros((n_time, n_ld), dtype=complex)

        # battery ------------------------------------------------------------------------------------------------------
        self.battery_active_prof = np.zeros((n_time, n_batt), dtype=bool)
        self.battery_power_profile = np.zeros((n_time, n_batt), dtype=float)
        self.battery_voltage_profile = np.zeros((n_time, n_batt), dtype=float)
        self.battery_cost_profile = np.zeros((n_time, n_batt), dtype=float)

        # static generator ---------------------------------------------------------------------------------------------
        self.static_gen_active_prof = np.zeros((n_time, n_sta_gen), dtype=bool)
        self.static_gen_power_profile = np.zeros((n_time, n_sta_gen), dtype=complex)

        # controlled generator -----------------------------------------------------------------------------------------
        self.generator_active_prof = np.zeros((n_time, n_gen), dtype=bool)
        self.generator_cost_profile = np.zeros((n_time, n_gen), dtype=float)
        self.generator_power_profile = np.zeros((n_time, n_gen), dtype=float)
        self.generator_power_factor_profile = np.zeros((n_time, n_gen), dtype=float)
        self.generator_voltage_profile = np.zeros((n_time, n_gen), dtype=float)

        # shunt --------------------------------------------------------------------------------------------------------
        self.shunt_active_prof = np.zeros((n_time, n_sh), dtype=bool)
        self.shunt_admittance_profile = np.zeros((n_time, n_sh), dtype=complex)

    def get_power_injections(self):
        """
        returns the complex power injections
        """
        Sbus = - self.C_bus_load * self.load_power_profile.T  # MW
        Sbus += self.C_bus_gen * self.generator_power_profile.T
        Sbus += self.C_bus_batt * self.battery_power_profile.T
        Sbus += self.C_bus_sta_gen * self.static_gen_power_profile.T

        return Sbus

    def re_index_time(self, t_idx):
        """
        Re-index all the time based profiles
        :param t_idx: new indices of the time profiles
        :return: Nothing, this is done in-place
        """

        self.time_array = self.time_array[t_idx]
        self.ntime = len(t_idx)

        # bus
        self.bus_active_prof = self.bus_active_prof[t_idx, :]

        # branch
        self.branch_active_prof = self.branch_active_prof[t_idx, :]  # np.zeros((n_time, n_br), dtype=int)
        self.branch_temp_oper_prof = self.branch_temp_oper_prof[t_idx, :]  # np.zeros((n_time, n_br), dtype=float)
        self.branch_rate_profile = self.branch_rate_profile[t_idx, :]  # np.zeros((n_time, n_br), dtype=float)
        self.branch_cost_profile = self.branch_cost_profile[t_idx, :]  # np.zeros((n_time, n_br), dtype=float)

        # load
        self.load_active_prof = self.load_active_prof[t_idx, :]   # np.zeros((n_time, n_ld), dtype=bool)
        self.load_cost_prof = self.load_cost_prof[t_idx, :]   # np.zeros((n_time, n_ld), dtype=float)

        self.load_power_profile = self.load_power_profile[t_idx, :]  # np.zeros((n_time, n_ld), dtype=complex)
        self.load_current_profile = self.load_current_profile[t_idx, :]  # np.zeros((n_time, n_ld), dtype=complex)
        self.load_admittance_profile = self.load_admittance_profile[t_idx, :]  # np.zeros((n_time, n_ld), dtype=complex)

        # battery
        self.battery_active_prof = self.battery_active_prof[t_idx, :]  # np.zeros((n_time, n_batt), dtype=bool)
        self.battery_power_profile = self.battery_power_profile[t_idx, :]  # np.zeros((n_time, n_batt), dtype=float)
        self.battery_voltage_profile = self.battery_voltage_profile[t_idx, :]  # np.zeros((n_time, n_batt), dtype=float)
        self.battery_cost_profile = self.battery_cost_profile[t_idx, :]  # np.zeros((n_time, n_batt), dtype=float)

        # static generator
        self.static_gen_active_prof = self.static_gen_active_prof[t_idx, :]  # np.zeros((n_time, n_sta_gen), dtype=bool)
        self.static_gen_power_profile = self.static_gen_power_profile[t_idx, :]  # np.zeros((n_time, n_sta_gen), dtype=complex)

        # controlled generator
        self.generator_active_prof = self.generator_active_prof[t_idx, :]  # np.zeros((n_time, n_gen), dtype=bool)
        self.generator_cost_profile = self.generator_cost_profile[t_idx, :]  # np.zeros((n_time, n_gen), dtype=float)
        self.generator_power_profile = self.generator_power_profile[t_idx, :]  # np.zeros((n_time, n_gen), dtype=float)
        self.generator_power_factor_profile = self.generator_power_factor_profile[t_idx, :]  # np.zeros((n_time, n_gen), dtype=float)
        self.generator_voltage_profile = self.generator_voltage_profile[t_idx, :]  # np.zeros((n_time, n_gen), dtype=float)

        # shunt
        self.shunt_active_prof = self.shunt_active_prof[t_idx, :]  # np.zeros((n_time, n_sh), dtype=bool)
        self.shunt_admittance_profile = self.shunt_admittance_profile[t_idx, :]  # np.zeros((n_time, n_sh), dtype=complex)

    def set_base_profile(self):
        """
        Re-index all the time based profiles
        :return: Nothing, this is done in-place
        """
        now = datetime.datetime.now()
        dte = datetime.datetime(year=now.year, month=1, day=1, hour=0)
        self.time_array = pd.to_datetime([dte])
        self.ntime = len(self.time_array)

        # branch
        self.branch_active_prof = self.branch_active.reshape(1, -1)  # np.zeros((n_time, n_br), dtype=int)
        self.branch_temp_oper_prof = self.branch_temp_oper.reshape(1, -1)  # np.zeros((n_time, n_br), dtype=float)
        self.branch_rate_profile = self.branch_rates.reshape(1, -1)  # np.zeros((n_time, n_br), dtype=float)
        self.branch_cost_profile = self.branch_cost.reshape(1, -1)  # np.zeros((n_time, n_br), dtype=float)

        # load
        self.load_active_prof = self.load_active.reshape(1, -1)   # np.zeros((n_time, n_ld), dtype=bool)
        self.load_cost_prof = self.load_cost.reshape(1, -1)   # np.zeros((n_time, n_ld), dtype=float)

        self.load_power_profile = self.load_power.reshape(1, -1)  # np.zeros((n_time, n_ld), dtype=complex)
        self.load_current_profile = self.load_current.reshape(1, -1)  # np.zeros((n_time, n_ld), dtype=complex)
        self.load_admittance_profile = self.load_admittance.reshape(1, -1)  # np.zeros((n_time, n_ld), dtype=complex)

        # battery
        self.battery_active_prof = self.battery_active.reshape(1, -1)  # np.zeros((n_time, n_batt), dtype=bool)
        self.battery_power_profile = self.battery_power.reshape(1, -1)  # np.zeros((n_time, n_batt), dtype=float)
        self.battery_voltage_profile = self.battery_voltage.reshape(1, -1)  # np.zeros((n_time, n_batt), dtype=float)
        self.battery_cost_profile = self.battery_cost.reshape(1, -1)  # np.zeros((n_time, n_batt), dtype=float)

        # static generator
        self.static_gen_active_prof = self.static_gen_active.reshape(1, -1)  # np.zeros((n_time, n_sta_gen), dtype=bool)
        self.static_gen_power_profile = self.static_gen_power.reshape(1, -1)  # np.zeros((n_time, n_sta_gen), dtype=complex)

        # controlled generator
        self.generator_active_prof = self.generator_active.reshape(1, -1)  # np.zeros((n_time, n_gen), dtype=bool)
        self.generator_cost_profile = self.generator_cost.reshape(1, -1)  # np.zeros((n_time, n_gen), dtype=float)
        self.generator_power_profile = self.generator_power.reshape(1, -1)  # np.zeros((n_time, n_gen), dtype=float)
        self.generator_power_factor_profile = self.generator_power_factor.reshape(1, -1)  # np.zeros((n_time, n_gen), dtype=float)
        self.generator_voltage_profile = self.generator_voltage.reshape(1, -1)  # np.zeros((n_time, n_gen), dtype=float)

        # shunt
        self.shunt_active_prof = self.shunt_active.reshape(1, -1)  # np.zeros((n_time, n_sh), dtype=bool)
        self.shunt_admittance_profile = self.shunt_admittance.reshape(1, -1)  # np.zeros((n_time, n_sh), dtype=complex)

    def get_different_states(self, prog_func=None, text_func=None):
        """
        Get a dictionary of different connectivity states
        :return: dictionary of states  {master state index -> list of states associated}
        """

        if text_func is not None:
            text_func('Enumerating different admittance states...')

        # initialize
        states = dict()
        k = 1
        for t in range(self.ntime):

            if prog_func is not None:
                prog_func(k / self.ntime * 100)

            # search this state in the already existing states
            found = False
            for t2 in states.keys():
                if np.array_equal(self.branch_active_prof[t, :], self.branch_active_prof[t2, :]):
                    states[t2].append(t)
                    found = True

            if not found:
                # new state found (append itself)
                states[t] = [t]

            k += 1

        return states

    def get_raw_circuit(self, add_generation, add_storage) -> SeriesIsland:
        """
        Returns the island object without partitions
        :param add_generation: Include the generators?
        :param add_storage: Include the storage?
        :return: SeriesIsland object
        """
        # Declare object to store the calculation inputs
        circuit = SeriesIsland(nbus=self.nbus,
                               nbr=self.nbr,
                               nhvdc=self.n_hvdc,
                               nvsc=self.n_vsc,
                               ntime=self.ntime,
                               nbat=self.n_batt,
                               nctrlgen=self.n_gen)

        # branches
        circuit.branch_rates = self.branch_rates
        circuit.branch_rates_prof = self.branch_rate_profile
        circuit.F = self.F
        circuit.T = self.T
        circuit.tap_f = self.branch_tap_f
        circuit.tap_t = self.branch_tap_t
        circuit.bus_names = self.bus_names
        circuit.branch_names = self.branch_names

        # connectivity matrices
        circuit.C_bus_load = self.C_bus_load
        circuit.C_bus_batt = self.C_bus_batt
        circuit.C_bus_sta_gen = self.C_bus_sta_gen
        circuit.C_bus_gen = self.C_bus_gen
        circuit.C_bus_shunt = self.C_bus_shunt

        # needed for the tap changer
        circuit.is_bus_to_regulated = self.branch_is_bus_to_regulated
        circuit.tap_position = self.branch_tap_position
        circuit.min_tap = self.branch_min_tap
        circuit.max_tap = self.branch_max_tap
        circuit.tap_inc_reg_up = self.branch_tap_inc_reg_up
        circuit.tap_inc_reg_down = self.branch_tap_inc_reg_down
        circuit.vset = self.branch_vset
        circuit.tap_ang = self.branch_tap_ang
        circuit.tap_mod = self.branch_tap_mod

        circuit.vsc_m = self.vsc_m

        # active power control
        circuit.controlled_gen_pmin = self.generator_pmin
        circuit.controlled_gen_pmax = self.generator_pmax
        circuit.controlled_gen_enabled = self.generator_active
        circuit.controlled_gen_dispatchable = self.generator_dispatchable
        circuit.battery_pmin = self.battery_pmin
        circuit.battery_pmax = self.battery_pmax
        circuit.battery_Enom = self.battery_Enom
        circuit.battery_soc_0 = self.battery_soc_0
        circuit.battery_discharge_efficiency = self.battery_discharge_efficiency
        circuit.battery_charge_efficiency = self.battery_charge_efficiency
        circuit.battery_min_soc = self.battery_min_soc
        circuit.battery_max_soc = self.battery_max_soc
        circuit.battery_enabled = self.battery_active
        circuit.battery_dispatchable = self.battery_dispatchable

        ################################################################################################################
        # loads, generators, batteries, etc...
        ################################################################################################################

        # Shunts
        Ysh = self.C_bus_shunt * (self.shunt_admittance / self.Sbase)

        # Loads
        S = self.C_bus_load * (- self.load_power / self.Sbase * self.load_active)
        I = self.C_bus_load * (- self.load_current / self.Sbase * self.load_active)
        Ysh += self.C_bus_load * (self.load_admittance / self.Sbase * self.load_active)

        if add_generation:
            # static generators
            S += self.C_bus_sta_gen * (self.static_gen_power / self.Sbase * self.static_gen_active)

            # generators
            pf2 = np.power(self.generator_power_factor, 2.0)
            # compute the reactive power from the active power and the power factor
            pf_sign = (self.generator_power_factor + 1e-20) / np.abs(self.generator_power_factor + 1e-20)
            Q = pf_sign * self.generator_power * np.sqrt((1.0 - pf2) / (pf2 + 1e-20))
            gen_S = self.generator_power + 1j * Q
            S += self.C_bus_gen * (gen_S / self.Sbase * self.generator_active)

        installed_generation_per_bus = self.C_bus_gen * (self.generator_nominal_power * self.generator_active)

        # batteries
        if add_storage:
            S += self.C_bus_batt * (self.battery_power / self.Sbase * self.battery_active)

        # Qmax
        q_max = self.C_bus_gen * (self.generator_qmax / self.Sbase) + self.C_bus_batt * (self.battery_qmax / self.Sbase)

        # Qmin
        q_min = self.C_bus_gen * (self.generator_qmin / self.Sbase) + self.C_bus_batt * (self.battery_qmin / self.Sbase)

        # assign the values
        circuit.Ysh = Ysh
        circuit.Sbus = S
        circuit.Ibus = I
        circuit.Vbus = self.V0
        circuit.Sbase = self.Sbase
        circuit.types = self.bus_types
        circuit.Qmax = q_max
        circuit.Qmin = q_min
        circuit.Sinstalled = installed_generation_per_bus

        # profiles...
        # Shunts
        Ysh_prof = self.C_bus_shunt * (self.shunt_admittance_profile / self.Sbase * self.shunt_active).T

        # Loads
        I_prof = self.C_bus_load * (- self.load_current_profile / self.Sbase * self.load_active).T
        Ysh_prof += self.C_bus_load * (self.load_admittance_profile / self.Sbase * self.load_active).T

        Sbus_prof = self.C_bus_load * (- self.load_power_profile / self.Sbase * self.load_active).T

        if add_generation:
            # static generators
            Sbus_prof += self.C_bus_sta_gen * (self.static_gen_power_profile / self.Sbase * self.static_gen_active).T

            # generators
            pf2 = np.power(self.generator_power_factor_profile, 2.0)

            # compute the reactive power from the active power and the power factor
            pf_sign = (self.generator_power_factor_profile + 1e-20) / \
                      np.abs(self.generator_power_factor_profile + 1e-20)

            Q = pf_sign * self.generator_power_profile * np.sqrt((1.0 - pf2) / (pf2 + 1e-20))

            gen_S = self.generator_power_profile + 1j * Q

            Sbus_prof += self.C_bus_gen * (gen_S / self.Sbase * self.generator_active).T

        # batteries
        if add_storage:
            Sbus_prof += self.C_bus_batt * (self.battery_power_profile / self.Sbase * self.battery_active).T

        circuit.Ysh_prof = Ysh_prof
        circuit.Sbus_prof = Sbus_prof
        circuit.Ibus_prof = I_prof
        circuit.time_array = self.time_array

        return circuit

    def compute(self, add_storage=True, add_generation=True, apply_temperature=False,
                branch_tolerance_mode=BranchImpedanceMode.Specified, ignore_single_node_islands=False,
                prog_func=None, text_func=None) -> Dict[int, List[SeriesIsland]]:
        """
        Compute the cross connectivity matrices to determine the circuit connectivity
        towards the calculation. Additionally, compute the calculation matrices.
        :param add_storage:
        :param add_generation:
        :param apply_temperature:
        :param branch_tolerance_mode:
        :param ignore_single_node_islands: If True, the single node islands are omitted
        :param prog_func: progress report function
        :param text_func: text report function
        :return: dictionary of lists of CalculationInputs instances where each one is a circuit island
        """

        # Compute all the different connectivity states
        states = self.get_different_states(prog_func=prog_func, text_func=text_func)

        calculation_islands_collection = dict()

        if text_func is not None:
            text_func('Computing topological states...')

        ni = len(states.items())
        k = 1
        for t, t_array in states.items():

            if prog_func is not None:
                prog_func(k / ni * 100.0)

            # get the raw circuit with the inner arrays computed
            circuit = self.get_raw_circuit(add_generation=add_generation, add_storage=add_storage)

            # compute the connectivity and the different admittance matrices
            circuit.Ybus, \
            circuit.Yf, \
            circuit.Yt, \
            circuit.B1, \
            circuit.B2, \
            circuit.Yseries, \
            circuit.Ysh_helm, \
            circuit.Ys, \
            circuit.GBc, \
            circuit.C_branch_bus_f, \
            circuit.C_branch_bus_t, \
            C_bus_bus, \
            C_branch_bus = calc_connectivity(idx_pi=self.idx_pi,
                                             idx_hvdc=self.idx_hvdc,
                                             idx_vsc=self.idx_vsc,
                                             C_branch_bus_f=self.C_branch_bus_f,
                                             C_branch_bus_t=self.C_branch_bus_t,
                                             branch_active=self.branch_active_prof[t, :],
                                             bus_active=self.bus_active_prof[t, :],

                                             # pi model
                                             apply_temperature=apply_temperature,
                                             R_corrected=self.R_corrected_at(t),
                                             R=self.branch_R,
                                             X=self.branch_X,
                                             G=self.branch_G,
                                             B=self.branch_B,
                                             branch_tolerance_mode=branch_tolerance_mode,
                                             impedance_tolerance=self.branch_impedance_tolerance,
                                             tap_mod=self.branch_tap_mod,
                                             tap_ang=self.branch_tap_ang,
                                             tap_t=self.branch_tap_t,
                                             tap_f=self.branch_tap_f,
                                             Ysh=circuit.Ysh_prof[:, t],

                                             # HVDC line
                                             Rdc=self.hvdc_R,

                                             # VSC model
                                             R1=self.vsc_R1,
                                             X1=self.vsc_X1,
                                             Gsw=self.vsc_G0,
                                             Beq=self.vsc_Beq,
                                             m=self.vsc_m,
                                             theta=self.vsc_theta
                                             )

            #  split the circuit object into the individual circuits that may arise from the topological islands
            calculation_islands = calc_islands(circuit=circuit,
                                               bus_active=self.bus_active,
                                               C_bus_bus=C_bus_bus,
                                               C_branch_bus=C_branch_bus,
                                               C_bus_gen=self.C_bus_gen,
                                               C_bus_batt=self.C_bus_batt,
                                               nbus=self.nbus,
                                               nbr=self.nbr,
                                               time_idx=t_array,
                                               ignore_single_node_islands=ignore_single_node_islands)

            calculation_islands_collection[t] = calculation_islands

            if t == 0:
                for island in calculation_islands:
                    self.bus_types[island.original_bus_idx] = island.types

            k += 1

        # return the list of islands
        return calculation_islands_collection

    def R_corrected_at(self, t):
        """
        Returns temperature corrected resistances (numpy array) based on a formula
        provided by: NFPA 70-2005, National Electrical Code, Table 8, footnote #2; and
        https://en.wikipedia.org/wiki/Electrical_resistivity_and_conductivity#Linear_approximation
        (version of 2019-01-03 at 15:20 EST).
        :param t: time index
        """
        return self.branch_R * (1.0 + self.branch_alpha * (self.branch_temp_oper_prof[t, :] - self.branch_temp_base))

    def get_B(self, apply_temperature=False):
        """
        Get the imaginary part of the admittance matrix without partitions
        :param apply_temperature:
        :return:
        """

        # Shunts
        Ysh = self.C_bus_shunt.T * (self.shunt_admittance / self.Sbase)

        # Loads
        Ysh += self.C_bus_load.T * (self.load_admittance / self.Sbase * self.load_active)

        # form the connectivity matrices with the states applied
        states_dia = sp.diags(self.branch_active)
        Cf = states_dia * self.C_branch_bus_f
        Ct = states_dia * self.C_branch_bus_t

        if apply_temperature:
            R = self.R_corrected()
        else:
            R = self.branch_R

        Ys = 1.0 / (R + 1.0j * self.branch_X)
        GBc = self.branch_G + 1.0j * self.branch_B
        tap = self.branch_tap_mod * np.exp(1.0j * self.branch_tap_ang)

        # branch primitives in vector form
        Ytt = (Ys + GBc / 2.0) / (self.branch_tap_t * self.branch_tap_t)
        Yff = (Ys + GBc / 2.0) / (self.branch_tap_f * self.branch_tap_f * tap * np.conj(tap))
        Yft = - Ys / (self.branch_tap_f * self.branch_tap_t * np.conj(tap))
        Ytf = - Ys / (self.branch_tap_t * self.branch_tap_f * tap)

        # form the admittance matrices
        Yf = sp.diags(Yff) * Cf + sp.diags(Yft) * Ct
        Yt = sp.diags(Ytf) * Cf + sp.diags(Ytt) * Ct
        Ybus = sparse(Cf.T * Yf + Ct.T * Yt + sp.diags(Ysh))

        return Ybus.imag
