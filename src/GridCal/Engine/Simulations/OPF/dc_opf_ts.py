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

"""
This file implements a DC-OPF for time series
That means that solves the OPF problem for a complete time series at once
"""

from GridCal.ThirdParty.pulp import *
import numpy as np
from itertools import product


def add_objective_function(problem: LpProblem,
                           Pg, Pb, LSlack, FSlack1, FSlack2,
                           cost_g, cost_b, cost_l, cost_br):
    """
    Add the objective function to the problem
    :param problem: LpProblem instance
    :param Pg: generator LpVars (ng, nt)
    :param Pb: batteries LpVars (nb, nt)
    :param LSlack: Load slack LpVars (nl, nt)
    :param FSlack1: Branch overload slack1 (m, nt)
    :param FSlack2: Branch overload slack2 (m, nt)
    :param cost_g: Cost of the generators (ng, nt)
    :param cost_b: Cost of the batteries (nb, nt)
    :param cost_l: Cost of the loss of load (nl, nt)
    :param cost_br: Cost of the overload (m, nt)
    :return: Nothing, just assign the objective function
    """

    f_obj = (cost_g * Pg).sum()

    f_obj += (cost_b * Pb).sum()

    f_obj += (cost_l * LSlack).sum()

    f_obj += (cost_br * (FSlack1 + FSlack2)).sum()

    problem += f_obj


def get_power_injections(C_bus_gen, Pg, C_bus_bat, Pb, C_bus_load, LSlack, Pl):
    """
    Create the power injections per bus
    :param C_bus_gen: Bus-Generators sparse connectivity matrix (n, ng)
    :param Pg: generator LpVars (ng, nt)
    :param C_bus_bat: Bus-Batteries sparse connectivity matrix (n, nb)
    :param Pb: Batteries LpVars (nb, nt)
    :param C_bus_load: Bus-Load sparse connectivity matrix (n, nl)
    :param LSlack: Load slack LpVars (nl, nt)
    :param Pl: Load values (nl, nt)
    :return: Power injection at the buses (n, nt)
    """

    P = lpDot(C_bus_gen.transpose(), Pg)

    P += lpDot(C_bus_bat.transpose(), Pb)

    P -= lpDot(C_bus_load.transpose(), Pl - LSlack)

    return P


def add_nodal_power_balance(numerical_circuit, problem: LpProblem, theta, P, start_, end_):
    """
    Add the nodal power balance
    :param numerical_circuit: NumericalCircuit instance
    :param problem: LpProblem instance
    :param theta: Voltage angles LpVars (n, nt)
    :param P: Power injection at the buses LpVars (n, nt)
    :return: Nothing, the restrictions are added to the problem
    """

    # do the topological computation
    calc_inputs_dict = numerical_circuit.compute_ts()

    # generate the time indices to simulate
    if end_ == -1:
        end_ = len(numerical_circuit.time_array)
    t = np.arange(start_, end_, 1)

    # for each partition of the profiles...
    for t_key, calc_inputs in calc_inputs_dict.items():

        # For every island, run the time series
        for island_index, calculation_input in enumerate(calc_inputs):

            # find the original indices
            bus_original_idx = calculation_input.original_bus_idx
            branch_original_idx = calculation_input.original_branch_idx

            # re-pack the variables for the island and time interval
            P_island = P[bus_original_idx, :][:, t]
            theta_island = theta[bus_original_idx, :][:, t]
            B_island = calculation_input.Ybus[bus_original_idx, :][:, bus_original_idx].imag

            pqpv = calculation_input.pqpv
            vd = calculation_input.ref

            # Add nodal power balance for the non slack nodes
            lpAddRestrictions2(problem=problem,
                               lhs=lpDot(B_island[pqpv, :][:, pqpv], theta_island[pqpv, :]),
                               rhs=P_island[pqpv, :],
                               name='Nodal_power_balance_pqpv',
                               op='=')

            # Add nodal power balance for the slack nodes
            lpAddRestrictions2(problem=problem,
                               lhs=lpDot(B_island[vd, :], theta_island),
                               rhs=P_island[vd, :],
                               name='Nodal_power_balance_vd',
                               op='=')

            # slack angles equal to zero
            lpAddRestrictions2(problem=problem,
                               lhs=theta_island[vd, :],
                               rhs=np.zeros_like(theta_island[vd, :]),
                               name='Theta_vd_zero',
                               op='=')


