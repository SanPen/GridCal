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

from GridCal.Engine.Core.snapshot_opf_data import SnapshotOpfData
from GridCal.Engine.Simulations.OPF.opf_templates import Opf, MIPSolvers
from GridCal.ThirdParty.pulp import *


def get_objective_function(Pg, Pb, LSlack, FSlack1, FSlack2,
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

    f_obj = lpSum(cost_g * Pg)

    f_obj += lpSum(cost_b * Pb)

    f_obj += lpSum(cost_l * LSlack)

    f_obj += lpSum(cost_br * (FSlack1 + FSlack2))

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

    lpAddRestrictions2(problem=problem,
                       lhs=Pg[idx],
                       rhs=P_fix[idx],
                       name='fixed_generation',
                       op='=')


def get_power_injections(C_bus_gen, Pg, C_bus_bat, Pb, C_bus_load, PlSlack, QlSlack, Pl, Ql):
    """
    Create the power injections per bus
    :param C_bus_gen: Bus-Generators sparse connectivity matrix (n, ng)
    :param Pg: generator LpVars (ng, nt)
    :param C_bus_bat: Bus-Batteries sparse connectivity matrix (n, nb)
    :param Pb: Batteries LpVars (nb, nt)
    :param C_bus_load: Bus-Load sparse connectivity matrix (n, nl)
    :param PlSlack: Load (real) slack LpVars (nl, nt)
    :param QlSlack: Load (imag) slack LpVars (nl, nt)
    :param Pl: Load values (nl, nt)
    :return: Power injection at the buses (n, nt)
    """

    P = lpDot(C_bus_gen, Pg)

    P += lpDot(C_bus_bat, Pb)

    P -= lpDot(C_bus_load, Pl - PlSlack)

    Q = - lpDot(C_bus_load, Ql - QlSlack)

    return P, Q


def add_ac_nodal_power_balance(numerical_circuit, problem: LpProblem, dvm, dva, P, Q):
    """
    Add the nodal power balance
    :param numerical_circuit: NumericalCircuit instance
    :param problem: LpProblem instance
    :param dva: Voltage angles LpVars (n, nt)
    :param P: Power injection at the buses LpVars (n, nt)
    :return: Nothing, the restrictions are added to the problem
    """

    # do the topological computation
    calculation_inputs = numerical_circuit.split_into_islands()

    nodal_restrictions_P = np.empty(numerical_circuit.nbus, dtype=object)
    nodal_restrictions_Q = np.empty(numerical_circuit.nbus, dtype=object)

    # simulate each island and merge the results
    for i, calc_inpt in enumerate(calculation_inputs):

        if len(calc_inpt.vd) > 0:
            # find the original indices
            bus_original_idx = np.array(calc_inpt.original_bus_idx)

            # re-pack the variables for the island and time interval
            P_island = P[bus_original_idx]  # the sizes already reflect the correct time span
            Q_island = Q[bus_original_idx]  # the sizes already reflect the correct time span
            dva_island = dva[bus_original_idx]  # the sizes already reflect the correct time span
            dvm_island = dvm[bus_original_idx]  # the sizes already reflect the correct time span

            B_island = calc_inpt.Ybus.imag
            G_island = calc_inpt.Ybus.real
            Bs_island = calc_inpt.Yseries.imag
            Gs_island = calc_inpt.Yseries.real

            pqpv = calc_inpt.pqpv
            pq = calc_inpt.pq
            pv = calc_inpt.pv
            vd = calc_inpt.vd
            vdpv = np.r_[vd, pv]
            vdpv.sort()

            # Add nodal real power balance for the non slack nodes
            idx = bus_original_idx[pqpv]
            nodal_restrictions_P[idx] = lpAddRestrictions2(problem=problem,
                                                           lhs=-lpDot(Bs_island[np.ix_(pqpv, pqpv)], dva_island[pqpv])
                                                               + lpDot(G_island[np.ix_(pqpv, pq)], dvm_island[pq]),
                                                           rhs=P_island[pqpv],
                                                           name='Nodal_real_power_balance_pqpv_is' + str(i),
                                                           op='=')

            # Add nodal reactive power balance for the non slack nodes
            idx = bus_original_idx[pq]
            nodal_restrictions_Q[idx] = lpAddRestrictions2(problem=problem,
                                                           lhs=-lpDot(Gs_island[np.ix_(pq, pqpv)], dva_island[pqpv])
                                                               - lpDot(B_island[np.ix_(pq, pq)], dvm_island[pq]),
                                                           rhs=Q_island[pq],
                                                           name='Nodal_imag_power_balance_pqpv_is' + str(i),
                                                           op='=')

            # Add nodal real power balance for the slack nodes
            idx = bus_original_idx[vd]
            nodal_restrictions_P[idx] = lpAddRestrictions2(problem=problem,
                                                           lhs=-lpDot(Bs_island[vd, :], dva_island)
                                                               + lpDot(G_island[vd, :], dvm_island),
                                                           rhs=P_island[vd],
                                                           name='Nodal_real_power_balance_vd_is' + str(i),
                                                           op='=')

            # delta of voltage angles equal to zero for the slack nodes (vd)
            lpAddRestrictions2(problem=problem,
                               lhs=dva_island[vd],
                               rhs=np.zeros_like(dva_island[vd]),
                               name='dVa_vd_zero_is' + str(i),
                               op='=')

            # delta of voltage module equal to zero for the slack and pv nodes (vdpv)
            lpAddRestrictions2(problem=problem,
                               lhs=dvm_island[vdpv],
                               rhs=np.zeros_like(dva_island[vdpv]),
                               name='dVm_vdpv_zero_is' + str(i),
                               op='=')

    return nodal_restrictions_P, nodal_restrictions_Q


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
                       rhs=np.array(Fmax + FSlack1),  # Fmax + FSlack1
                       name='from_to_branch_rate',
                       op='<=')

    # to-from branch power restriction
    lpAddRestrictions2(problem=problem,
                       lhs=load_t,
                       rhs=np.array(Fmax + FSlack2),  # Fmax + FSlack2
                       name='to_from_branch_rate',
                       op='<=')

    return load_f, load_t


