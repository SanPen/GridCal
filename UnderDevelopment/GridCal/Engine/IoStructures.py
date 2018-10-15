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

import os
import pickle as pkl
from warnings import warn
import pandas as pd
from numpy import complex, double, sqrt, zeros, ones, nan_to_num, exp, conj, ndarray, vstack, power, delete, where, \
    r_, Inf, linalg, maximum, array, nan, shape, arange, sort, interp, iscomplexobj, c_, argwhere, floor
from scipy.sparse import diags, hstack as hstack_s, vstack as vstack_s
from scipy.sparse.linalg import factorized
from pySOT import *
from pyDOE import lhs
from scipy.sparse import csc_matrix, lil_matrix
from matplotlib import pyplot as plt
from sklearn.ensemble import RandomForestRegressor

# from GridCal.Engine.NewEngine import NumericalCircuit
from GridCal.Engine.PlotConfig import LINEWIDTH
from GridCal.Engine.BasicStructures import CDF
from GridCal.Engine.Numerical.JacobianBased import Jacobian
from GridCal.Engine.BasicStructures import BusMode


class CalculationInputs:

    def __init__(self, nbus, nbr, ntime, nbat, nctrlgen):
        """
        Constructor
        :param nbus: number of buses
        :param nbr: number of branches
        :param ntime: number of time steps
        """
        self.nbus = nbus
        self.nbr = nbr
        self.ntime = ntime

        self.Sbase = 100.0

        self.time_array = None

        self.original_bus_idx = list()
        self.original_branch_idx = list()

        self.bus_names = np.empty(self.nbus, dtype=object)
        self.branch_names = np.empty(self.nbr, dtype=object)

        # resulting matrices (calculation)
        self.Yf = csc_matrix((nbr, nbus), dtype=complex)
        self.Yt = csc_matrix((nbr, nbus), dtype=complex)
        self.Ybus = csc_matrix((nbus, nbus), dtype=complex)
        self.Yseries = csc_matrix((nbus, nbus), dtype=complex)
        self.B1 = csc_matrix((nbus, nbus), dtype=float)
        self.B2 = csc_matrix((nbus, nbus), dtype=float)

        self.Ysh = np.zeros(nbus, dtype=complex)
        self.Sbus = np.zeros(nbus, dtype=complex)
        self.Ibus = np.zeros(nbus, dtype=complex)

        self.Ysh_prof = np.zeros((nbus, ntime), dtype=complex)
        self.Sbus_prof = np.zeros((nbus, ntime), dtype=complex)
        self.Ibus_prof = np.zeros((nbus, ntime), dtype=complex)

        self.Vbus = np.ones(nbus, dtype=complex)
        self.Vmin = np.ones(nbus, dtype=float)
        self.Vmax = np.ones(nbus, dtype=float)
        self.types = np.zeros(nbus, dtype=int)
        self.Qmin = np.zeros(nbus, dtype=float)
        self.Qmax = np.zeros(nbus, dtype=float)

        self.F = np.zeros(nbr, dtype=int)
        self.T = np.zeros(nbr, dtype=int)

        # vectors to re-calculate the admittance matrices
        self.Ys = np.zeros(nbr, dtype=complex)
        self.GBc = np.zeros(nbr, dtype=complex)
        self.tap_f = np.zeros(nbr, dtype=float)
        self.tap_t = np.zeros(nbr, dtype=float)
        self.tap_ang = np.zeros(nbr, dtype=float)

        # needed fot the tap changer
        self.is_bus_to_regulated = np.zeros(nbr, dtype=int)
        self.bus_to_regulated_idx = None
        self.tap_position = np.zeros(nbr, dtype=int)
        self.min_tap = np.zeros(nbr, dtype=int)
        self.max_tap = np.zeros(nbr, dtype=int)
        self.tap_inc_reg_up = np.zeros(nbr, dtype=float)
        self.tap_inc_reg_down = np.zeros(nbr, dtype=float)
        self.vset = np.zeros(nbr, dtype=float)

        self.C_branch_bus_f = csc_matrix((nbr, nbus), dtype=complex)
        self.C_branch_bus_t = csc_matrix((nbr, nbus), dtype=complex)

        # Active power control
        self.controlled_gen_pmin = np.zeros(nctrlgen, dtype=float)
        self.controlled_gen_pmax = np.zeros(nctrlgen, dtype=float)
        self.controlled_gen_enabled = np.zeros(nctrlgen, dtype=bool)
        self.controlled_gen_dispatchable = np.zeros(nctrlgen, dtype=bool)

        self.battery_pmin = np.zeros(nbat, dtype=float)
        self.battery_pmax = np.zeros(nbat, dtype=float)
        self.battery_Enom = np.zeros(nbat, dtype=float)
        self.battery_soc_0 = np.zeros(nbat, dtype=float)
        self.battery_discharge_efficiency = np.zeros(nbat, dtype=float)
        self.battery_charge_efficiency = np.zeros(nbat, dtype=float)
        self.battery_min_soc = np.zeros(nbat, dtype=float)
        self.battery_max_soc = np.zeros(nbat, dtype=float)
        self.battery_enabled = np.zeros(nbat, dtype=bool)
        self.battery_dispatchable = np.zeros(nbat, dtype=bool)

        # computed on consolidation
        self.dispatcheable_batteries_bus_idx = list()

        # connectivity matrices used to formulate OPF problems
        self.C_load_bus = None
        self.C_batt_bus = None
        self.C_sta_gen_bus = None
        self.C_ctrl_gen_bus = None
        self.C_shunt_bus = None

        # ACPF system matrix factorization
        self.Asys = None

        self.branch_rates = np.zeros(nbr)

        self.pq = list()
        self.pv = list()
        self.ref = list()
        self.sto = list()
        self.pqpv = list()

        self.logger =list()

        self.available_structures = ['Vbus', 'Sbus', 'Ibus', 'Ybus', 'Yshunt', 'Yseries', "B'", "B''", 'Types',
                                     'Jacobian', 'Qmin', 'Qmax']

    def compile_types(self, types_new=None):
        """
        Compile the types
        :param types_new: new array of types to consider
        :return: Nothing
        """
        if types_new is not None:
            self.types = types_new.copy()
        self.pq = np.where(self.types == BusMode.PQ.value[0])[0]
        self.pv = np.where(self.types == BusMode.PV.value[0])[0]
        self.ref = np.where(self.types == BusMode.REF.value[0])[0]
        self.sto = np.where(self.types == BusMode.STO_DISPATCH.value)[0]

        if len(self.ref) == 0:  # there is no slack!

            if len(self.pv) == 0:  # there are no pv neither -> blackout grid

                warn('There are no slack nodes selected')
                self.logger.append('There are no slack nodes selected')

            else:  # select the first PV generator as the slack

                mx = max(self.Sbus[self.pv])
                if mx > 0:
                    # find the generator that is injecting the most
                    i = np.where(self.Sbus == mx)[0][0]

                else:
                    # all the generators are injecting zero, pick the first pv
                    i = self.pv[0]

                # delete the selected pv bus from the pv list and put it in the slack list
                self.pv = np.delete(self.pv, np.where(self.pv == i)[0])
                self.ref = [i]
                # print('Setting bus', i, 'as slack')

            self.ref = np.ndarray.flatten(np.array(self.ref))
            self.types[self.ref] = BusMode.REF.value[0]
        else:
            pass  # no problem :)

        self.pqpv = np.r_[self.pq, self.pv]
        self.pqpv.sort()
        pass

    def consolidate(self):
        """
        Compute the magnitudes that cannot be computed vector-wise
        """
        self.bus_to_regulated_idx = np.where(self.is_bus_to_regulated > 0)[0]

        dispatcheable_batteries_idx = np.where(self.battery_dispatchable == True)[0]
        self.dispatcheable_batteries_bus_idx = np.where(np.array(self.C_batt_bus[dispatcheable_batteries_idx, :].sum(axis=0))[0] > 0)[0]

        self.compile_types()

    def get_island(self, bus_idx, branch_idx, gen_idx, bat_idx):
        """
        Get a sub-island
        :param bus_idx: bus indices of the island
        :param branch_idx: branch indices of the island
        :return: CalculationInputs instance
        """
        obj = CalculationInputs(len(bus_idx), len(branch_idx), self.ntime, len(bat_idx), len(gen_idx))

        # remember the island original indices
        obj.original_bus_idx = bus_idx
        obj.original_branch_idx = branch_idx

        obj.Yf = self.Yf[branch_idx, :][:, bus_idx].copy()
        obj.Yt = self.Yt[branch_idx, :][:, bus_idx].copy()
        obj.Ybus = self.Ybus[bus_idx, :][:, bus_idx].copy()
        obj.Yseries = self.Yseries[bus_idx, :][:, bus_idx].copy()
        obj.B1 = self.B1[bus_idx, :][:, bus_idx].copy()
        obj.B2 = self.B2[bus_idx, :][:, bus_idx].copy()

        obj.Ysh = self.Ysh[bus_idx]
        obj.Sbus = self.Sbus[bus_idx]
        obj.Ibus = self.Ibus[bus_idx]
        obj.Vbus = self.Vbus[bus_idx]
        obj.types = self.types[bus_idx]
        obj.Qmin = self.Qmin[bus_idx]
        obj.Qmax = self.Qmax[bus_idx]
        obj.Vmin = self.Vmin[bus_idx]
        obj.Vmax = self.Vmax[bus_idx]

        obj.F = self.F[branch_idx]
        obj.T = self.T[branch_idx]
        obj.branch_rates = self.branch_rates[branch_idx]
        obj.bus_names = self.bus_names[bus_idx]
        obj.branch_names = self.branch_names[branch_idx]

        obj.Ysh_prof = self.Ysh_prof[bus_idx, :]
        obj.Sbus_prof = self.Sbus_prof[bus_idx, :]
        obj.Ibus_prof = self.Ibus_prof[bus_idx, :]

        obj.C_branch_bus_f = self.C_branch_bus_f[branch_idx, :][:, bus_idx]
        obj.C_branch_bus_t = self.C_branch_bus_t[branch_idx, :][:, bus_idx]

        obj.C_load_bus = self.C_load_bus[:, bus_idx]
        obj.C_batt_bus = self.C_batt_bus[:, bus_idx]
        obj.C_sta_gen_bus = self.C_sta_gen_bus[:, bus_idx]
        obj.C_ctrl_gen_bus = self.C_ctrl_gen_bus[:, bus_idx]
        obj.C_shunt_bus = self.C_shunt_bus[:, bus_idx]

        obj.is_bus_to_regulated = self.is_bus_to_regulated[branch_idx]
        obj.tap_position = self.tap_position[branch_idx]
        obj.min_tap = self.min_tap[branch_idx]
        obj.max_tap = self.max_tap[branch_idx]
        obj.tap_inc_reg_up = self.tap_inc_reg_up[branch_idx]
        obj.tap_inc_reg_down = self.tap_inc_reg_down[branch_idx]
        obj.vset = self.vset[branch_idx]
        obj.tap_ang = self.tap_ang[branch_idx]

        obj.Ys = self.Ys
        obj.GBc = self.GBc
        obj.tap_f = self.tap_f
        obj.tap_t = self.tap_t

        self.controlled_gen_pmin = self.controlled_gen_pmin[gen_idx]
        self.controlled_gen_pmax = self.controlled_gen_pmax[gen_idx]
        self.controlled_gen_enabled = self.controlled_gen_enabled[gen_idx]
        self.controlled_gen_dispatchable = self.controlled_gen_dispatchable[gen_idx]
        self.battery_pmin = self.battery_pmin[bat_idx]
        self.battery_pmax = self.battery_pmax[bat_idx]
        self.battery_Enom = self.battery_Enom[bat_idx]
        self.battery_soc_0 = self.battery_soc_0[bat_idx]
        self.battery_discharge_efficiency = self.battery_discharge_efficiency[bat_idx]
        self.battery_charge_efficiency = self.battery_charge_efficiency[bat_idx]
        self.battery_min_soc = self.battery_min_soc[bat_idx]
        self.battery_max_soc = self.battery_max_soc[bat_idx]
        self.battery_enabled = self.battery_enabled[bat_idx]
        self.battery_dispatchable = self.battery_dispatchable[bat_idx]

        obj.consolidate()

        return obj

    def compute_branch_results(self, V):
        """
        Compute the branch magnitudes from the voltages
        :param V: Voltage vector solution in p.u.
        :return: CalculationResults instance with all the grid magnitudes
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
        A11 = -self.Yseries.imag[self.pqpv, :][:, self.pqpv]
        A12 = self.Ybus.real[self.pqpv, :][:, self.pq]
        A21 = -self.Yseries.real[self.pq, :][:, self.pqpv]
        A22 = -self.Ybus.imag[self.pq, :][:, self.pq]

        A = vstack_s([hstack_s([A11, A12]),
                      hstack_s([A21, A22])], format="csc")

        # form the slack system matrix
        A11s = -self.Yseries.imag[self.ref, :][:, self.pqpv]
        A12s = self.Ybus.real[self.ref, :][:, self.pq]
        A_slack = hstack_s([A11s, A12s], format="csr")

        self.Asys = factorized(A)
        return A, A_slack

    def get_structure(self, structure_type):
        """
        Get a DataFrame with the input
        Args:
            structure_type: 'Vbus', 'Sbus', 'Ibus', 'Ybus', 'Yshunt', 'Yseries', 'Types'

        Returns: Pandas DataFrame
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
        # print('\ntypes\n', self.types)
        # print('\nSbus\n', self.Sbus)
        # print('\nVbus\n', self.Vbus)
        # print('\nYsh\n', self.Ysh)

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


