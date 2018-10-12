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
from scipy.sparse import csc_matrix, hstack as hstack_s, vstack as vstack_s

from GridCal.Engine.BasicStructures import BusMode
from GridCal.Engine.PowerFlowDriver import PowerFlowMP
from GridCal.Engine.IoStructures import CalculationInputs, OptimalPowerFlowResults
from GridCal.Engine.Numerical.DC_OPF import Cproduct
from GridCal.Engine.CalculationEngine import MultiCircuit


class AcOpf_old:

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


class AcOpfIsland:

    def __init__(self, nbus, nbr, b_idx):
        """
        Intermediate object to store a DC OPF problem
        :param nbus: Number of buses
        :param nbr: Number of branches
        :param b_idx: Buses indices in the original grid
        """

        # number of nodes
        self.nbus = nbus

        # number of branches
        self.nbr = nbr

        # LP problem instance
        self.problem = pulp.LpProblem("AC optimal power flow", pulp.LpMinimize)

        # calculated node power
        self.calculated_power = np.zeros(nbus, dtype=object)

        # injection power
        self.P = np.zeros(nbus, dtype=object)

        # branch flow
        self.flow = np.zeros(nbr, dtype=object)

        # original bus indices
        self.b_idx = b_idx

    def copy(self):

        obj = AcOpfIsland(self.nbus, self.nbr, self.b_idx)

        obj.problem = self.problem.copy()

        obj.P = self.P.copy()

        obj.flow = self.flow.copy()

        obj.calculated_power = self.calculated_power

        return obj


