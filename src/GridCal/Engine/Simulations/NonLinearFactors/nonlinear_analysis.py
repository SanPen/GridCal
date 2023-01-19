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
import numba as nb
import scipy as sp

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit, SnapshotData
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods import helm_coefficients_dY, helm_preparation_dY


def calc_V_outage(branch_data, If, Ybus, Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv):
    """
    Calculate the voltage due to outages in a non-linear manner with HELM.
    The main novelty is the introduction of s.AY, thus delaying it
    Use directly V from HELM, do not go for Pade, may need more time for not much benefit

    :param branch_data: branch data for all branches to disconnect
    :param If: from currents of the initial power flow
    :param Ybus: original admittance matrix
    :param Yseries: admittance matrix with only series branches
    :param V0: initial voltage array
    :param S0: vector of powers
    :param Ysh0: array of shunt admittances
    :param pq: set of PQ buses
    :param pv: set of PV buses
    :param sl: set of slack buses
    :param pqpv: set of PQ + PV buses
    :return: matrix of voltages after the outages and power flow errors
    """

    nbus = Ybus.shape[0]
    nbr = len(branch_data)
    V_cont = np.zeros((nbus, nbr), dtype=complex)
    err = np.zeros(nbr)

    mat_factorized, Uini, Xini, Yslack, Vslack, vec_P, vec_Q, Ysh, vec_W, pq_, pv_, pqpv_, npqpv, n = helm_preparation_dY(Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv)

    for i in range(nbr):

        row_buses_f, col_buses_f = branch_data.C_branch_bus_f.nonzero()
        row_buses_t, col_buses_t = branch_data.C_branch_bus_t.nonzero()

        # build the admittance matrix that modifies the original admittance matrix
        dY = build_dY_outage(bus_f=col_buses_f[i],
                             bus_t=col_buses_t[i],
                             G0sw=branch_data.G0sw[i][0],
                             Beq=branch_data.Beq[i][0],
                             k=branch_data.k[i],
                             If=If[col_buses_f[i]],
                             a=branch_data.a[i],
                             b=branch_data.b[i],
                             c=branch_data.c[i],
                             rs=branch_data.R[i],
                             xs=branch_data.X[i],
                             gsh=branch_data.G[i],
                             bsh=branch_data.B[i],
                             tap_module=branch_data.m[i][0],
                             vtap_f=branch_data.tap_f[i],
                             vtap_t=branch_data.tap_t[i],
                             tap_angle=branch_data.theta[i][0],
                             n_bus=nbus)

        # solve the modified HELM
        U, V, iter_, norm_f = helm_coefficients_dY(dY, mat_factorized, Uini, Xini, Yslack, Ysh, Ybus, vec_P, vec_Q, S0,
                                                   vec_W, V0, Vslack, pq_, pv_, pqpv_, npqpv, n, pqpv, pq, sl,
                                                   tolerance=1e-6, max_coeff=10)

        V_cont[:, i] = V
        err[i] = norm_f

    return V_cont, err


def build_dY_outage(bus_f, bus_t, G0sw, Beq, k, If, a, b, c, rs, xs,
                    gsh, bsh, tap_module, vtap_f, vtap_t, tap_angle, n_bus):
    """
    Construct the ∆Y admittance matrix for all the contingencies
    :param bus_f:
    :param bus_t:
    :param G0sw:
    :param Beq:
    :param k:
    :param If:
    :param a:
    :param b:
    :param c:
    :param rs:
    :param xs:
    :param gsh:
    :param bsh:
    :param tap_module:
    :param vtap_f:
    :param vtap_t:
    :param tap_angle:
    :param n_bus:
    :return:
    """
    # compute G-switch
    Gsw = G0sw + a * np.power(If, 2) + b * If + c

    # form the admittance matrices
    ys = 1.0 / (rs + 1.0j * xs + 1e-20)  # series admittance
    bc2 = (gsh + 1j * bsh) / 2.0  # shunt admittance
    mp = k * tap_module

    Yff = Gsw + (ys + bc2 + 1.0j * Beq) / (mp * mp * vtap_f * vtap_f)
    Yft = -ys / (mp * np.exp(-1.0j * tap_angle) * vtap_f * vtap_t)
    Ytf = -ys / (mp * np.exp(1.0j * tap_angle) * vtap_t * vtap_f)
    Ytt = (ys + bc2) / (vtap_t * vtap_t)

    data = [Yff, Yft, Ytf, Ytt]
    row = [bus_f, bus_f, bus_t, bus_t]
    col = [bus_f, bus_t, bus_f, bus_t]

    dYmat = sp.sparse.csr_matrix((data, (row, col)), shape=(n_bus, n_bus))  # TODO: Make absolutely certain of this, as it is coded it matches the COO format

    return -1 * dYmat  # negative because we are removing these admittances


