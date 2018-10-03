#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This program implements the DC power flow as a linear program
"""
from pulp import *
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt


class DcOpf:

    def __init__(self, Sbase, B, branches, flow_limits, demand, pq, pv, vd,
                 costs, lower_limits, upper_limits):
        """
        OPF simple dispatch problem
        :param Sbase: System base power (MVA)
        :param B: System susceptance matrix (Imaginary part of the admittance matrix)
        :param branches: List of branches from, to bus indices
        :param flow_limits: Array of branch flow limits
        :param demand: Array of node demand
        :param pqpv: list of non-slack nodes
        :param pv: list of nodes with generation
        :param vd: list of slack nodes
        :param costs: list of generator costs
        :param lower_limits: generation lower limits
        :param upper_limits: generation upper limits
        """
        self.Sbase = Sbase
        self.B = B
        self.branches = branches

        self.nbus = B.shape[0]

        # node sets
        self.pqpv = np.r_[pq, pv]
        self.pqpv.sort()
        self.pv = pv
        self.vd = vd
        self.pq = pq

        # All the values must be in p.u.
        self.costs = costs
        self.flow_limits = flow_limits / Sbase
        self.PD = demand / Sbase
        self.lower_limits = lower_limits / Sbase
        self.upper_limits = upper_limits / Sbase

        npv = len(self.pv)
        n = len(self.PD)

        # declare the voltage angles
        self.theta = [None] * n
        for i in range(n):
            self.theta[i] = LpVariable("Theta" + str(i), -0.5, 0.5)

        # declare the generation
        self.PG = [None] * n
        for i in range(n):
            self.PG[i] = LpVariable("PG" + str(i), self.lower_limits[i], self.upper_limits[i])

    def solve(self):
        """
        Solve OPF
        :return:
        """
        prob = LpProblem("DC optimal power flow", LpMinimize)

        n = len(self.PD)

        ################################################################################################################
        # Add the objective function
        ################################################################################################################
        fobj = 0

        # add the voltage angles as zeros
        for j in self.pqpv:
            fobj += self.theta[j] * 0.0

        # Add the generators cost
        for i in range(n):
            fobj += self.PG[i] * self.costs[i]

        # Add the objective function to the problem
        prob += fobj

        ################################################################################################################
        # Add the matrix multiplication as constraints
        # See: https://math.stackexchange.com/questions/1727572/solving-a-feasible-system-of-linear-equations-
        #      using-linear-programming
        ################################################################################################################
        for i in self.pqpv:
            s = 0
            for j in self.pqpv:
                s += self.B[i, j] * self.theta[j]
            prob.add(s == -self.PD[i] + self.PG[i], 'ct_node_mismatch_' + str(i))
            # prob += s == -self.PD[i] + self.PG[i]

        ################################################################################################################
        #  set the slack nodes voltage angle
        ################################################################################################################
        for i in self.vd:
            prob.add(self.theta[i] == 0, 'ct_slack_theta')
            # prob += self.theta[i] == 0

        ################################################################################################################
        #  set the slack generator power
        ################################################################################################################
        for i in self.vd:
            val = 0
            for j in range(self.nbus):
                val += self.B[i, j] * self.theta[j]
            prob.add(self.PG[i] == val, 'ct_slack_power_' + str(i))
            # prob += self.PG[i] == val

        ################################################################################################################
        #  set the PQ generators equal to zero
        ################################################################################################################
        for i in self.pq:
            # prob += LpConstraint(self.PG[i] == 0, name='ct_zero_pq_gen_' + str(i))
            prob.add(self.PG[i] == 0, 'ct_zero_pq_gen_' + str(i))

        ################################################################################################################
        # Set the branch limits
        ################################################################################################################
        for k, coord in enumerate(self.branches):
            i, j = coord
            # branch flow
            Fij = self.B[i, j] * (self.theta[i] - self.theta[j])
            Fji = self.B[i, j] * (self.theta[j] - self.theta[i])
            # constraints
            prob.add(Fij <= self.flow_limits[k], 'ct_br_flow_ij_' + str(k))
            prob.add(Fji <= self.flow_limits[k], 'ct_br_flow_ji_' + str(k))

        ################################################################################################################
        # Solve
        ################################################################################################################
        prob.writeLP('opf.lp')
        prob.solve()  # solve with CBC
        # prob.solve(CPLEX())

        # The status of the solution is printed to the screen
        print("Status:", LpStatus[prob.status])

        # The optimised objective function value is printed to the screen
        print("Cost =", value(prob.objective), '€')

    def print(self):
        """
        Print results
        :return:
        """
        print('\nVoltage angles (in rad)')
        for i, th in enumerate(self.theta):
            print('Bus', i, '->', th.value())

        print('\nGeneration power (in MW)')
        for i, g in enumerate(self.PG):
            val = g.value() * self.Sbase if g.value() is not None else 'None'
            print('Gen', i, '->', val)

        # Set the branch limits
        print('\nBranch flows (in MW)')
        for k, coord in enumerate(self.branches):
            i, j = coord
            if self.theta[i].value() is not None and self.theta[j].value() is not None:
                F = self.B[i, j] * (self.theta[i].value() - self.theta[j].value()) * self.Sbase
            else:
                F = 'None'
            print('Branch ' + str(i) + '-' + str(j) + '(', self.flow_limits[k] * self.Sbase, 'MW) ->', F)

if __name__ == '__main__':

    # Susceptance matrix in p.u.
    B = np.array([[-25.99739726,   7.53424658,   7.53424658,   0.        ,  10.95890411],
                  [  7.53424658, -26.06094761,   9.27835052,   0.        ,   9.27835052],
                  [  7.53424658,   9.27835052, -23.11906051,   6.34146341,   0.        ],
                  [  0.        ,   0.        ,   6.34146341, -15.59481393,   9.27835052],
                  [ 10.95890411,   9.27835052,   0.        ,   9.27835052, -29.48560514]])

    # Branch indices
    branches = [[2, 0],
                [3, 2],
                [4, 3],
                [4, 1],
                [4, 0],
                [1, 0],
                [1, 2]]

    # Branch flows in MW
    flow_limits = np.array([70, 18, 20, 10, 90, 60, 20])

    # Node demands in MW
    PD = np.array([0.  , 40 , 25, 0, 50])

    pq = np.array([1, 2, 4])
    vd = np.array([0])
    pv = np.array([3])

    # Generator costs in €/MW (vector for all the nodes...)
    costs = np.array([0, 0, 0, 0, 0])

    # Generator limits in MW (vectors for all the nodes...)
    lower_lim = np.array([0, 0, 0, 0, 0, 0])
    upper_lim = np.array([100, 100, 100, 100, 100])

    # System base power (MW)
    Sbase = 100.0

    # declare and solve problem
    problem = DcOpf(Sbase, B, branches, flow_limits, PD, pq, pv, vd, costs, lower_lim, upper_lim)
    problem.solve()
    problem.print()

