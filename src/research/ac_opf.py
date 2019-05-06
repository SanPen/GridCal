"""
This program implements the DC power flow as a linear program
"""
from pulp import *
import numpy as np
import pandas as pd
from scipy.sparse import hstack as hstack_s, vstack as vstack_s

from GridCal.Engine import *


class AcOPf:

    def __init__(self, circuit: MultiCircuit, voltage_band=0.1):
        """
        Linearized AC power flow, solved with a linear solver :o
        :param circuit: GridCal Circuit instance
        """

        self.vm_low = 1.0 - voltage_band
        self.vm_high = 1.0 + voltage_band
        self.load_shedding = False

        self.circuit = circuit
        self.Sbase = circuit.Sbase

        # node sets
        self.pv = circuit.power_flow_input.pv
        self.pq = circuit.power_flow_input.pq
        self.vd = circuit.power_flow_input.ref
        self.pvpq = r_[self.pv, self.pq]
        self.pvpqpq = r_[self.pv, self.pq, self.pq]

        Y = circuit.power_flow_input.Ybus
        self.B = circuit.power_flow_input.Ybus.imag
        Ys = circuit.power_flow_input.Yseries
        S = circuit.power_flow_input.Sbus
        self.V = circuit.power_flow_input.Vbus.copy()

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
        self.nbranch = len(self.circuit.branches)
        self.nbus = len(self.circuit.buses)
        self.dx_var = [None] * self.nn

        self.flow_ij = [None] * self.nbranch
        self.flow_ji = [None] * self.nbranch

        self.theta_dict = dict()

        self.loads = np.zeros(self.nn)
        self.load_shed = [None] * self.nn

        npv = len(self.pv)
        npq = len(self.pq)
        for i in range(self.nn):
            if i < (npv+npq):
                self.dx_var[i] = LpVariable("Va" + str(i), -0.5, 0.5)
                self.theta_dict[self.pvpq[i]] = self.dx_var[i]  # dictionary to store the angles for the pvpq nodes
                self.load_shed[i] = pulp.LpVariable("LoadShed_P_" + str(i), 0.0, 1e20)
            else:
                self.dx_var[i] = LpVariable("Vm" + str(i))
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
        prob = LpProblem("AC power flow", LpMinimize)

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
        for k, bus in enumerate(self.circuit.buses):

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
            for k, branch in enumerate(self.circuit.branches):
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
                generators = self.circuit.buses[k].controlled_generators + self.circuit.buses[k].batteries

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
                                node_power_injection += gen.P_prof.values[t_idx] / self.Sbase
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
                generators = self.circuit.buses[k].controlled_generators + self.circuit.buses[k].batteries

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
        for k, branch in enumerate(self.circuit.branches):
            i = self.circuit.buses_dict[branch.bus_from]
            j = self.circuit.buses_dict[branch.bus_to]

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
                prob.add(self.flow_ij[k] + self.slack_loading_ij_p[k] - self.slack_loading_ij_n[k] <= branch.rate / self.Sbase,
                         'ct_br_flow_ij_' + str(k))
                prob.add(self.flow_ji[k] + self.slack_loading_ji_p[k] - self.slack_loading_ji_n[k] <= branch.rate / self.Sbase,
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
                for load in self.circuit.buses[i].loads:
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

                        self.problem.add(calculated_node_power == node_power_injection - self.loads[i] + self.load_shed[i],
                                         self.circuit.buses[i].name + '_ct_node_mismatch_' + str(k))

                        # if there is no load at the node, do not allow load shedding
                        if len(self.circuit.buses[i].loads) == 0:
                            self.problem.add(self.load_shed[i] == 0.0, self.circuit.buses[i].name + '_ct_null_load_shed_' + str(k))

                    else:
                        self.problem.add(calculated_node_power == node_power_injection - self.loads[i],
                                         self.circuit.buses[i].name + '_ct_node_mismatch_' + str(k))
        else:
            # Use the load profile values at index=t_idx
            for k, i in enumerate(self.pqpv):

                # these restrictions come from the build step to be fulfilled with the load now
                node_power_injection = self.p_restrictions[k]
                calculated_node_power = self.s_restrictions[k]

                # add the nodal demand
                for load in self.circuit.buses[i].loads:
                    if load.active:
                        if k < (npq + npv):
                            self.loads[i] += load.P_prof.values[t_idx] / self.Sbase
                        else:
                            self.loads[i] += load.Q_prof.values[t_idx] / self.Sbase
                    else:
                        pass

                # add the restriction
                if self.load_shedding:

                    self.problem.add(
                        calculated_node_power == node_power_injection - self.loads[i] + self.load_shed[i],
                        self.circuit.buses[i].name + '_ct_node_mismatch_' + str(k))

                    # if there is no load at the node, do not allow load shedding
                    if len(self.circuit.buses[i].loads) == 0:
                        self.problem.add(self.load_shed[i] == 0.0,
                                         self.circuit.buses[i].name + '_ct_null_load_shed_' + str(k))

                else:
                    self.problem.add(calculated_node_power == node_power_injection - self.loads[i],
                                     self.circuit.buses[i].name + '_ct_node_mismatch_' + str(k))

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
        df_v = pd.DataFrame(data=np.c_[abs(self.V), np.angle(self.V), self.V.real, self.V.imag],
                            columns=['Module', 'Angle(rad)', 'Real', 'Imag'],
                            index=['Bus' + str(i) for i in range(self.V.shape[0])])

        # compose branches results
        flows = zeros(self.nbranch)
        loading = zeros(self.nbranch)
        br_names = [None] * self.nbranch
        for k in range(self.nbranch):
            flows[k] = abs(self.flow_ij[k].value()) * self.Sbase
            loading[k] = flows[k] / self.circuit.branches[k].rate * 100.0
            br_names[k] = 'Branch ' + str(k)

        df_f = pd.DataFrame(data=np.c_[flows, loading],
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


if __name__ == '__main__':

    print('Loading...')
    grid = FileOpen('lynn5buspv.xlsx').open()

    # grid.load_file('IEEE30.xlsx')
    # grid.load_file('Illinois200Bus.xlsx')

    grid.compile()

    print('Solving...')
    # declare and solve problem
    problem = AcOPf(grid)
    problem.build()
    problem.set_loads()
    problem.solve()
    problem.print()
