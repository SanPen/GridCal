"""
This program implements the DC power flow as a linear program
"""
from pulp import *
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt


class DcOpf:

    def __init__(self, B, P, pqpv, vd):

        self.B = B
        self.P = P
        self.pqpv = pqpv
        self.vd = vd
        npqpv = len(self.pqpv)
        self.n = len(self.P)

        self.Bred = B[self.pqpv, :][:, self.pqpv]
        self.Pred = P[self.pqpv]

        # declare the voltage angles
        self.theta = [None] * self.n
        for i in range(self.n):
            self.theta[i] = LpVariable("Theta" + str(i), 0.0, 10.0)

    def solve(self):

        prob = LpProblem("DC power flow", LpMinimize)

        npqpv = len(self.pqpv)

        # Add the objective function (all zeros)
        fobj = 0
        for j in self.pqpv:
            fobj += self.theta[j] * 0.0

        prob += fobj

        ################################################################################################################
        # Add the matrix multiplication as constraints
        # See: https://math.stackexchange.com/questions/1727572/solving-a-feasible-system-of-linear-equations-
        #      using-linear-programming
        ################################################################################################################
        # for i in self.pqpv:
        #     s = 0
        #     for j in self.pqpv:
        #         s += self.B[i, j] * self.theta[j]
        #
        #     const = s == self.P[i]
        #     print(const)
        #     prob += const

        nr = self.Bred.shape[0]
        for i in range(nr):
            s = 0
            for j in range(nr):
                s += self.Bred[i, j] * self.theta[self.pqpv[j]]

            const = s == self.Pred[i]
            print(const)
            prob += const

        #  set the slack nodes
        for i in self.vd:
            prob += self.theta[i] == 0

        # Solve
        prob.solve()

        # The status of the solution is printed to the screen
        print("Status:", LpStatus[prob.status])

        # The optimised objective function value is printed to the screen
        print("Mismatch = ", value(prob.objective))

    def print(self):
        print('Voltage angles (in rad)')
        for i, th in enumerate(self.theta):
            print('Bus', i, '->', th.value())


if __name__ == '__main__':

    B = np.array([[-25.99739726,   7.53424658,   7.53424658,   0.        ,  10.95890411],
                  [  7.53424658, -26.06094761,   9.27835052,   0.        ,   9.27835052],
                  [  7.53424658,   9.27835052, -23.11906051,   6.34146341,   0.        ],
                  [  0.        ,   0.        ,   6.34146341, -15.59481393,   9.27835052],
                  [ 10.95890411,   9.27835052,   0.        ,   9.27835052, -29.48560514]])

    P = np.array([ 0.  , -0.4 , -0.25, -0.4 , -0.5 ])
    pqpv = np.array([1, 2, 3, 4])
    vd = np.array([0])

    # declare and solve problem
    problem = DcOpf(B, P, pqpv, vd)
    problem.solve()
    problem.print()

    # error formula
    # error = -Bred.dot(theta).sum() + Pred.sum()

    # theta = array([1,  0.05815598,  0.05782403,  0.08629646,  0.06241284])