class PowerFlowResults:

    def __init__(self, Sbus=None, voltage=None, Sbranch=None, Ibranch=None, loading=None, losses=None, tap_module=None,
                 flow_direction=None, error=None, converged=None, Qpv=None, battery_power_inc=None, inner_it=None,
                 outer_it=None, elapsed=None, methods=None):
        """
        Power flow results
        :param Sbus: Bus power calculated
        :param voltage:  Voltages array (p.u.)
        :param Sbranch: Branches power array (MVA)
        :param Ibranch: Branches current array (p.u.)
        :param loading: Branches loading array (p.u.)
        :param losses: Branches losses array (MW)
        :param tap_module: tap module computed for all the branches
        :param flow_direction: flow direction at each of the branches
        :param error: power flow error value
        :param converged: converged (True / False)
        :param Qpv: Reactive power at the PV nodes array (p.u.)
        :param inner_it: number of inner iterations
        :param outer_it: number of outer iterations
        :param elapsed: time elapsed in seconds
        :param methods: methods used
        """

        self.Sbus = Sbus

        self.voltage = voltage

        self.Sbranch = Sbranch

        self.Ibranch = Ibranch

        self.loading = loading

        self.losses = losses

        self.flow_direction = flow_direction

        self.tap_module = tap_module

        self.error = error

        self.converged = converged

        self.Qpv = Qpv

        self.battery_power_inc = battery_power_inc

        self.overloads = None

        self.overvoltage = None

        self.undervoltage = None

        self.overloads_idx = None

        self.overvoltage_idx = None

        self.undervoltage_idx = None

        self.buses_useful_for_storage = None

        self.available_results = ['Bus voltage',
                                  # 'Bus voltage (polar)',
                                  'Branch power', 'Branch current',
                                  'Branch_loading', 'Branch losses', 'Battery power']

        self.plot_bars_limit = 100

        self.inner_iterations = inner_it

        self.outer_iterations = outer_it

        self.elapsed = elapsed

        self.methods = methods

    def copy(self):
        """
        Return a copy of this
        @return:
        """
        return PowerFlowResults(Sbus=self.Sbus, voltage=self.voltage, Sbranch=self.Sbranch,
                                Ibranch=self.Ibranch, loading=self.loading,
                                losses=self.losses, error=self.error,
                                converged=self.converged, Qpv=self.Qpv, inner_it=self.inner_iterations,
                                outer_it=self.outer_iterations, elapsed=self.elapsed, methods=self.methods)

    def initialize(self, n, m):
        """
        Initialize the arrays
        @param n: number of buses
        @param m: number of branches
        @return:
        """
        self.Sbus = zeros(n, dtype=complex)

        self.voltage = zeros(n, dtype=complex)

        self.overvoltage = zeros(n, dtype=complex)

        self.undervoltage = zeros(n, dtype=complex)

        self.Sbranch = zeros(m, dtype=complex)

        self.Ibranch = zeros(m, dtype=complex)

        self.loading = zeros(m, dtype=complex)

        self.flow_direction = zeros(m, dtype=float)

        self.losses = zeros(m, dtype=complex)

        self.overloads = zeros(m, dtype=complex)

        self.error = list()

        self.converged = list()

        self.buses_useful_for_storage = list()

        self.plot_bars_limit = 100

        self.inner_iterations = list()

        self.outer_iterations = list()

        self.elapsed = list()

        self.methods = list()

    def apply_from_island(self, results, b_idx, br_idx):
        """
        Apply results from another island circuit to the circuit results represented here
        @param results: PowerFlowResults
        @param b_idx: bus original indices
        @param br_idx: branch original indices
        @return:
        """
        self.Sbus[b_idx] = results.Sbus

        self.voltage[b_idx] = results.voltage

        # self.overvoltage[b_idx] = results.overvoltage

        # self.undervoltage[b_idx] = results.undervoltage

        self.Sbranch[br_idx] = results.Sbranch

        self.Ibranch[br_idx] = results.Ibranch

        self.loading[br_idx] = results.loading

        self.losses[br_idx] = results.losses

        self.flow_direction[br_idx] = results.flow_direction

        # self.overloads[br_idx] = results.overloads

        # if results.error > self.error:
        self.error.append(results.error)

        self.converged.append(results.converged)

        self.inner_iterations.append(results.inner_iterations)

        self.outer_iterations.append(results.outer_iterations)

        self.elapsed.append(results.elapsed)

        self.methods.append(results.methods)

        # self.converged = self.converged and results.converged

        # if results.buses_useful_for_storage is not None:
        #     self.buses_useful_for_storage = b_idx[results.buses_useful_for_storage]

    def check_limits(self, F, T, Vmax, Vmin, wo=1, wv1=1, wv2=1):
        """
        Check the grid violations on the whole circuit
        Args:
            F:
            T:
            Vmax:
            Vmin:
            wo:
            wv1:
            wv2:
        Returns:summation of the deviations
        """
        # branches: Returns the loading rate when greater than 1 (nominal), zero otherwise
        br_idx = where(self.loading > 1)[0]
        bb_f = F[br_idx]
        bb_t = T[br_idx]
        self.overloads = self.loading[br_idx]

        # Over and under voltage values in the indices where it occurs
        Vabs = np.abs(self.voltage)
        vo_idx = where(Vabs > Vmax)[0]
        self.overvoltage = (Vabs - Vmax)[vo_idx]
        vu_idx = where(Vabs < Vmin)[0]
        self.undervoltage = (Vmin - Vabs)[vu_idx]

        self.overloads_idx = br_idx

        self.overvoltage_idx = vo_idx

        self.undervoltage_idx = vu_idx

        self.buses_useful_for_storage = list(set(r_[vo_idx, vu_idx, bb_f, bb_t]))

        return np.abs(wo * np.sum(self.overloads) + wv1 * np.sum(self.overvoltage) + wv2 * np.sum(self.undervoltage))

    def get_convergence_report(self):

        res = 'converged' + str(self.converged)

        res += '\n\tinner_iterations: ' + str(self.inner_iterations)

        res += '\n\touter_iterations: ' + str(self.outer_iterations)

        res += '\n\terror: ' + str(self.error)

        res += '\n\telapsed: ' + str(self.elapsed)

        res += '\n\tmethods: ' + str(self.methods)

        return res

    def get_report_dataframe(self, island_idx=0):

        data = np.c_[self.methods[island_idx],
                     self.converged[island_idx],
                     self.error[island_idx],
                     self.elapsed[island_idx],
                     self.inner_iterations[island_idx]]
        col = ['Method', 'Converged?', 'Error', 'Elapsed (s)', 'Iterations']
        df = pd.DataFrame(data, columns=col)

        return df

    def plot(self, result_type, ax=None, indices=None, names=None):
        """
        Plot the results
        Args:
            result_type:
            ax:
            indices:
            names:

        Returns:

        """

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        if indices is None and names is not None:
            indices = array(range(len(names)))

        if len(indices) > 0:
            labels = names[indices]
            y_label = ''
            title = ''
            polar = False
            if result_type == 'Bus voltage':
                y = self.voltage[indices]
                y_label = '(p.u.)'
                title = 'Bus voltage '
                polar = False

            elif result_type == 'Bus voltage (polar)':
                y = self.voltage[indices]
                y_label = '(p.u.)'
                title = 'Bus voltage '
                polar = True

            elif result_type == 'Branch power':
                y = self.Sbranch[indices]
                y_label = '(MVA)'
                title = 'Branch power '
                polar = False

            elif result_type == 'Branch current':
                y = self.Ibranch[indices]
                y_label = '(p.u.)'
                title = 'Branch current '
                polar = False

            elif result_type == 'Branch_loading':
                y = self.loading[indices] * 100
                y_label = '(%)'
                title = 'Branch loading '
                polar = False

            elif result_type == 'Branch losses':
                y = self.losses[indices]
                y_label = '(MVA)'
                title = 'Branch losses '
                polar = False

            elif result_type == 'Battery power':
                y = self.battery_power_inc[indices]
                y_label = '(MVA)'
                title = 'Battery power'
                polar = False
            else:
                n = len(labels)
                y = np.zeros(n)
                x_label = ''
                y_label = ''
                title = ''

            # plot
            df = pd.DataFrame(data=y, index=labels, columns=[result_type])
            if len(df.columns) < self.plot_bars_limit:
                df.abs().plot(ax=ax, kind='bar')
            else:
                df.abs().plot(ax=ax, legend=False, linewidth=LINEWIDTH)
            ax.set_ylabel(y_label)
            ax.set_title(title)

            return df

        else:
            return None

    def export_all(self):
        """
        Exports all the results to DataFrames
        :return: Bus results, Branch reuslts
        """

        # buses results
        vm = np.abs(self.voltage)
        va = np.angle(self.voltage)
        vr = self.voltage.real
        vi = self.voltage.imag
        bus_data = c_[vr, vi, vm, va]
        bus_cols = ['Real voltage (p.u.)', 'Imag Voltage (p.u.)', 'Voltage module (p.u.)', 'Voltage angle (rad)']
        df_bus = pd.DataFrame(data=bus_data, columns=bus_cols)

        # branch results
        sr = self.Sbranch.real
        si = self.Sbranch.imag
        sm = np.abs(self.Sbranch)
        ld = np.abs(self.loading)
        ls = np.abs(self.losses)

        branch_data = c_[sr, si, sm, ld, ls]
        branch_cols = ['Real power (MW)', 'Imag power (MVAr)', 'Power module (MVA)', 'Loading(%)', 'Losses (MVA)']
        df_branch = pd.DataFrame(data=branch_data, columns=branch_cols)

        return df_bus, df_branch


