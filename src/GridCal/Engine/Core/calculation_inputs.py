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

from warnings import warn
import numpy as np
import pandas as pd
from scipy.sparse import diags, hstack as hstack_s, vstack as vstack_s
from scipy.sparse.linalg import factorized
from scipy.sparse import csc_matrix


from GridCal.Engine.basic_structures import BusMode
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCal.Engine.Simulations.PowerFlow.jacobian_based_power_flow import Jacobian


class CalculationInputs:
    """
    **nbus** (int): Number of buses

    **nbr** (int): Number of branches

    **ntime** (int): Number of time steps

    **nbat** (int): Number of batteries

    **nctrlgen** (int): Number of voltage controlled generators
    """

    def __init__(self, nbus, nbr, ntime, nbat, nctrlgen):

        self.nbus = nbus
        self.nbr = nbr
        self.ntime = ntime

        self.Sbase = 100.0

        self.time_array = None

        self.bus_names = np.empty(self.nbus, dtype=object)
        self.branch_names = np.empty(self.nbr, dtype=object)

        # lists of connectivity matrices (calculation)
        self.C_branch_bus_f = [csc_matrix((nbr, nbus), dtype=complex)] * ntime
        self.C_branch_bus_t = [csc_matrix((nbr, nbus), dtype=complex)] * ntime
        self.Yf = [csc_matrix((nbr, nbus), dtype=complex)] * ntime
        self.Yt = [csc_matrix((nbr, nbus), dtype=complex)] * ntime
        self.Ybus = [csc_matrix((nbus, nbus), dtype=complex)] * ntime
        self.Yseries = [csc_matrix((nbus, nbus), dtype=complex)] * ntime
        self.B1 = [csc_matrix((nbus, nbus), dtype=float)] * ntime
        self.B2 = [csc_matrix((nbus, nbus), dtype=float)] * ntime

        # structures to keep indices
        # time -> island -> indices
        self.original_bus_idx = [list()] * ntime
        self.original_branch_idx = [list()] * ntime
        self.original_gen_idx = [list()] * ntime
        self.original_bat_idx = [list()] * ntime

        # vectors to re-calculate the admittance matrices
        self.Ys = [np.zeros(nbr, dtype=complex)] * ntime
        self.GBc = [np.zeros(nbr, dtype=complex)] * ntime
        self.tap_f = np.zeros(nbr, dtype=float)
        self.tap_t = np.zeros(nbr, dtype=float)
        self.tap_ang = np.zeros(nbr, dtype=float)
        self.tap_mod = np.zeros(nbr, dtype=float)

        # injection profiles
        self.Ysh = np.zeros((ntime, nbus), dtype=complex)
        self.Sbus = np.zeros((ntime, nbus), dtype=complex)
        self.Ibus = np.zeros((ntime, nbus), dtype=complex)

        self.Vbus = np.ones(nbus, dtype=complex)
        self.Vmin = np.ones(nbus, dtype=float)
        self.Vmax = np.ones(nbus, dtype=float)
        self.types = np.zeros(nbus, dtype=int)
        self.Qmin = np.zeros(nbus, dtype=float)
        self.Qmax = np.zeros(nbus, dtype=float)

        # branch properties
        self.F = np.zeros(nbr, dtype=int)
        self.T = np.zeros(nbr, dtype=int)
        self.branch_rates = np.zeros(nbr)

        # needed fot the tap changer
        self.is_bus_to_regulated = np.zeros(nbr, dtype=int)
        self.bus_to_regulated_idx = None
        self.tap_position = np.zeros(nbr, dtype=int)
        self.min_tap = np.zeros(nbr, dtype=int)
        self.max_tap = np.zeros(nbr, dtype=int)
        self.tap_inc_reg_up = np.zeros(nbr, dtype=float)
        self.tap_inc_reg_down = np.zeros(nbr, dtype=float)
        self.vset = np.zeros(nbr, dtype=float)

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

        # this lists initially remain the same
        self.pq = list()
        self.pv = list()
        self.ref = list()
        self.sto = list()
        self.pqpv = list()

        self.logger = list()

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
        self.bus_to_regulated_idx = np.where(self.is_bus_to_regulated == True)[0]

        dispatcheable_batteries_idx = np.where(self.battery_dispatchable == True)[0]
        self.dispatcheable_batteries_bus_idx = np.where(np.array(self.C_batt_bus[dispatcheable_batteries_idx, :].sum(axis=0))[0] > 0)[0]

        self.compile_types()

    def get_island(self, bus_idx, branch_idx, gen_idx, bat_idx, t=0):
        """
        Get a sub-island
        :param bus_idx: bus indices of the island
        :param branch_idx: branch indices of the island
        :param gen_idx: generator indices
        :param bat_idx: battery indices
        :param t: snapshot index
        :return: CalculationInputs instance
        """
        obj = CalculationInputs(len(bus_idx), len(branch_idx), 1, len(bat_idx), len(gen_idx))

        # remember the island original indices
        obj.original_bus_idx[0] = bus_idx
        obj.original_branch_idx[0] = branch_idx

        obj.Yf[0] = self.Yf[t][branch_idx, :][:, bus_idx].copy()
        obj.Yt[0] = self.Yt[t][branch_idx, :][:, bus_idx].copy()
        obj.Ybus[0] = self.Ybus[t][bus_idx, :][:, bus_idx].copy()
        obj.Yseries[0] = self.Yseries[t][bus_idx, :][:, bus_idx].copy()
        obj.B1[0] = self.B1[t][bus_idx, :][:, bus_idx].copy()
        obj.B2[0] = self.B2[t][bus_idx, :][:, bus_idx].copy()
        obj.C_branch_bus_f[0] = self.C_branch_bus_f[t][branch_idx, :][:, bus_idx]
        obj.C_branch_bus_t[0] = self.C_branch_bus_t[t][branch_idx, :][:, bus_idx]

        obj.Ysh = self.Ysh[t, bus_idx]
        obj.Sbus = self.Sbus[t, bus_idx]
        obj.Ibus = self.Ibus[t, bus_idx]

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

    def compute_branch_results(self, V, t=0):
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
        data.Sbus[self.ref] = V[self.ref] * np.conj(self.Ybus[t][self.ref, :].dot(V))

        # Reactive power at the pv nodes: keep the original P injection and set the calculated reactive power
        Q = (V[self.pv] * np.conj(self.Ybus[t][self.pv, :].dot(V))).imag

        data.Sbus[t, self.pv] = self.Sbus[t, self.pv].real + 1j * Q

        # Branches current, loading, etc
        data.If = self.Yf[t] * V
        data.It = self.Yt[t] * V
        data.Sf = self.C_branch_bus_f[t] * V * np.conj(data.If)
        data.St = self.C_branch_bus_t[t] * V * np.conj(data.It)

        # Branch losses in MVA
        data.losses = (data.Sf + data.St)

        # Branch current in p.u.
        data.Ibranch = np.maximum(data.If, data.It)

        # Branch power in MVA
        data.Sbranch = np.maximum(data.Sf, data.St)

        # Branch loading in p.u.
        data.loading = data.Sbranch / (self.branch_rates + 1e-9)

        return data

    def re_calc_admittance_matrices(self, tap_mod, t=0):
        """
        Recalculate the admittance matrices as the tap changes
        :param tap_mod: tap modules per bus
        :param t: snapshot index
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
        self.Yf[t] = diags(Yff) * Cf + diags(Yft) * Ct
        self.Yt[t] = diags(Ytf) * Cf + diags(Ytt) * Ct
        self.Ybus[t] = csc_matrix(Cf.T * self.Yf[t] + Ct.T * self.Yt[t] + diags(self.Ysh[t, :]))

        # branch primitives in vector form
        Ytts = self.Ys
        Yffs = Ytts / (tap * np.conj(tap))
        Yfts = - self.Ys / np.conj(tap)
        Ytfs = - self.Ys / tap

        # form the admittance matrices of the series elements
        Yfs = diags(Yffs) * Cf + diags(Yfts) * Ct
        Yts = diags(Ytfs) * Cf + diags(Ytts) * Ct
        self.Yseries[t] = csc_matrix(Cf.T * Yfs + Ct.T * Yts)

        X = (1 / self.Ys).imag
        b1 = 1.0 / (X + 1e-20)
        B1f = diags(-b1) * Cf + diags(-b1) * Ct
        B1t = diags(-b1) * Cf + diags(-b1) * Ct
        self.B1[t] = csc_matrix(Cf.T * B1f + Ct.T * B1t)

        b2 = b1 + self.GBc.imag  # B == GBc.imag
        b2_ff = -(b2 / (tap * np.conj(tap))).real
        b2_ft = -(b1 / np.conj(tap)).real
        b2_tf = -(b1 / tap).real
        b2_tt = - b2
        B2f = diags(b2_ff) * Cf + diags(b2_ft) * Ct
        B2t = diags(b2_tf) * Cf + diags(b2_tt) * Ct
        self.B2[t] = csc_matrix(Cf.T * B2f + Ct.T * B2t)

    def build_linear_ac_sys_mat(self, t=0):
        """
        Get the AC linear approximation matrices
        :param t: snapshot index
        :return:
        """
        A11 = -self.Yseries[t].imag[self.pqpv, :][:, self.pqpv]
        A12 = self.Ybus[t].real[self.pqpv, :][:, self.pq]
        A21 = -self.Yseries[t].real[self.pq, :][:, self.pqpv]
        A22 = -self.Ybus[t].imag[self.pq, :][:, self.pq]

        A = vstack_s([hstack_s([A11, A12]),
                      hstack_s([A21, A22])], format="csc")

        # form the slack system matrix
        A11s = -self.Yseries[t].imag[self.ref, :][:, self.pqpv]
        A12s = self.Ybus[t].real[self.ref, :][:, self.pq]
        A_slack = hstack_s([A11s, A12s], format="csr")

        self.Asys[t] = factorized(A)

        return A, A_slack

    def get_structure(self, structure_type, t=0):
        """
        Get a DataFrame with the input
        :param structure_type: 'Vbus', 'Sbus', 'Ibus', 'Ybus', 'Yshunt', 'Yseries', 'Types'
        :param t: snapshot index
        Returns: Pandas DataFrame
        """

        if structure_type == 'Vbus':

            df = pd.DataFrame(data=self.Vbus, columns=['Voltage (p.u.)'], index=self.bus_names)

        elif structure_type == 'Sbus':
            df = pd.DataFrame(data=self.Sbus[t, :], columns=['Power (p.u.)'], index=self.bus_names)

        elif structure_type == 'Ibus':
            df = pd.DataFrame(data=self.Ibus[t, :], columns=['Current (p.u.)'], index=self.bus_names)

        elif structure_type == 'Ybus':
            df = pd.DataFrame(data=self.Ybus[t].toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == 'Yshunt':
            df = pd.DataFrame(data=self.Ysh[t, :], columns=['Shunt admittance (p.u.)'], index=self.bus_names)

        elif structure_type == 'Yseries':
            df = pd.DataFrame(data=self.Yseries[t].toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == "B'":
            df = pd.DataFrame(data=self.B1[t].toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == "B''":
            df = pd.DataFrame(data=self.B2[t].toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == 'Types':
            df = pd.DataFrame(data=self.types, columns=['Bus types'], index=self.bus_names)

        elif structure_type == 'Qmin':
            df = pd.DataFrame(data=self.Qmin, columns=['Qmin'], index=self.bus_names)

        elif structure_type == 'Qmax':
            df = pd.DataFrame(data=self.Qmax, columns=['Qmax'], index=self.bus_names)

        elif structure_type == 'Jacobian':

            J = Jacobian(self.Ybus[t], self.Vbus, self.Ibus[t, :], self.pq, self.pqpv)

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

    def print(self, bus_names, t=0):
        """
        print in console
        :param bus_names: Names of the buses
        :param t: snapshot index
        """

        df_bus = pd.DataFrame(
            np.c_[self.types, np.abs(self.Vbus), np.angle(self.Vbus), self.Vbus.real, self.Vbus.imag,
                  self.Sbus[t, :].real, self.Sbus[t, :].imag, self.Ysh[t, :].real, self.Ysh[t, :].imag],
            index=bus_names, columns=['Type', '|V|', 'angle', 're{V}', 'im{V}', 'P', 'Q', 'Gsh', 'Bsh'])
        # df_bus.sort_index(inplace=True)

        print('\nBus info\n', df_bus)

        if self.nbus < 100:
            print('\nYbus\n', pd.DataFrame(self.Ybus[t].todense(), columns=bus_names, index=bus_names))

        print('PQ:', self.pq)
        print('PV:', self.pv)
        print('REF:', self.ref)