def calc_ptdf_from_V(V_cont, Y, Pini, correct_values=True):
    """
    Compute the power transfer distribution factor from the voltages
    :param V_cont: matrix of voltages for all outages, size nbus * nbranch
    :param Y: bus admittance matrix
    :param Pini: initial active power per bus
    :param correct_values: Correct nonsense values
    :return: matrix of ptdf
    """

    nbr = V_cont.shape[1]
    Pbus = np.real(V_cont * np.conj(Y * V_cont))
    Pinim = np.vstack([Pini] * nbr).T

    ptdf = (Pbus - Pinim) / Pinim

    if correct_values:  # TODO check more efficient way

        # correct stupid values
        i1, j1 = np.where(ptdf > 1.2)
        for i, j in zip(i1, j1):
            ptdf[i, j] = 0

        i2, j2 = np.where(ptdf < -1.2)
        for i, j in zip(i2, j2):
            ptdf[i, j] = 0

        # ensure +-1 values
        i1, j1 = np.where(ptdf > 1)
        for i, j in zip(i1, j1):
            ptdf[i, j] = 1

        i2, j2 = np.where(ptdf < -1)
        for i, j in zip(i2, j2):
            ptdf[i, j] = -1

    return ptdf.T


def calc_lodf_from_V(V_cont, Yf, Cf, Pini, correct_values=True):
    """
    Compute the line outage distribution factor from the voltages
    :param V_cont: matrix of voltages for all outages, size nbus * nbranch
    :param Yf: from bus admittance matrix
    :param Cf: from connectivity matrix
    :param Pini: initial active power per line (from side)
    :param correct_values: Correct nonsense values
    :return: matrix of lodf
    """

    nbr = V_cont.shape[1]
    Vf = Cf * V_cont
    Pf = np.real(Vf * np.conj(Yf * V_cont))
    Pinim = np.vstack([Pini] * nbr).T

    lodf = (Pf - Pinim) / Pinim

    if correct_values:  # TODO check more efficient way

        # correct stupid values
        i1, j1 = np.where(lodf > 1.2)
        for i, j in zip(i1, j1):
            lodf[i, j] = 0

        i2, j2 = np.where(lodf < -1.2)
        for i, j in zip(i2, j2):
            lodf[i, j] = 0

        # ensure +-1 values
        i1, j1 = np.where(lodf > 1)
        for i, j in zip(i1, j1):
            lodf[i, j] = 1

        i2, j2 = np.where(lodf < -1)
        for i, j in zip(i2, j2):
            lodf[i, j] = -1

    return lodf


@nb.njit(cache=True)
def make_otdf(ptdf, lodf, j):
    """
    Outage sensitivity of the branches when transferring power from the bus j to the slack
        LODF: outage transfer distribution factors
    :param ptdf: power transfer distribution factors matrix (n-branch, n-bus)
    :param lodf: line outage distribution factors matrix (n-branch, n-branch)
    :param j: index of the bus injection
    :return: LODF matrix (n-branch, n-branch)
    """
    nk = ptdf.shape[0]
    nl = nk
    otdf = np.empty((nk, nl))

    for k in range(nk):
        for l in range(nl):
            otdf[k, l] = ptdf[k, j] + lodf[k, l] * ptdf[l, j]

    return otdf


@nb.njit(parallel=True)
def make_otdf_max(ptdf, lodf):
    """
    Maximum Outage sensitivity of the branches when transferring power from any bus to the slack
        LODF: outage transfer distribution factors
    :param ptdf: power transfer distribution factors matrix (n-branch, n-bus)
    :param lodf: line outage distribution factors matrix (n-branch, n-branch)
    :return: LODF matrix (n-branch, n-branch)
    """
    nj = ptdf.shape[1]
    nk = ptdf.shape[0]
    nl = nk
    otdf = np.zeros((nk, nl))

    if nj < 500:
        for j in range(nj):
            for k in range(nk):
                for l in range(nl):
                    val = ptdf[k, j] + lodf[k, l] * ptdf[l, j]
                    if abs(val) > abs(otdf[k, l]):
                        otdf[k, l] = val
    else:
        for j in nb.prange(nj):
            for k in range(nk):
                for l in range(nl):
                    val = ptdf[k, j] + lodf[k, l] * ptdf[l, j]
                    if abs(val) > abs(otdf[k, l]):
                        otdf[k, l] = val
    return otdf


