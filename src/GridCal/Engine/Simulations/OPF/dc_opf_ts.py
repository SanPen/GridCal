# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""
This file implements a DC-OPF for time series
That means that solves the OPF problem for a complete time series at once
"""
import numpy as np
from itertools import product

from GridCal.Engine.basic_structures import ZonalGrouping
from GridCal.Engine.Simulations.OPF.opf_templates import OpfTimeSeries, LpProblem, LpVariable, Logger
from GridCal.Engine.basic_structures import MIPSolvers
from GridCal.Engine.Core.time_series_opf_data import OpfTimeCircuit
import GridCal.ThirdParty.pulp as pl
from GridCal.Engine.Devices.enumerations import TransformerControlType, ConverterControlType, HvdcControlType, GenerationNtcFormulation


def get_objective_function(Pg, Pb, LSlack, FSlack1, FSlack2, FCSlack1, FCSlack2,
                           flow_from_a1_to_a2, sum_gen_area_1, sum_gen_area_2,
                           cost_g, cost_b, cost_l, cost_br):
    """
    Add the objective function to the problem
    :param Pg: generator LpVars (ng, nt)
    :param Pb: batteries LpVars (nb, nt)
    :param LSlack: Load slack LpVars (nl, nt)
    :param FSlack1: Branch overload slack1 (m, nt)
    :param FSlack2: Branch overload slack2 (m, nt)
    :param FCSlack1: Branch contingency overload slack1 (m, nt)
    :param FCSlack2: Branch contingency overload slack2 (m, nt)
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

    f_obj += cost_br * pl.lpSum(FCSlack1) + cost_br * pl.lpSum(FCSlack2)

    if flow_from_a1_to_a2 is not None:
        f_obj -= pl.lpSum(flow_from_a1_to_a2)  # maximize

    if sum_gen_area_1 is not None:
        f_obj -= pl.lpSum(sum_gen_area_1)  # maximize
        f_obj += pl.lpSum(sum_gen_area_2)  # minimize

    return f_obj


