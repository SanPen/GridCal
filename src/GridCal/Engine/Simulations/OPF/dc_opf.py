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
import pulp
import numpy as np
from scipy.sparse import csc_matrix
import pandas as pd
from GridCal.Engine.Core.multi_circuit import MultiCircuit


def Cproduct(C, vect):
    """
    Connectivity matrix-vector product
    :param C: Connectivity matrix
    :param vect: vector of object type
    :return:
    """
    n_rows, n_cols = C.shape
    res = np.zeros(n_cols, dtype=object)
    for i in range(n_cols):
        # compute the slack node power
        for ii in range(C.indptr[i], C.indptr[i + 1]):
            j = C.indices[ii]
            res[i] += C.data[ii] * vect[j]
    return res


class DcOpfIsland:

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
        self.problem = pulp.LpProblem("DC optimal power flow", pulp.LpMinimize)

        # calculated node power
        self.calculated_power = np.zeros(nbus, dtype=object)

        # injection power
        self.P = np.zeros(nbus, dtype=object)

        # branch flow
        self.flow = np.zeros(nbr, dtype=object)

        # original bus indices
        self.b_idx = b_idx

    def copy(self):

        obj = DcOpfIsland(self.nbus, self.nbr, self.b_idx)

        obj.problem = self.problem.copy()

        obj.P = self.P.copy()

        obj.flow = self.flow.copy()

        obj.calculated_power = self.calculated_power

        return obj


