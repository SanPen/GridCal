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

from pulp import *
import numpy as np

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.OPF.pulp_extra import lpDot, make_vars, lpAddRestrictions2


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

    P = lpDot(C_bus_gen, Pg)

    P += lpDot(C_bus_bat, Pb)

    P -= lpDot(C_bus_load, LSlack + Pl)

    return P


def add_nodal_power_balance(problem: LpProblem, B, theta, P, pqpv, vd):
    """
    Add the nodal power balance
    :param problem: LpProblem instance
    :param B: Susceptance matrix (n, n)
    :param theta: Voltage angles LpVars (n, nt)
    :param P: Power injection at the buses LpVars (n, nt)
    :param pqpv: list of indices of the pq and pv nodes
    :param vd: list of indices of the slack nodes
    :return: Nothing, the restrictions are added to the problem
    """

    # Nodal power balance for the non slack nodes
    lpAddRestrictions2(problem=problem,
                       lhs=lpDot(B[pqpv, :][:, pqpv], theta[pqpv, :]),
                       rhs=P[pqpv, :],
                       name='Nodal_power_balance_pqpv',
                       op='=')

    # nodal power balance for the slack nodes
    lpAddRestrictions2(problem=problem,
                       lhs=lpDot(B[vd, :], theta),
                       rhs=P[vd, :],
                       name='Nodal_power_balance_vd',
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

    # from-to branch power restriction
    lpAddRestrictions2(problem=problem,
                       lhs=lpDot(Bseries, (theta_f - theta_t)),
                       rhs=Fmax + FSlack1,
                       name='from_to_branch_rate',
                       op='<=')

    # to-from branch power restriction
    lpAddRestrictions2(problem=problem,
                       lhs=lpDot(Bseries, (theta_t - theta_f)),
                       rhs=Fmax + FSlack2,
                       name='to_from_branch_rate',
                       op='<=')

    # lpAddRestrictions2(problem=problem,
    #                    lhs=FSlack1,
    #                    rhs=FSlack2,
    #                    name='rate_slack_eq',
    #                    op='<=')


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
    for i in range(len(dt)):

        t = i + 1

        # set the energy value Et = E(t-1) + dt * Pb / eff
        lpAddRestrictions2(problem=problem,
                           lhs=E[:, t],
                           rhs=E[:, t-1] - dt[i] * Pb[:, t] * eff_inv,
                           name='initial_soc',
                           op='=')


def solve_opf_ts(grid: MultiCircuit):

    numerical_circuit = grid.compile()
    islands = numerical_circuit.compute()

    # general indices
    n = numerical_circuit.nbus
    m = numerical_circuit.nbr
    ng = numerical_circuit.n_ctrl_gen
    nb = numerical_circuit.n_batt
    nl = numerical_circuit.n_ld
    nt = numerical_circuit.ntime
    Sbase = numerical_circuit.Sbase

    # battery
    Capacity = numerical_circuit.battery_Enom / Sbase
    minSoC = numerical_circuit.battery_min_soc
    maxSoC = numerical_circuit.battery_max_soc
    SoC0 = numerical_circuit.battery_soc_0
    Pb_max = numerical_circuit.battery_pmax / Sbase
    Pb_min = numerical_circuit.battery_pmin / Sbase
    Efficiency = (numerical_circuit.battery_discharge_efficiency + numerical_circuit.battery_charge_efficiency) / 2.0

    # generator
    Pg_max = numerical_circuit.generator_pmax
    Pg_min = numerical_circuit.generator_pmin

    # load
    Pl = (numerical_circuit.load_active_prof * numerical_circuit.load_power_profile).transpose() / Sbase

    # branch
    Fmax = numerical_circuit.br_rates / Sbase
    Bseries = numerical_circuit.branch_active_prof * (1 / (numerical_circuit.R + 1j * numerical_circuit.X))

    # time
    dt = np.zeros(nt)
    for t in range(1, nt):
        # time delta in hours
        dt[t-1] = (numerical_circuit.time_array[t] - numerical_circuit.time_array[t-1]).seconds / 3600

    # create LP variables
    Pg = make_vars(name='Pg', shape=(ng, nt), Lb=Pg_min, Ub=Pg_max)
    Pb = make_vars(name='Pb', shape=(nb, nt), Lb=Pb_min, Ub=Pb_max)
    E = make_vars(name='E', shape=(nb, nt), Lb=Capacity * minSoC, Ub=Capacity * maxSoC)
    LSlack = make_vars(name='LSlack', shape=(nl, nt), Lb=0, Ub=None)
    theta = make_vars(name='theta', shape=(n, nt), Lb=-0.5, Ub=0.5)
    theta_f = theta[numerical_circuit.F, :]
    theta_t = theta[numerical_circuit.T, :]
    FSlack1 = make_vars(name='FSlack1', shape=(m, nt), Lb=0, Ub=None)
    FSlack2 = make_vars(name='FSlack2', shape=(m, nt), Lb=0, Ub=None)

    # declare problem
    problem = LpProblem(name='DC_OPF_Time_Series')

    # add the objective function
    add_objective_function(problem, Pg, Pb, LSlack, FSlack1, FSlack2, cost_g, cost_b, cost_l, cost_br)

    P = get_power_injections(C_bus_gen=numerical_circuit.C_gen_bus,
                             Pg=Pg,
                             C_bus_bat=numerical_circuit.C_batt_bus,
                             Pb=Pb,
                             C_bus_load=numerical_circuit.C_load_bus,
                             LSlack=LSlack,
                             Pl=Pl)

    add_nodal_power_balance(problem, B, theta, P, pqpv, vd)

    add_branch_loading_restriction(problem, theta_f, theta_t, Bseries, Fmax, FSlack1, FSlack2)

    add_battery_discharge_restriction(problem, SoC0, Capacity, Efficiency, Pb, E, dt)

    problem.solve()

    return problem
