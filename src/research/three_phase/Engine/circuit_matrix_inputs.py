
import numpy as np
from scipy.sparse import lil_matrix

from research.three_phase.Engine.general import *
from research.three_phase.Engine.circuit_matrix_results import *


class CircuitMatrixInputs:

    def __init__(self, n, m, n_phase):
        """
        Class to store the compiled circuit matrices and vectors
        :param n: number of nodes
        :param m: number of branches
        :param n_phase: circuit number of phases
        """

        # list of slack bus indices
        self.ref = list()

        # list of pq bus indices
        self.pq = list()

        # list of pv bus indices
        self.pv = list()

        # nodal voltage initial solution (p.u.)
        self.Vbus = np.ones((n * n_phase), dtype=np.complex)

        # nodal power injections (p.u.)
        self.Sbus = np.zeros((n * n_phase), dtype=np.complex)

        # nodal current injections (p.u.)
        self.Ibus = np.zeros((n * n_phase), dtype=np.complex)

        # exponential load model parameters
        self.P0 = np.zeros((n * n_phase), dtype=np.float)
        self.Q0 = np.zeros((n * n_phase), dtype=np.float)
        self.exp_p = np.zeros((n * n_phase), dtype=np.float)
        self.exp_q = np.zeros((n * n_phase), dtype=np.float)
        self.V0 = np.zeros((n * n_phase), dtype=np.float)

        # polynomial load model
        self.A = np.zeros((n * n_phase), dtype=np.float)
        self.B = np.zeros((n * n_phase), dtype=np.float)
        self.C = np.zeros((n * n_phase), dtype=np.float)

        # nodal admittances (p.u.)
        self.Ybus_sh = np.zeros((n * n_phase), dtype=np.complex)

        # nodal admittance matrix (p.u.)
        self.Ybus = lil_matrix((n * n_phase, n * n_phase), dtype=np.complex)  # sparse and complex in lil format
        self.Yseries = lil_matrix((n * n_phase, n * n_phase), dtype=np.complex)  # sparse and complex in lil format

        # self.Yf = lil_matrix((m * n_phase, n * n_phase), dtype=np.complex)
        # self.Yt = lil_matrix((m * n_phase, n * n_phase), dtype=np.complex)

        # branch-bus connectivity matrix
        self.Cf = lil_matrix((m * n_phase, n * n_phase), dtype=int)
        self.Ct = lil_matrix((m * n_phase, n * n_phase), dtype=int)

        # branch (lines and transformers) ratings in MVA (per wire)
        self.branch_rates = np.zeros((m * n_phase), dtype=int)

        # columns mask for Ybus
        self.mask_c = np.zeros((n * n_phase), dtype=int)

        # rows mask for Ybus, Sbus, Ibus, Vbus
        self.mask_r = np.zeros((n * n_phase), dtype=int)

        # branches mask
        self.mask_k = np.zeros((m * n_phase), dtype=int)

        # bus types array
        self.bus_types = np.zeros((n * n_phase), dtype=int)

        # buses mask
        self.bus_mask = None

    def consolidate(self):
        """
        Consolidate in-place the matrices and vectors so that
        the non-connected phases are removed (having non connected phases makes Ybus singular)
        """

        # find the indices of the connected phases
        idx_r = np.where(self.mask_r > 0)[0]
        idx_c = np.where(self.mask_c > 0)[0]
        idx_k = np.where(self.mask_k > 0)[0]
        self.bus_mask = self.mask_r + self.mask_c

        # reduce the matrices and vectors (eliminate the spurious phases)
        self.Vbus = self.Vbus[idx_r]
        self.Sbus = self.Sbus[idx_r]
        self.Ibus = self.Ibus[idx_r]

        # reduce the exponential load model parameters
        self.P0 = self.P0[idx_r]
        self.Q0 = self.Q0[idx_r]
        self.exp_p = self.exp_p[idx_r]
        self.exp_q = self.exp_q[idx_r]
        self.V0 = self.V0[idx_r]

        # reduce the polynomial load model
        self.A = self.A[idx_r]
        self.B = self.B[idx_r]
        self.C = self.C[idx_r]

        self.Ybus = self.Ybus[idx_r, :][:, idx_c]
        self.Yseries = self.Yseries[idx_r, :][:, idx_c]

        # self.Yf = self.Yf[idx_k, :][:, idx_c]
        # self.Yt = self.Yt[idx_k, :][:, idx_c]

        self.Cf = self.Cf[idx_k, :][:, idx_c]
        self.Ct = self.Ct[idx_k, :][:, idx_c]

        self.branch_rates = self.branch_rates[idx_k]

        # self.print('POST' + "-"*80)

        # determine the bus-type arrays
        self.bus_types = self.bus_types[idx_r]

        for k, tpe in enumerate(self.bus_types):

            # keep track of the node types
            if tpe == BusTypes.Ref.value:
                self.ref.append(k)

            elif tpe == BusTypes.PQ.value:
                self.pq.append(k)

            elif tpe == BusTypes.PV.value:
                self.pv.append(k)

    def compute_branch_results(self, V):
        """
        Compute the branch magnitudes from the voltages
        :param V: Voltage vector solution in p.u.
        :return: PowerFlowResults instance with all the grid magnitudes
        """

        # declare circuit results
        data = CircuitMatrixResults()

        # copy the voltage
        data.V = V

        # power at the slack nodes
        data.Sbus = self.Sbus.copy()
        data.Sbus[self.ref] = V[self.ref] * np.conj(self.Ybus[self.ref, :].dot(V))

        # Reactive power at the pv nodes: keep the original P injection and set the calculated reactive power
        Q = (V[self.pv] * np.conj(self.Ybus[self.pv, :].dot(V))).imag
        data.Sbus[self.pv] = self.Sbus[self.pv].real + 1j * Q

        # Branches current, loading, etc
        # data.If = self.Yf * V
        # data.It = self.Yt * V
        data.If = self.Cf * self.Ybus * V
        data.It = self.Ct * self.Ybus * V
        data.Sf = self.Cf * V * np.conj(data.If)
        data.St = self.Ct * V * np.conj(data.It)

        # Branch losses in MVA
        data.losses = (data.Sf + data.St)

        # Branch current in p.u.
        data.Ibranch = np.maximum(data.If, data.It)

        # Branch power in MVA
        data.Sbranch = np.maximum(data.Sf, data.St)

        # Branch loading in p.u.
        data.loading = data.Sbranch / (self.branch_rates + 1e-9)

        return data

    def print(self, msg=''):
        """

        :return:
        """
        print('\n\n', msg)
        print("Ybus:\n", self.Ybus.todense())
        print("mask_r:\n", self.mask_r)
        print("mask_c:\n", self.mask_c)

        # print("Yf:\n", self.Yf.todense())
        # print("Yt:\n", self.Yt.todense())
        # print("mask_f:\n", self.mask_f)
        # print("mask_t:\n", self.mask_t)
        print("mask_k:\n", self.mask_k)

        print("Cf:\n", self.Cf.todense())
        print("Ct:\n", self.Ct.todense())

        print("Vbus:\n", self.Vbus)
        print("Sbus:\n", self.Sbus)
        print("Ibus:\n", self.Ibus)

        # print("F:\n", self.F)
        # print("T:\n", self.T)
        print("Rates:\n", self.branch_rates)