def add_branch_loading_restriction(problem: LpProblem,
                                   theta_f, theta_t, Bseries,
                                   Fmax, FSlack1, FSlack2):
    """
    Add the branch loading restrictions
    :param problem: LpProblem instance
    :param theta_f: voltage angles at the "from" side of the branches (m, nt)
    :param theta_t: voltage angles at the "to" side of the branches (m, nt)
    :param Bseries: Array of branch susceptances (m)
    :param Fmax: Array of branch ratings (m, nt)
    :param FSlack1: Array of branch loading slack variables in the from-to sense
    :param FSlack2: Array of branch loading slack variables in the to-from sense
    :return: Nothing
    """

    load_f = Bseries * (theta_f - theta_t)
    load_t = Bseries * (theta_t - theta_f)

    # from-to branch power restriction
    lpAddRestrictions2(problem=problem,
                       lhs=load_f,
                       rhs=np.array([Fmax + FSlack1[:, i] for i in range(FSlack1.shape[1])]).transpose(),  # Fmax + FSlack1
                       name='from_to_branch_rate',
                       op='<=')

    # to-from branch power restriction
    lpAddRestrictions2(problem=problem,
                       lhs=load_t,
                       rhs=np.array([Fmax + FSlack2[:, i] for i in range(FSlack2.shape[1])]).transpose(),  # Fmax + FSlack2
                       name='to_from_branch_rate',
                       op='<=')

    return load_f, load_t


def add_battery_discharge_restriction(problem: LpProblem, SoC0, Capacity, Efficiency, Pb, E, dt):
    """
    Add the batteries capacity restrictions
    :param problem: LpProblem instance
    :param SoC0: State of Charge at 0 (nb)
    :param SoCmax: Maximum State of Charge (nb)
    :param SoCmin: Minimum State of Charge (nb)
    :param Capacity: Capacities of the batteries (nb) in MWh/MW base
    :param Efficiency: Roundtrip efficiency
    :param Pb: Batteries injection power LpVars (nb, nt)
    :param E: Batteries Energy state LpVars (nb, nt)
    :param dt: time increments in hours (nt-1)
    :return: Nothing, the restrictions are added to the problem
    """

    # set the initial state of charge
    lpAddRestrictions2(problem=problem,
                       lhs=E[:, 0],
                       rhs=SoC0 * Capacity,
                       name='initial_soc',
                       op='=')

    # compute the inverse of he efficiency because pulp does not divide by floats
    eff_inv = 1 / Efficiency

    # set the Energy values for t=1:nt
    for i in range(len(dt) - 1):

        t = i + 1

        # set the energy value Et = E(t-1) + dt * Pb / eff
        lpAddRestrictions2(problem=problem,
                           lhs=E[:, t],
                           rhs=E[:, t-1] - dt[i] * Pb[:, t] * eff_inv,
                           name='initial_soc_t' + str(t) + '_',
                           op='=')