class TimeSeriesInput:

    def __init__(self, s_profile: pd.DataFrame = None, i_profile: pd.DataFrame = None, y_profile: pd.DataFrame = None):
        """
        Time series input
        @param s_profile: DataFrame with the profile of the injected power at the buses
        @param i_profile: DataFrame with the profile of the injected current at the buses
        @param y_profile: DataFrame with the profile of the shunt admittance at the buses
        """

        # master time array. All the profiles must match its length
        self.time_array = None

        self.Sprof = s_profile
        self.Iprof = i_profile
        self.Yprof = y_profile

        # Array of load admittances (shunt)
        self.Y = None

        # Array of load currents
        self.I = None

        # Array of aggregated bus power (loads, generators, storage, etc...)
        self.S = None

        # is this timeSeriesInput valid? typically it is valid after compiling it
        self.valid = False

    def compile(self):
        """
        Generate time-consistent arrays
        @return:
        """
        cols = list()
        self.valid = False
        merged = None
        for p in [self.Sprof, self.Iprof, self.Yprof]:
            if p is None:
                cols.append(None)
            else:
                if merged is None:
                    merged = p
                else:
                    merged = pd.concat([merged, p], axis=1)
                cols.append(p.columns)
                self.valid = True

        # by merging there could have been time inconsistencies that would produce NaN
        # to solve it we "interpolate" by replacing the NaN by the nearest value
        if merged is not None:
            merged.interpolate(method='nearest', axis=0, inplace=True)

            t, n = merged.shape

            # pick the merged series time
            self.time_array = merged.index.values

            # Array of aggregated bus power (loads, generators, storage, etc...)
            if cols[0] is not None:
                self.S = merged[cols[0]].values
            else:
                self.S = zeros((t, n), dtype=complex)

            # Array of load currents
            if cols[1] is not None:
                self.I = merged[cols[1]].values
            else:
                self.I = zeros((t, n), dtype=complex)

            # Array of load admittances (shunt)
            if cols[2] is not None:
                self.Y = merged[cols[2]].values
            else:
                self.Y = zeros((t, n), dtype=complex)

    def get_at(self, t):
        """
        Returns the necessary values
        @param t: time index
        @return:
        """
        return self.Y[t, :], self.I[t, :], self.S[t, :]

    def get_from_buses(self, bus_idx):
        """

        @param bus_idx:
        @return:
        """
        ts = TimeSeriesInput()
        ts.S = self.S[:, bus_idx]
        ts.I = self.I[:, bus_idx]
        ts.Y = self.Y[:, bus_idx]
        ts.valid = True
        return ts

    def apply_from_island(self, res, bus_original_idx, branch_original_idx, nbus_full, nbranch_full):
        """

        :param res: TimeSeriesInput
        :param bus_original_idx:
        :param branch_original_idx:
        :param nbus_full:
        :param nbranch_full:
        :return:
        """

        if res is not None:
            if self.Sprof is None:
                self.time_array = res.time_array
                # t = len(self.time_array)
                self.Sprof = pd.DataFrame()  # zeros((t, nbus_full), dtype=complex)
                self.Iprof = pd.DataFrame()  # zeros((t, nbranch_full), dtype=complex)
                self.Yprof = pd.DataFrame()  # zeros((t, nbus_full), dtype=complex)

            self.Sprof[res.Sprof.columns.values] = res.Sprof
            self.Iprof[res.Iprof.columns.values] = res.Iprof
            self.Yprof[res.Yprof.columns.values] = res.Yprof

    def copy(self):

        cpy = TimeSeriesInput()

        # master time array. All the profiles must match its length
        cpy.time_array = self.time_array

        cpy.Sprof = self.Sprof.copy()
        cpy.Iprof = self.Iprof.copy()
        cpy.Yprof = self.Yprof.copy()

        # Array of load admittances (shunt)
        cpy.Y = self.Y.copy()

        # Array of load currents
        cpy.I = self.I.copy()

        # Array of aggregated bus power (loads, generators, storage, etc...)
        cpy.S = self.S.copy()

        # is this timeSeriesInput valid? typically it is valid after compiling it
        cpy.valid = self.valid

        return cpy