class AcOpf:

    def __init__(self, multi_circuit: MultiCircuit, verbose=False,
                 allow_load_shedding=False, allow_generation_shedding=False,
                 load_shedding_weight=10000, generation_shedding_weight=10000):
        """
        DC OPF problem
        :param multi_circuit: multi circuit instance
        :param verbose: verbose?
        :param allow_load_shedding: Allow load shedding?
        :param allow_generation_shedding: Allow generation shedding?
        :param load_shedding_weight: weight for the load shedding at the objective function
        :param generation_shedding_weight: weight for the generation shedding at the objective function
        """

        # list of OP object islands
        self.opf_islands = list()

        # list of opf islands to solve apart (this allows to split the problem and only assign loads on a series)
        self.opf_islands_to_solve = list()

        # flags
        self.verbose = verbose
        self.allow_load_shedding = allow_load_shedding
        self.allow_generation_shedding = allow_generation_shedding

        self.generation_shedding_weight = generation_shedding_weight
        self.load_shedding_weight = load_shedding_weight

        # circuit compilation
        self.multi_circuit = multi_circuit
        self.numerical_circuit = self.multi_circuit.compile()
        self.islands = self.numerical_circuit.compute()

        # compile the indices
        # indices of generators that contribute to the static power vector 'S'
        self.gen_s_idx = np.where((np.logical_not(self.numerical_circuit.controlled_gen_dispatchable)
                                   * self.numerical_circuit.controlled_gen_enabled) == True)[0]

        self.bat_s_idx = np.where((np.logical_not(self.numerical_circuit.battery_dispatchable)
                                   * self.numerical_circuit.battery_enabled) == True)[0]

        # indices of generators that are to be optimized via the solution vector 'x'
        self.gen_x_idx = np.where((self.numerical_circuit.controlled_gen_dispatchable
                                   * self.numerical_circuit.controlled_gen_enabled) == True)[0]

        self.bat_x_idx = np.where((self.numerical_circuit.battery_dispatchable
                                   * self.numerical_circuit.battery_enabled) == True)[0]

        # get the devices
        self.controlled_generators = self.multi_circuit.get_controlled_generators()
        self.batteries = self.multi_circuit.get_batteries()
        self.loads = self.multi_circuit.get_loads()

        # shortcuts...
        nbus = self.numerical_circuit.nbus
        nbr = self.numerical_circuit.nbr
        ngen = len(self.controlled_generators)
        nbat = len(self.batteries)
        Sbase = self.multi_circuit.Sbase

        # bus angles and modules
        self.dVa = np.array([pulp.LpVariable("dVa_" + str(i), -0.5, 0.5) for i in range(nbus)])
        self.dVm = np.array([pulp.LpVariable("dVm_" + str(i),
                                             self.numerical_circuit.Vmin[i] - 1,
                                             self.numerical_circuit.Vmax[i] - 1) for i in range(nbus)])
        self.Vm = np.array([pulp.LpVariable("Vm_" + str(i),
                                            self.numerical_circuit.Vmin[i],
                                            self.numerical_circuit.Vmax[i]) for i in range(nbus)])

        # Generator variables (P and P shedding)
        self.controlled_generators_P = np.empty(ngen, dtype=object)
        self.controlled_generators_cost = np.zeros(ngen)
        self.generation_shedding = np.empty(ngen, dtype=object)
        for i, gen in enumerate(self.controlled_generators):
            name = 'GEN_' + gen.name + '_' + str(i)
            pmin = gen.Pmin / Sbase
            pmax = gen.Pmax / Sbase
            self.controlled_generators_P[i] = pulp.LpVariable(name + '_P',  pmin, pmax)
            self.generation_shedding[i] = pulp.LpVariable(name + '_SHEDDING', 0.0, 1e20)
            self.controlled_generators_cost[i] = gen.Cost

        # Batteries
        self.battery_P = np.empty(nbat, dtype=object)
        self.battery_cost = np.zeros(nbat)
        self.battery_lower_bound = np.zeros(nbat)
        for i, battery in enumerate(self.batteries):
            name = 'BAT_' + battery.name + '_' + str(i)
            pmin = battery.Pmin / Sbase
            pmax = battery.Pmax / Sbase
            self.battery_lower_bound[i] = pmin
            self.battery_P[i] = pulp.LpVariable(name + '_P', pmin, pmax)
            self.battery_cost[i] = battery.Cost

        # load shedding
        self.load_shedding = np.array([pulp.LpVariable("LoadShed_" + load.name + '_' + str(i), 0.0, 1e20)
                                       for i, load in enumerate(self.loads)])

        # declare the loading slack vars
        self.slack_loading_ij_p = np.empty(nbr, dtype=object)
        self.slack_loading_ji_p = np.empty(nbr, dtype=object)
        self.slack_loading_ij_n = np.empty(nbr, dtype=object)
        self.slack_loading_ji_n = np.empty(nbr, dtype=object)
        for i in range(nbr):
            self.slack_loading_ij_p[i] = pulp.LpVariable("LoadingSlack_ij_p_" + str(i), 0, 1e20)
            self.slack_loading_ji_p[i] = pulp.LpVariable("LoadingSlack_ji_p_" + str(i), 0, 1e20)
            self.slack_loading_ij_n[i] = pulp.LpVariable("LoadingSlack_ij_n_" + str(i), 0, 1e20)
            self.slack_loading_ji_n[i] = pulp.LpVariable("LoadingSlack_ji_n_" + str(i), 0, 1e20)

        self.branch_flows_ij = np.empty(nbr, dtype=object)
        self.branch_flows_ji = np.empty(nbr, dtype=object)

        self.converged = True

    def build_solvers(self):
        """
        Builds the solvers for each island
        :return:
        """

        # Sbase shortcut
        Sbase = self.numerical_circuit.Sbase

        # objective contributions of generators
        fobj_gen = Cproduct(csc_matrix(self.numerical_circuit.C_ctrl_gen_bus), self.controlled_generators_P * self.controlled_generators_cost)

        # objective contribution of the batteries
        fobj_bat = Cproduct(csc_matrix(self.numerical_circuit.C_batt_bus), self.battery_P * self.battery_cost)

        # LP variables for the controlled generators
        P = Cproduct(csc_matrix(self.numerical_circuit.C_ctrl_gen_bus[self.gen_x_idx, :]),
                     self.controlled_generators_P[self.gen_x_idx])

        # LP variables for the batteries
        P += Cproduct(csc_matrix(self.numerical_circuit.C_batt_bus[self.bat_x_idx, :]),
                      self.battery_P[self.bat_x_idx])

        if self.allow_load_shedding:
            load_shedding_per_bus = Cproduct(csc_matrix(self.numerical_circuit.C_load_bus), self.load_shedding)
            P += load_shedding_per_bus
        else:
            load_shedding_per_bus = np.zeros(self.numerical_circuit.nbus)

        if self.allow_generation_shedding:
            # the shedding variables go in opposite sense
            generation_shedding_per_bus = Cproduct(csc_matrix(self.numerical_circuit.C_ctrl_gen_bus),
                                                   self.generation_shedding)
            P -= generation_shedding_per_bus
        else:
            generation_shedding_per_bus = np.zeros(self.numerical_circuit.nbus)

        # angles and branch susceptances
        theta_f = Cproduct(csc_matrix(self.numerical_circuit.C_branch_bus_f.T), self.dVa)
        theta_t = Cproduct(csc_matrix(self.numerical_circuit.C_branch_bus_t.T), self.dVa)
        Btotal = self.numerical_circuit.get_B()
        B_br = np.ravel(Btotal[self.numerical_circuit.F, self.numerical_circuit.T]).T
        self.branch_flows_ij = B_br * (theta_f - theta_t)
        self.branch_flows_ji = B_br * (theta_t - theta_f)

        for island in self.islands:

            # indices shortcuts
            b_idx = island.original_bus_idx
            br_idx = island.original_branch_idx

            # declare an island to store the "open" formulation
            island_problem = AcOpfIsland(island.nbus, island.nbr, b_idx)

            # set the opf island power
            island_problem.P = P[b_idx]

            # Objective function
            fobj = fobj_gen[b_idx].sum() + fobj_bat[b_idx].sum()

            if self.allow_load_shedding:
                fobj += load_shedding_per_bus[b_idx].sum() * self.load_shedding_weight

            if self.allow_generation_shedding:
                fobj += generation_shedding_per_bus[b_idx].sum() * self.generation_shedding_weight

            fobj += self.slack_loading_ij_p[br_idx].sum() - self.slack_loading_ij_n[br_idx].sum()
            fobj += self.slack_loading_ji_p[br_idx].sum() - self.slack_loading_ji_n[br_idx].sum()

            island_problem.problem += fobj

            # get the susceptance matrix
            B = island.Ybus.imag

            # get the system matrix
            Asys, A_slack = island.build_linear_ac_sys_mat()

            # compose the vector x = [dtheta|dVm]
            npqpv = len(island.pqpv)
            npq = len(island.pq)
            nref = len(island.ref)
            x = np.empty(npqpv + npq + nref, dtype=object)
            x[0:npqpv] = self.dVa[island.pqpv]
            x[npqpv:npqpv+npq] = self.dVm[island.pq]
            x[npqpv + npq: npqpv + npq + nref] = self.dVm[island.ref]

            # linear system product Asys x X
            island_problem.calculated_power = np.zeros(npqpv + npq + nref, dtype=object)
            island_problem.calculated_power[0:npqpv+npq] = Cproduct(Asys, x[0:npqpv+npq])
            island_problem.calculated_power[npqpv + npq: npqpv + npq + nref] = Cproduct(A_slack.T, x[0:npqpv+npq])

            # rating restrictions -> Bij * (theta_i - theta_j), for the island branches
            branch_flow_ft = self.branch_flows_ij[br_idx]
            branch_flow_tf = self.branch_flows_ji[br_idx]

            # modify the flow restrictions to allow overloading but penalizing it
            branch_flow_ft += self.slack_loading_ij_p[br_idx] - self.slack_loading_ij_n[br_idx]
            branch_flow_tf += self.slack_loading_ji_p[br_idx] - self.slack_loading_ji_n[br_idx]

            # add the rating restrictions to the problem
            for i in range(island.nbr):
                name1 = 'ct_br_flow_ji_' + str(i)
                name2 = 'ct_br_flow_ij_' + str(i)
                island_problem.problem.addConstraint(branch_flow_ft[i] <= island.branch_rates[i] / Sbase, name2)
                island_problem.problem.addConstraint(branch_flow_tf[i] <= island.branch_rates[i] / Sbase, name1)

            # set the slack angles to zero and the voltage module to the absolute
            for i in island.ref:
                island_problem.problem.addConstraint(self.dVa[i] == 0)
                island_problem.problem.addConstraint(self.Vm[i] == abs(self.numerical_circuit.V0[i]))
            #
            for i in island.pq:
                island_problem.problem.addConstraint(self.Vm[i] == 1 + self.dVm[i])

            # set the voltage magnitude to the set voltage in the PV nodes
            for i in island.pv:
                island_problem.problem.addConstraint(self.Vm[i] == abs(self.numerical_circuit.V0[i]))

            # store the problem to extend it later
            self.opf_islands.append(island_problem)

    def set_state(self, load_power, static_gen_power, controlled_gen_power,
                  Emin=None, Emax=None, E=None, dt=0,
                  force_batteries_to_charge=False, bat_idx=None, battery_loading_pu=0.01):
        """
        Set the current state
        :param load_power: vector of load power (same size as the number of loads)
        :param static_gen_power: vector of static generators load (same size as the static gen objects)
        :param controlled_gen_power: vector of controlled generators power (same size as the ctrl. generatos)
        :param force_batteries_to_charge: shall we force batteries to charge?
        :param bat_idx: battery indices that shall be forced to charge
        :param battery_loading_pu: amount of the changing band to force to charge
        """
        # Sbase shortcut
        Sbase = self.numerical_circuit.Sbase

        # Loads for all the circuits
        S = - self.numerical_circuit.C_load_bus.T * (load_power / Sbase * self.numerical_circuit.load_enabled)

        # static generators for all the circuits
        S += self.numerical_circuit.C_sta_gen_bus.T * (static_gen_power / Sbase *
                                                       self.numerical_circuit.static_gen_enabled)

        # decompose in real and imaginary
        P = S.real
        Q = S.imag

        # controlled generators for all the circuits (enabled and not dispatcheable)
        P += (self.numerical_circuit.C_ctrl_gen_bus[self.gen_s_idx, :]).T * \
             (controlled_gen_power[self.gen_s_idx] / Sbase)

        # storage params per bus
        if E is not None:
            E_bus = self.numerical_circuit.C_batt_bus.T * E
            Emin_bus = self.numerical_circuit.C_batt_bus.T * Emin
            Emax_bus = self.numerical_circuit.C_batt_bus.T * Emax
            batteries_at_each_bus_all = Cproduct(csc_matrix(self.numerical_circuit.C_batt_bus), self.battery_P)

        if force_batteries_to_charge:
            batteries_at_each_bus = Cproduct(csc_matrix(self.numerical_circuit.C_batt_bus[bat_idx, :]),
                                             self.battery_P[bat_idx])

            battery_charge_amount_per_bus = Cproduct(csc_matrix(self.numerical_circuit.C_batt_bus[bat_idx, :]),
                                                     self.battery_lower_bound * battery_loading_pu)

        else:
            batteries_at_each_bus = None
            battery_charge_amount_per_bus = None

        # set the power at each island
        self.opf_islands_to_solve = list()
        for k, island_problem in enumerate(self.opf_islands):

            # perform a copy of the island
            island_copy = island_problem.copy()

            # modify the power injections at the island nodes
            island_copy.P += P[island_copy.b_idx]

            # set all the power balance restrictions -> (Calculated power == injections power)
            npqpv = len(self.islands[k].pqpv)
            npq = len(self.islands[k].pq)
            nref = len(self.islands[k].ref)
            for i in range(npqpv):
                name = 'ct_node_mismatch_P_' + str(i)
                j = self.islands[k].pqpv[i]
                island_copy.problem.addConstraint(island_copy.calculated_power[i] == island_copy.P[j], name)

            for i in range(npqpv, npqpv+npq):
                name = 'ct_node_mismatch_Q_' + str(i)
                j = self.islands[k].pq[i-npqpv]
                island_copy.problem.addConstraint(island_copy.calculated_power[i] == Q[j], name)

            for i in range(npqpv+npq, npqpv+npq+nref):
                name = 'ct_node_mismatch_P_' + str(i)
                j = self.islands[k].ref[i-npqpv-npq]
                island_copy.problem.addConstraint(island_copy.calculated_power[i] == P[j], name)

                # Set storage energy limits (always)
                if E is not None:
                    E_bus_is = E_bus[island_copy.b_idx]
                    Emin_bus_is = Emin_bus[island_copy.b_idx]
                    Emax_bus_is = Emax_bus[island_copy.b_idx]
                    for i, bat_P in enumerate(batteries_at_each_bus_all):
                        if bat_P != 0:
                            # control the energy
                            island_copy.problem.addConstraint(E_bus_is[i] - bat_P * dt >= Emin_bus_is[i])
                            island_copy.problem.addConstraint(E_bus_is[i] - bat_P * dt <= Emax_bus_is[i])

                if force_batteries_to_charge:
                    # re-pack the restrictions for the island
                    battery_at_each_bus_island = batteries_at_each_bus[island_copy.b_idx]
                    # Assign the restrictions
                    for i, bat_P in enumerate(battery_at_each_bus_island):
                        if bat_P != 0:
                            # force the battery to charge
                            island_copy.problem.addConstraint(bat_P <= battery_charge_amount_per_bus[i])
            # store the island copy
            self.opf_islands_to_solve.append(island_copy)

    def set_default_state(self):
        """
        Set the default loading state
        """
        self.set_state(load_power=self.numerical_circuit.load_power,
                       static_gen_power=self.numerical_circuit.static_gen_power,
                       controlled_gen_power=self.numerical_circuit.controlled_gen_power)

    def set_state_at(self, t, force_batteries_to_charge=False, bat_idx=None, battery_loading_pu=0.01,
                     Emin=None, Emax=None, E=None, dt=0):
        """
        Set the problem state at at time index
        :param t: time index
        """
        self.set_state(load_power=self.numerical_circuit.load_power_profile[t, :],
                       static_gen_power=self.numerical_circuit.static_gen_power_profile[t, :],
                       controlled_gen_power=self.numerical_circuit.controlled_gen_power_profile[t, :],
                       Emin=Emin, Emax=Emax, E=E, dt=dt,
                       force_batteries_to_charge=force_batteries_to_charge,
                       bat_idx=bat_idx,
                       battery_loading_pu=battery_loading_pu)

    def solve(self, verbose=False):
        """
        Solve all islands (the results remain in the variables...)
        """
        self.converged = True
        for island_problem in self.opf_islands_to_solve:

            # solve island
            island_problem.problem.solve()

            if island_problem.problem.status == -1:
                self.converged = False

            if verbose:
                print("Status:", pulp.LpStatus[island_problem.problem.status])

                # The optimised objective function value is printed to the screen
                print("Cost =", pulp.value(island_problem.problem.objective), '€')

        if verbose:
            if self.allow_load_shedding:
                val = pulp.value(self.load_shedding.sum())
                print('Load shed:', val)

            if self.allow_generation_shedding:
                val = pulp.value(self.generation_shedding.sum())
                print('Generation shed:', val)

            val = pulp.value(self.slack_loading_ij_p.sum())
            val += pulp.value(self.slack_loading_ji_p.sum())
            val += pulp.value(self.slack_loading_ij_n.sum())
            val += pulp.value(self.slack_loading_ji_n.sum())
            print('Overloading:', val)

            print('Batteries power:', self.get_batteries_power().sum())

    def save(self):
        """
        Save all the problem instances
        """
        for i, island_problem in enumerate(self.opf_islands_to_solve):
            island_problem.problem.writeLP('dc_opf_island_' + str(i) + '.lp')

    def get_voltage(self):
        """
        Get the complex voltage composition from the LP angles solution
        """
        Va = np.array([elm.value() for elm in self.dVa])
        Vm = np.array([elm.value() for elm in self.Vm])
        return Vm * np.exp(1j * Va)

    def get_branch_flows(self):
        """
        Return the DC branch flows
        :return: numpy array
        """
        return np.array([pulp.value(eq) for eq in self.branch_flows_ij])

    def get_overloads(self):
        """
        get the overloads into an array
        """
        return np.array([a.value() + b.value() + c.value() + d.value() for a, b, c, d in
                         zip(self.slack_loading_ij_p, self.slack_loading_ji_p,
                             self.slack_loading_ij_n, self.slack_loading_ji_n)])

    def get_batteries_power(self):
        """
        Get array of battery dispatched power
        """
        return np.array([elm.value() for elm in self.battery_P])

    def get_controlled_generation(self):
        """
        Get array of controlled generators power
        """
        return np.array([elm.value() for elm in self.controlled_generators_P])

    def get_load_shedding(self):
        """
        Load shedding array
        """
        return np.array([elm.value() for elm in self.load_shedding])

    def get_generation_shedding(self):
        """
        Load shedding array
        """
        return np.array([elm.value() for elm in self.generation_shedding])

    def get_gen_results_df(self):
        """
        Get the generation values DataFrame
        """
        # Sbase shortcut
        Sbase = self.numerical_circuit.Sbase

        data = [elm.value() * Sbase for elm in np.r_[self.controlled_generators_P, self.battery_P]]
        index = [elm.name for elm in (self.controlled_generators + self.batteries)]

        df = pd.DataFrame(data=data, index=index, columns=['Power (MW)'])

        return df

    def get_voltage_results_df(self):
        """
        Get the voltage angles DataFrame
        """
        Va = np.array([elm.value() for elm in self.dVa])
        Vm = np.array([elm.value() for elm in self.Vm])
        data = np.c_[Vm, Va]

        df = pd.DataFrame(data=data, index=self.numerical_circuit.bus_names, columns=['Module p.u.', 'Angles (deg)'])

        return df

    def get_branch_flows_df(self):
        """
        Get hte DC branch flows DataFrame
        """
        # Sbase shortcut
        Sbase = self.numerical_circuit.Sbase

        data = self.get_branch_flows() * Sbase

        df = pd.DataFrame(data=data, index=self.numerical_circuit.branch_names, columns=['Branch flow (MW)'])

        return df

    def get_loading(self):
        Sbase = self.numerical_circuit.Sbase
        data = self.get_branch_flows() * Sbase
        loading = data / self.numerical_circuit.br_rates

        return loading


