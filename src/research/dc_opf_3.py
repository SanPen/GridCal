#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This program implements the DC power flow as a linear program
This version uses the sparse structures and it the problem compilation is
blazing fast compared to the full matrix version
"""
from pulp import *
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from GridCal.Engine import *


class DcOpf:

    def __init__(self, multi_circuit: MultiCircuit):
        """
        OPF simple dispatch problem
        :param multi_circuit: GridCal Circuit instance (remember this must be a connected island)
        """

        self.multi_circuit = multi_circuit

        # circuit compilation
        self.numerical_circuit = self.multi_circuit.compile()
        self.islands = self.numerical_circuit.compute()

        self.Sbase = multi_circuit.Sbase
        self.B = csc_matrix(self.numerical_circuit.get_B())
        self.nbus = self.B.shape[0]

        # node sets
        self.pqpv = self.islands[0].pqpv
        self.pv = self.islands[0].pv
        self.vd = self.islands[0].ref
        self.pq = self.islands[0].pq

        # declare the voltage angles
        self.theta = [None] * self.nbus
        for i in range(self.nbus):
            self.theta[i] = LpVariable("Theta" + str(i), -0.5, 0.5)

        # declare the generation
        self.PG = list()

    def solve(self):
        """
        Solve OPF using the sparse formulation
        :return:
        """

        '''
        CSR format explanation:
        The standard CSR representation where the column indices for row i are stored in 

        -> indices[indptr[i]:indptr[i+1]] 

        and their corresponding values are stored in 

        -> data[indptr[i]:indptr[i+1]]

        If the shape parameter is not supplied, the matrix dimensions are inferred from the index arrays.

        https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csr_matrix.html
        '''

        # print('Compiling LP')
        prob = LpProblem("DC optimal power flow", LpMinimize)

        ################################################################################################################
        # Add the objective function
        ################################################################################################################
        fobj = 0

        # add the voltage angles multiplied by zero (trick)
        for j in self.pqpv:
            fobj += self.theta[j] * 0.0

        # Add the generators cost
        for bus in self.multi_circuit.buses:

            # check that there are at least one generator at the slack node
            if len(bus.controlled_generators) == 0 and bus.type == BusMode.REF:
                raise Warning('There is no generator at the Slack node ' + bus.name + '!!!')

            # Add the bus LP vars
            for gen in bus.controlled_generators:

                # create the generation variable
                gen.initialize_lp_vars()

                # add the variable to the objective function
                fobj += gen.LPVar_P * gen.Cost

                self.PG.append(gen.LPVar_P)  # add the var reference just to print later...

        # Add the objective function to the problem
        prob += fobj

        ################################################################################################################
        # Add the matrix multiplication as constraints
        # See: https://math.stackexchange.com/questions/1727572/solving-a-feasible-system-of-linear-equations-
        #      using-linear-programming
        ################################################################################################################
        for i in self.pqpv:
            s = 0
            d = 0

            # add the calculated node power
            for ii in range(self.B.indptr[i], self.B.indptr[i+1]):
                j = self.B.indices[ii]
                if j not in self.vd:
                    s += self.B.data[ii] * self.theta[j]

            # add the generation LP vars
            for gen in self.multi_circuit.buses[i].controlled_generators:
                d += gen.LPVar_P

            # add the nodal demand
            for load in self.multi_circuit.buses[i].loads:
                d -= load.P / self.Sbase

            prob.add(s == d, 'ct_node_mismatch_' + str(i))

        ################################################################################################################
        #  set the slack nodes voltage angle
        ################################################################################################################
        for i in self.vd:
            prob.add(self.theta[i] == 0, 'ct_slack_theta')

        ################################################################################################################
        #  set the slack generator power
        ################################################################################################################
        for i in self.vd:
            val = 0
            g = 0

            # compute the slack node power
            for ii in range(self.B.indptr[i], self.B.indptr[i+1]):
                j = self.B.indices[ii]
                val += self.B.data[ii] * self.theta[j]

            # Sum the slack generators
            for gen in self.multi_circuit.buses[i].controlled_generators:
                g += gen.LPVar_P

            # the sum of the slack node generators must be equal to the slack node power
            prob.add(g == val, 'ct_slack_power_' + str(i))

        ################################################################################################################
        # Set the branch limits
        ################################################################################################################
        buses_dict = {bus: i for i, bus in enumerate(self.multi_circuit.buses)}
        for k, branch in enumerate(self.multi_circuit.branches):
            i = buses_dict[branch.bus_from]
            j = buses_dict[branch.bus_to]
            # branch flow
            Fij = self.B[i, j] * (self.theta[i] - self.theta[j])
            Fji = self.B[i, j] * (self.theta[j] - self.theta[i])
            # constraints
            prob.add(Fij <= branch.rate / self.Sbase, 'ct_br_flow_ij_' + str(k))
            prob.add(Fji <= branch.rate / self.Sbase, 'ct_br_flow_ji_' + str(k))

        ################################################################################################################
        # Solve
        ################################################################################################################
        print('Solving LP')
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
        print('\nVoltages in p.u.')
        for i, th in enumerate(self.theta):
            print('Bus', i, '->', 1, '<', th.value(), 'rad')

        print('\nGeneration power (in MW)')
        for i, g in enumerate(self.PG):
            val = g.value() * self.Sbase if g.value() is not None else 'None'
            print(g.name, '->', val)

        # Set the branch limits
        print('\nBranch flows (in MW)')
        buses_dict = {bus: i for i, bus in enumerate(self.multi_circuit.buses)}
        for k, branch in enumerate(self.multi_circuit.branches):
            i = buses_dict[branch.bus_from]
            j = buses_dict[branch.bus_to]
            if self.theta[i].value() is not None and self.theta[j].value() is not None:
                F = self.B[i, j] * (self.theta[i].value() - self.theta[j].value()) * self.Sbase
            else:
                F = 'None'
            print('Branch ' + str(i) + '-' + str(j) + '(', branch.rate, 'MW) ->', F)


if __name__ == '__main__':

    grid = FileOpen('lynn5buspv.xlsx').open()
    # grid = FileOpen('IEEE30.xlsx').open()
    # grid = FileOpen('Illinois200Bus.xlsx').open()

    # declare and solve problem
    problem = DcOpf(grid)
    problem.solve()
    problem.print()