class MonteCarloInput:

    def __init__(self, n, Scdf, Icdf, Ycdf):
        """
        Monte carlo input constructor
        @param n: number of nodes
        @param Scdf: Power cumulative density function
        @param Icdf: Current cumulative density function
        @param Ycdf: Admittances cumulative density function
        """

        # number of nodes
        self.n = n

        self.Scdf = Scdf

        self.Icdf = Icdf

        self.Ycdf = Ycdf

    def __call__(self, samples=0, use_latin_hypercube=False):
        """
        Call this object
        :param samples: number of samples
        :param use_latin_hypercube: use Latin Hypercube to sample
        :return: Time series object
        """
        if use_latin_hypercube:

            lhs_points = lhs(self.n, samples=samples, criterion='center')

            if samples > 0:
                S = zeros((samples, self.n), dtype=complex)
                I = zeros((samples, self.n), dtype=complex)
                Y = zeros((samples, self.n), dtype=complex)

                for i in range(self.n):
                    if self.Scdf[i] is not None:
                        S[:, i] = self.Scdf[i].get_at(lhs_points[:, i])

        else:
            if samples > 0:
                S = zeros((samples, self.n), dtype=complex)
                I = zeros((samples, self.n), dtype=complex)
                Y = zeros((samples, self.n), dtype=complex)

                for i in range(self.n):
                    if self.Scdf[i] is not None:
                        S[:, i] = self.Scdf[i].get_sample(samples)
            else:
                S = zeros(self.n, dtype=complex)
                I = zeros(self.n, dtype=complex)
                Y = zeros(self.n, dtype=complex)

                for i in range(self.n):
                    if self.Scdf[i] is not None:
                        S[i] = complex(self.Scdf[i].get_sample()[0])

        time_series_input = TimeSeriesInput()
        time_series_input.S = S
        time_series_input.I = I
        time_series_input.Y = Y
        time_series_input.valid = True

        return time_series_input

    def get_at(self, x):
        """
        Get samples at x
        Args:
            x: values in [0, 1] to sample the CDF

        Returns: Time series object
        """
        S = zeros((1, self.n), dtype=complex)
        I = zeros((1, self.n), dtype=complex)
        Y = zeros((1, self.n), dtype=complex)

        for i in range(self.n):
            if self.Scdf[i] is not None:
                S[:, i] = self.Scdf[i].get_at(x[i])

        time_series_input = TimeSeriesInput()
        time_series_input.S = S
        time_series_input.I = I
        time_series_input.Y = Y
        time_series_input.valid = True

        return time_series_input