@nb.njit(cache=True)
def make_contingency_flows(lodf, flows):
    """
    Make contingency Sf matrix
    :param lodf: line outage distribution factors
    :param flows: base Sf in MW
    :return: outage Sf for every line after each contingency (n-branch, n-branch[outage])
    """
    nbr = lodf.shape[0]
    omw = np.zeros((nbr, nbr))

    for m in range(nbr):
        for c in range(nbr):
            if m != c:
                omw[m, c] = flows[m] + lodf[m, c] * flows[c]

    return omw


@nb.njit(cache=True)
def make_transfer_limits(ptdf, flows, rates):
    """
    Compute the maximum transfer limits of each branch in normal operation
    :param ptdf: power transfer distribution factors matrix (n-branch, n-bus)
    :param flows: base Sf in MW
    :param rates: array of branch rates
    :return: Max transfer limits vector  (n-branch)
    """
    nbr = ptdf.shape[0]
    nbus = ptdf.shape[1]
    tmc = np.zeros(nbr)

    for m in range(nbr):
        for i in range(nbus):

            if ptdf[m, i] != 0.0:
                val = (rates[m] - flows[m]) / ptdf[m, i]  # I want it with sign

                # update the transference value
                if abs(val) > abs(tmc[m]):
                    tmc[m] = val

    return tmc


@nb.njit(parallel=True)
def make_contingency_transfer_limits(otdf_max, lodf, flows, rates):
    """
    Compute the maximum transfer limits after contingency of each branch
    :param otdf_max: Maximum Outage sensitivity of the branches when transferring power
                     from any bus to the slack  (n-branch, n-branch)
    :param omw: contingency Sf matrix (n-branch, n-branch)
    :param rates: array of branch rates
    :return: Max transfer limits matrix  (n-branch, n-branch)
    """
    nbr = otdf_max.shape[0]
    tmc = np.zeros((nbr, nbr))

    if nbr < 500:
        for m in range(nbr):
            for c in range(nbr):
                if m != c:
                    if otdf_max[m, c] != 0.0:
                        omw = flows[m] + lodf[m, c] * flows[c]  # compute the contingency flow
                        tmc[m, c] = (rates[m] - omw) / otdf_max[m, c]  # i want it with sign
    else:
        for m in nb.prange(nbr):
            for c in range(nbr):
                if m != c:
                    if otdf_max[m, c] != 0.0:
                        omw = flows[m] + lodf[m, c] * flows[c]  # compute the contingency flow
                        tmc[m, c] = (rates[m] - omw) / otdf_max[m, c]  # i want it with sign

    return tmc


def make_worst_contingency_transfer_limits(tmc):

    nbr = tmc.shape[0]
    wtmc = np.zeros((nbr, 2))

    wtmc[:, 0] = tmc.max(axis=1)
    wtmc[:, 1] = tmc.min(axis=1)

    return wtmc