def set_fix_generation(problem, Pg, P_profile, enabled_for_dispatch):
    """
    Set the generation fixed at the non dispatchable generators
    :param problem: LP problem instance
    :param Pg: Array of generation variables
    :param P_profile: Array of fixed generation values
    :param enabled_for_dispatch: array of "enables" for dispatching generators
    :return: Nothing
    """

    idx = np.where(enabled_for_dispatch == False)[0]

    pl.lpAddRestrictions2(problem=problem,
                          lhs=Pg[idx, :],
                          rhs=P_profile[idx, :],
                          # Fmax + FSlack2
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

    P = pl.lpDot(C_bus_gen, Pg)

    P += pl.lpDot(C_bus_bat, Pb)

    P -= pl.lpDot(C_bus_load, Pl - LSlack)

    return P


def formulate_dc_nodal_power_balance(numerical_circuit: OpfTimeCircuit, problem: LpProblem, theta, P, start_, end_):
    """
    Add the nodal power balance
    :param numerical_circuit: NumericalCircuit instance
    :param problem: LpProblem instance
    :param theta: Voltage angles LpVars (n, nt)
    :param P: Power injection at the buses LpVars (n, nt)
    :return: Nothing, the restrictions are added to the problem (nbus, nt)
    """

    # do the topological computation
    calc_inputs = numerical_circuit.split_into_islands(ignore_single_node_islands=True)

    # generate the time indices to simulate
    if end_ == -1:
        end_ = len(numerical_circuit.time_array)

    # For every island, run the time series
    nodal_restrictions = np.empty((numerical_circuit.nbus, end_ - start_), dtype=object)
    for i, calc_inpt in enumerate(calc_inputs):

        # find the original indices
        bus_original_idx = np.array(calc_inpt.original_bus_idx)

        # re-pack the variables for the island and time interval
        P_island = P[bus_original_idx, :]  # the sizes already reflect the correct time span
        theta_island = theta[bus_original_idx, :]  # the sizes already reflect the correct time span
        B_island = calc_inpt.Ybus.imag

        pqpv = calc_inpt.pqpv
        vd = calc_inpt.vd

        # Add nodal power balance for the non slack nodes
        idx = bus_original_idx[pqpv]
        nodal_restrictions[idx] = pl.lpAddRestrictions2(problem=problem,
                                                        lhs=pl.lpDot(B_island[np.ix_(pqpv, pqpv)], theta_island[pqpv, :]),
                                                        rhs=P_island[pqpv, :],
                                                        name='Nodal_power_balance_pqpv_is' + str(i),
                                                        op='=')

        # Add nodal power balance for the slack nodes
        idx = bus_original_idx[vd]
        nodal_restrictions[idx] = pl.lpAddRestrictions2(problem=problem,
                                                        lhs=pl.lpDot(B_island[vd, :], theta_island),
                                                        rhs=P_island[vd, :],
                                                        name='Nodal_power_balance_vd_is' + str(i),
                                                        op='=')

        # slack angles equal to zero
        pl.lpAddRestrictions2(problem=problem,
                              lhs=theta_island[vd, :],
                              rhs=np.zeros_like(theta_island[vd, :]),
                              name='Theta_vd_zero_is' + str(i),
                              op='=')

    return nodal_restrictions


def add_branch_loading_restriction(problem: LpProblem,
                                   nc: OpfTimeCircuit,
                                   theta, F, T,
                                   ratings, ratings_slack_from, ratings_slack_to,
                                   monitored, active):
    """
    Add the branch loading restrictions
    :param problem: LpProblem instance
    :param nc: OpfTimeCircuit instance
    :param theta: array of LpVariables with the bus angles (n, nt)
    :param F: Array with the "from" branch indices (m)
    :param T: Array with the "to" branch indices (m)
    :param ratings: Array of branch ratings (m, nt)
    :param ratings_slack_from: Array of branch loading slack variables in the from-to sense
    :param ratings_slack_to: Array of branch loading slack variables in the to-from sense
    :param monitored: Array with the monitoring status (m, nt)
    :param active: Array with the active status (m, nt)
    :return: Pbr_f: Array of power flowing through the branch (m, nt)
             tau: Array of tap angles in the phase shifters (m, nt)
             Pinj_tau: Array of the nodal power injections due to the phase shift (n, nt)
    """

    nbr, nt = ratings_slack_to.shape

    # from-to branch power restriction
    Pbr_f = np.zeros((nbr, nt), dtype=object)
    tau = np.zeros((nbr, nt), dtype=object)
    Pinj_tau = np.zeros((nc.nbus, nt), dtype=object)

    for m, t in product(range(nbr), range(nt)):
        if active[m, t]:

            # compute the branch susceptance
            if nc.branch_data.branch_dc[m]:
                bk = -1.0 / nc.branch_data.R[m]
            else:
                bk = -1.0 / nc.branch_data.X[m]

            # compute the flow
            if nc.branch_data.control_mode[m] == TransformerControlType.Pt:
                # is a phase shifter device (like phase shifter transformer or VSC with P control)
                tau[m, t] = LpVariable('Tau_{0}_{1}'.format(m, t), nc.branch_data.theta_min[m], nc.branch_data.theta_max[m])
                Pbr_f[m, t] = bk * (theta[F[m], t] - theta[T[m], t] + tau[m, t])

                # power injected and subtracted due to the phase shift
                Pinj_tau[F[m], t] = -bk * tau[m, t]
                Pinj_tau[T[m], t] = bk * tau[m, t]

            else:
                # regular branch
                tau[m, t] = 0.0
                Pbr_f[m, t] = bk * (theta[F[m], t] - theta[T[m], t])

            if monitored[m]:
                problem.add(Pbr_f[m, t] <= ratings[m, t] + ratings_slack_from[m, t], 'upper_rate_{0}_{1}'.format(m, t))
                problem.add(-ratings[m, t] - ratings_slack_to[m, t] <= Pbr_f[m, t], 'lower_rate_{0}_{1}'.format(m, t))
        else:
            Pbr_f[m, t] = 0

    return Pbr_f, tau, Pinj_tau


def formulate_contingency(problem: LpProblem, numerical_circuit: OpfTimeCircuit, flow_f, ratings, LODF, monitor,
                          lodf_tolerance):
    """

    :param problem:
    :param numerical_circuit:
    :param flow_f:
    :param LODF:
    :param monitor:
    :return:
    """
    nbr, nt = ratings.shape

    # get the indices of the branches marked for contingency
    con_br_idx = numerical_circuit.branch_data.get_contingency_enabled_indices()

    # formulate contingency flows
    # this is done in a separated loop because all te flow variables must exist beforehand
    flow_lst = list()
    indices = list()  # (t, m, contingency_m)
    overload1_lst = list()
    overload2_lst = list()

    for t, m in product(range(nt), range(nbr)):  # for every branch

        if monitor[m]:  # the monitor variable is pre-computed in the previous loop
            _f = numerical_circuit.branch_data.F[m]
            _t = numerical_circuit.branch_data.T[m]

            for ic, c in enumerate(con_br_idx):  # for every contingency

                if m != c and abs(LODF[m, c]) >= lodf_tolerance:

                    # compute the N-1 flow
                    contingency_flow = flow_f[m, t] + LODF[m, c] * flow_f[c, t]

                    # rating restriction in the sense from-to
                    overload1 = LpVariable("n-1_overload1_{0}_{1}_{2}".format(t, m, c), 0, 99999)
                    problem.add(contingency_flow <= (ratings[m, t] + overload1),
                                "n-1_ft_up_rating_{0}_{1}_{2}".format(t, m, c))

                    # rating restriction in the sense to-from
                    overload2 = LpVariable("n-1_overload2_{0}_{1}_{2}".format(t, m, c), 0, 99999)
                    problem.add((-ratings[m, t] - overload2) <= contingency_flow,
                                "n-1_tf_down_rating_{0}_{1}_{2}".format(t, m, c))

                    # store the variables
                    flow_lst.append(contingency_flow)
                    overload1_lst.append(overload1)
                    overload2_lst.append(overload2)
                    indices.append((t, m, c))

    return flow_lst, overload1_lst, overload2_lst, indices


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
    pl.lpAddRestrictions2(problem=problem,
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
        pl.lpAddRestrictions2(problem=problem,
                              lhs=E[:, t],
                              rhs=E[:, t - 1] - dt[i] * Pb[:, t] * eff_inv,
                              name='initial_soc_t' + str(t) + '_',
                              op='=')


def formulate_hvdc_flow(problem: LpProblem, angles, Pinj, rates, active, Pset,
                        control_mode, dispatchable, angle_droop, F, T, Sbase,
                        logger: Logger = Logger(), inf=999999):
    """

    :param problem:
    :param angles:
    :param Pinj:
    :param rates:
    :param active:
    :param Pset:
    :param control_mode:
    :param dispatchable:
    :param angle_droop:
    :param F:
    :param T:
    :param logger:
    :param inf:
    :param Sbase:
    :return:
    """
    nhvdc, nt = rates.shape

    flow_f = np.zeros((nhvdc, nt), dtype=object)

    for t, i in product(range(nt), range(nhvdc)):

        if active[i, t]:

            _f = F[i]
            _t = T[i]

            if control_mode[i] == HvdcControlType.type_0_free:

                if rates[i, t] <= 0:
                    logger.add_error('Rate = 0', 'HVDC:{0} t:{1}'.format(i, t), rates[i, t])

                # formulate the hvdc flow as an AC line equivalent
                flow_f[i, t] = LpVariable('flow_hvdc1_{0}_{1}'.format(i, t), -rates[i, t], rates[i, t])
                P0 = Pset[i, t] / Sbase
                problem.add(flow_f[i, t] == P0 + angle_droop[i, t] * (angles[_f, t] - angles[_t, t]),
                            "hvdc_flow_set_{0}_{1}".format(i, t))

                # add the injections matching the flow
                Pinj[_f, t] -= flow_f[i, t]
                Pinj[_t, t] += flow_f[i, t]

                # rating restriction in the sense from-to: eq.17
                # overload1[i, t] = LpVariable('overload_hvdc1_{0}_{1}'.format(i, t), 0, inf)
                # problem.add(flow_f[i, t] <= (rates[i, t] + overload1[i, t]), "hvdc_ft_rating_{0}_{1}".format(i, t))

                # rating restriction in the sense to-from: eq.18
                # overload2[i, t] = LpVariable('overload_hvdc2_{0}_{1}'.format(i, t), 0, inf)
                # problem.add((-rates[i, t] - overload2[i, t]) <= flow_f[i, t], "hvdc_tf_rating_{0}_{1}".format(i, t))

            elif control_mode[i] == HvdcControlType.type_1_Pset and not dispatchable[i]:
                # simple injections model: The power is set by the user
                P0 = Pset[i, t] / Sbase
                flow_f[i, t] = P0  # + hvdc_control1[i, t] - hvdc_control2[i, t]
                Pinj[_f, t] -= flow_f[i, t]
                Pinj[_t, t] += flow_f[i, t]

            elif control_mode[i] == HvdcControlType.type_1_Pset and dispatchable[i]:
                # simple injections model, the power is a variable and it is optimized
                P0 = LpVariable('hvdc_pf_{0}_{1}'.format(i, t), -rates[i, t], rates[i, t])
                flow_f[i, t] = P0
                Pinj[_f, t] -= flow_f[i, t]
                Pinj[_t, t] += flow_f[i, t]

    return flow_f


def formulate_inter_area_flow(numerical_circuit: OpfTimeCircuit,
                              buses_areas_1, buses_areas_2,
                              flow_f, hvdc_flow_f):
    """
    Formulate the flow that goes through the links from the area 1 (from) to the area 2 (to)
    :param numerical_circuit: OpfTimeCircuit instance
    :param buses_areas_1: array of bus indices that compose the area 1 (from)
    :param buses_areas_2: array of bus indices that compose the area 2 (to)
    :param flow_f: array of branch flows
    :param hvdc_flow_f: array of HVDC links flows
    :return: vector per time step of the sum of flows 1->2 with the correct sign as a PuLP equation
    """
    nhvdc, nt = hvdc_flow_f.shape

    inter_area_branches = numerical_circuit.get_inter_areas_branches(buses_areas_1=buses_areas_1,
                                                                     buses_areas_2=buses_areas_2)
    inter_area_hvdc = numerical_circuit.get_inter_areas_hvdc(buses_areas_1=buses_areas_1,
                                                             buses_areas_2=buses_areas_2)

    flows_ft = np.zeros((len(inter_area_branches), nt), dtype=object)
    flows_hvdc_ft = np.zeros((len(inter_area_hvdc), nt), dtype=object)
    flow_from_a1_to_a2 = np.zeros(nt, dtype=object)

    for t in range(nt):

        for i, (k, sign) in enumerate(inter_area_branches):
            flows_ft[i, t] = sign * flow_f[k, t]

        for i, (k, sign) in enumerate(inter_area_hvdc):
            flows_hvdc_ft[i, t] = sign * hvdc_flow_f[k, t]

        flow_from_a1_to_a2[t] = pl.lpSum(flows_ft) + pl.lpSum(flows_hvdc_ft)

    return flow_from_a1_to_a2


def formulate_area_generation_summations(numerical_circuit: OpfTimeCircuit, buses_areas_1, buses_areas_2, Pg):
    """
    Compute the summation of the generation in the area 1 and area 2
    :param numerical_circuit: OpfTimeCircuit instance
    :param buses_areas_1: array of bus indices that compose the area 1 (from)
    :param buses_areas_2: array of bus indices that compose the area 2 (to)
    :param Pg: Array of generator variables
    :return: Summation of generation in the area 1, summation of the generation in the are 2
    """

    _, nt = Pg.shape

    gens_in_a1, gens_in_a2, gens_out = numerical_circuit.get_generators_per_areas(buses_in_a1=buses_areas_1,
                                                                                  buses_in_a2=buses_areas_2)

    bat_in_a1, bat_in_a2, bat_out = numerical_circuit.get_batteries_per_areas(buses_in_a1=buses_areas_1,
                                                                              buses_in_a2=buses_areas_2)

    sum_a1 = np.zeros(nt, dtype=object)
    sum_a2 = np.zeros(nt, dtype=object)

    for t in range(nt):

        for bus_idx, gen_idx in gens_in_a1:
            sum_a1[t] += Pg[gen_idx, t]

        for bus_idx, gen_idx in gens_in_a2:
            sum_a2[t] += Pg[gen_idx, t]

        for bus_idx, gen_idx in bat_in_a1:
            sum_a1[t] += Pg[gen_idx, t]

        for bus_idx, gen_idx in bat_in_a2:
            sum_a2[t] += Pg[gen_idx, t]

    return sum_a1, sum_a2


class OpfDcTimeSeries(OpfTimeSeries):

    def __init__(self, numerical_circuit: OpfTimeCircuit, start_idx, end_idx, solver_type: MIPSolvers = MIPSolvers.CBC,
                 zonal_grouping: ZonalGrouping = ZonalGrouping.NoGrouping,
                 skip_generation_limits=False, consider_contingencies=False, LODF=None, lodf_tolerance=0.001,
                 maximize_inter_area_flow=False,
                 buses_areas_1=None, buses_areas_2=None):
        """
        DC time series linear optimal power flow
        :param numerical_circuit: NumericalCircuit instance
        :param start_idx: start index of the time series
        :param end_idx: end index of the time series
        :param solver_type: MIP solver_type to use
        :param zonal_grouping:
        :param skip_generation_limits:
        :param consider_contingencies:
        :param LODF:
        :param lodf_tolerance:
        :param maximize_inter_area_flow:
        :param buses_areas_1:
        :param buses_areas_2:
        """
        OpfTimeSeries.__init__(self, numerical_circuit=numerical_circuit,
                               start_idx=start_idx, end_idx=end_idx,
                               solver_type=solver_type, skip_formulation=True)

        self.zonal_grouping = zonal_grouping
        self.skip_generation_limits = skip_generation_limits
        self.consider_contingencies = consider_contingencies
        self.LODF = LODF
        self.lodf_tolerance = lodf_tolerance

        self.maximize_inter_area_flow = maximize_inter_area_flow
        self.buses_areas_1: List[int] = buses_areas_1
        self.buses_areas_2: List[int] = buses_areas_2

    def formulate(self, batteries_energy_0=None):
        """
        Formulate the DC OPF time series in the non-sequential fashion (all to the solver_type at once)
        :param batteries_energy_0: initial energy state of the batteries (if none, the default is taken)
        :return: PuLP Problem instance
        """

        # general indices
        n = self.numerical_circuit.nbus
        m = self.numerical_circuit.nbr
        ng = self.numerical_circuit.ngen
        nb = self.numerical_circuit.nbatt
        nl = self.numerical_circuit.nload
        nt = self.end_idx - self.start_idx
        a = self.start_idx
        b = self.end_idx
        Sbase = self.numerical_circuit.Sbase

        # battery
        Capacity = self.numerical_circuit.battery_enom / Sbase
        minSoC = self.numerical_circuit.battery_min_soc
        maxSoC = self.numerical_circuit.battery_max_soc
        if batteries_energy_0 is None:
            SoC0 = self.numerical_circuit.battery_soc_0
        else:
            SoC0 = (batteries_energy_0 / Sbase) / Capacity
        Pb_max = self.numerical_circuit.battery_pmax / Sbase
        Pb_min = self.numerical_circuit.battery_pmin / Sbase
        Efficiency = (self.numerical_circuit.battery_discharge_efficiency + self.numerical_circuit.battery_charge_efficiency) / 2.0
        cost_b = self.numerical_circuit.battery_cost[:, a:b]

        # generator
        if self.skip_generation_limits:
            Pg_max = np.zeros(self.numerical_circuit.ngen) * 99999999.0
            Pg_min = np.zeros(self.numerical_circuit.ngen) * -99999999.0
        else:
            Pg_max = self.numerical_circuit.generator_pmax / Sbase
            Pg_min = self.numerical_circuit.generator_pmin / Sbase

        P_profile = self.numerical_circuit.generator_p[:, a:b] / Sbase
        cost_g = self.numerical_circuit.generator_cost[:, a:b]
        enabled_for_dispatch = self.numerical_circuit.generator_dispatchable

        # load
        Pl = (self.numerical_circuit.load_active[:, a:b] * self.numerical_circuit.load_s.real[:, a:b]) / Sbase
        cost_l = self.numerical_circuit.load_cost[:, a:b]

        # branch
        branch_ratings = self.numerical_circuit.branch_rates[:, a:b] / Sbase
        br_active = self.numerical_circuit.branch_data.branch_active[:, a:b]
        F = self.numerical_circuit.F
        T = self.numerical_circuit.T
        cost_br = self.numerical_circuit.branch_cost[:, a:b]

        # Compute time delta in hours
        dt = np.zeros(nt)  # here nt = end_idx - start_idx
        for t in range(1, nt + 1):
            if a + t < nt:
                dt[t - 1] = (self.numerical_circuit.time_array[a + t] - self.numerical_circuit.time_array[a + t - 1]).seconds / 3600
            else:
                dt[t - 1] = 1.0

        # create LP variables
        Pg = pl.lpMakeVars(name='Pg', shape=(ng, nt), lower=Pg_min, upper=Pg_max)
        Pb = pl.lpMakeVars(name='Pb', shape=(nb, nt), lower=Pb_min, upper=Pb_max)
        E = pl.lpMakeVars(name='E', shape=(nb, nt), lower=Capacity * minSoC, upper=Capacity * maxSoC)
        load_slack = pl.lpMakeVars(name='LSlack', shape=(nl, nt), lower=0, upper=None)
        theta = pl.lpMakeVars(name='theta', shape=(n, nt),
                              lower=self.numerical_circuit.bus_data.angle_min,
                              upper=self.numerical_circuit.bus_data.angle_max)
        branch_rating_slack1 = pl.lpMakeVars(name='FSlack1', shape=(m, nt), lower=0, upper=None)
        branch_rating_slack2 = pl.lpMakeVars(name='FSlack2', shape=(m, nt), lower=0, upper=None)

        # declare problem ----------------------------------------------------------------------------------------------
        self.problem = LpProblem(name='DC_OPF_Time_Series')

        # set the fixed generation values ------------------------------------------------------------------------------
        set_fix_generation(problem=self.problem,
                           Pg=Pg,
                           P_profile=P_profile,
                           enabled_for_dispatch=enabled_for_dispatch)

        # compute the power injections ---------------------------------------------------------------------------------
        P = get_power_injections(C_bus_gen=self.numerical_circuit.generator_data.C_bus_gen,
                                 Pg=Pg,
                                 C_bus_bat=self.numerical_circuit.battery_data.C_bus_batt,
                                 Pb=Pb,
                                 C_bus_load=self.numerical_circuit.load_data.C_bus_load,
                                 LSlack=load_slack,
                                 Pl=Pl)

        # formulate the simple HVDC models -----------------------------------------------------------------------------
        hvdc_flow_f = formulate_hvdc_flow(problem=self.problem,
                                          angles=theta,
                                          Pinj=P,
                                          rates=self.numerical_circuit.hvdc_data.rate[:, a:b] / Sbase,
                                          active=self.numerical_circuit.hvdc_data.active[:, a:b],
                                          Pset=self.numerical_circuit.hvdc_data.Pset[:, a:b],
                                          control_mode=self.numerical_circuit.hvdc_data.control_mode,
                                          dispatchable=self.numerical_circuit.hvdc_data.dispatchable,
                                          angle_droop=self.numerical_circuit.hvdc_data.get_angle_droop_in_pu_rad(Sbase),
                                          F=self.numerical_circuit.hvdc_data.get_bus_indices_f(),
                                          T=self.numerical_circuit.hvdc_data.get_bus_indices_t(),
                                          Sbase=Sbase,
                                          logger=self.logger,
                                          inf=999999)

        # add branch restrictions --------------------------------------------------------------------------------------
        if self.zonal_grouping == ZonalGrouping.NoGrouping:
            flow_f, tau, Pinj_tau = add_branch_loading_restriction(problem=self.problem,
                                                                   nc=self.numerical_circuit,
                                                                   theta=theta,
                                                                   F=F,
                                                                   T=T,
                                                                   ratings=branch_ratings,
                                                                   ratings_slack_from=branch_rating_slack1,
                                                                   ratings_slack_to=branch_rating_slack2,
                                                                   monitored=self.numerical_circuit.branch_data.monitor_loading,
                                                                   active=br_active)

        elif self.zonal_grouping == ZonalGrouping.All:
            flow_f = np.zeros((self.numerical_circuit.nbr, nt))
            tau = np.ones((self.numerical_circuit.nbr, nt))
            Pinj_tau = np.zeros((self.numerical_circuit.nbr, nt))

        else:
            raise ValueError()

        # set the nodal restrictions -----------------------------------------------------------------------------------
        self.nodal_restrictions = formulate_dc_nodal_power_balance(numerical_circuit=self.numerical_circuit,
                                                                   problem=self.problem,
                                                                   theta=theta,
                                                                   P=P + Pinj_tau,   # add the phase shift injections
                                                                   start_=self.start_idx,
                                                                   end_=self.end_idx)

        # if there are batteries, add the batteries --------------------------------------------------------------------
        if nb > 0:
            add_battery_discharge_restriction(problem=self.problem,
                                              SoC0=SoC0,
                                              Capacity=Capacity,
                                              Efficiency=Efficiency,
                                              Pb=Pb, E=E, dt=dt)

        if self.consider_contingencies:
            con_flow_lst, con_overload1_lst, con_overload2_lst, \
            con_br_idx = formulate_contingency(problem=self.problem,
                                               numerical_circuit=self.numerical_circuit,
                                               flow_f=flow_f,
                                               ratings=branch_ratings,
                                               LODF=self.LODF,
                                               monitor=self.numerical_circuit.branch_data.monitor_loading,
                                               lodf_tolerance=self.lodf_tolerance)
        else:
            con_flow_lst = list()
            con_br_idx = list()
            con_overload1_lst = list()
            con_overload2_lst = list()

        # maximize the power from->to ----------------------------------------------------------------------------------
        if self.maximize_inter_area_flow:
            flow_from_a1_to_a2 = formulate_inter_area_flow(numerical_circuit=self.numerical_circuit,
                                                           buses_areas_1=self.buses_areas_1,
                                                           buses_areas_2=self.buses_areas_2,
                                                           flow_f=flow_f,
                                                           hvdc_flow_f=hvdc_flow_f)

            sum_gen_area_1, sum_gen_area_2 = formulate_area_generation_summations(
                numerical_circuit=self.numerical_circuit,
                buses_areas_1=self.buses_areas_1,
                buses_areas_2=self.buses_areas_2,
                Pg=Pg)

        else:
            flow_from_a1_to_a2 = None
            sum_gen_area_1 = None
            sum_gen_area_2 = None

        # add the objective function -----------------------------------------------------------------------------------
        self.problem += get_objective_function(Pg=Pg,
                                               Pb=Pb,
                                               LSlack=load_slack,
                                               FSlack1=branch_rating_slack1,
                                               FSlack2=branch_rating_slack2,
                                               FCSlack1=con_overload1_lst,
                                               FCSlack2=con_overload2_lst,
                                               flow_from_a1_to_a2=flow_from_a1_to_a2,
                                               sum_gen_area_1=sum_gen_area_1,
                                               sum_gen_area_2=sum_gen_area_2,
                                               cost_g=cost_g,
                                               cost_b=cost_b,
                                               cost_l=cost_l,
                                               cost_br=cost_br)

        # Assign variables to keep
        # transpose them to be in the format of GridCal: time, device
        self.theta = theta.transpose()
        self.Pg = Pg.transpose()
        self.Pb = Pb.transpose()
        self.Pl = Pl.transpose()

        self.Pinj = P.transpose()

        self.phase_shift = tau.transpose()

        self.hvdc_flow = hvdc_flow_f.transpose()

        self.E = E.transpose()
        self.load_shedding = load_slack.transpose()
        self.s_from = flow_f.transpose()
        self.s_to = -flow_f.transpose()
        self.overloads = (branch_rating_slack1 + branch_rating_slack2).transpose()
        self.rating = branch_ratings.T

        self.contingency_flows_list = con_flow_lst
        self.contingency_indices_list = con_br_idx  # [(t, m, c), ...]
        self.contingency_flows_slacks_list = con_overload1_lst


if __name__ == '__main__':

    from GridCal.Engine import *

    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'

    main_circuit = FileOpen(fname).open()

    # main_circuit.buses[3].controlled_generators[0].enabled_dispatch = False

    # get the power flow options from the GUI
    solver = SolverType.DC_OPF
    mip_solver = MIPSolvers.CBC
    grouping = TimeGrouping.Daily
    pf_options = PowerFlowOptions()

    options = OptimalPowerFlowOptions(solver=solver,
                                      time_grouping=grouping,
                                      mip_solver=mip_solver,
                                      power_flow_options=pf_options)

    start = 0
    end = len(main_circuit.time_profile)

    # create the OPF time series instance
    # if non_sequential:
    optimal_power_flow_time_series = OptimalPowerFlowTimeSeries(grid=main_circuit,
                                                                options=options,
                                                                start_=start,
                                                                end_=end)

    optimal_power_flow_time_series.run()

    v = optimal_power_flow_time_series.results.voltage
    print('Angles\n', np.angle(v))

    l = optimal_power_flow_time_series.results.loading
    print('Branch loading\n', l)

    g = optimal_power_flow_time_series.results.generator_power
    print('Gen power\n', g)

    pr = optimal_power_flow_time_series.results.shadow_prices
    print('Nodal prices \n', pr)

    import pandas as pd
    pd.DataFrame(optimal_power_flow_time_series.results.loading).to_excel('opf_loading.xlsx')