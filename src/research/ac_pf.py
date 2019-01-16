"""
This program implements the DC power flow as a linear program
"""
from pulp import *
import numpy as np
import pandas as pd
from scipy.sparse import hstack as hstack_s, vstack as vstack_s

from GridCal.Engine.calculation_engine import *


class AcPf:

    def __init__(self, Y, Ys, S, V, pv, pq, vd):
        """
        Linearized AC power flow, solved with a linear solver :o
        :param Y: Admittance matrix
        :param Ys: Admittance matrix of the series elements
        :param S: Power injections vector
        :param V: Initial voltages
        :param pv: pv node indices
        :param pq: pq node indices
        :param vd: slack node indices
        """

        # node sets
        self.pv = pv
        self.vd = vd
        self.pq =pq
        self.pvpq = r_[pv, pq]
        self.V = V.copy()

        # form the system matrix
        A11 = -Ys.imag[self.pvpq, :][:, self.pvpq]
        A12 = Y.real[self.pvpq, :][:, self.pq]
        A21 = -Ys.real[self.pq, :][:, self.pvpq]
        A22 = -Y.imag[self.pq, :][:, self.pq]
        self.H = vstack_s([hstack_s([A11, A12]),
                           hstack_s([A21, A22])], format="csr")

        # compose the right hand side (power vectors)
        self.rhs = r_[S.real[self.pvpq], S.imag[self.pq]]

        # declare the voltage angles
        self.n = self.H.shape[0]
        self.dx = [None] * self.n
        for i in range(self.n):
            self.dx[i] = LpVariable("dx" + str(i))

        # declare the generation
        self.PG = list()

    def solve(self):

        prob = LpProblem("AC power flow", LpMinimize)

        # Add the objective function (all zeros)
        fobj = 0
        for i in range(self.n):
            fobj += self.dx[i] * 0.0

        prob += fobj

        ################################################################################################################
        # Add the matrix multiplication as constraints
        # See: https://math.stackexchange.com/questions/1727572/solving-a-feasible-system-of-linear-equations-
        #      using-linear-programming
        ################################################################################################################
        # for i in range(self.n):
        #     s = 0
        #     for j in range(self.n):
        #         s += self.H[i, j] * self.dx[j]
        #
        #     const = s == self.rhs[i]
        #     print(const)
        #     prob += const

        for i in range(self.n):
            s = 0

            # add the calculated node power
            for ii in range(self.H.indptr[i], self.H.indptr[i + 1]):
                j = self.H.indices[ii]
                s += self.H.data[ii] * self.dx[j]

            const = s == self.rhs[i]
            prob += const

        # Solve
        prob.solve()

        # The status of the solution is printed to the screen
        print("Status:", LpStatus[prob.status])

        # The optimised objective function value is printed to the screen
        print("Mismatch = ", value(prob.objective))

        # compose the results vector
        x = zeros(self.n)
        for i, th in enumerate(self.dx):
            x[i] = th.value()

        #  set the pv voltages
        npv = len(self.pv)
        va_pv = x[0:npv]
        vm_pv = abs(self.V[self.pv])
        self.V[self.pv] = vm_pv * exp(1j * va_pv)

        # set the PQ voltages
        npq = len(self.pq)
        va_pq = x[npv:npv + npq]
        vm_pq = abs(self.V[self.pq]) + x[npv + npq::]
        self.V[self.pq] = vm_pq * exp(1j * va_pq)

    def print(self):
        print('Voltage solution')
        # for i in range(self.V.shape[0]):
        #     print('Bus', i, '->', self.V[i], '\t', abs(self.V[i]), '\t', np.angle(self.V[i]))

        df = pd.DataFrame(data=np.c_[abs(self.V), np.angle(self.V), self.V.real, self.V.imag],
                          columns=['Module', 'Angle(rad)', 'Real', 'Imag'],
                          index=['Bus' + str(i) for i in range(self.V.shape[0])])
        print(df)


if __name__ == '__main__':

    grid = MultiCircuit()

    grid.load_file('lynn5buspq.xlsx')
    # grid.load_file('IEEE30.xlsx')
    # grid.load_file('Illinois200Bus.xlsx')

    grid.compile()

    print('Running...')
    for circuit in grid.circuits:
        # declare and solve problem
        problem = AcPf(Y=circuit.power_flow_input.Ybus,
                       Ys=circuit.power_flow_input.Yseries,
                       S=circuit.power_flow_input.Sbus,
                       V=circuit.power_flow_input.Vbus,
                       pv=circuit.power_flow_input.pv,
                       pq=circuit.power_flow_input.pq,
                       vd=circuit.power_flow_input.ref)
        problem.solve()
        problem.print()