class MonteCarloResults:

    def __init__(self, n, m, p=0):
        """
        Constructor
        @param n: number of nodes
        @param m: number of branches
        @param p: number of points (rows)
        """

        self.n = n

        self.m = m

        self.S_points = zeros((p, n), dtype=complex)

        self.V_points = zeros((p, n), dtype=complex)

        self.I_points = zeros((p, m), dtype=complex)

        self.loading_points = zeros((p, m), dtype=complex)

        # self.Vstd = zeros(n, dtype=complex)

        self.error_series = list()

        self.voltage = zeros(n)
        self.current = zeros(m)
        self.loading = zeros(m)
        self.sbranch = zeros(m)
        self.losses = zeros(m)

        # magnitudes standard deviation convergence
        self.v_std_conv = None
        self.c_std_conv = None
        self.l_std_conv = None

        # magnitudes average convergence
        self.v_avg_conv = None
        self.c_avg_conv = None
        self.l_avg_conv = None

        self.available_results = ['Bus voltage avg', 'Bus voltage std',
                                  'Branch current avg', 'Branch current std',
                                  'Branch loading avg', 'Branch loading std',
                                  'Bus voltage CDF', 'Branch loading CDF']

    def append_batch(self, mcres):
        """
        Append a batch (a MonteCarloResults object) to this object
        @param mcres: MonteCarloResults object
        @return:
        """
        self.S_points = vstack((self.S_points, mcres.S_points))
        self.V_points = vstack((self.V_points, mcres.V_points))
        self.I_points = vstack((self.I_points, mcres.I_points))
        self.loading_points = vstack((self.loading_points, mcres.loading_points))

    def get_voltage_sum(self):
        """
        Return the voltage summation
        @return:
        """
        return self.V_points.sum(axis=0)

    def compile(self):
        """
        Compiles the final Monte Carlo values by running an online mean and
        @return:
        """
        p, n = self.V_points.shape
        ni, m = self.I_points.shape
        step = 1
        nn = int(floor(p / step) + 1)
        self.v_std_conv = zeros((nn, n))
        self.c_std_conv = zeros((nn, m))
        self.l_std_conv = zeros((nn, m))
        self.v_avg_conv = zeros((nn, n))
        self.c_avg_conv = zeros((nn, m))
        self.l_avg_conv = zeros((nn, m))

        v_mean = zeros(n)
        c_mean = zeros(m)
        l_mean = zeros(m)
        v_std = zeros(n)
        c_std = zeros(m)
        l_std = zeros(m)

        for t in range(1, p, step):
            v_mean_prev = v_mean.copy()
            c_mean_prev = c_mean.copy()
            l_mean_prev = l_mean.copy()

            v = abs(self.V_points[t, :])
            c = abs(self.I_points[t, :])
            l = abs(self.loading_points[t, :])

            v_mean += (v - v_mean) / t
            v_std += (v - v_mean) * (v - v_mean_prev)
            self.v_avg_conv[t] = v_mean
            self.v_std_conv[t] = v_std / t

            c_mean += (c - c_mean) / t
            c_std += (c - c_mean) * (c - c_mean_prev)
            self.c_std_conv[t] = c_std / t
            self.c_avg_conv[t] = c_mean

            l_mean += (l - l_mean) / t
            l_std += (l - l_mean) * (l - l_mean_prev)
            self.l_std_conv[t] = l_std / t
            self.l_avg_conv[t] = l_mean

        self.voltage = self.v_avg_conv[-2]
        self.current = self.c_avg_conv[-2]
        self.loading = self.l_avg_conv[-2]

    def save(self, fname):
        """
        Export as pickle
        Args:
            fname:

        Returns:

        """
        data = [self.S_points, self.V_points, self.I_points]

        with open(fname, "wb") as output_file:
            pkl.dump(data, output_file)

    def open(self, fname):
        """
        open pickle
        Args:
            fname: file name
        Returns: true if succeeded, false otherwise

        """
        if os.path.exists(fname):
            with open(fname, "rb") as input_file:
                self.S_points, self.V_points, self.I_points = pkl.load(input_file)
            return True
        else:
            warn(fname + " not found")
            return False

    def query_voltage(self, power_array):
        """
        Fantastic function that allows to query the voltage from the sampled points without having to run power flows
        Args:
            power_array: power injections vector

        Returns: Interpolated voltages vector
        """
        x_train = np.hstack((self.S_points.real, self.S_points.imag))
        y_train = np.hstack((self.V_points.real, self.V_points.imag))
        x_test = np.hstack((power_array.real, power_array.imag))

        n, d = x_train.shape

        # #  declare PCA reductor
        # red = PCA()
        #
        # # Train PCA
        # red.fit(x_train, y_train)
        #
        # # Reduce power dimensions
        # x_train = red.transform(x_train)

        # model = MLPRegressor(hidden_layer_sizes=(10*n, n, n, n), activation='relu', solver='adam', alpha=0.0001,
        #                      batch_size=2, learning_rate='constant', learning_rate_init=0.01, power_t=0.5,
        #                      max_iter=3, shuffle=True, random_state=None, tol=0.0001, verbose=True,
        #                      warm_start=False, momentum=0.9, nesterovs_momentum=True, early_stopping=False,
        #                      validation_fraction=0.1, beta_1=0.9, beta_2=0.999, epsilon=1e-08)

        # algorithm : {‘auto’, ‘ball_tree’, ‘kd_tree’, ‘brute’},
        # model = KNeighborsRegressor(n_neighbors=4, algorithm='brute', leaf_size=16)

        model = RandomForestRegressor(10)

        # model = DecisionTreeRegressor()

        # model = LinearRegression()

        model.fit(x_train, y_train)

        y_pred = model.predict(x_test)

        return y_pred[:, :int(d / 2)] + 1j * y_pred[:, int(d / 2):d]

    def get_index_loading_cdf(self, max_val=1.0):
        """
        Find the elements where the CDF is greater or equal to a velue
        :param max_val: value to compare
        :return: indices, associated probability
        """

        # turn the loading real values into CDF
        cdf = CDF(np.abs(self.loading_points.real[:, :]))

        n = cdf.arr.shape[1]
        idx = list()
        val = list()
        prob = list()
        for i in range(n):
            # Find the indices that surpass max_val
            many_idx = np.where(cdf.arr[:, i] > max_val)[0]

            # if there are indices, pick the first; store it and its associated probability
            if len(many_idx) > 0:
                idx.append(i)
                val.append(cdf.arr[many_idx[0], i])
                prob.append(1 - cdf.prob[many_idx[0]])  # the CDF stores the chance of beign leq than the value, hence the overload is the complementary

        return idx, val, prob, cdf.arr[-1, :]

    def plot(self, result_type, ax=None, indices=None, names=None):
        """
        Plot the results
        :param result_type:
        :param ax:
        :param indices:
        :param names:
        :return:
        """

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        p, n = self.V_points.shape

        if indices is None:
            if names is None:
                indices = arange(0, n, 1)
                labels = None
            else:
                indices = array(range(len(names)))
                labels = names[indices]
        else:
            labels = names[indices]

        if len(indices) > 0:

            y_label = ''
            title = ''
            if result_type == 'Bus voltage avg':
                y = self.v_avg_conv[1:-1, indices]
                y_label = '(p.u.)'
                x_label = 'Sampling points'
                title = 'Bus voltage \naverage convergence'

            elif result_type == 'Branch current avg':
                y = self.c_avg_conv[1:-1, indices]
                y_label = '(p.u.)'
                x_label = 'Sampling points'
                title = 'Bus current \naverage convergence'

            elif result_type == 'Branch loading avg':
                y = self.l_avg_conv[1:-1, indices]
                y_label = '(%)'
                x_label = 'Sampling points'
                title = 'Branch loading \naverage convergence'

            elif result_type == 'Bus voltage std':
                y = self.v_std_conv[1:-1, indices]
                y_label = '(p.u.)'
                x_label = 'Sampling points'
                title = 'Bus voltage standard \ndeviation convergence'

            elif result_type == 'Branch current std':
                y = self.c_std_conv[1:-1, indices]
                y_label = '(p.u.)'
                x_label = 'Sampling points'
                title = 'Bus current standard \ndeviation convergence'

            elif result_type == 'Branch loading std':
                y = self.l_std_conv[1:-1, indices]
                y_label = '(%)'
                x_label = 'Sampling points'
                title = 'Branch loading standard \ndeviation convergence'

            elif result_type == 'Bus voltage CDF':
                cdf = CDF(np.abs(self.V_points[:, indices]))
                cdf.plot(ax=ax)
                y_label = '(p.u.)'
                x_label = 'Probability $P(X \leq x)$'
                title = 'Bus voltage'

            elif result_type == 'Branch loading CDF':
                cdf = CDF(np.abs(self.loading_points.real[:, indices]))
                cdf.plot(ax=ax)
                y_label = '(p.u.)'
                x_label = 'Probability $P(X \leq x)$'
                title = 'Branch loading'

            else:
                x_label = ''
                y_label = ''
                title = ''

            if 'CDF' not in result_type:
                df = pd.DataFrame(data=y, columns=labels)

                if len(df.columns) > 10:
                    df.abs().plot(ax=ax, linewidth=LINEWIDTH, legend=False)
                else:
                    df.abs().plot(ax=ax, linewidth=LINEWIDTH, legend=True)
            else:
                df = pd.DataFrame(index=cdf.prob, data=cdf.arr, columns=labels)

            ax.set_title(title)
            ax.set_ylabel(y_label)
            ax.set_xlabel(x_label)

            return df

        else:
            return None


