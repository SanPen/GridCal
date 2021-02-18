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
import numpy as np
import GridCal.ThirdParty.pulp as pl
# from GridCal.Engine.Core.snapshot_opf_data import SnapshotOpfData
from GridCal.Engine.Simulations.OPF.opf_templates import Opf, MIPSolvers


def add_objective_function(Pg, Pb, LSlack, FSlack1, FSlack2,
                           cost_g, cost_b, cost_l, cost_br):
    """
    Add the objective function to the problem
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

    f_obj = pl.lpSum(cost_g * Pg)

    f_obj += pl.lpSum(cost_b * Pb)

    f_obj += pl.lpSum(cost_l * LSlack)

    f_obj += pl.lpSum(cost_br * (FSlack1 + FSlack2))

    return f_obj


def set_fix_generation(problem, Pg, P_fix, enabled_for_dispatch):
    """
    Set the generation fixed at the non dispatchable generators
    :param problem: LP problem instance
    :param Pg: Array of generation variables
    :param P_fix: Array of fixed generation values
    :param enabled_for_dispatch: array of "enables" for dispatching generators
    :return: Nothing
    """

    idx = np.where(enabled_for_dispatch == False)[0]

    pl.lpAddRestrictions2(problem=problem,
                          lhs=Pg[idx],
                          rhs=P_fix[idx],
                          name='fixed_generation',
                          op='=')


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

    return pl.lpDot(C_bus_gen, Pg) + pl.lpDot(C_bus_bat, Pb) - pl.lpDot(C_bus_load, Pl - LSlack)


def add_dc_nodal_power_balance(numerical_circuit, problem: pl.LpProblem, theta, P):
    """
    Add the nodal power balance
    :param numerical_circuit: NumericalCircuit instance
    :param problem: LpProblem instance
    :param theta: Voltage angles LpVars (n, nt)
    :param P: Power injection at the buses LpVars (n, nt)
    :return: Nothing, the restrictions are added to the problem
    """

    # do the topological computation
    calculation_inputs = numerical_circuit.split_into_islands()

    nodal_restrictions = np.empty(numerical_circuit.nbus, dtype=object)

    # simulate each island and merge the results
    for i, calc_inpt in enumerate(calculation_inputs):

        # if there is a slack it means that there is at least one generator,
        # otherwise these equations do not make sense
        if len(calc_inpt.vd) > 0:

            # find the original indices
            bus_original_idx = np.array(calc_inpt.original_bus_idx)

            # re-pack the variables for the island and time interval
            P_island = P[bus_original_idx]  # the sizes already reflect the correct time span
            theta_island = theta[bus_original_idx]  # the sizes already reflect the correct time span
            B_island = calc_inpt.Ybus.imag

            pqpv = calc_inpt.pqpv
            vd = calc_inpt.vd

            # Add nodal power balance for the non slack nodes
            idx = bus_original_idx[pqpv]
            nodal_restrictions[idx] = pl.lpAddRestrictions2(problem=problem,
                                                            lhs=pl.lpDot(B_island[np.ix_(pqpv, pqpv)], theta_island[pqpv]),
                                                            rhs=P_island[pqpv],
                                                            name='Nodal_power_balance_pqpv_is' + str(i),
                                                            op='=')

            # Add nodal power balance for the slack nodes
            idx = bus_original_idx[vd]
            nodal_restrictions[idx] = pl.lpAddRestrictions2(problem=problem,
                                                            lhs=pl.lpDot(B_island[vd, :], theta_island),
                                                            rhs=P_island[vd],
                                                            name='Nodal_power_balance_vd_is' + str(i),
                                                            op='=')

            # slack angles equal to zero
            pl.lpAddRestrictions2(problem=problem,
                                  lhs=theta_island[vd],
                                  rhs=np.zeros(len(vd)),
                                  name='Theta_vd_zero_is' + str(i),
                                  op='=')

    return nodal_restrictions


def add_branch_loading_restriction(problem: pl.LpProblem, theta_f, theta_t, Bseries, rating, FSlack1, FSlack2):
    """
    Add the branch loading restrictions
    :param problem: LpProblem instance
    :param theta_f: voltage angles at the "from" side of the branches (m)
    :param theta_t: voltage angles at the "to" side of the branches (m)
    :param Bseries: Array of branch susceptances (m)
    :param rating: Array of branch ratings (m)
    :param FSlack1: Array of branch loading slack variables in the from-to sense
    :param FSlack2: Array of branch loading slack variables in the to-from sense
    :return: load_f and load_t arrays (LP+float)
    """

    load_f = Bseries * (theta_f - theta_t)
    load_t = Bseries * (theta_t - theta_f)

    # from-to branch power restriction
    pl.lpAddRestrictions2(problem=problem,
                          lhs=load_f,
                          rhs=rating + FSlack1,  # rating + FSlack1
                          name='from_to_branch_rate',
                          op='<=')

    # to-from branch power restriction
    pl.lpAddRestrictions2(problem=problem,
                          lhs=load_t,
                          rhs=rating + FSlack2,  # rating + FSlack2
                          name='to_from_branch_rate',
                          op='<=')

    return load_f, load_t


class OpfDc(Opf):

    def __init__(self, numerical_circuit, solver: MIPSolvers = MIPSolvers.CBC):
        """
        DC time series linear optimal power flow
        :param numerical_circuit: NumericalCircuit instance
        """
        Opf.__init__(self, numerical_circuit=numerical_circuit, solver=solver)

        # build the formulation
        self.problem = self.formulate()

    def formulate(self):
        """
        Formulate the AC OPF time series in the non-sequential fashion (all to the solver at once)
        :return: PuLP Problem instance
        """

        # general indices
        n = self.numerical_circuit.nbus
        m = self.numerical_circuit.nbr
        ng = self.numerical_circuit.ngen
        nb = self.numerical_circuit.nbatt
        nl = self.numerical_circuit.nload
        Sbase = self.numerical_circuit.Sbase

        # battery
        Pb_max = self.numerical_circuit.battery_pmax / Sbase
        Pb_min = self.numerical_circuit.battery_pmin / Sbase
        cost_b = self.numerical_circuit.battery_cost

        # generator
        Pg_max = self.numerical_circuit.generator_pmax / Sbase
        Pg_min = self.numerical_circuit.generator_pmin / Sbase
        cost_g = self.numerical_circuit.generator_cost
        P_fix = self.numerical_circuit.generator_p / Sbase
        enabled_for_dispatch = self.numerical_circuit.generator_dispatchable

        # load
        Pl = (self.numerical_circuit.load_active * self.numerical_circuit.load_s.real) / Sbase
        cost_l = self.numerical_circuit.load_cost

        # branch
        branch_ratings = self.numerical_circuit.branch_rates / Sbase
        Ys = 1 / (self.numerical_circuit.branch_R + 1j * self.numerical_circuit.branch_X)
        Bseries = (self.numerical_circuit.branch_active * Ys).imag
        cost_br = self.numerical_circuit.branch_cost

        # create LP variables
        Pg = pl.lpMakeVars(name='Pg', shape=ng, lower=Pg_min, upper=Pg_max)
        Pb = pl.lpMakeVars(name='Pb', shape=nb, lower=Pb_min, upper=Pb_max)
        load_slack = pl.lpMakeVars(name='LSlack', shape=nl, lower=0, upper=None)
        theta = pl.lpMakeVars(name='theta', shape=n, lower=-3.14, upper=3.14)
        theta_f = theta[self.numerical_circuit.F]
        theta_t = theta[self.numerical_circuit.T]
        branch_rating_slack1 = pl.lpMakeVars(name='FSlack1', shape=m, lower=0, upper=None)
        branch_rating_slack2 = pl.lpMakeVars(name='FSlack2', shape=m, lower=0, upper=None)

        # declare problem
        problem = pl.LpProblem(name='DC_OPF')

        # add generator bound restrictions
        # pl.lpAddRestrictions2(problem, lhs=Pg_min, rhs=Pg, name='Pg_min', op='<=')
        # pl.lpAddRestrictions2(problem, lhs=Pg, rhs=Pg_max, name='Pg_max', op='<=')
        # pl.lpAddRestrictions2(problem, lhs=Pb_min, rhs=Pb, name='Pb_min', op='<=')
        # pl.lpAddRestrictions2(problem, lhs=Pb, rhs=Pb_max, name='Pb_max', op='<=')

        # add the objective function
        problem += add_objective_function(Pg, Pb, load_slack,
                                          branch_rating_slack1,
                                          branch_rating_slack2,
                                          cost_g, cost_b, cost_l, cost_br)

        # set the fixed generation values
        set_fix_generation(problem=problem, Pg=Pg, P_fix=P_fix, enabled_for_dispatch=enabled_for_dispatch)

        # compute the nodal power injections
        P = get_power_injections(C_bus_gen=self.numerical_circuit.generator_data.C_bus_gen, Pg=Pg,
                                 C_bus_bat=self.numerical_circuit.battery_data.C_bus_batt, Pb=Pb,
                                 C_bus_load=self.numerical_circuit.load_data.C_bus_load,
                                 LSlack=load_slack, Pl=Pl)

        # add the DC grid restrictions (with real slack losses)
        nodal_restrictions = add_dc_nodal_power_balance(numerical_circuit=self.numerical_circuit,
                                                        problem=problem,
                                                        theta=theta,
                                                        P=P)

        # add the branch loading restriction
        load_f, load_t = add_branch_loading_restriction(problem=problem,
                                                        theta_f=theta_f,
                                                        theta_t=theta_t,
                                                        Bseries=Bseries,
                                                        rating=branch_ratings,
                                                        FSlack1=branch_rating_slack1,
                                                        FSlack2=branch_rating_slack2)

        # Assign variables to keep
        # transpose them to be in the format of GridCal: time, device
        self.theta = theta
        self.Pg = Pg
        self.Pb = Pb
        self.Pl = Pl
        self.load_shedding = load_slack
        self.s_from = load_f
        self.s_to = load_t
        self.overloads = branch_rating_slack1 + branch_rating_slack2
        self.rating = branch_ratings
        self.nodal_restrictions = nodal_restrictions

        return problem


if __name__ == '__main__':
    from GridCal.Engine.basic_structures import BranchImpedanceMode
    from GridCal.Engine.IO.file_handler import FileOpen
    from GridCal.Engine.Core.snapshot_opf_data import compile_snapshot_opf_circuit

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'

    main_circuit = FileOpen(fname).open()

    # main_circuit.buses[3].controlled_generators[0].enabled_dispatch = False

    numerical_circuit_ = compile_snapshot_opf_circuit(circuit=main_circuit,
                                                      apply_temperature=False,
                                                      branch_tolerance_mode=BranchImpedanceMode.Specified)

    problem = OpfDc(numerical_circuit=numerical_circuit_)

    print('Solving...')
    status = problem.solve()

    # print("Status:", status)

    v = problem.get_voltage()
    print('Angles\n', np.angle(v))

    l = problem.get_loading()
    print('Branch loading\n', l)

    g = problem.get_generator_power()
    print('Gen power\n', g)

    pr = problem.get_shadow_prices()
    print('Nodal prices \n', pr)
