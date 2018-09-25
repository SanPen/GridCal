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
import pandas as pd
import pulp
import numpy as np
from numpy import complex, zeros, exp, r_, array, angle, c_
from scipy.sparse import hstack as hstack_s, vstack as vstack_s
from matplotlib import pyplot as plt

from PyQt5.QtCore import QRunnable

from GridCal.Engine.IoStructures import CalculationInputs
from GridCal.Engine.CalculationEngine import MultiCircuit
from GridCal.Engine.PlotConfig import LINEWIDTH
from GridCal.Engine.BasicStructures import BusMode
from GridCal.Engine.PowerFlowDriver import PowerFlowMP, SolverType


########################################################################################################################
# Optimal Power flow classes
########################################################################################################################

class DcOpf:

    def __init__(self, calculation_input: CalculationInputs, buses, branches, options):
        """
        OPF simple dispatch problem
        :param calculation_input: GridCal Circuit instance (remember this must be a connected island)
        :param options: OptimalPowerFlowOptions instance
        """

        self.calculation_input = calculation_input

        self.buses = buses
        self.buses_dict = {bus: i for i, bus in enumerate(buses)}  # dictionary of bus objects given their indices
        self.branches = branches

        self.load_shedding = options.load_shedding

        self.Sbase = calculation_input.Sbase
        self.B = calculation_input.Ybus.imag.tocsr()
        self.nbus = calculation_input.nbus
        self.nbranch = calculation_input.nbr

        # node sets
        self.pqpv = calculation_input.pqpv
        self.pv = calculation_input.pv
        self.vd = calculation_input.ref
        self.pq = calculation_input.pq

        # declare the voltage angles and the possible load shed values
        self.theta = [None] * self.nbus
        self.load_shed = [None] * self.nbus
        for i in range(self.nbus):
            self.theta[i] = pulp.LpVariable("Theta_" + str(i), -0.5, 0.5)
            self.load_shed[i] = pulp.LpVariable("LoadShed_" + str(i), 0.0, 1e20)

        # declare the slack vars
        self.slack_loading_ij_p = [None] * self.nbranch
        self.slack_loading_ji_p = [None] * self.nbranch
        self.slack_loading_ij_n = [None] * self.nbranch
        self.slack_loading_ji_n = [None] * self.nbranch

        if self.load_shedding:
            pass

        else:

            for i in range(self.nbranch):
                self.slack_loading_ij_p[i] = pulp.LpVariable("LoadingSlack_ij_p_" + str(i), 0, 1e20)
                self.slack_loading_ji_p[i] = pulp.LpVariable("LoadingSlack_ji_p_" + str(i), 0, 1e20)
                self.slack_loading_ij_n[i] = pulp.LpVariable("LoadingSlack_ij_n_" + str(i), 0, 1e20)
                self.slack_loading_ji_n[i] = pulp.LpVariable("LoadingSlack_ji_n_" + str(i), 0, 1e20)

        # declare the generation
        self.PG = list()

        # LP problem
        self.problem = None

        # potential errors flag
        self.potential_errors = False

        # Check if the problem was solved or not
        self.solved = False

        # LP problem restrictions saved on build and added to the problem with every load change
        self.s_restrictions = list()
        self.p_restrictions = list()

        self.loads = zeros(self.nbus)

    def build(self, t_idx=None):
        """
        Build the OPF problem using the sparse formulation
        In this step, the circuit loads are not included
        those are added separately for greater flexibility
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

        print('Compiling LP')
        prob = pulp.LpProblem("DC optimal power flow", pulp.LpMinimize)

        # initialize the potential errors
        self.potential_errors = False

        ################################################################################################################
        # Add the objective function
        ################################################################################################################
        fobj = 0.0

        # add the voltage angles multiplied by zero (trick)
        for j in self.pqpv:
            fobj += self.theta[j] * 0.0

        # Add the generators cost
        for k, bus in enumerate(self.buses):

            generators = bus.controlled_generators + bus.batteries

            # check that there are at least one generator at the slack node
            if len(generators) == 0 and bus.type == BusMode.REF:
                self.potential_errors = True
                warn('There is no generator at the Slack node ' + bus.name + '!!!')

            # Add the bus LP vars
            for i, gen in enumerate(generators):

                # add the variable to the objective function
                if gen.active and gen.enabled_dispatch:
                    if t_idx is None:
                        fobj += gen.LPVar_P * gen.Cost
                        # add the var reference just to print later...
                        self.PG.append(gen.LPVar_P)
                    else:
                        fobj += gen.LPVar_P_prof[t_idx] * gen.Cost
                        # add the var reference just to print later...
                        self.PG.append(gen.LPVar_P_prof[t_idx])
                else:
                    pass  # the generator is not active

            # minimize the load shedding if activated
            if self.load_shedding:
                fobj += self.load_shed[k]

        # minimize the branch loading slack if not load shedding
        if not self.load_shedding:
            # Minimize the branch overload slacks
            for k, branch in enumerate(self.branches):
                if branch.active:
                    fobj += self.slack_loading_ij_p[k] + self.slack_loading_ij_n[k]
                    fobj += self.slack_loading_ji_p[k] + self.slack_loading_ji_n[k]
                else:
                    pass  # the branch is not active

        # Add the objective function to the problem
        prob += fobj

        ################################################################################################################
        # Add the nodal power balance equations as constraints (without loads, those are added later)
        # See: https://math.stackexchange.com/questions/1727572/solving-a-feasible-system-of-linear-equations-
        #      using-linear-programming
        ################################################################################################################
        for i in self.pqpv:

            calculated_node_power = 0
            node_power_injection = 0
            generators = self.buses[i].controlled_generators + self.buses[i].batteries

            # add the calculated node power
            for ii in range(self.B.indptr[i], self.B.indptr[i + 1]):

                j = self.B.indices[ii]

                if j not in self.vd:

                    calculated_node_power += self.B.data[ii] * self.theta[j]

                    if self.B.data[ii] < 1e-6:
                        warn("There are susceptances close to zero.")

            # add the generation LP vars
            if t_idx is None:
                for gen in generators:
                    if gen.active:
                        if gen.enabled_dispatch:
                            # add the dispatch variable
                            node_power_injection += gen.LPVar_P
                        else:
                            # set the default value
                            node_power_injection += gen.P / self.Sbase
                    else:
                        pass
            else:
                for gen in generators:
                    if gen.active:
                        if gen.enabled_dispatch:
                            # add the dispatch variable
                            node_power_injection += gen.LPVar_P_prof[t_idx]
                        else:
                            # set the default profile value
                            node_power_injection += gen.Pprof.values[t_idx] / self.Sbase
                    else:
                        pass

            # Store the terms for adding the load later.
            # This allows faster problem compilation in case of recurrent runs
            self.s_restrictions.append(calculated_node_power)
            self.p_restrictions.append(node_power_injection)

            # # add the nodal demand: See 'set_loads()'
            # for load in self.circuit.buses[i].loads:
            #     node_power_injection -= load.S.real / self.Sbase
            #
            # prob.add(calculated_node_power == node_power_injection, 'ct_node_mismatch_' + str(i))

        ################################################################################################################
        #  set the slack nodes voltage angle
        ################################################################################################################
        for i in self.vd:
            prob.add(self.theta[i] == 0, 'ct_slack_theta_' + str(i))

        ################################################################################################################
        #  set the slack generator power
        ################################################################################################################
        for i in self.vd:

            val = 0
            g = 0
            generators = self.buses[i].controlled_generators + self.buses[i].batteries

            # compute the slack node power
            for ii in range(self.B.indptr[i], self.B.indptr[i + 1]):
                j = self.B.indices[ii]
                val += self.B.data[ii] * self.theta[j]

            # Sum the slack generators
            if t_idx is None:
                for gen in generators:
                    if gen.active and gen.enabled_dispatch:
                        g += gen.LPVar_P
                    else:
                        pass
            else:
                for gen in generators:
                    if gen.active and gen.enabled_dispatch:
                        g += gen.LPVar_P_prof[t_idx]
                    else:
                        pass

            # the sum of the slack node generators must be equal to the slack node power
            prob.add(g == val, 'ct_slack_power_' + str(i))

        ################################################################################################################
        # Set the branch limits
        ################################################################################################################
        any_rate_zero = False
        for k, branch in enumerate(self.branches):

            if branch.active:
                i = self.buses_dict[branch.bus_from]
                j = self.buses_dict[branch.bus_to]

                # branch flow
                Fij = self.B[i, j] * (self.theta[i] - self.theta[j])
                Fji = self.B[i, j] * (self.theta[j] - self.theta[i])

                # constraints
                if not self.load_shedding:
                    # Add slacks
                    prob.add(Fij + self.slack_loading_ij_p[k] - self.slack_loading_ij_n[k] <= branch.rate / self.Sbase,
                             'ct_br_flow_ij_' + str(k))
                    prob.add(Fji + self.slack_loading_ji_p[k] - self.slack_loading_ji_n[k] <= branch.rate / self.Sbase,
                             'ct_br_flow_ji_' + str(k))
                    # prob.add(Fij <= branch.rate / self.Sbase, 'ct_br_flow_ij_' + str(k))
                    # prob.add(Fji <= branch.rate / self.Sbase, 'ct_br_flow_ji_' + str(k))
                else:
                    # The slacks are in the form of load shedding
                    prob.add(Fij <= branch.rate / self.Sbase, 'ct_br_flow_ij_' + str(k))
                    prob.add(Fji <= branch.rate / self.Sbase, 'ct_br_flow_ji_' + str(k))

                if branch.rate <= 1e-6:
                    any_rate_zero = True
            else:
                pass  # the branch is not active...

        # No branch can have rate = 0, otherwise the problem fails
        if any_rate_zero:
            self.potential_errors = True
            warn('There are branches with no rate.')

        # set the global OPF LP problem
        self.problem = prob

    def set_loads(self, t_idx=None):
        """
        Add the loads to the LP problem
        Args:
            t_idx: time index, if none, the default object values are taken
        """

        if t_idx is None:

            # use the default loads
            for k, i in enumerate(self.pqpv):

                # these restrictions come from the build step to be fulfilled with the load now
                node_power_injection = self.p_restrictions[k]
                calculated_node_power = self.s_restrictions[k]

                # add the nodal demand
                for load in self.buses[i].loads:
                    if load.active:
                        self.loads[i] += load.S.real / self.Sbase
                    else:
                        pass

                if calculated_node_power is 0 and node_power_injection is 0:
                    # nodes without injection or generation
                    pass
                else:
                    # add the restriction
                    if self.load_shedding:

                        self.problem.add(
                            calculated_node_power == node_power_injection - self.loads[i] + self.load_shed[i],
                            self.buses[i].name + '_ct_node_mismatch_' + str(k))

                        # if there is no load at the node, do not allow load shedding
                        if len(self.buses[i].loads) == 0:
                            self.problem.add(self.load_shed[i] == 0.0,
                                             self.buses[i].name + '_ct_null_load_shed_' + str(k))

                    else:
                        self.problem.add(calculated_node_power == node_power_injection - self.loads[i],
                                         self.buses[i].name + '_ct_node_mismatch_' + str(k))
        else:
            # Use the load profile values at index=t_idx
            for k, i in enumerate(self.pqpv):

                # these restrictions come from the build step to be fulfilled with the load now
                node_power_injection = self.p_restrictions[k]
                calculated_node_power = self.s_restrictions[k]

                # add the nodal demand
                for load in self.buses[i].loads:
                    if load.active:
                        self.loads[i] += load.Sprof.values[t_idx].real / self.Sbase
                    else:
                        pass

                # add the restriction
                if self.load_shedding:

                    self.problem.add(
                        calculated_node_power == node_power_injection - self.loads[i] + self.load_shed[i],
                        self.buses[i].name + '_ct_node_mismatch_' + str(k))

                    # if there is no load at the node, do not allow load shedding
                    if len(self.buses[i].loads) == 0:
                        self.problem.add(self.load_shed[i] == 0.0,
                                         self.buses[i].name + '_ct_null_load_shed_' + str(k))

                else:
                    self.problem.add(calculated_node_power == node_power_injection - self.loads[i],
                                     self.buses[i].name + '_ct_node_mismatch_' + str(k))

    def solve(self):
        """
        Solve the LP OPF problem
        """

        if not self.potential_errors:

            # if there is no problem there, make it
            if self.problem is None:
                self.build()

            print('Solving LP')
            print('Load shedding:', self.load_shedding)
            self.problem.solve()  # solve with CBC
            # prob.solve(CPLEX())

            # self.problem.writeLP('dcopf.lp')

            # The status of the solution is printed to the screen
            print("Status:", pulp.LpStatus[self.problem.status])

            # The optimised objective function value is printed to the screen
            print("Cost =", pulp.value(self.problem.objective), '€')

            self.solved = True

        else:
            self.solved = False

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
        for k, branch in enumerate(self.branches):
            i = self.buses_dict[branch.bus_from]
            j = self.buses_dict[branch.bus_to]
            if self.theta[i].value() is not None and self.theta[j].value() is not None:
                F = self.B[i, j] * (self.theta[i].value() - self.theta[j].value()) * self.Sbase
            else:
                F = 'None'
            print('Branch ' + str(i) + '-' + str(j) + '(', branch.rate, 'MW) ->', F)

    def get_results(self, save_lp_file=False, t_idx=None, realistic=False):
        """
        Return the optimization results
        :param save_lp_file:
        :param t_idx:
        :param realistic:
        :return: OptimalPowerFlowResults instance
        """

        # initialize results object
        n = len(self.buses)
        m = len(self.branches)
        res = OptimalPowerFlowResults(is_dc=True)
        res.initialize(n, m)

        if save_lp_file:
            # export the problem formulation to an LP file
            self.problem.writeLP('dcopf.lp')

        if self.solved:

            if realistic:

                # Add buses
                for i in range(n):
                    # Set the voltage
                    res.voltage[i] = 1 * exp(1j * self.theta[i].value())

                    if self.load_shed is not None:
                        res.load_shedding[i] = self.load_shed[i].value()

                # Set the values
                res.Sbranch, res.Ibranch, res.loading, \
                res.losses, res.flow_direction, res.Sbus = PowerFlowMP.power_flow_post_process(self.calculation_input, res.voltage)

            else:
                # Add buses
                for i in range(n):
                    # g = 0.0
                    #
                    # generators = self.circuit.buses[i].controlled_generators + self.circuit.buses[i].batteries
                    #
                    # # Sum the slack generators
                    # if t_idx is None:
                    #     for gen in generators:
                    #         if gen.active and gen.enabled_dispatch:
                    #             g += gen.LPVar_P.value()
                    # else:
                    #     for gen in generators:
                    #         if gen.active and gen.enabled_dispatch:
                    #             g += gen.LPVar_P_prof[t_idx].value()
                    #
                    # # Set the results
                    # res.Sbus[i] = (g - self.loads[i]) * self.circuit.Sbase

                    # Set the voltage
                    res.voltage[i] = 1 * exp(1j * self.theta[i].value())

                    if self.load_shed is not None:
                        res.load_shedding[i] = self.load_shed[i].value()

                # Set the values
                res.Sbranch, res.Ibranch, res.loading, \
                res.losses, res.flow_direction, res.Sbus = PowerFlowMP.power_flow_post_process(self.calculation_input, res.voltage, only_power=True)

                # Add branches
                for k, branch in enumerate(self.branches):

                    if branch.active:
                        # get the from and to nodal indices of the branch
                        i = self.buses_dict[branch.bus_from]
                        j = self.buses_dict[branch.bus_to]

                        # compute the power flowing
                        if self.theta[i].value() is not None and self.theta[j].value() is not None:
                            F = self.B[i, j] * (self.theta[i].value() - self.theta[j].value()) * self.Sbase
                        else:
                            F = -1

                        # Set the results
                        if self.slack_loading_ij_p[k] is not None:
                            res.overloads[k] = (self.slack_loading_ij_p[k].value()
                                                + self.slack_loading_ji_p[k].value()
                                                - self.slack_loading_ij_n[k].value()
                                                - self.slack_loading_ji_n[k].value()) * self.Sbase
                        res.Sbranch[k] = F
                        res.loading[k] = abs(F / branch.rate)
                    else:
                        pass

        else:
            # the problem did not solve, pass
            pass

        return res


class AcOpf:

    def __init__(self, calculation_input: CalculationInputs, buses, branches, options, voltage_band=0.1):
        """
        Linearized AC power flow, solved with a linear solver :o
        :param calculation_input: GridCal Circuit instance
        """

        self.vm_low = 1.0 - voltage_band
        self.vm_high = 1.0 + voltage_band

        self.load_shedding = options.load_shedding

        self.calculation_input = calculation_input

        self.buses = buses
        self.buses_dict = {bus: i for i, bus in enumerate(buses)}
        self.branches = branches

        self.Sbase = calculation_input.Sbase

        # node sets
        self.pv = calculation_input.pv
        self.pq = calculation_input.pq
        self.vd = calculation_input.ref
        self.pvpq = r_[self.pv, self.pq]
        self.pvpqpq = r_[self.pv, self.pq, self.pq]

        Y = calculation_input.Ybus
        self.B = calculation_input.Ybus.imag
        Ys = calculation_input.Yseries
        S = calculation_input.Sbus
        self.V = calculation_input.Vbus.copy()

        # form the system matrix
        A11 = -Ys.imag[self.pvpq, :][:, self.pvpq]
        A12 = Y.real[self.pvpq, :][:, self.pq]
        A21 = -Ys.real[self.pq, :][:, self.pvpq]
        A22 = -Y.imag[self.pq, :][:, self.pq]
        self.sys_mat = vstack_s([hstack_s([A11, A12]),
                                 hstack_s([A21, A22])], format="csr")

        # form the slack system matrix
        A11s = -Ys.imag[self.vd, :][:, self.pvpq]
        A12s = Y.real[self.vd, :][:, self.pq]
        self.sys_mat_slack = hstack_s([A11s, A12s], format="csr")

        # compose the right hand side (power vectors)
        self.rhs = r_[S.real[self.pvpq], S.imag[self.pq]]

        # declare the voltage increments dx
        self.nn = self.sys_mat.shape[0]
        self.nbranch = len(self.branches)
        self.nbus = len(self.buses)
        self.dx_var = [None] * self.nn

        self.flow_ij = [None] * self.nbranch
        self.flow_ji = [None] * self.nbranch

        self.theta_dict = dict()

        self.loads = zeros(self.nn)
        self.load_shed = [None] * self.nn

        npv = len(self.pv)
        npq = len(self.pq)
        for i in range(self.nn):
            if i < (npv + npq):
                self.dx_var[i] = pulp.LpVariable("Va" + str(i), -0.5, 0.5)
                self.theta_dict[self.pvpq[i]] = self.dx_var[i]  # dictionary to store the angles for the pvpq nodes
                self.load_shed[i] = pulp.LpVariable("LoadShed_P_" + str(i), 0.0, 1e20)
            else:
                self.dx_var[i] = pulp.LpVariable("Vm" + str(i))
                self.load_shed[i] = pulp.LpVariable("LoadShed_Q_" + str(i), 0.0, 1e20)

        # declare the slack vars
        self.slack_loading_ij_p = [None] * self.nbranch
        self.slack_loading_ji_p = [None] * self.nbranch
        self.slack_loading_ij_n = [None] * self.nbranch
        self.slack_loading_ji_n = [None] * self.nbranch

        if self.load_shedding:
            pass

        else:

            for i in range(self.nbranch):
                self.slack_loading_ij_p[i] = pulp.LpVariable("LoadingSlack_ij_p_" + str(i), 0, 1e20)
                self.slack_loading_ji_p[i] = pulp.LpVariable("LoadingSlack_ji_p_" + str(i), 0, 1e20)
                self.slack_loading_ij_n[i] = pulp.LpVariable("LoadingSlack_ij_n_" + str(i), 0, 1e20)
                self.slack_loading_ji_n[i] = pulp.LpVariable("LoadingSlack_ji_n_" + str(i), 0, 1e20)

        # declare the generation
        self.PG = list()

        # LP problem
        self.problem = None

        # potential errors flag
        self.potential_errors = False

        # Check if the problem was solved or not
        self.solved = False

        # LP problem restrictions saved on build and added to the problem with every load change
        self.s_restrictions = list()
        self.p_restrictions = list()

    def build(self, t_idx=None):
        """
        Formulate and Solve the AC LP problem
        :return: Nothing
        """
        prob = pulp.LpProblem("AC power flow", pulp.LpMinimize)

        npv = len(self.pv)
        npq = len(self.pq)

        ################################################################################################################
        # Add the objective function
        ################################################################################################################
        fobj = 0.0

        # Add the objective function (all zeros)
        # for i in range(self.nn):
        #     fobj += self.dx_var[i] * 0.0

        # Add the generators cost
        for k, bus in enumerate(self.buses):

            generators = bus.controlled_generators + bus.batteries

            # check that there are at least one generator at the slack node
            if len(generators) == 0 and bus.type == BusMode.REF:
                self.potential_errors = True
                warn('There is no generator at the Slack node ' + bus.name + '!!!')

            # Add the bus LP vars
            for i, gen in enumerate(generators):

                # add the variable to the objective function
                if gen.active and gen.enabled_dispatch:
                    if t_idx is None:
                        fobj += gen.LPVar_P * gen.Cost
                        # add the var reference just to print later...
                        self.PG.append(gen.LPVar_P)
                    else:
                        fobj += gen.LPVar_P_prof[t_idx] * gen.Cost
                        # add the var reference just to print later...
                        self.PG.append(gen.LPVar_P_prof[t_idx])
                else:
                    pass  # the generator is not active

            # minimize the load shedding if activated
            if self.load_shedding:
                fobj += self.load_shed[k]

        # minimize the branch loading slack if not load shedding
        if not self.load_shedding:
            # Minimize the branch overload slacks
            for k, branch in enumerate(self.branches):
                if branch.active:
                    fobj += self.slack_loading_ij_p[k] + self.slack_loading_ij_n[k]
                    fobj += self.slack_loading_ji_p[k] + self.slack_loading_ji_n[k]
                else:
                    pass  # the branch is not active

        # Add the objective function to the problem
        prob += fobj
        ################################################################################################################
        # Add the matrix multiplication as constraints
        # See: https://math.stackexchange.com/questions/1727572/solving-a-feasible-system-of-linear-equations-
        #      using-linear-programming
        ################################################################################################################

        # Matrix product
        for i in range(self.nn):

            calculated_node_power = 0
            node_power_injection = 0

            # add the calculated node power
            for ii in range(self.sys_mat.indptr[i], self.sys_mat.indptr[i + 1]):
                j = self.sys_mat.indices[ii]
                calculated_node_power += self.sys_mat.data[ii] * self.dx_var[j]

            # Only for PV!
            if i < npv:

                # gather the generators at the node
                k = self.pvpqpq[i]
                generators = self.buses[k].controlled_generators + self.buses[k].batteries

                # add the generation LP vars
                if t_idx is None:
                    for gen in generators:
                        if gen.active:
                            if gen.enabled_dispatch:
                                # add the dispatch variable
                                node_power_injection += gen.LPVar_P
                            else:
                                # set the default value
                                node_power_injection += gen.P / self.Sbase
                        else:
                            pass
                else:
                    for gen in generators:
                        if gen.active:
                            if gen.enabled_dispatch:
                                # add the dispatch variable
                                node_power_injection += gen.LPVar_P_prof[t_idx]
                            else:
                                # set the default profile value
                                node_power_injection += gen.Pprof.values[t_idx] / self.Sbase
                        else:
                            pass
            else:
                pass  # it is a PQ node, no generators there

            # Store the terms for adding the load later.
            # This allows faster problem compilation in case of recurrent runs
            self.s_restrictions.append(calculated_node_power)
            self.p_restrictions.append(node_power_injection)

            # const = s == self.rhs[i]
            # prob += const

        ################################################################################################################
        # Add the matrix multiplication as constraints (slack)
        ################################################################################################################

        for i in range(self.sys_mat_slack.shape[0]):  # vd nodes

            calculated_node_power = 0
            node_power_injection = 0

            # add the calculated node power
            for ii in range(self.sys_mat_slack.indptr[i], self.sys_mat_slack.indptr[i + 1]):
                j = self.sys_mat_slack.indices[ii]
                calculated_node_power += self.sys_mat_slack.data[ii] * self.dx_var[j]

            # Only for PV!
            if i < npv:

                # gather the generators at the node
                k = self.vd[i]
                generators = self.buses[k].controlled_generators + self.buses[k].batteries

                # add the generation LP vars
                if t_idx is None:
                    for gen in generators:
                        if gen.active and gen.enabled_dispatch:
                            node_power_injection += gen.LPVar_P
                        else:
                            pass
                else:
                    for gen in generators:
                        if gen.active and gen.enabled_dispatch:
                            node_power_injection += gen.LPVar_P_prof[t_idx]
                        else:
                            pass
            else:
                pass  # it is a PQ node, no generators there

            # the sum of the slack node generators must be equal to the slack node power
            prob.add(calculated_node_power == node_power_injection, 'ct_slack_power_' + str(i))

        ################################################################################################################
        # control the voltage module between vm_low and vm_high
        ################################################################################################################
        for k, i in enumerate(self.pq):
            vm_var = abs(self.V[i]) + self.dx_var[npv + npq + k]  # compose the voltage module
            prob += vm_var <= self.vm_high
            prob += self.vm_low <= vm_var

        ################################################################################################################
        # control the voltage angles: Already defined with bounds
        ################################################################################################################
        # No need, already done

        ################################################################################################################
        # Set the branch limits: This is the same as in the DC OPF, unless a better approximation is found
        ################################################################################################################
        for k, branch in enumerate(self.branches):
            i = self.buses_dict[branch.bus_from]
            j = self.buses_dict[branch.bus_to]

            if i in self.theta_dict.keys():
                va_i = self.theta_dict[i]
            else:
                va_i = 0.0  # is slack

            if j in self.theta_dict.keys():
                va_j = self.theta_dict[j]
            else:
                va_j = 0.0

            # branch flow
            self.flow_ij[k] = self.B[i, j] * (va_i - va_j)
            self.flow_ji[k] = self.B[i, j] * (va_j - va_i)

            # constraints
            if not self.load_shedding:
                # Add slacks
                prob.add(self.flow_ij[k] + self.slack_loading_ij_p[k] - self.slack_loading_ij_n[
                    k] <= branch.rate / self.Sbase,
                         'ct_br_flow_ij_' + str(k))
                prob.add(self.flow_ji[k] + self.slack_loading_ji_p[k] - self.slack_loading_ji_n[
                    k] <= branch.rate / self.Sbase,
                         'ct_br_flow_ji_' + str(k))
            else:
                # The slacks are in the form of load shedding
                prob.add(self.flow_ij[k] <= branch.rate / self.Sbase, 'ct_br_flow_ij_' + str(k))
                prob.add(self.flow_ji[k] <= branch.rate / self.Sbase, 'ct_br_flow_ji_' + str(k))

        # set the current problem
        self.problem = prob

    def set_loads(self, t_idx=None):
        """
        Add the loads to the LP problem
        Args:
            t_idx: time index, if none, the default object values are taken
        """
        npv = len(self.pv)
        npq = len(self.pq)

        if t_idx is None:

            # use the default loads
            for k, i in enumerate(self.pvpqpq):

                # these restrictions come from the build step to be fulfilled with the load now
                node_power_injection = self.p_restrictions[k]
                calculated_node_power = self.s_restrictions[k]

                # add the nodal demand
                for load in self.buses[i].loads:
                    if load.active:
                        if k < (npq + npv):
                            self.loads[i] += load.S.real / self.Sbase
                        else:
                            self.loads[i] += load.S.imag / self.Sbase
                    else:
                        pass

                if calculated_node_power is 0 and node_power_injection is 0:
                    # nodes without injection or generation
                    pass
                else:
                    # add the restriction
                    if self.load_shedding:

                        self.problem.add(
                            calculated_node_power == node_power_injection - self.loads[i] + self.load_shed[i],
                            self.buses[i].name + '_ct_node_mismatch_' + str(k))

                        # if there is no load at the node, do not allow load shedding
                        if len(self.buses[i].loads) == 0:
                            self.problem.add(self.load_shed[i] == 0.0,
                                             self.buses[i].name + '_ct_null_load_shed_' + str(k))

                    else:
                        self.problem.add(calculated_node_power == node_power_injection - self.loads[i],
                                         self.buses[i].name + '_ct_node_mismatch_' + str(k))
        else:
            # Use the load profile values at index=t_idx
            for k, i in enumerate(self.pvpq):

                # these restrictions come from the build step to be fulfilled with the load now
                node_power_injection = self.p_restrictions[k]
                calculated_node_power = self.s_restrictions[k]

                # add the nodal demand
                for load in self.buses[i].loads:
                    if load.active:
                        if k < (npq + npv):
                            self.loads[i] += load.Sprof.values[t_idx].real / self.Sbase
                        else:
                            self.loads[i] += load.Sprof.values[t_idx].imag / self.Sbase
                    else:
                        pass

                # add the restriction
                if self.load_shedding:

                    self.problem.add(
                        calculated_node_power == node_power_injection - self.loads[i] + self.load_shed[i],
                        self.buses[i].name + '_ct_node_mismatch_' + str(k))

                    # if there is no load at the node, do not allow load shedding
                    if len(self.buses[i].loads) == 0:
                        self.problem.add(self.load_shed[i] == 0.0,
                                         self.buses[i].name + '_ct_null_load_shed_' + str(k))

                else:
                    self.problem.add(calculated_node_power == node_power_injection - self.loads[i],
                                     self.buses[i].name + '_ct_node_mismatch_' + str(k))

    def solve(self):
        """
        Solve the LP OPF problem
        """

        if self.problem is None:
            self.build()

        if not self.potential_errors:

            # if there is no problem there, make it
            if self.problem is None:
                self.build()

            print('Solving LP')
            print('Load shedding:', self.load_shedding)
            self.problem.solve()  # solve with CBC
            # prob.solve(CPLEX())

            # self.problem.writeLP('dcopf.lp')

            # The status of the solution is printed to the screen
            print("Status:", pulp.LpStatus[self.problem.status])

            # The optimised objective function value is printed to the screen
            print("Cost =", pulp.value(self.problem.objective), '€')

            self.solved = True

            # Solve
            self.problem.solve()
            self.problem.writeLP('ac_opf.lp')

            # compose the results vector ###############################################################################
            npv = len(self.pv)
            npq = len(self.pq)

            x_inc = zeros(self.nn)
            for i, th in enumerate(self.dx_var):
                x_inc[i] = th.value()

            #  set the pv voltages
            va_pv = x_inc[0:npv]
            vm_pv = abs(self.V[self.pv])
            self.V[self.pv] = vm_pv * exp(1j * va_pv)

            # set the pq voltages
            va_pq = x_inc[npv:npv + npq]
            vm_pq = abs(self.V[self.pq]) + x_inc[npv + npq:]
            self.V[self.pq] = vm_pq * exp(1j * va_pq)

        else:
            self.solved = False

    def print(self):
        print('Voltage solution')

        # compose voltages results
        df_v = pd.DataFrame(data=c_[abs(self.V), angle(self.V), self.V.real, self.V.imag],
                            columns=['Module', 'Angle(rad)', 'Real', 'Imag'],
                            index=['Bus' + str(i) for i in range(self.V.shape[0])])

        # compose branches results
        flows = zeros(self.nbranch)
        loading = zeros(self.nbranch)
        br_names = [None] * self.nbranch
        for k in range(self.nbranch):
            flows[k] = abs(self.flow_ij[k].value()) * self.Sbase
            loading[k] = flows[k] / self.branches[k].rate * 100.0
            br_names[k] = 'Branch ' + str(k)

        df_f = pd.DataFrame(data=c_[flows, loading],
                            columns=['Flow (MW)', 'Loading (%)'],
                            index=br_names)

        generation = zeros(len(self.PG))
        gen_names = [None] * len(self.PG)
        for k, gen_var in enumerate(self.PG):
            generation[k] = gen_var.value() * self.Sbase
            gen_names[k] = 'Gen' + str(k)

        df_g = pd.DataFrame(data=generation,
                            columns=['Gen(MW)'],
                            index=gen_names)
        print(df_v)
        print(df_f)
        print(df_g)

    def get_results(self, save_lp_file=False, t_idx=None, realistic=False):
        """
        Return the optimization results
        :param save_lp_file:
        :param t_idx:
        :param realistic: compute the realistic values associated with the voltage solution
        :return: OptimalPowerFlowResults instance
        """

        # initialize results object
        n_bus = len(self.buses)
        n_branch = len(self.branches)
        res = OptimalPowerFlowResults(is_dc=False)
        res.initialize(n_bus, n_branch)

        if save_lp_file:
            # export the problem formulation to an LP file
            self.problem.writeLP('acopf.lp')

        if self.solved:

            if realistic:
                # Set the values
                res.Sbranch, res.Ibranch, res.loading, \
                res.losses, res.flow_direction, res.Sbus = PowerFlowMP.power_flow_post_process(self.calculation_input, self.V)
                res.voltage = self.V
            else:

                # Add buses
                for i in range(n_bus):

                    g = 0.0
                    generators = self.buses[i].controlled_generators + self.buses[i].batteries

                    # Sum the slack generators
                    if t_idx is None:
                        for gen in generators:
                            if gen.active and gen.enabled_dispatch:
                                g += gen.LPVar_P.value()
                    else:
                        for gen in generators:
                            if gen.active and gen.enabled_dispatch:
                                g += gen.LPVar_P_prof[t_idx].value()

                    # Set the results (power, load shedding)
                    res.Sbus[i] = (g - self.loads[i]) * self.calculation_input.Sbase

                    if self.load_shed is not None:
                        res.load_shedding[i] = self.load_shed[i].value()

                # Set the values
                res.Sbranch, res.Ibranch, res.loading, \
                res.losses, res.flow_direction, res.Sbus = PowerFlowMP.power_flow_post_process(self.calculation_input, self.V, only_power=True)
                res.voltage = self.V
                angles = angle(self.V)

                # Add branches
                for k, branch in enumerate(self.branches):

                    if branch.active:
                        # get the from and to nodal indices of the branch
                        i = self.buses_dict[branch.bus_from]
                        j = self.buses_dict[branch.bus_to]

                        # compute the power flowing
                        if angles[i] is not None and angles[j] is not None:
                            F = self.B[i, j] * (angles[i] - angles[j]) * self.Sbase
                        else:
                            F = -1

                        # Set the results
                        if self.slack_loading_ij_p[k] is not None:
                            res.overloads[k] = (self.slack_loading_ij_p[k].value()
                                                + self.slack_loading_ji_p[k].value()
                                                - self.slack_loading_ij_n[k].value()
                                                - self.slack_loading_ji_n[k].value()) * self.Sbase
                        res.Sbranch[k] = F
                        res.loading[k] = abs(F / branch.rate)
                    else:
                        pass

        else:
            # the problem did not solve, pass
            pass

        return res


class OptimalPowerFlowOptions:

    def __init__(self, verbose=False, load_shedding=False, solver=SolverType.DC_OPF, realistic_results=False):
        """
        OPF options constructor
        :param verbose:
        :param load_shedding:
        :param solver:
        :param realistic_results:
        """
        self.verbose = verbose

        self.load_shedding = load_shedding

        self.solver = solver

        self.realistic_results = realistic_results


class OptimalPowerFlowResults:

    def __init__(self, Sbus=None, voltage=None, load_shedding=None, Sbranch=None, overloads=None,
                 loading=None, losses=None, converged=None, is_dc=False):
        """
        OPF results constructor
        :param Sbus: bus power injections
        :param voltage: bus voltages
        :param load_shedding: load shedding values
        :param Sbranch: branch power values
        :param overloads: branch overloading values
        :param loading: branch loading values
        :param losses: branch losses
        :param converged: converged?
        """
        self.Sbus = Sbus

        self.voltage = voltage

        self.load_shedding = load_shedding

        self.Sbranch = Sbranch

        self.overloads = overloads

        self.loading = loading

        self.losses = losses

        self.flow_direction = None

        self.converged = converged

        self.available_results = ['Bus voltage', 'Bus power', 'Branch power', 'Branch loading',
                                  'Branch overloads', 'Load shedding']

        self.plot_bars_limit = 100

        self.is_dc = is_dc

    def copy(self):
        """
        Return a copy of this
        @return:
        """
        return OptimalPowerFlowResults(Sbus=self.Sbus,
                                       voltage=self.voltage,
                                       load_shedding=self.load_shedding,
                                       Sbranch=self.Sbranch,
                                       overloads=self.overloads,
                                       loading=self.loading,
                                       losses=self.losses,
                                       converged=self.converged)

    def initialize(self, n, m):
        """
        Initialize the arrays
        @param n: number of buses
        @param m: number of branches
        @return:
        """
        self.Sbus = zeros(n, dtype=complex)

        self.voltage = zeros(n, dtype=complex)

        self.load_shedding = zeros(n, dtype=float)

        self.Sbranch = zeros(m, dtype=complex)

        self.loading = zeros(m, dtype=complex)

        self.overloads = zeros(m, dtype=complex)

        self.losses = zeros(m, dtype=complex)

        self.converged = list()

        self.plot_bars_limit = 100

    def apply_from_island(self, results, b_idx, br_idx):
        """
        Apply results from another island circuit to the circuit results represented here
        @param results: PowerFlowResults
        @param b_idx: bus original indices
        @param br_idx: branch original indices
        @return:
        """
        self.Sbus[b_idx] = results.Sbus

        self.voltage[b_idx] = results.voltage

        self.load_shedding[b_idx] = results.load_shedding

        self.Sbranch[br_idx] = results.Sbranch

        self.loading[br_idx] = results.loading

        self.overloads[br_idx] = results.overloads

        self.losses[br_idx] = results.losses

        self.converged.append(results.converged)

    def plot(self, result_type, ax=None, indices=None, names=None):
        """
        Plot the results
        :param result_type:
        :param ax:
        :param indices:
        :param names:
        :return:
        """

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        if indices is None:
            indices = array(range(len(names)))

        if len(indices) > 0:
            labels = names[indices]
            y_label = ''
            title = ''
            if result_type == 'Bus voltage':
                if self.is_dc:
                    y = np.angle(self.voltage[indices])
                    y_label = '(rad)'
                    title = 'Bus voltage angle'
                else:
                    y = np.abs(self.voltage[indices])
                    y_label = '(p.u.)'
                    title = 'Bus voltage'

            elif result_type == 'Branch power':
                y = self.Sbranch[indices].real
                y_label = '(MW)'
                title = 'Branch power '

            elif result_type == 'Bus power':
                y = self.Sbus[indices].real
                y_label = '(MW)'
                title = 'Bus power '

            elif result_type == 'Branch loading':
                y = np.abs(self.loading[indices] * 100.0)
                y_label = '(%)'
                title = 'Branch loading '

            elif result_type == 'Branch overloads':
                y = np.abs(self.overloads[indices])
                y_label = '(MW)'
                title = 'Branch overloads '

            elif result_type == 'Branch losses':
                y = self.losses[indices].real
                y_label = '(MW)'
                title = 'Branch losses '

            elif result_type == 'Load shedding':
                y = self.load_shedding[indices]
                y_label = '(MW)'
                title = 'Load shedding'

            else:
                pass

            df = pd.DataFrame(data=y, index=labels, columns=[result_type])
            df.fillna(0, inplace=True)

            if len(df.columns) < self.plot_bars_limit:
                df.plot(ax=ax, kind='bar')
            else:
                df.plot(ax=ax, legend=False, linewidth=LINEWIDTH)
            ax.set_ylabel(y_label)
            ax.set_title(title)

            return df

        else:
            return None


class OptimalPowerFlow(QRunnable):
    # progress_signal = pyqtSignal(float)
    # progress_text = pyqtSignal(str)
    # done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: OptimalPowerFlowOptions):
        """
        PowerFlow class constructor
        @param grid: MultiCircuit Object
        @param options: OPF options
        """
        QRunnable.__init__(self)

        # Grid to run a power flow in
        self.grid = grid

        # Options to use
        self.options = options

        # OPF results
        self.results = None

        # set cancel state
        self.__cancel__ = False

        self.all_solved = True

    def single_optimal_power_flow(self, calculation_input: CalculationInputs, buses, branches, t_idx=None):
        """
        Run a power flow simulation for a single circuit
        @param calculation_input: Single island circuit
        @param t_idx: time index, if none the default values are taken
        @return: OptimalPowerFlowResults object
        """

        # declare LP problem
        if self.options.solver == SolverType.DC_OPF:
            problem = DcOpf(calculation_input, buses, branches, self.options)
        else:
            problem = AcOpf(calculation_input, buses, branches, self.options)

        problem.build(t_idx=t_idx)
        problem.set_loads(t_idx=t_idx)
        problem.solve()

        # results
        res = problem.get_results(t_idx=t_idx, realistic=self.options.realistic_results)

        return res, problem.solved

    def opf(self, t_idx=None):
        """
        Run a power flow for every circuit
        @return: OptimalPowerFlowResults object
        """
        # print('PowerFlow at ', self.grid.name)
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        self.results = OptimalPowerFlowResults()
        self.results.initialize(n, m)
        # self.progress_signal.emit(0.0)

        self.all_solved = True

        print('Compiling...', end='')
        numerical_circuit = self.grid.compile()
        calculation_inputs = numerical_circuit.compute()

        if len(calculation_inputs) > 1:

            for calculation_input in calculation_inputs:

                buses = [self.grid.buses[i] for i in calculation_input.original_bus_idx]
                branches = [self.grid.branches[i] for i in calculation_input.original_branch_idx]

                if self.options.verbose:
                    print('Solving ' + calculation_input.name)

                # run OPF
                if len(calculation_input.ref) > 0:
                    optimal_power_flow_results, solved = self.single_optimal_power_flow(calculation_input, buses,
                                                                                        branches, t_idx=t_idx)
                else:
                    optimal_power_flow_results = OptimalPowerFlowResults(is_dc=True)
                    optimal_power_flow_results.initialize(calculation_input.nbus, calculation_input.nbr)
                    solved = True  # couldn't solve because it was impossible to formulate the problem so we skip it...
                    warn('The island does not have any slack...')

                # assert the total solvability
                self.all_solved = self.all_solved and solved

                # merge island results
                self.results.apply_from_island(optimal_power_flow_results,
                                               calculation_input.original_bus_idx,
                                               calculation_input.original_branch_idx)
        else:
            # only one island ...
            calculation_input = calculation_inputs[0]

            if self.options.verbose:
                print('Solving ' + calculation_input.name)

            # run OPF
            optimal_power_flow_results, solved = self.single_optimal_power_flow(calculation_input, self.grid.buses,
                                                                                self.grid.branches, t_idx=t_idx)

            # assert the total solvability
            self.all_solved = self.all_solved and solved

            # merge island results
            self.results.apply_from_island(optimal_power_flow_results,
                                           calculation_input.original_bus_idx,
                                           calculation_input.original_branch_idx)

        return self.results

    def run(self):
        """

        :return:
        """
        self.opf()

    def run_at(self, t):
        """
        Run power flow at the time series object index t
        @param t: time index
        @return: OptimalPowerFlowResults object
        """

        res = self.opf(t)

        return res

    def cancel(self):
        self.__cancel__ = True

