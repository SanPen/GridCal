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
from GridCal.Engine.basic_structures import ZonalGrouping
from GridCal.Engine.Core.snapshot_opf_data import SnapshotOpfData
from GridCal.Engine.Simulations.OPF.opf_templates import Opf, MIPSolvers, Logger, LpVariable
from GridCal.Engine.Devices.enumerations import TransformerControlType, ConverterControlType, HvdcControlType, GenerationNtcFormulation


def add_objective_function(Pg, Pb, LSlack, FSlack1, FSlack2, FCSlack1, FCSlack2,
                           hvdc_overload1, hvdc_overload2,
                           hvdc_control1_slacks, hvdc_control2_slacks,
                           cost_g, cost_b, cost_l, cost_br):
    """
    Add the objective function to the problem
    :param Pg: generator LpVars (ng, nt)
    :param Pb: batteries LpVars (nb, nt)
    :param LSlack: Load slack LpVars (nl, nt)
    :param FSlack1: Branch overload slack1 (m, nt)
    :param FSlack2: Branch overload slack2 (m, nt)
    :param FCSlack1: Branch contingency overload slack1 [list]
    :param FCSlack2: Branch contingency overload slack2 [List]
    :param hvdc_overload1: HVDC overload (nhvdc, nt)
    :param hvdc_overload2: HVDC overload (nhvdc, nt)
    :param hvdc_control1_slacks: HVDC control slack 1 (nhvdc, nt)
    :param hvdc_control2_slacks: HVDC control slack 2 (nhvdc, nt)
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

    f_obj += pl.lpSum(FCSlack1 + FCSlack2)

    if len(hvdc_overload1) > 0:
        f_obj += pl.lpSum(hvdc_overload1 + hvdc_overload2 + hvdc_control1_slacks + hvdc_control2_slacks)

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


def add_dc_nodal_power_balance(numerical_circuit: SnapshotOpfData, problem: pl.LpProblem, theta, P):
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


def add_branch_loading_restriction(problem: pl.LpProblem, nc: SnapshotOpfData,
                                   F, T, theta, active, monitored,
                                   ratings, ratings_slack_from, ratings_slack_to):
    """
    Add the branch loading restrictions
    :param problem: LpProblem instance
    :param nc: SnapshotOpfData instance
    :param F:
    :param T:
    :param theta: voltage angles
    :param ys: Array of branch linear admittances (m)
    :param active: Array of branch active states
    :param monitored: Array of branch monitoring
    :param ratings: Array of branch ratings (m)
    :param ratings_slack_from: Array of branch loading slack variables in the from-to sense
    :param ratings_slack_to: Array of branch loading slack variables in the to-from sense
    :return: load_f and load_t arrays (LP+float)
    """
    nbr = len(ratings)

    # from-to branch power restriction
    Pbr_f = np.zeros(nbr, dtype=object)
    tau = np.zeros(nbr, dtype=object)

    for m in range(nbr):
        if active[m]:

            # compute the branch susceptance
            if nc.branch_data.branch_dc[m]:
                bk = -1.0 / nc.branch_data.R[m]
            else:
                bk = -1.0 / nc.branch_data.X[m]

            # compute the flow
            if nc.branch_data.control_mode[m] == TransformerControlType.Pt:
                # is a phase shifter device (like phase shifter transformer or VSC with P control)
                tau[m] = LpVariable('Tau_{}'.format(m), nc.branch_data.theta_min[m], nc.branch_data.theta_max[m])
                Pbr_f[m] = bk * (theta[F[m]] - theta[T[m]] + tau[m])
            else:
                # is a regular branch
                Pbr_f[m] = bk * (theta[F[m]] - theta[T[m]])

            if monitored[m]:
                problem.add(Pbr_f[m] <= ratings[m] + ratings_slack_from[m], 'upper_rate_{0}'.format(m))
                problem.add(-ratings[m] - ratings_slack_to[m] <= Pbr_f[m], 'lower_rate_{0}'.format(m))
        else:
            Pbr_f[m] = 0

    return Pbr_f, tau


def formulate_contingency(problem: pl.LpProblem, numerical_circuit: SnapshotOpfData, flow_f, ratings, LODF, monitor, lodf_tolerance):
    """
    Formulate contingencies
    :param problem:
    :param numerical_circuit:
    :param flow_f:
    :param ratings:
    :param LODF:
    :param monitor:
    :return:
    """
    nbr = ratings.shape[0]

    # get the indices of the branches marked for contingency
    con_br_idx = numerical_circuit.branch_data.get_contingency_enabled_indices()

    # formulate contingency flows
    # this is done in a separated loop because all te flow variables must exist beforehand
    flow_lst = list()
    indices = list()  # (t, m, contingency_m)
    overload1_lst = list()
    overload2_lst = list()

    for m in range(nbr):  # for every branch

        if monitor[m]:  # the monitor variable is pre-computed in the previous loop
            _f = numerical_circuit.branch_data.F[m]
            _t = numerical_circuit.branch_data.T[m]

            for ic, c in enumerate(con_br_idx):  # for every contingency

                if m != c and abs(LODF[m, c]) >= lodf_tolerance:

                    # compute the N-1 flow
                    contingency_flow = flow_f[m] + LODF[m, c] * flow_f[c]

                    # rating restriction in the sense from-to
                    overload1 = LpVariable("n-1_overload1_{0}_{1}".format(m, c), 0, 99999)
                    problem.add(contingency_flow <= (ratings[m] + overload1), "n-1_ft_up_rating_{0}_{1}".format(m, c))

                    # rating restriction in the sense to-from
                    overload2 = LpVariable("n-1_overload2_{0}_{1}".format(m, c), 0, 99999)
                    problem.add((-ratings[m] - overload2) <= contingency_flow, "n-1_tf_down_rating_{0}_{1}".format(m, c))

                    # store the variables
                    flow_lst.append(contingency_flow)
                    overload1_lst.append(overload1)
                    overload2_lst.append(overload2)
                    indices.append((m, c))

    return flow_lst, overload1_lst, overload2_lst, indices


def formulate_hvdc_flow(problem: pl.LpProblem, nc: SnapshotOpfData, angles, Pinj, t=0,
                        logger: Logger = Logger(), inf=999999):
    """

    :param problem:
    :param nc:
    :param angles:
    :param Pinj:
    :param t:
    :param logger:
    :param inf:
    :return:
    """
    rates = nc.hvdc_data.rate[:, t] / nc.Sbase
    F = nc.hvdc_data.get_bus_indices_f()
    T = nc.hvdc_data.get_bus_indices_t()

    flow_f = np.zeros(nc.nhvdc, dtype=object)
    overload1 = np.zeros(nc.nhvdc, dtype=object)
    overload2 = np.zeros(nc.nhvdc, dtype=object)
    hvdc_control1 = np.zeros(nc.nhvdc, dtype=object)
    hvdc_control2 = np.zeros(nc.nhvdc, dtype=object)

    for i in range(nc.nhvdc):

        if nc.hvdc_data.active[i, t]:

            _f = F[i]
            _t = T[i]

            hvdc_control1[i] = LpVariable('hvdc_control1_' + str(i), 0, inf)
            hvdc_control2[i] = LpVariable('hvdc_control2_' + str(i), 0, inf)
            P0 = nc.hvdc_data.Pt[i, t] / nc.Sbase

            if nc.hvdc_data.control_mode[i] == HvdcControlType.type_0_free:

                if rates[i] <= 0:
                    logger.add_error('Rate = 0', 'HVDC:{0}'.format(i), rates[i])

                # formulate the hvdc flow as an AC line equivalent
                bk = 1.0 / nc.hvdc_data.r[i]  # TODO: yes, I know... DC...
                flow_f[i] = P0 + bk * (angles[_f] - angles[_t]) + hvdc_control1[i] - hvdc_control2[i]

                # add the injections matching the flow
                Pinj[_f] -= flow_f[i]
                Pinj[_t] += flow_f[i]

                # rating restriction in the sense from-to: eq.17
                overload1[i] = LpVariable('overload_hvdc1_' + str(i), 0, inf)
                problem.add(flow_f[i] <= (rates[i] + overload1[i]), "hvdc_ft_rating_" + str(i))

                # rating restriction in the sense to-from: eq.18
                overload2[i] = LpVariable('overload_hvdc2_' + str(i), 0, inf)
                problem.add((-rates[i] - overload2[i]) <= flow_f[i], "hvdc_tf_rating_" + str(i))

            elif nc.hvdc_data.control_mode[i] == HvdcControlType.type_1_Pset and not nc.hvdc_data.dispatchable[i]:
                # simple injections model: The power is set by the user
                flow_f[i] = P0 + hvdc_control1[i] - hvdc_control2[i]
                Pinj[_f] -= flow_f[i]
                Pinj[_t] += flow_f[i]

            elif nc.hvdc_data.control_mode[i] == HvdcControlType.type_1_Pset and nc.hvdc_data.dispatchable[i]:
                # simple injections model, the power is a variable and it is optimized
                P0 = LpVariable('hvdc_pf_' + str(i), -rates[i], rates[i])
                flow_f[i] = P0 + hvdc_control1[i] - hvdc_control2[i]
                Pinj[_f] -= flow_f[i]
                Pinj[_t] += flow_f[i]

    return flow_f, overload1, overload2, hvdc_control1, hvdc_control2


class OpfDc(Opf):

    def __init__(self, numerical_circuit, solver_type: MIPSolvers = MIPSolvers.CBC,
                 zonal_grouping: ZonalGrouping = ZonalGrouping.NoGrouping,
                 skip_generation_limits=False, consider_contingencies=False, LODF=None,
                 lodf_tolerance=0.001):
        """
        DC time series linear optimal power flow
        :param numerical_circuit: NumericalCircuit instance
        :param solver_type:
        :param zonal_grouping:
        :param skip_generation_limits:
        :param consider_contingencies:
        :param LODF:
        """

        self.zonal_grouping = zonal_grouping
        self.skip_generation_limits = skip_generation_limits
        self.consider_contingencies = consider_contingencies
        self.LODF = LODF
        self.lodf_tolerance = lodf_tolerance

        Opf.__init__(self, numerical_circuit=numerical_circuit, solver_type=solver_type)

    def formulate(self):
        """
        Formulate the AC OPF time series in the non-sequential fashion (all to the solver_type at once)
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
        if self.skip_generation_limits:
            Pg_max = np.zeros(self.numerical_circuit.ngen) + 99999
            Pg_min = np.zeros(self.numerical_circuit.ngen) - 99999
        else:
            Pg_max = self.numerical_circuit.generator_pmax / Sbase
            Pg_min = self.numerical_circuit.generator_pmin / Sbase
        cost_g = self.numerical_circuit.generator_cost
        P_fix = self.numerical_circuit.generator_p / Sbase
        enabled_for_dispatch = self.numerical_circuit.generator_dispatchable

        # load
        Pl = (self.numerical_circuit.load_active * self.numerical_circuit.load_s.real) / Sbase
        cost_l = self.numerical_circuit.load_cost

        # branch
        branch_active = self.numerical_circuit.branch_data.branch_active[:, 0]
        branch_monitored = self.numerical_circuit.branch_data.monitor_loading
        branch_ratings = self.numerical_circuit.branch_rates / Sbase

        cost_br = self.numerical_circuit.branch_cost

        # create LP variables
        Pg = pl.lpMakeVars(name='Pg', shape=ng, lower=Pg_min, upper=Pg_max)
        Pb = pl.lpMakeVars(name='Pb', shape=nb, lower=Pb_min, upper=Pb_max)
        load_slack = pl.lpMakeVars(name='LSlack', shape=nl, lower=0, upper=None)
        theta = pl.lpMakeVars(name='theta', shape=n,
                              lower=self.numerical_circuit.bus_data.angle_min,
                              upper=self.numerical_circuit.bus_data.angle_max)
        branch_rating_slack1 = pl.lpMakeVars(name='FSlack1', shape=m, lower=0, upper=None)
        branch_rating_slack2 = pl.lpMakeVars(name='FSlack2', shape=m, lower=0, upper=None)

        # declare problem
        problem = pl.LpProblem(name='DC_OPF')

        # set the fixed generation values
        set_fix_generation(problem=problem, Pg=Pg, P_fix=P_fix, enabled_for_dispatch=enabled_for_dispatch)

        # compute the nodal power injections
        P = get_power_injections(C_bus_gen=self.numerical_circuit.generator_data.C_bus_gen, Pg=Pg,
                                 C_bus_bat=self.numerical_circuit.battery_data.C_bus_batt, Pb=Pb,
                                 C_bus_load=self.numerical_circuit.load_data.C_bus_load,
                                 LSlack=load_slack, Pl=Pl)

        # formulate the simple HVDC models
        hvdc_flow_f, hvdc_overload1, hvdc_overload2, \
        hvdc_control1_slacks, hvdc_control2_slacks = formulate_hvdc_flow(problem=problem,
                                                                         nc=self.numerical_circuit,
                                                                         angles=theta,
                                                                         Pinj=P,
                                                                         t=0,
                                                                         logger=self.logger,
                                                                         inf=999999)

        # add the DC grid restrictions (with real slack losses)
        nodal_restrictions = add_dc_nodal_power_balance(numerical_circuit=self.numerical_circuit,
                                                        problem=problem,
                                                        theta=theta,
                                                        P=P)

        # add the branch loading restriction
        load_f, tau = add_branch_loading_restriction(problem=problem,
                                                     nc=self.numerical_circuit,
                                                     F=self.numerical_circuit.F,
                                                     T=self.numerical_circuit.T,
                                                     theta=theta,
                                                     active=branch_active,
                                                     monitored=branch_monitored,
                                                     ratings=branch_ratings,
                                                     ratings_slack_from=branch_rating_slack1,
                                                     ratings_slack_to=branch_rating_slack2)

        if self.consider_contingencies:
            con_flow_lst, con_overload1_lst, con_overload2_lst, \
            con_idx = formulate_contingency(problem=problem,
                                            numerical_circuit=self.numerical_circuit,
                                            flow_f=load_f,
                                            ratings=branch_ratings,
                                            LODF=self.LODF,
                                            monitor=self.numerical_circuit.branch_data.monitor_loading,
                                            lodf_tolerance=self.lodf_tolerance)
        else:
            con_flow_lst = list()
            con_idx = list()
            con_overload1_lst = list()
            con_overload2_lst = list()

        # add the objective function
        problem += add_objective_function(Pg, Pb, load_slack,
                                          branch_rating_slack1,
                                          branch_rating_slack2,
                                          con_overload1_lst,
                                          con_overload2_lst,
                                          hvdc_overload1, hvdc_overload2,
                                          hvdc_control1_slacks, hvdc_control2_slacks,
                                          cost_g, cost_b, cost_l, cost_br)

        # Assign variables to keep
        # transpose them to be in the format of GridCal: time, device
        self.theta = theta
        self.Pg = Pg
        self.Pb = Pb
        self.Pl = Pl

        self.Pinj = P

        self.phase_shift = tau

        self.hvdc_flow = hvdc_flow_f
        self.hvdc_slacks = hvdc_overload1 + hvdc_overload2

        self.load_shedding = load_slack
        self.s_from = load_f
        self.s_to = -load_f
        self.overloads = branch_rating_slack1 + branch_rating_slack2
        self.rating = branch_ratings
        self.nodal_restrictions = nodal_restrictions

        self.contingency_flows_list = con_flow_lst
        self.contingency_indices_list = con_idx  # [(t, m, c), ...]
        self.contingency_flows_slacks_list = con_overload1_lst

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
