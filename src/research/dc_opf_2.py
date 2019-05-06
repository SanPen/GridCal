#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This program implements the DC power flow as a linear program
"""
from pulp import *
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from GridCal.Engine import *


class DcOpf:

    def __init__(self, circuit: Circuit):
        """
        OPF simple dispatch problem
        :param circuit: GridCal Circuit instance (remember this must be a connected island)
        """

        self.circuit = circuit

        self.Sbase = circuit.Sbase
        self.B = circuit.power_flow_input.Ybus.imag
        self.nbus = self.B.shape[0]

        # node sets
        self.pqpv = circuit.power_flow_input.pqpv
        self.pv = circuit.power_flow_input.pv
        self.vd = circuit.power_flow_input.ref
        self.pq = circuit.power_flow_input.pq

        # declare the voltage angles
        self.theta = [None] * self.nbus
        for i in range(self.nbus):
            self.theta[i] = LpVariable("Theta" + str(i), -0.5, 0.5)

        # declare the generation
        self.PG = list()

    def solve(self):
        """
        Solve OPF
        :return:
        """

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
        for bus in self.circuit.buses:

            # check that there are at least one generator at the slack node
            if len(bus.controlled_generators) == 0 and bus.type == BusMode.REF:
                raise Warning('There is no generator at the Slack node ' + bus.name + '!!!')

            # Add the bus LP vars
            for gen in bus.controlled_generators:
                # create the controlled variable
                name = "Gen" + gen.name + '_' + bus.name
                gen.make_lp_vars(name)

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
            for j in self.pqpv:
                print(i, j, self.B[i, j])
                s += self.B[i, j] * self.theta[j]

            # add the generation LP vars
            for gen in self.circuit.buses[i].controlled_generators:
                d += gen.LPVar_P

            # add the nodal demand
            for load in self.circuit.buses[i].loads:
                d -= load.S.real / self.Sbase

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
            for j in range(self.nbus):
                if self.B[i, j] != 0.0:
                    val += self.B[i, j] * self.theta[j]

            # Sum the slack generators
            for gen in self.circuit.buses[i].controlled_generators:
                g += gen.LPVar_P

            # the sum of the slack node generators must be equal to the slack node power
            prob.add(g == val, 'ct_slack_power_' + str(i))

        ################################################################################################################
        # Set the branch limits
        ################################################################################################################
        for k, branch in enumerate(self.circuit.branches):
            i = self.circuit.buses_dict[branch.bus_from]
            j = self.circuit.buses_dict[branch.bus_to]
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
        print('\nVoltage angles (in rad)')
        for i, th in enumerate(self.theta):
            print('Bus', i, '->', th.value())

        print('\nGeneration power (in MW)')
        for i, g in enumerate(self.PG):
            val = g.value() * self.Sbase if g.value() is not None else 'None'
            print(g.name, '->', val)

        # Set the branch limits
        print('\nBranch flows (in MW)')
        for k, branch in enumerate(self.circuit.branches):
            i = self.circuit.buses_dict[branch.bus_from]
            j = self.circuit.buses_dict[branch.bus_to]
            if self.theta[i].value() is not None and self.theta[j].value() is not None:
                F = self.B[i, j] * (self.theta[i].value() - self.theta[j].value()) * self.Sbase
            else:
                F = 'None'
            print('Branch ' + str(i) + '-' + str(j) + '(', branch.rate, 'MW) ->', F)


if __name__ == '__main__':

    grid = MultiCircuit()
    grid.load_file('lynn5buspv.xlsx')
    # grid.load_file('IEEE30.xlsx')
    # grid.load_file('Illinois200Bus.xlsx')
    # grid.load_file('/home/santi/Documentos/GitHub/GridCal/UnderDevelopment/GridCal/Pegase 2869.xlsx')

    grid.compile()

    for circuit in grid.circuits:

        # print('\nYbus:\n', circuit.power_flow_input.Ybus.todense())
        # print('\nYseries:\n', circuit.power_flow_input.Yseries.todense())
        # print('\nYshunt:\n', circuit.power_flow_input.Yshunt)
        # print('\nSbus:\n', circuit.power_flow_input.Sbus)
        # print('\nIbus:\n', circuit.power_flow_input.Ibus)
        # print('\nVbus:\n', circuit.power_flow_input.Vbus)
        # print('\ntypes:\n', circuit.power_flow_input.types)
        # print('\npq:\n', circuit.power_flow_input.pq)
        # print('\npv:\n', circuit.power_flow_input.pv)
        # print('\nvd:\n', circuit.power_flow_input.ref)

        # declare and solve problem
        problem = DcOpf(circuit)
        problem.solve()
        problem.print()