class OpfAcNonSequentialTimeSeries:

    def __init__(self, grid, start_idx, end_idx):
        """

        :param grid:
        :param start_idx:
        :param end_idx:
        """
        self.grid = grid
        self.start_idx = start_idx
        self.end_idx = end_idx

        self.theta = None
        self.Pg = None
        self.Pb = None
        self.Pl = None
        self.E = None
        self.s_from = None
        self.s_to = None
        self.overloads = None
        self.rating = None
        self.load_shedding = None

        self.problem = self.formulate()

    def formulate(self):
        """
        Formulate the AC OPF time series in the non-sequential fashion (all to the solver at once)
        :return: PuLP Problem instance
        """
        numerical_circuit = self.grid.compile()

        # general indices
        n = numerical_circuit.nbus
        m = numerical_circuit.nbr
        ng = numerical_circuit.n_ctrl_gen
        nb = numerical_circuit.n_batt
        nl = numerical_circuit.n_ld
        nt = self.end_idx - self.start_idx  # numerical_circuit.ntime
        a = self.start_idx
        b = self.end_idx
        Sbase = numerical_circuit.Sbase

        # battery
        Capacity = numerical_circuit.battery_Enom / Sbase
        minSoC = numerical_circuit.battery_min_soc
        maxSoC = numerical_circuit.battery_max_soc
        SoC0 = numerical_circuit.battery_soc_0
        Pb_max = numerical_circuit.battery_pmax / Sbase
        Pb_min = numerical_circuit.battery_pmin / Sbase
        Efficiency = (numerical_circuit.battery_discharge_efficiency + numerical_circuit.battery_charge_efficiency) / 2.0
        cost_b = numerical_circuit.battery_cost_profile[a:b, :].transpose()

        # generator
        Pg_max = numerical_circuit.generator_pmax / Sbase
        Pg_min = numerical_circuit.generator_pmin / Sbase
        cost_g = numerical_circuit.generator_cost_profile[a:b, :].transpose()

        # load
        Pl = (numerical_circuit.load_active_prof[a:b, :] * numerical_circuit.load_power_profile.real[a:b, :]).transpose() / Sbase
        cost_l = numerical_circuit.load_cost_prof[a:b, :].transpose()

        # branch
        branch_ratings = numerical_circuit.br_rates / Sbase
        Bseries = (numerical_circuit.branch_active_prof[a:b, :] * (
                    1 / (numerical_circuit.R + 1j * numerical_circuit.X))).imag.transpose()
        cost_br = numerical_circuit.branch_cost_profile[a:b, :].transpose()

        # Compute time delta in hours
        dt = np.zeros(nt)  # here nt = end_idx - start_idx
        for t in range(1, nt):
            dt[t - 1] = (numerical_circuit.time_array[a + t] - numerical_circuit.time_array[a + t - 1]).seconds / 3600

        # create LP variables
        Pg = lpMakeVars(name='Pg', shape=(ng, nt), lower=Pg_min, upper=Pg_max)
        Pb = lpMakeVars(name='Pb', shape=(nb, nt), lower=Pb_min, upper=Pb_max)
        E = lpMakeVars(name='E', shape=(nb, nt), lower=Capacity * minSoC, upper=Capacity * maxSoC)
        load_slack = lpMakeVars(name='LSlack', shape=(nl, nt), lower=0, upper=None)
        theta = lpMakeVars(name='theta', shape=(n, nt), lower=-3.14, upper=3.14)
        theta_f = theta[numerical_circuit.F, :]
        theta_t = theta[numerical_circuit.T, :]
        branch_rating_slack1 = lpMakeVars(name='FSlack1', shape=(m, nt), lower=0, upper=None)
        branch_rating_slack2 = lpMakeVars(name='FSlack2', shape=(m, nt), lower=0, upper=None)

        # declare problem
        problem = LpProblem(name='DC_OPF_Time_Series')

        # add the objective function
        add_objective_function(problem, Pg, Pb, load_slack, branch_rating_slack1, branch_rating_slack2,
                               cost_g, cost_b, cost_l, cost_br)

        P = get_power_injections(C_bus_gen=numerical_circuit.C_gen_bus,
                                 Pg=Pg,
                                 C_bus_bat=numerical_circuit.C_batt_bus,
                                 Pb=Pb,
                                 C_bus_load=numerical_circuit.C_load_bus,
                                 LSlack=load_slack,
                                 Pl=Pl)

        add_nodal_power_balance(numerical_circuit, problem, theta, P, start_=self.start_idx, end_=self.end_idx)

        load_f, load_t = add_branch_loading_restriction(problem, theta_f, theta_t, Bseries, branch_ratings,
                                                        branch_rating_slack1, branch_rating_slack2)

        # if there are batteries, add the batteries
        if nb > 0:
            add_battery_discharge_restriction(problem, SoC0, Capacity, Efficiency, Pb, E, dt)

        # Assign variables to keep
        # transpose them to be in the format of GridCal: time, device
        self.theta = theta.transpose()
        self.Pg = Pg.transpose()
        self.Pb = Pb.transpose()
        self.Pl = Pl.transpose()
        self.E = E.transpose()
        self.load_shedding = load_slack.transpose()
        self.s_from = load_f.transpose()
        self.s_to = load_t.transpose()
        self.overloads = (branch_rating_slack1 + branch_rating_slack2).transpose()
        self.rating = branch_ratings

        return problem

    def solve(self):
        """
        Call PuLP to solve the problem
        """
        params = PULP_CBC_CMD(fracGap=0.00001, threads=None, msg=1)
        self.problem.solve(params)

        return LpStatus[self.problem.status]

    def extract2D(self, arr, make_abs=False):
        """
        Extract values fro the 2D array of LP variables
        :param arr: 2D array of LP variables
        :param make_abs: substitute the result by its abs value
        :return: 2D numpy array
        """
        val = np.zeros(arr.shape)
        for i, j in product(range(val.shape[0]), range(val.shape[1])):
            val[i, j] = arr[i, j].value()
        if make_abs:
            val = np.abs(val)

        return val

    def get_voltage(self):
        """
        return the complex voltages (time, device)
        :return: 2D array
        """
        angles = self.extract2D(self.theta)
        return np.ones_like(angles) * np.exp(-1j * angles)

    def get_overloads(self):
        """
        return the branch overloads (time, device)
        :return: 2D array
        """
        return self.extract2D(self.overloads)

    def get_loading(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        l = self.extract2D(self.s_from, make_abs=True)
        return l / self.rating

    def get_branch_power(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract2D(self.s_from, make_abs=True) * self.grid.Sbase

    def get_battery_power(self):
        """
        return the battery dispatch (time, device)
        :return: 2D array
        """
        return self.extract2D(self.Pb) * self.grid.Sbase

    def get_battery_energy(self):
        """
        return the battery energy (time, device)
        :return: 2D array
        """
        return self.extract2D(self.E) * self.grid.Sbase

    def get_generator_power(self):
        """
        return the generator dispatch (time, device)
        :return: 2D array
        """
        return self.extract2D(self.Pg) * self.grid.Sbase

    def get_load_shedding(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.extract2D(self.load_shedding) * self.grid.Sbase

    def get_load_power(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.extract2D(self.Pl) * self.grid.Sbase


if __name__ == '__main__':

        from GridCal.Engine.IO.file_handler import FileOpen

        # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
        # fname = r'C:\Users\A487516\Documents\GitHub\GridCal\Grids_and_profiles\grids\Lynn 5 Bus pv.gridcal'
        # fname = r'C:\Users\A487516\Documents\GitHub\GridCal\Grids_and_profiles\grids\IEEE39_1W.gridcal'
        fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
        main_circuit = FileOpen(fname).open()

        problem = OpfAcNonSequentialTimeSeries(grid=main_circuit, start_idx=0, end_idx=5*24)

        print('Solving...')
        status = problem.solve()

        # print("Status:", status)

        v = problem.get_voltage()
        print('Angles\n', np.angle(v))

        l = problem.get_loading()
        print('Branch loading\n', l)

        g = problem.get_generator_power()
        print('Gen power\n', g)

        pass
