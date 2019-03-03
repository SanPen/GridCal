
import networkx as nx
from matplotlib import pyplot as plt

from research.three_phase.Engine.circuit_matrix_inputs import *


class Circuit:

    def __init__(self, Sbase=100, n_phase=3):
        """
        Circuit constructor
        This circuit must be fully connected
        :param Sbase: Base power in MVA
        :param n_phase: Number of phases of the circuit
        """

        # circuit base power in MVA
        self.Sbase = Sbase

        # number of phases of the circuit
        self.n_phase = n_phase

        # list of buses
        self.buses = list()

        # list of branches (lines, transformers, etc.)
        self.branches = list()

        # dictionary of bus objects to their index [obj] -> index
        self.bus_idx = dict()

        # circuit Graph
        self.graph = None

    @staticmethod
    def apply_ABCD(k, f, t, phases_from, phases_to, n_phase, Ybus, Yseries, Cf, Ct,
                   mask_r, mask_c, mask_k,
                   A, B, C, D, As, Ds):
        """
        Generic function to apply the A, B, C, D sub-matrices to the larger Ybus matrix
        :param k: index of the branch in the circuit
        :param f: index of the "from" bus in the circuit
        :param t: index of the "to" bus in the circuit
        :param phases_from: vector of connection phases of the "from" bus
        :param phases_to: vector of connection phases of the "to" bus
        :param n_phase: number of phases of the circuit
        :param Ybus: Circuit admittance matrix (sparse and complex)
        :param Yf: Circuit branch- "from" bus admittance matrix
        :param Yt: Circuit branch- "to" bus admittance matrix
        :param Cf: Circuit branch- "from" bus connectivity matrix
        :param Ct: Circuit branch- "to" bus connectivity matrix
        :param mask_r: mask for the rows of Ybus
        :param mask_c: mask for the columns of Ybus
        :param mask_k: mask for the branches
        :param A: admittance sub-matrix "A"
        :param B: admittance sub-matrix "B"
        :param C: admittance sub-matrix "C"
        :param D: admittance sub-matrix "D"
        :return: Nothing, The matrices Ybus, Cf, Ct, and the masks are modified in-place (bu reference)
        """
        # Set the A, B, C, D matrices into the larger Ybus Matrix
        a = 0
        for i in phases_from:
            b = 0
            for j in phases_to:

                # Admittance matrix
                Ybus[f * n_phase + i, f * n_phase + j] += A[a, b]
                Ybus[f * n_phase + i, t * n_phase + j] += B[a, b]
                Ybus[t * n_phase + i, f * n_phase + j] += C[a, b]
                Ybus[t * n_phase + i, t * n_phase + j] += D[a, b]

                Yseries[f * n_phase + i, f * n_phase + j] += As[a, b]
                Yseries[f * n_phase + i, t * n_phase + j] += B[a, b]
                Yseries[t * n_phase + i, f * n_phase + j] += C[a, b]
                Yseries[t * n_phase + i, t * n_phase + j] += Ds[a, b]

                # branch-bus admittance matrices
                # Yf[k * n_phase + i, f * n_phase + j] += A[a, b]
                # Yf[k * n_phase + i, t * n_phase + j] += B[a, b]
                # Yt[k * n_phase + i, f * n_phase + j] += C[a, b]
                # Yt[k * n_phase + i, t * n_phase + j] += D[a, b]

                # branch-bus connectivity matrices
                Cf[k * n_phase + i, f * n_phase + j] = 1
                Cf[k * n_phase + i, t * n_phase + j] = -1
                Ct[k * n_phase + i, f * n_phase + j] = -1
                Ct[k * n_phase + i, t * n_phase + j] = 1

                # masks
                mask_r[f * n_phase + i] = 1
                mask_r[t * n_phase + i] = 1
                mask_c[f * n_phase + j] = 1
                mask_c[t * n_phase + j] = 1
                mask_k[k * n_phase + i] = 1

                b += 1
            a += 1

    def compile(self):
        """
        Compile the circuit into matrices
        :return: circuit data object (instance of CircuitMatrices)
        """
        n = len(self.buses)
        m = len(self.branches)
        self.graph = nx.Graph()

        # declare the matrices container object
        data = CircuitMatrixInputs(n, m, self.n_phase)

        # compile nodes
        for k, elm in enumerate(self.buses):

            # collect the node magnitudes in per unit
            elm.apply_YISV(k, data, self.Sbase, n_phase=self.n_phase)

            # store the object and its index in a dictionary
            self.bus_idx[elm] = k

            # set the node entry in a graph
            self.graph.add_node(elm.name, pos=(elm.x, elm.y))

        # Add the bus shunt admittances vector into Ybus diagonal
        ib = range(len(data.Vbus))
        data.Ybus[ib, ib] += data.Ybus_sh

        # compile branches
        for k, elm in enumerate(self.branches):

            # get the from and to bus indices from the connection objects of the branch element
            f = self.bus_idx[elm.f]
            t = self.bus_idx[elm.t]

            self.graph.add_edge(elm.f.name, elm.t.name)

            # apply the ABCD parameters in per unit
            A, B, C, D, As, Ds = elm.get_ABCD(self.Sbase)
            self.apply_ABCD(k, f, t,
                            phases_from=elm.phases_from,
                            phases_to=elm.phases_to,
                            n_phase=self.n_phase,
                            Ybus=data.Ybus,
                            Yseries=data.Yseries,
                            Cf=data.Cf,
                            Ct=data.Ct,
                            mask_r=data.mask_r,
                            mask_c=data.mask_c,
                            mask_k=data.mask_k,
                            A=A, B=B, C=C, D=D, As=As, Ds=Ds)

            # get the rating
            for i in range(self.n_phase):
                data.branch_rates[k * self.n_phase + i] = elm.rating

        # consolidate the data: Reduce the matrices, find the bus type lists, etc...
        data.consolidate()

        return data

    def pack_node_solution(self, vec):
        """
        Pack a nodal vector to match the buses
        :param vec: nodal vector (can be non symmetric)
        :return: packed vector by bus
        """
        n = len(self.buses)
        val = [None] * n

        a = 0
        for k, elm in enumerate(self.buses):
            val[k] = vec[a:a + elm.number_of_phases]
            a += elm.number_of_phases

        return val

    def pack_branch_solution(self, vec):
        """
        Pack a nodal vector to match the buses
        :param vec: nodal vector (can be non symmetric)
        :return: packed vector by bus
        """
        m = len(self.branches)
        val = [None] * m

        a = 0
        for k, elm in enumerate(self.branches):
            val[k] = vec[a:a + elm.number_of_phases]
            a += elm.number_of_phases

        return val

    def plot(self):
        """
        Plot the circuit layout
        :return:
        """
        # from networkx.drawing.nx_pylab import draw_networkx
        # fig = plt.Figure(figsize=(16, 12))
        # ax = fig.add_subplot(111)
        pos = nx.get_node_attributes(self.graph, 'pos')
        nx.draw(self.graph, pos,  with_labels=True, figsize=(16, 12))
        plt.show()