class DcOpf:

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
        self.gen_s_idx = np.where((np.logical_not(self.numerical_circuit.generator_dispatchable)
                                   * self.numerical_circuit.generator_active) == True)[0]

        self.bat_s_idx = np.where((np.logical_not(self.numerical_circuit.battery_dispatchable)
                                   * self.numerical_circuit.battery_active) == True)[0]

        # indices of generators that are to be optimized via the solution vector 'x'
        self.gen_x_idx = np.where((self.numerical_circuit.generator_dispatchable
                                   * self.numerical_circuit.generator_active) == True)[0]

        self.bat_x_idx = np.where((self.numerical_circuit.battery_dispatchable
                                   * self.numerical_circuit.battery_active) == True)[0]

        # get the devices
        self.controlled_generators = self.multi_circuit.get_generators()
        self.batteries = self.multi_circuit.get_batteries()
        self.loads = self.multi_circuit.get_loads()

        # shortcuts...
        nbus = self.numerical_circuit.nbus
        nbr = self.numerical_circuit.nbr
        ngen = len(self.controlled_generators)
        nbat = len(self.batteries)
        Sbase = self.multi_circuit.Sbase

        # bus angles
        self.theta = np.array([pulp.LpVariable("Theta_" + str(i), -0.5, 0.5) for i in range(nbus)])

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
        self.numerical_circuit.C_batt_bus = csc_matrix(self.numerical_circuit.C_batt_bus)
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

        self.converged = False

    def build_solvers(self):
        """
        Builds the solvers for each island
        :return:
        """

        # Sbase shortcut
        Sbase = self.numerical_circuit.Sbase

        # objective contributions of generators
        fobj_gen = Cproduct(csc_matrix(self.numerical_circuit.C_gen_bus),
                            self.controlled_generators_P * self.controlled_generators_cost)

        # objective contribution of the batteries
        fobj_bat = Cproduct(csc_matrix(self.numerical_circuit.C_batt_bus),
                            self.battery_P * self.battery_cost)

        # LP variables for the controlled generators
        P = Cproduct(csc_matrix(self.numerical_circuit.C_gen_bus[self.gen_x_idx, :]),
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
            generation_shedding_per_bus = Cproduct(csc_matrix(self.numerical_circuit.C_gen_bus),
                                                   self.generation_shedding)
            P -= generation_shedding_per_bus
        else:
            generation_shedding_per_bus = np.zeros(self.numerical_circuit.nbus)

        # angles and branch susceptances
        theta_f = Cproduct(csc_matrix(self.numerical_circuit.C_branch_bus_f.T), self.theta)
        theta_t = Cproduct(csc_matrix(self.numerical_circuit.C_branch_bus_t.T), self.theta)
        Btotal = self.numerical_circuit.get_B()
        B_br = np.ravel(Btotal[self.numerical_circuit.F, self.numerical_circuit.T]).T
        self.branch_flows_ij = B_br * (theta_f - theta_t)
        self.branch_flows_ji = B_br * (theta_t - theta_f)

        for island in self.islands:

            # indices shortcuts
            b_idx = island.original_bus_idx
            br_idx = island.original_branch_idx

            # declare an island to store the "open" formulation
            island_problem = DcOpfIsland(island.nbus, island.nbr, b_idx)

            # set the opf island power
            island_problem.P = P[b_idx]

            # Objective function
            fobj = fobj_gen[b_idx].sum() + fobj_bat[b_idx].sum()

            if self.allow_load_shedding:
                fobj += load_shedding_per_bus[b_idx].sum() * self.load_shedding_weight

            if self.allow_generation_shedding:
                fobj += generation_shedding_per_bus[b_idx].sum() * self.generation_shedding_weight

            fobj += self.slack_loading_ij_p[br_idx].sum() + self.slack_loading_ij_n[br_idx].sum()
            fobj += self.slack_loading_ji_p[br_idx].sum() + self.slack_loading_ji_n[br_idx].sum()

            island_problem.problem += fobj

            # susceptance matrix
            B = island.Ybus.imag

            # calculated power at the non-slack nodes
            island_problem.calculated_power[island.pqpv] = Cproduct(B[island.pqpv, :][:, island.pqpv].T,
                                                                    self.theta[island.pqpv])

            # calculated power at the slack nodes
            island_problem.calculated_power[island.ref] = Cproduct(B[:, island.ref], self.theta)

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

            # set the slack angles to zero
            for i in island.ref:
                island_problem.problem.addConstraint(self.theta[i] == 0)

            # store the problem to extend it later
            self.opf_islands.append(island_problem)

    def set_state(self, load_power, static_gen_power, generator_power,
                  Emin=None, Emax=None, E=None, dt=0,
                  force_batteries_to_charge=False, bat_idx=None, battery_loading_pu=0.01):
        """
        Set the loading and batteries state
        :param load_power: vector of load power (same size as the number of loads)
        :param static_gen_power: vector of static generators load (same size as the static gen objects)
        :param generator_power: vector of controlled generators power (same size as the ctrl. generators)
        :param Emin: Minimum energy per battery in MWh / Sbase -> 1/h
        :param Emax: Maximum energy per battery in MWh / Sbase -> 1/h
        :param E: Current energy charge in MWh / Sbase -> 1/h
        :param dt: time step in hours
        :param force_batteries_to_charge: shall we force batteries to charge?
        :param bat_idx: battery indices that shall be forced to charge
        :param battery_loading_pu: amount of the nominal band to charge to use (0.1=10%)
        """
        # Sbase shortcut
        Sbase = self.numerical_circuit.Sbase

        # Loads for all the circuits
        P = - self.numerical_circuit.C_load_bus.T * (load_power.real / Sbase * self.numerical_circuit.load_active)

        # static generators for all the circuits
        P += self.numerical_circuit.C_sta_gen_bus.T * (static_gen_power.real / Sbase *
                                                       self.numerical_circuit.static_gen_active)

        # controlled generators for all the circuits (enabled and not dispatchable)
        P += (self.numerical_circuit.C_gen_bus[self.gen_s_idx, :]).T * \
             (generator_power[self.gen_s_idx] / Sbase)

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
            for i in range(island_copy.nbus):
                name = 'ct_node_mismatch_' + str(i)
                island_copy.problem.addConstraint(island_copy.calculated_power[i] == island_copy.P[i], name)

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
                       generator_power=self.numerical_circuit.generator_power)

    def set_state_at(self, t, force_batteries_to_charge=False, bat_idx=None, battery_loading_pu=0.01,
                     Emin=None, Emax=None, E=None, dt=0):
        """
        Set the problem state at at time index
        :param t: time index
        """
        self.set_state(load_power=self.numerical_circuit.load_power_profile[t, :],
                       static_gen_power=self.numerical_circuit.static_gen_power_profile[t, :],
                       generator_power=self.numerical_circuit.generator_power_profile[t, :],
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
                print("Status:", pulp.LpStatus[island_problem.problem.status], island_problem.problem.status)

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
        Va = np.array([elm.value() for elm in self.theta])
        Vm = np.abs(self.numerical_circuit.V0)
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
        data = [elm.value() for elm in self.theta]

        df = pd.DataFrame(data=data, index=self.numerical_circuit.bus_names, columns=['Angles (deg)'])

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

    problem = DcOpf(main_circuit, allow_load_shedding=True, allow_generation_shedding=True)

    # run default state
    problem.build_solvers()
    problem.set_default_state()
    problem.solve(verbose=True)
    problem.save()

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
