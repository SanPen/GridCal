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
from scipy.sparse import hstack as hstack_s, vstack as vstack_s
from matplotlib import pyplot as plt

from GridCal.Engine.BasicStructures import BusMode
from GridCal.Engine.PowerFlowDriver import PowerFlowMP
from GridCal.Engine.IoStructures import CalculationInputs, OptimalPowerFlowResults




class DcOpf:

    def __init__(self, calculation_input: CalculationInputs=None, buses=list(), branches=list(), options=None):
        """
        OPF simple dispatch problem
        :param calculation_input: GridCal Circuit instance (remember this must be a connected island)
        :param options: OptimalPowerFlowOptions instance
        """

        self.calculation_input = calculation_input

        self.buses = buses
        self.buses_dict = {bus: i for i, bus in enumerate(buses)}  # dictionary of bus objects given their indices
        self.branches = branches

        self.options = options

        if options is not None:
            self.load_shedding = options.load_shedding
        else:
            self.load_shedding = False

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

        self.loads = np.zeros(self.nbus)

    def copy(self):

        obj = DcOpf(calculation_input=self.calculation_input, options=self.options)

        obj.calculation_input = self.calculation_input

        obj.buses = self.buses
        obj.buses_dict = self.buses_dict
        obj.branches = self.branches

        obj.load_shedding = self.load_shedding

        obj.Sbase = self.Sbase
        obj.B = self.B
        obj.nbus = self.nbus
        obj.nbranch = self.nbranch

        # node sets
        obj.pqpv = self.pqpv.copy()
        obj.pv = self.pv.copy()
        obj.vd = self.vd.copy()
        obj.pq = self.pq.copy()

        # declare the voltage angles and the possible load shed values
        obj.theta = self.theta.copy()
        obj.load_shed = self.load_shed.copy()

        # declare the slack vars
        obj.slack_loading_ij_p = self.slack_loading_ij_p.copy()
        obj.slack_loading_ji_p = self.slack_loading_ji_p.copy()
        obj.slack_loading_ij_n = self.slack_loading_ij_n.copy()
        obj.slack_loading_ji_n = self.slack_loading_ji_n.copy()

        # declare the generation
        obj.PG = self.PG.copy()

        # LP problem
        obj.problem = self.problem.copy()

        # potential errors flag
        obj.potential_errors = self.potential_errors

        # Check if the problem was solved or not
        obj.solved = self.solved

        # LP problem restrictions saved on build and added to the problem with every load change
        obj.p_restrictions = self.p_restrictions.copy()
        obj.s_restrictions = self.s_restrictions.copy()

        obj.loads = np.zeros(self.nbus)

        return obj

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

        self.loads = np.zeros(self.nbus)

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

                # Add non dispatcheable generation
                generators = self.buses[i].controlled_generators + self.buses[i].batteries
                for gen in generators:
                    if gen.active and not gen.enabled_dispatch:
                        self.loads[i] -= gen.P / self.Sbase

                # Add the static generators
                for gen in self.buses[i].static_generators:
                    if gen.active:
                        self.loads[i] -= gen.S.real / self.Sbase

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

                # Add non dispatcheable generation
                generators = self.buses[i].controlled_generators + self.buses[i].batteries
                for gen in generators:
                    if gen.active and not gen.enabled_dispatch:
                        self.loads[i] -= gen.Pprof.values[t_idx] / self.Sbase

                # Add the static generators
                for gen in self.buses[i].static_generators:
                    if gen.active:
                        self.loads[i] -= gen.Sprof.values[t_idx].real / self.Sbase

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
                    res.voltage[i] = 1 * np.exp(1j * self.theta[i].value())

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
                    generators = self.buses[i].controlled_generators + self.buses[i].batteries

                    # copy the generators LpVAr
                    if t_idx is None:
                        pass
                        # for gen in generators:
                        #     if gen.active and gen.enabled_dispatch:
                        #         g += gen.LPVar_P.value()
                    else:
                        # copy the LpVar
                        for gen in generators:
                            if gen.active and gen.enabled_dispatch:
                                val = gen.LPVar_P.value()
                                var = pulp.LpVariable('')
                                var.varValue = val
                                gen.LPVar_P_prof[t_idx] = var
                    #
                    # # Set the results
                    # res.Sbus[i] = (g - self.loads[i]) * self.circuit.Sbase

                    # Set the voltage
                    res.voltage[i] = 1 * np.exp(1j * self.theta[i].value())

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

    def __init__(self, calculation_input: CalculationInputs, buses=list(), branches=list(),
                 options=None, voltage_band=0.1):
        """
        Linearized AC power flow, solved with a linear solver :o
        :param calculation_input: GridCal Circuit instance
        """

        self.vm_low = 1.0 - voltage_band
        self.vm_high = 1.0 + voltage_band

        self.load_shedding = options.load_shedding

        self.calculation_input = calculation_input

        self.options = options

        self.buses = buses
        self.buses_dict = {bus: i for i, bus in enumerate(buses)}
        self.branches = branches

        self.Sbase = calculation_input.Sbase

        # node sets
        self.pv = calculation_input.pv
        self.pq = calculation_input.pq
        self.vd = calculation_input.ref
        self.pvpq = np.r_[self.pv, self.pq]
        self.pvpqpq = np.r_[self.pv, self.pq, self.pq]

        # Y = calculation_input.Ybus
        self.B = calculation_input.Ybus.imag
        # Ys = calculation_input.Yseries
        # S = calculation_input.Sbus
        self.V = calculation_input.Vbus.copy()

        # form the system matrix
        self.sys_mat = None
        # A11 = -Ys.imag[self.pvpq, :][:, self.pvpq]
        # A12 = Y.real[self.pvpq, :][:, self.pq]
        # A21 = -Ys.real[self.pq, :][:, self.pvpq]
        # A22 = -Y.imag[self.pq, :][:, self.pq]
        # self.sys_mat = vstack_s([hstack_s([A11, A12]),
        #                          hstack_s([A21, A22])], format="csr")

        # form the slack system matrix
        # A11s = -Ys.imag[self.vd, :][:, self.pvpq]
        # A12s = Y.real[self.vd, :][:, self.pq]
        # self.sys_mat_slack = hstack_s([A11s, A12s], format="csr")
        self.sys_mat_slack = None

        # compose the right hand side (power vectors)
        # self.rhs = np.r_[S.real[self.pvpq], S.imag[self.pq]]
        self.rhs = None

        # declare the voltage increments dx
        self.nn = 0
        self.nbranch = len(self.branches)
        self.nbus = len(self.buses)
        self.dx_var = [None] * self.nn

        self.flow_ij = [None] * self.nbranch
        self.flow_ji = [None] * self.nbranch

        self.theta_dict = dict()

        self.loads = np.zeros(self.nn)
        self.load_shed = [None] * self.nn

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

        # form the system matrix
        Y = self.calculation_input.Ybus
        Ys = self.calculation_input.Yseries
        S = self.calculation_input.Sbus
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

        # right hand side
        self.rhs = np.r_[S.real[self.pvpq], S.imag[self.pq]]

        self.nn = self.sys_mat.shape[0]
        self.nbranch = len(self.branches)
        self.nbus = len(self.buses)
        self.dx_var = [None] * self.nn
        self.loads = np.zeros(self.nn)
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

    def copy(self):

        obj = AcOpf(self.calculation_input, options=self.options)

        obj.buses = self.buses.copy()
        obj.buses_dict = self.buses_dict.copy()
        obj.branches = self.branches.copy()

        # self.Sbase = calculation_input.Sbase

        # node sets
        # self.pv = calculation_input.pv
        # self.pq = calculation_input.pq
        # self.vd = calculation_input.ref
        # self.pvpq = np.r_[self.pv, self.pq]
        # self.pvpqpq = np.r_[self.pv, self.pq, self.pq]

        # Y = calculation_input.Ybus
        # self.B = calculation_input.Ybus.imag
        # Ys = calculation_input.Yseries
        # S = calculation_input.Sbus
        # self.V = calculation_input.Vbus.copy()

        # form the system matrix
        # A11 = -Ys.imag[self.pvpq, :][:, self.pvpq]
        # A12 = Y.real[self.pvpq, :][:, self.pq]
        # A21 = -Ys.real[self.pq, :][:, self.pvpq]
        # A22 = -Y.imag[self.pq, :][:, self.pq]
        obj.sys_mat = self.sys_mat.copy()

        # form the slack system matrix
        # A11s = -Ys.imag[self.vd, :][:, self.pvpq]
        # A12s = Y.real[self.vd, :][:, self.pq]
        obj.sys_mat_slack = self.sys_mat_slack.copy()

        # compose the right hand side (power vectors)
        obj.rhs = self.rhs.copy()

        # declare the voltage increments dx
        obj.nn = self.nn
        obj.nbranch = self.nbranch
        obj.nbus = self.nbus
        obj.dx_var = self.dx_var.copy()

        obj.flow_ij = self.flow_ij.copy()
        obj.flow_ij = self.flow_ij.copy()

        obj.theta_dict = self.theta_dict.copy()

        obj.loads = self.loads.copy()
        obj.load_shed = self.load_shed.copy()

        # declare the slack vars
        obj.slack_loading_ij_p = self.slack_loading_ij_p.copy()
        obj.slack_loading_ji_p = self.slack_loading_ji_p.copy()
        obj.slack_loading_ij_n = self.slack_loading_ij_n.copy()
        obj.slack_loading_ji_n = self.slack_loading_ji_n.copy()

        # declare the generation
        obj.PG = self.PG.copy()

        # LP problem
        obj.problem = self.problem.copy()

        # potential errors flag
        obj.potential_errors = self.potential_errors

        # Check if the problem was solved or not
        obj.solved = self.solved

        # LP problem restrictions saved on build and added to the problem with every load change
        obj.s_restrictions = self.s_restrictions.copy()
        obj.p_restrictions = self.p_restrictions.copy()

        return obj

    def set_loads(self, t_idx=None):
        """
        Add the loads to the LP problem
        Args:
            t_idx: time index, if none, the default object values are taken
        """
        npv = len(self.pv)
        npq = len(self.pq)

        self.loads = np.zeros(self.nn)

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

                # Add non dispatcheable generation
                generators = self.buses[i].controlled_generators + self.buses[i].batteries
                for gen in generators:
                    if gen.active and not gen.enabled_dispatch:
                        self.loads[i] -= gen.P / self.Sbase

                # Add the static generators
                for gen in self.buses[i].static_generators:
                    if gen.active:
                        self.loads[i] -= gen.S.real / self.Sbase

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

                # Add non dispatcheable generation
                generators = self.buses[i].controlled_generators + self.buses[i].batteries
                for gen in generators:
                    if gen.active and not gen.enabled_dispatch:
                        self.loads[i] -= gen.Pprof.values[t_idx] / self.Sbase

                # Add the static generators
                for gen in self.buses[i].static_generators:
                    if gen.active:
                        self.loads[i] -= gen.Sprof.values[t_idx].real / self.Sbase

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

            x_inc = np.zeros(self.nn)
            for i, th in enumerate(self.dx_var):
                x_inc[i] = th.value()

            #  set the pv voltages
            va_pv = x_inc[0:npv]
            vm_pv = abs(self.V[self.pv])
            self.V[self.pv] = vm_pv * np.exp(1j * va_pv)

            # set the pq voltages
            va_pq = x_inc[npv:npv + npq]
            vm_pq = abs(self.V[self.pq]) + x_inc[npv + npq:]
            self.V[self.pq] = vm_pq * np.exp(1j * va_pq)

        else:
            self.solved = False

    def print(self):
        print('Voltage solution')

        # compose voltages results
        df_v = pd.DataFrame(data=np.c_[abs(self.V), np.angle(self.V), self.V.real, self.V.imag],
                            columns=['Module', 'Angle(rad)', 'Real', 'Imag'],
                            index=['Bus' + str(i) for i in range(self.V.shape[0])])

        # compose branches results
        flows = np.zeros(self.nbranch)
        loading = np.zeros(self.nbranch)
        br_names = [None] * self.nbranch
        for k in range(self.nbranch):
            flows[k] = abs(self.flow_ij[k].value()) * self.Sbase
            loading[k] = flows[k] / self.branches[k].rate * 100.0
            br_names[k] = 'Branch ' + str(k)

        df_f = pd.DataFrame(data=np.c_[flows, loading],
                            columns=['Flow (MW)', 'Loading (%)'],
                            index=br_names)

        generation = np.zeros(len(self.PG))
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
                # run a full power flow
                res.Sbranch, res.Ibranch, res.loading, \
                res.losses, res.flow_direction, res.Sbus = PowerFlowMP.power_flow_post_process(self.calculation_input,
                                                                                               self.V)
                res.voltage = self.V

            else:

                # Add buses
                for i in range(n_bus):

                    g = 0.0
                    generators = self.buses[i].controlled_generators + self.buses[i].batteries

                    # copy the generators LpVAr
                    if t_idx is None:
                        pass
                        # for gen in generators:
                        #     if gen.active and gen.enabled_dispatch:
                        #         g += gen.LPVar_P.value()
                    else:
                        # copy the LpVar
                        for gen in generators:
                            if gen.active and gen.enabled_dispatch:
                                val = gen.LPVar_P.value()
                                var = pulp.LpVariable('')
                                var.varValue = val
                                gen.LPVar_P_prof[t_idx] = var

                    # Set the results (power, load shedding)
                    res.Sbus[i] = (g - self.loads[i]) * self.calculation_input.Sbase

                    if self.load_shed is not None:
                        res.load_shedding[i] = self.load_shed[i].value()

                # Set the values
                res.Sbranch, res.Ibranch, res.loading, \
                res.losses, res.flow_direction, res.Sbus = PowerFlowMP.power_flow_post_process(self.calculation_input,
                                                                                               self.V, only_power=True)
                res.voltage = self.V
                angles = np.angle(self.V)

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