if __name__ == '__main__':

    main_circuit = MultiCircuit()
    # fname = 'D:\\GitHub\\GridCal\\Grids_and_profiles\\grids\\lynn5buspv.xlsx'
    fname = 'D:\\GitHub\\GridCal\\Grids_and_profiles\\grids\\IEEE 30 Bus with storage.xlsx'
    # fname = 'C:\\Users\\spenate\\Documents\\PROYECTOS\\Sensible\\Report\\Test3 - Batteries\\Evora test 3 with storage.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 30 Bus with storage.xlsx'

    print('Reading...')
    main_circuit.load_file(fname)

    problem = AcOpf(main_circuit, allow_load_shedding=True, allow_generation_shedding=True)

    # run default state
    problem.build_solvers()
    problem.set_default_state()
    problem.solve(verbose=True)
    problem.save()

    print('\nResults:\n')
    res_df = problem.get_gen_results_df()
    print(res_df)

    res_df = problem.get_voltage_results_df()
    print(res_df)

    res_df = problem.get_branch_flows_df()
    print(res_df)

    # run time series
    for t in range(len(main_circuit.time_profile)):
        print(t)
        problem.set_state_at(t, force_batteries_to_charge=True, bat_idx=[], battery_loading_pu=0.01)
        problem.solve(verbose=True)