class OptimalPowerFlowResults:

    def __init__(self, Sbus=None, voltage=None, load_shedding=None, generation_shedding=None,
                 battery_power=None, controlled_generation_power=None,
                 Sbranch=None, overloads=None, loading=None, converged=None):
        """
        OPF results constructor
        :param Sbus: bus power injections
        :param voltage: bus voltages
        :param load_shedding: load shedding values
        :param Sbranch: branch power values
        :param overloads: branch overloading values
        :param loading: branch loading values
        :param losses: branch losses
        :param converged: converged?
        """
        self.Sbus = Sbus

        self.voltage = voltage

        self.load_shedding = load_shedding

        self.generation_shedding = generation_shedding

        self.Sbranch = Sbranch

        self.overloads = overloads

        self.loading = loading

        self.battery_power = battery_power

        self.controlled_generation_power = controlled_generation_power

        self.flow_direction = None

        self.converged = converged

        self.available_results = ['Bus voltage module', 'Bus voltage angle', 'Branch power',
                                  'Branch loading', 'Branch overloads', 'Load shedding',
                                  'Controlled generator shedding',
                                  'Controlled generator power', 'Battery power']

        self.plot_bars_limit = 100

    def copy(self):
        """
        Return a copy of this
        @return:
        """
        return OptimalPowerFlowResults(Sbus=self.Sbus,
                                       voltage=self.voltage,
                                       load_shedding=self.load_shedding,
                                       Sbranch=self.Sbranch,
                                       overloads=self.overloads,
                                       loading=self.loading,
                                       generation_shedding=self.generation_shedding,
                                       battery_power=self.battery_power,
                                       controlled_generation_power=self.controlled_generation_power,
                                       converged=self.converged)

    def initialize(self, n, m):
        """
        Initialize the arrays
        @param n: number of buses
        @param m: number of branches
        @return:
        """
        self.Sbus = zeros(n, dtype=complex)

        self.voltage = zeros(n, dtype=complex)

        self.load_shedding = zeros(n, dtype=float)

        self.Sbranch = zeros(m, dtype=complex)

        self.loading = zeros(m, dtype=complex)

        self.overloads = zeros(m, dtype=complex)

        self.losses = zeros(m, dtype=complex)

        self.converged = list()

        self.plot_bars_limit = 100

    def plot(self, result_type, ax=None, indices=None, names=None):
        """
        Plot the results
        :param result_type: type of results (string)
        :param ax: matplotlib axis object
        :param indices: element indices
        :param names: element names
        :return: DataFrame of the results (or None if the result was not understood)
        """

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        if indices is None:
            indices = array(range(len(names)))

        if len(indices) > 0:
            labels = names[indices]
            y_label = ''
            title = ''
            if result_type == 'Bus voltage module':
                y = np.abs(self.voltage[indices])
                y_label = '(p.u.)'
                title = 'Bus voltage module'

            if result_type == 'Bus voltage angle':
                y = np.angle(self.voltage[indices])
                y_label = '(Radians)'
                title = 'Bus voltage angle'

            elif result_type == 'Branch power':
                y = self.Sbranch[indices].real
                y_label = '(MW)'
                title = 'Branch power '

            elif result_type == 'Bus power':
                y = self.Sbus[indices].real
                y_label = '(MW)'
                title = 'Bus power '

            elif result_type == 'Branch loading':
                y = np.abs(self.loading[indices] * 100.0)
                y_label = '(%)'
                title = 'Branch loading '

            elif result_type == 'Branch overloads':
                y = np.abs(self.overloads[indices])
                y_label = '(MW)'
                title = 'Branch overloads '

            elif result_type == 'Branch losses':
                y = self.losses[indices].real
                y_label = '(MW)'
                title = 'Branch losses '

            elif result_type == 'Load shedding':
                y = self.load_shedding[indices]
                y_label = '(MW)'
                title = 'Load shedding'

            elif result_type == 'Controlled generator shedding':
                y = self.generation_shedding[indices]
                y_label = '(MW)'
                title = 'Controlled generator shedding'

            elif result_type == 'Controlled generator power':
                y = self.controlled_generation_power[indices]
                y_label = '(MW)'
                title = 'Controlled generators power'

            elif result_type == 'Battery power':
                y = self.battery_power[indices]
                y_label = '(MW)'
                title = 'Battery power'

            else:
                pass

            df = pd.DataFrame(data=y, index=labels, columns=[result_type])
            df.fillna(0, inplace=True)

            if len(df.columns) < self.plot_bars_limit:
                df.plot(ax=ax, kind='bar')
            else:
                df.plot(ax=ax, legend=False, linewidth=LINEWIDTH)
            ax.set_ylabel(y_label)
            ax.set_title(title)

            return df

        else:
            return None

