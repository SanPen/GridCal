import pandas as pd
from numpy import ones, r_, linalg, Inf, delete
from numpy.core.multiarray import zeros, where, ndarray, array
from numpy.core.umath import conj
from warnings import warn

from GridCal.grid.model.node_type import NodeType


class PowerFlowInput:

    def __init__(self, n, m):
        """
        Power Flow study input values
        @param n: Number of buses
        @param m: Number of branches
        """
        # Array of integer values representing the buses types
        self.types = zeros(n, dtype=int)

        self.ref = None

        self.pv = None

        self.pq = None

        self.sto = None

        self.pqpv = None

        # Branch admittance matrix with the from buses
        self.Yf = zeros((m, n), dtype=complex)

        # Branch admittance matrix with the to buses
        self.Yt = zeros((m, n), dtype=complex)

        # Array with the 'from' index of the from bus of each branch
        self.F = zeros(m, dtype=int)

        # Array with the 'to' index of the from bus of each branch
        self.T = zeros(m, dtype=int)

        # array to store a 1 for the active branches
        self.active_branches = zeros(m, dtype=int)

        # Full admittance matrix (will be converted to sparse)
        self.Ybus = zeros((n, n), dtype=complex)

        # Full impedance matrix (will be computed upon requirement ad the inverse of Ybus)
        self.Zbus = None

        # Admittance matrix of the series elements (will be converted to sparse)
        self.Yseries = zeros((n, n), dtype=complex)

        # Admittance matrix of the shunt elements (actually it is only the diagonal, so let's make it a vector)
        self.Yshunt = zeros(n, dtype=complex)

        # Jacobian matrix 1 for the fast-decoupled power flow
        self.B1 = zeros((n, n), dtype=double)

        # Jacobian matrix 2 for the fast-decoupled power flow
        self.B2 = zeros((n, n), dtype=double)

        # Array of line-line nominal voltages of the buses
        self.Vnom = zeros(n)

        # Currents at the buses array
        self.Ibus = zeros(n, dtype=complex)

        # Powers at the buses array
        self.Sbus = zeros(n, dtype=complex)

        # Voltages at the buses array
        self.Vbus = zeros(n, dtype=complex)

        self.Vmin = zeros(n, dtype=double)

        self.Vmax = zeros(n, dtype=double)

        self.Qmin = ones(n, dtype=double) * -9999

        self.Qmax = ones(n, dtype=double) * 9999

        self.branch_rates = zeros(m)

        self.bus_names = zeros(n, dtype=object)

        self.available_structures = ['Vbus', 'Sbus', 'Ibus', 'Ybus', 'Yshunt', 'Yseries', 'Types', 'Jacobian']

    def compile(self):
        """
        Make the matrices sparse
        Create the ref, pv and pq lists
        @return:
        """
        self.Yf = sparse(self.Yf)
        self.Yt = sparse(self.Yt)
        self.Ybus = sparse(self.Ybus)
        self.Yseries = sparse(self.Yseries)
        self.B1 = sparse(self.B1)
        self.B2 = sparse(self.B2)
        # self.Yshunt = sparse(self.Yshunt)  No need to make it sparse, it is a vector already
        # compile the types lists from the types vector
        self.compile_types()

    def mismatch(self, V, Sbus):
        """
        Compute the power flow mismatch
        @param V: Voltage array (calculated)
        @param Sbus: Power array (especified)
        @return: mismatch of the computed solution
        """
        Scalc = V * conj(self.Ybus * V)
        mis = Scalc - Sbus  # compute the mismatch
        F = r_[mis[self.pv].real,
               mis[self.pq].real,
               mis[self.pq].imag]

        # check tolerance
        normF = linalg.norm(F, Inf)

        return normF

    def compile_types(self, types_new=None):
        """
        Compile the types
        @return:
        """
        if types_new is not None:
            self.types = types_new.copy()
        self.pq = where(self.types == NodeType.PQ.value[0])[0]
        self.pv = where(self.types == NodeType.PV.value[0])[0]
        self.ref = where(self.types == NodeType.REF.value[0])[0]
        self.sto = where(self.types == NodeType.STO_DISPATCH.value)[0]

        if len(self.ref) == 0:
            if len(self.pv) == 0:
                warn('There are no slack nodes selected')
            else:  # select the first PV generator as the slack
                mx = max(self.Sbus)
                i = where(self.Sbus == mx)[0]
                print('Setting the bus ' + str(i) + ' as slack instead of pv')
                self.pv = delete(self.pv, i)
                self.ref = [i]
            self.ref = ndarray.flatten(array(self.ref))
        else:
            pass  # no problem :)

        self.pqpv = r_[self.pq, self.pv]
        self.pqpv.sort()

    def set_from(self, obj, bus_idx, br_idx):
        """
        Copy data from other PowerFlowInput object
        @param obj: PowerFlowInput instance
        @param bus_idx: original bus indices
        @param br_idx: original branch indices
        @return:
        """
        self.types[bus_idx] = obj.types

        self.bus_names[bus_idx] = obj.bus_names

        # self.ref = None
        #
        # self.pv = None
        #
        # self.pq = None
        #
        # self.sto = None

        # Branch admittance matrix with the from buses
        self.Yf[br_idx, :][:, bus_idx] = obj.Yf.todense()

        # Branch admittance matrix with the to buses
        self.Yt[br_idx, :][:, bus_idx] = obj.Yt.todense()

        # Array with the 'from' index of the from bus of each branch
        self.F[br_idx] = obj.F

        # Array with the 'to' index of the from bus of each branch
        self.T[br_idx] = obj.T

        # array to store a 1 for the active branches
        self.active_branches[br_idx] = obj.active_branches

        # Full admittance matrix (will be converted to sparse)
        self.Ybus[bus_idx, :][:, bus_idx] = obj.Ybus.todense()

        # Admittance matrix of the series elements (will be converted to sparse)
        self.Yseries[bus_idx, :][:, bus_idx] = obj.Yseries.todense()

        # Admittance matrix of the shunt elements (will be converted to sparse)
        self.Yshunt[bus_idx] = obj.Yshunt

        # Currents at the buses array
        self.Ibus[bus_idx] = obj.Ibus

        # Powers at the buses array
        self.Sbus[bus_idx] = obj.Sbus

        # Voltages at the buses array
        self.Vbus[bus_idx] = obj.Vbus

        self.Vmin[bus_idx] = obj.Vmin

        self.Vmax[bus_idx] = obj.Vmax

        # self.Qmin = ones(n, dtype=double) * -9999
        #
        # self.Qmax = ones(n, dtype=double) * 9999

        self.branch_rates[br_idx] = obj.branch_rates

        self.compile()

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
            df = pd.DataFrame(data=self.Yshunt, columns=['Shunt admittance (p.u.)'], index=self.bus_names)

        elif structure_type == 'Yseries':
            df = pd.DataFrame(data=self.Yseries.toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == 'Types':
            df = pd.DataFrame(data=self.types, columns=['Bus types'], index=self.bus_names)

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