class NonLinearAnalysis:

    def __init__(self, grid: MultiCircuit, distributed_slack=True, correct_values=True, pf_results=None):
        """

        :param grid:
        :param distributed_slack:
        """

        self.grid = grid

        self.distributed_slack = distributed_slack

        self.correct_values = correct_values

        self.numerical_circuit: SnapshotData = None

        self.PTDF = None  # power transfer distribution factors (n_br, n_bus)

        self.LODF = None # line outage distribution factors (n_br, n_br)

        self._OTDF = None

        self.V_cont = None  # contingency voltages (n_bus, n_br)

        self.err = 0.0

        self.pf_results = pf_results

        self.logger = Logger()

    def run(self):
        """
        Run the PTDF and LODF
        """
        self.numerical_circuit = compile_snapshot_circuit(self.grid)
        islands = self.numerical_circuit.split_into_islands()
        n_br = self.numerical_circuit.nbr
        n_bus = self.numerical_circuit.nbus
        self.PTDF = np.zeros((n_br, n_bus))
        self.LODF = np.zeros((n_br, n_br))
        self.V_cont = np.zeros((n_bus, n_br), dtype=complex)

        # check if power_flow results are passed
        if self.pf_results is None:
            self.logger.add_error('No initial power flow found, it is needed')
            raise Exception('No initial power flow found, it is needed')

        else:

            # compute the PTDF and LODF per islands
            if len(islands) > 0:
                for n_island, island in enumerate(islands):

                    # no slacks will make it impossible to compute the PTDF analytically
                    if len(island.vd) == 1:
                        if len(island.pqpv) > 0:

                            V_cont, err = calc_V_outage(island.branch_data, 
                                                        self.pf_results.If,
                                                        island.Ybus,
                                                        island.Yseries,
                                                        island.Vbus,
                                                        island.Sbus,
                                                        island.Yshunt,
                                                        island.pq,
                                                        island.pv,
                                                        island.vd,
                                                        island.pqpv)

                            ptdf_island = calc_ptdf_from_V(V_cont=V_cont,
                                                           Y=island.Ybus,
                                                           Pini=np.real(self.pf_results.Sbus),
                                                           correct_values=self.correct_values)

                            lodf_island = calc_lodf_from_V(V_cont=V_cont,
                                                           Yf=island.Yf,
                                                           Cf=island.Cf,
                                                           Pini=np.real(self.pf_results.Sf),
                                                           correct_values=self.correct_values)

                            # assign objects to the full matrix
                            self.err = err  # how to map it well?
                            self.V_cont[np.ix_(island.original_bus_idx, island.original_branch_idx)] = V_cont
                            self.PTDF[np.ix_(island.original_branch_idx, island.original_bus_idx)] = ptdf_island
                            self.LODF[np.ix_(island.original_branch_idx, island.original_branch_idx)] = lodf_island

                        else:
                            self.logger.add_error('No PQ or PV nodes', 'Island {}'.format(n_island))
                    elif len(island.vd) == 0:
                        self.logger.add_warning('No slack bus', 'Island {}'.format(n_island))
                    else:
                        self.logger.add_error('More than one slack bus', 'Island {}'.format(n_island))
            else:

                # there is only 1 island, use island[0]
                self.V_cont, self.err = calc_V_outage(islands[0].branch_data,
                                                      self.pf_results.If,
                                                      islands[0].Ybus,
                                                      islands[0].Yseries,
                                                      islands[0].Vbus,
                                                      islands[0].Sbus,
                                                      islands[0].Yshunt,
                                                      islands[0].pq,
                                                      islands[0].pv,
                                                      islands[0].vd,
                                                      islands[0].pqpv)

                self.PTDF = calc_ptdf_from_V(V_cont=self.V_cont,
                                             Y=islands[0].Ybus,
                                             Pini=np.real(self.pf_results.Sbus))

                self.LODF = calc_lodf_from_V(V_cont=self.V_cont,
                                             Yf=islands[0].Yf,
                                             Cf=islands[0].Cf,
                                             Pini=np.real(self.pf_results.Sf))

            print('Done running')

    @property
    def OTDF(self):
        """
        Maximum Outage sensitivity of the branches when transferring power from any bus to the slack
        LODF: outage transfer distribution factors
        :return: Maximum LODF matrix (n-branch, n-branch)
        """
        if self._OTDF is None:  # lazy-evaluation
            self._OTDF = make_otdf_max(self.PTDF, self.LODF)

        return self._OTDF

    def get_transfer_limits(self, flows):
        """
        compute the normal transfer limits
        :param flows: base Sf in MW
        :return: Max transfer limits vector (n-branch)
        """
        return make_transfer_limits(self.PTDF, flows, self.numerical_circuit.Rates)

    def get_contingency_transfer_limits(self, flows):
        """
        Compute the contingency transfer limits
        :param flows: base Sf in MW
        :return: Max transfer limits matrix (n-branch, n-branch)
        """
        return make_contingency_transfer_limits(self.OTDF, self.LODF, flows, self.numerical_circuit.Rates)

    def get_flows(self, Sbus):
        """
        Compute the time series branch Sf using the PTDF
        :param Sbus: Power injections time series array
        :return: branch active power Sf time series
        """

        # option 2: call the power directly
        Pbr = np.dot(self.PTDF, Sbus.real) * self.grid.Sbase

        return Pbr

    def get_flows_time_series(self, Sbus):
        """
        Compute the time series branch Sf using the PTDF
        :param Sbus: Power injections time series array
        :return: branch active power Sf time series
        """

        # option 2: call the power directly
        Pbr = np.dot(self.PTDF, Sbus.real).T * self.grid.Sbase

        return Pbr