class OpfAc(Opf):

    def __init__(self, numerical_circuit: SnapshotOpfData, solver: MIPSolvers = MIPSolvers.CBC):
        """
        DC time series linear optimal power flow
        :param numerical_circuit: NumericalCircuit instance
        """
        Opf.__init__(self, numerical_circuit=numerical_circuit, solver=solver)

        self.v0 = None
        self.dva = None
        self.dvm = None
        self.Ql = None

        # build the formulation
        self.problem = self.formulate()

    def formulate(self):
        """
        Formulate the AC OPF time series in the non-sequential fashion (all to the solver at once)
        :return: PuLP Problem instance
        """
        numerical_circuit = self.numerical_circuit

        # general indices
        n = numerical_circuit.nbus
        m = numerical_circuit.nbr
        ng = numerical_circuit.ngen
        nb = numerical_circuit.nbatt
        nl = numerical_circuit.nload
        Sbase = numerical_circuit.Sbase

        # battery
        Pb_max = numerical_circuit.battery_pmax / Sbase
        Pb_min = numerical_circuit.battery_pmin / Sbase
        cost_b = numerical_circuit.battery_cost

        # generator
        Pg_max = numerical_circuit.generator_pmax / Sbase
        Pg_min = numerical_circuit.generator_pmin / Sbase
        cost_g = numerical_circuit.generator_cost
        P_fix = numerical_circuit.generator_p / Sbase
        enabled_for_dispatch = numerical_circuit.generator_dispatchable

        # load
        Pl = (numerical_circuit.load_active * numerical_circuit.load_s.real) / Sbase
        Ql = (numerical_circuit.load_active * numerical_circuit.load_s.imag) / Sbase
        cost_l = numerical_circuit.load_cost

        # branch
        branch_ratings = numerical_circuit.branch_rates / Sbase
        Bseries = (numerical_circuit.branch_active * (1 / (numerical_circuit.branch_R + 1j * numerical_circuit.branch_X))).imag
        cost_br = numerical_circuit.branch_cost

        # create LP variables
        Pg = lpMakeVars(name='Pg', shape=ng, lower=Pg_min, upper=Pg_max)
        Pb = lpMakeVars(name='Pb', shape=nb, lower=Pb_min, upper=Pb_max)
        load_slack = lpMakeVars(name='LSlack', shape=nl, lower=0, upper=None)
        dva = lpMakeVars(name='dva', shape=n, lower=-3.14, upper=3.14)
        dvm = lpMakeVars(name='dvm', shape=n, lower=0, upper=2)
        theta_f = dva[numerical_circuit.F]
        theta_t = dva[numerical_circuit.T]
        branch_rating_slack1 = lpMakeVars(name='FSlack1', shape=m, lower=0, upper=None)
        branch_rating_slack2 = lpMakeVars(name='FSlack2', shape=m, lower=0, upper=None)

        # declare problem
        problem = LpProblem(name='AC_OPF')

        # add the objective function
        problem += get_objective_function(Pg, Pb, load_slack, branch_rating_slack1, branch_rating_slack2,
                                          cost_g, cost_b, cost_l, cost_br)

        # set the fixed generation values
        set_fix_generation(problem=problem, Pg=Pg, P_fix=P_fix, enabled_for_dispatch=enabled_for_dispatch)

        # compute the power injections per node
        P, Q = get_power_injections(C_bus_gen=numerical_circuit.generator_data.C_bus_gen, Pg=Pg,
                                    C_bus_bat=numerical_circuit.battery_data.C_bus_batt, Pb=Pb,
                                    C_bus_load=numerical_circuit.load_data.C_bus_load,
                                    PlSlack=load_slack, QlSlack=load_slack,
                                    Pl=Pl, Ql=Ql)

        # compute the nodal power balance restrictions
        nodal_restrictions_P, nodal_restrictions_Q = add_ac_nodal_power_balance(numerical_circuit=numerical_circuit,
                                                                                problem=problem,
                                                                                dvm=dvm, dva=dva, P=P, Q=Q)

        # add the branch loading restriction
        load_f, load_t = add_branch_loading_restriction(problem, theta_f, theta_t, Bseries, branch_ratings,
                                                        branch_rating_slack1, branch_rating_slack2)

        # Assign variables to keep
        # transpose them to be in the format of GridCal: time, device
        self.v0 = np.abs(numerical_circuit.Vbus)
        self.dva = dva
        self.dvm = dvm
        self.Pg = Pg
        self.Pb = Pb
        self.Pl = Pl
        self.load_shedding = load_slack
        self.s_from = load_f
        self.s_to = load_t
        self.overloads = branch_rating_slack1 + branch_rating_slack2
        self.rating = branch_ratings
        self.nodal_restrictions = nodal_restrictions_P

        return problem

    def get_voltage(self):
        """
        return the complex voltages (time, device)
        :return: 2D array
        """
        angles = self.extract(self.dva)
        modules = self.v0 + self.extract(self.dvm)
        return modules * np.exp(-1j * angles)


if __name__ == '__main__':
    from GridCal.Engine.basic_structures import BranchImpedanceMode
    from GridCal.Engine.IO.file_handler import FileOpen
    from GridCal.Engine.Core.snapshot_opf_data import compile_snapshot_opf_circuit

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv (2 islands).gridcal'

    main_circuit = FileOpen(fname).open()

    # main_circuit.buses[3].controlled_generators[0].enabled_dispatch = False

    numerical_circuit_ = compile_snapshot_opf_circuit(circuit=main_circuit,
                                                      apply_temperature=False,
                                                      branch_tolerance_mode=BranchImpedanceMode.Specified)

    problem = OpfAc(numerical_circuit=numerical_circuit_)

    print('Solving...')
    status = problem.solve()

    # print("Status:", status)

    v = problem.get_voltage()
    print('Modules\n', np.abs(v))
    print('Angles\n', np.angle(v))

    l = problem.get_loading()
    print('Branch loading\n', l)

    g = problem.get_generator_power()
    print('Gen power\n', g)

    pr = problem.get_shadow_prices()
    print('Nodal prices \n', pr)
