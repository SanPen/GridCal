from pulp import *
import numpy as np
import pandas as pd
from scipy.sparse import lil_matrix, csc_matrix, diags
from itertools import product

from Ordena2.engine.enumerations import TimeFrame
from Ordena2.engine.model.asset_model import AssetsModel, DeviceType
from Ordena2.engine.solvers.short_term_general import GeneralSolver, ProblemResults, ProblemOptions


class PulpSolver(GeneralSolver):

    def __init__(self, problem: AssetsModel, options: ProblemOptions):
        """

        :param problem:
        :param options:
        """
        GeneralSolver.__init__(self, problem=problem, options=options)

        # Node balance constraints
        self.node_constraint = list()

        self.results = None

    def add_transmission_grid(self, t, prob, F, T, Ybus, pqpv, slack, theta, node_power, node_power_balance, P_bus,
                              load_slack_at_the_buses, price_power_at_the_buses, branch_rates,
                              Fij, Fji, Fij_slack_p, Fji_slack_p, Fij_slack_n, Fji_slack_n):
        """
        Adds the linear power flow equations with the branch flow limits
        :param t: time step
        :param prob: PuLP problem
        :param F: vector of "from" bus indices for every branch
        :param T: vector of "to" bus indices for every branch
        :param theta: matrix of voltage angles (LPVars)
        :param node_power: Matrix of grid restrictions (empty)
        :param node_power_balance:
        :param P_bus:
        :param load_slack_at_the_buses:
        :param price_power_at_the_buses:
        :param branch_rates:
        :param Fij:
        :param Fji:
        :param Fij_slack_p:
        :param Fji_slack_p:
        :return:
        """

        B = -Ybus.imag
        pqpv = pqpv
        slack = slack

        ############################################################################################################
        # PQPV Node power balance constraints
        ############################################################################################################
        node_power[t, pqpv] = self.Cproduct(B[pqpv, :][:, pqpv], theta[t, pqpv])

        for i in pqpv:
            node_power_balance[t, i] = (node_power[t, i] == P_bus[i, t] + price_power_at_the_buses[i, t] - load_slack_at_the_buses[i, t])
            prob.add(node_power_balance[t, i], 'ct_node_mismatch_N' + str(i + 1) + '_t' + str(t))

        ############################################################################################################
        #  set the slack nodes voltage angle
        ############################################################################################################
        for i in slack:
            prob.add(theta[t, i] == 0, 'ct_slack_theta_' + str(i) + '_t' + str(t))

        ############################################################################################################
        #  set the slack generator power
        #  Node power balance in the slack
        ############################################################################################################
        for i in slack:
            node_power[t, i] = self.Cproduct(B[i, :], theta[t, :])[0]

            node_power_balance[t, i] = (node_power[t, i] == P_bus[i, t] + price_power_at_the_buses[i, t])
            prob.add(node_power_balance[t, i], 'ct_slack_power_N' + str(i + 1) + '_t' + str(t))

        ############################################################################################################
        # Set the branch limits
        ############################################################################################################
        for k in range(branch_rates.shape[1]):
            i = F[k]
            j = T[k]

            # branch flow
            Fij[t, k] = B[i, j] * (theta[t, i] - theta[t, j])
            Fji[t, k] = B[i, j] * (theta[t, j] - theta[t, i])

            # constraints
            prob.add(Fij[t, k] + Fij_slack_p[t, k] - Fij_slack_n[t, k] <= branch_rates[t, k],
                     'ct_flow_from_Br' + str(k + 1) + '_t' + str(t))
            prob.add(Fji[t, k] + Fji_slack_p[t, k] - Fji_slack_n[t, k] <= branch_rates[t, k],
                     'ct_flow_to_Br' + str(k + 1) + '_t' + str(t))

            # prob.add(Fij[t, k] <= branch_rates[t, k], 'ct_flow_from_Br' + str(k + 1) + '_t' + str(t))
            # prob.add(Fji[t, k] <= branch_rates[t, k], 'ct_flow_to_Br' + str(k + 1) + '_t' + str(t))

    def add_power_balance(self, t, prob, node_power, P_bus, load_slack_at_the_buses, price_power_at_the_buses):
        """
        Adds the linear power flow equations with the branch flow limits
        :param t: time step
        :param prob: PuLP problem
        :param node_power: Matrix of grid restrictions (empty)
        :param P_bus:
        :param load_slack_at_the_buses:
        :param price_power_at_the_buses:
        :return:
        """

        ############################################################################################################
        # PQPV Node power balance constraints
        ############################################################################################################

        res = (0 == lpSum(P_bus[:, t]) + price_power_at_the_buses[:, t] - lpSum(load_slack_at_the_buses[:, t]))
        prob.add(res, 'ct_power_balance_N' + str(+ 1) + '_t' + str(t + 1))

    def solve(self):
        """
        Solve the problem
        :return:
        """
        prob = LpProblem("security market dispatch", LpMinimize)
        fobj = 0

        # compile the assets into arrays
        numerical = self.problem.compile()
        # get start and ending time indices
        t_min, t_max = self.options.start_, self.options.end_
        time = self.problem.time_profile[TimeFrame.ShortTerm].astype(float) / 1e9 / 3600  # unix time array in hours
        nt = numerical.electric.nt
        # nt = t_max - t_min
        n_bus = numerical.electric.n_bus
        n_br = numerical.electric.n_br
        n_gen = len(numerical.electric.P_gen)
        n_price = numerical.electric.n_price
        n_load = len(numerical.electric.P_load)
        Sbase = numerical.electric.Sbase

        # indices of the generators' array where there is a hydro plant
        hydro_elec_idx = np.where(numerical.electric.gen_types == DeviceType.HydroPlantDevice.value)[0]
        n_elec_hydro = len(hydro_elec_idx)  # number of electric hydro plants

        # if the end is None, then set it to the maximum value
        if t_max is None:
            t_max = nt

        bus_names = [elm.name for elm in self.problem.electrical_grid.buses]
        branch_names = [elm.name for elm in self.problem.electrical_grid.branches]

        self.results = ProblemResults(time_array=self.problem.time_profile[TimeFrame.ShortTerm],
                                      nbus=n_bus,
                                      nbr=n_br,
                                      ngen=n_gen,
                                      nload=n_load,
                                      nhydro=n_elec_hydro,
                                      nprice=n_price)

        ################################################################################################################
        # exit conditions
        ################################################################################################################
        if n_bus == 0:  # or (n_gen + n_price) == 0 or n_load == 0:
            self.success = False
            return self.results

        ################################################################################################################
        # Create the generation variables
        ################################################################################################################

        # get the generation and scale it with Sbase
        generator_power = numerical.electric.P_gen.copy().astype(object) / Sbase

        # primary, secondary and tertiary availabilities per generator and time slot
        pr_generator_power = np.empty((n_gen, nt), dtype=object)
        sr_generator_power = np.empty((n_gen, nt), dtype=object)
        tr_generator_power = np.empty((n_gen, nt), dtype=object)

        gen_max = numerical.electric.p_max_gen / Sbase

        # find where the generators are dispatchable to replace the generation values by an LP variable
        wh = np.where(numerical.electric.dispatchable_gen == 1)
        for i, t in zip(*wh):  # i: generator index, t: time step
            name = 'Gen ' + str(i) + '_' + str(t)
            generator_power[i, t] = LpVariable(name, lowBound=0, upBound=gen_max[i])

            pr_generator_power[i, t] = LpVariable('Pr' + name, lowBound=0, upBound=gen_max[i])
            sr_generator_power[i, t] = LpVariable('Sr' + name, lowBound=0, upBound=gen_max[i])
            tr_generator_power[i, t] = LpVariable('Tr' + name, lowBound=0, upBound=gen_max[i])

        # declare the water level arrays
        ramp_up_slack = np.empty((n_gen, nt), dtype=object)
        ramp_down_slack = np.empty((n_gen, nt), dtype=object)

        # fill in the subsequent states with LP variables
        for i, t in product(range(n_gen), range(nt)):
            suffix = str(i) + '_' + str(t)
            # ramp_up_slack[i, t] = LpVariable('Gen_rup_' + suffix, lowBound=0, upBound=gen_max[i])
            # ramp_down_slack[i, t] = LpVariable('Gen_rdwn_' + suffix, lowBound=0, upBound=gen_max[i])

            ramp_up_slack[i, t] = LpVariable('Gen_rup_' + suffix, lowBound=0, upBound=None)
            ramp_down_slack[i, t] = LpVariable('Gen_rdwn_' + suffix, lowBound=0, upBound=None)

        # apply the generation availability
        generator_power *= numerical.electric.state_gen

        # generation at the buses (might contain LPVars and numbers)
        generation_at_the_buses = self.Cproduct(csc_matrix(numerical.electric.C_bus_gen), generator_power)

        # reserves' slacks
        pr_slack_pos = np.empty(nt, dtype=object)
        sr_slack_pos = np.empty(nt, dtype=object)
        tr_slack_pos = np.empty(nt, dtype=object)
        pr_slack_neg = np.empty(nt, dtype=object)
        sr_slack_neg = np.empty(nt, dtype=object)
        tr_slack_neg = np.empty(nt, dtype=object)

        for t in range(nt):
            pr_slack_pos[t] = LpVariable('Pr_slack_p' + str(t), lowBound=0, upBound=None)
            sr_slack_pos[t] = LpVariable('Sr_slack_p' + str(t), lowBound=0, upBound=None)
            tr_slack_pos[t] = LpVariable('Tr_slack_p' + str(t), lowBound=0, upBound=None)

            pr_slack_neg[t] = LpVariable('Pr_slack_n' + str(t), lowBound=0, upBound=None)
            sr_slack_neg[t] = LpVariable('Sr_slack_n' + str(t), lowBound=0, upBound=None)
            tr_slack_neg[t] = LpVariable('Tr_slack_n' + str(t), lowBound=0, upBound=None)

        ################################################################################################################
        # Create the load variables
        ################################################################################################################

        # get the generation and scale it with Sbase
        load_power = numerical.electric.P_load / Sbase

        # primary, secondary and tertiary power needs per time slot (aggregated for all loads...)
        pr_power = (numerical.electric.pr_factor_prof * load_power).sum(axis=0)
        sr_power = (numerical.electric.sr_factor_prof * load_power).sum(axis=0)
        tr_power = (numerical.electric.tr_factor_prof * load_power).sum(axis=0)

        # declare the load slacks that will be filled where the loads are dispatchable
        Pload_slack = np.zeros((n_load, nt), dtype=object)

        # find where the generators are dispatchable to replace the generation values by an LP variable
        wh = np.where(numerical.electric.dispatchable_load == 1)
        for i, t in zip(*wh):  # i: generator index, t: time step
            name = 'Load_curtail ' + str(i) + '_' + str(t)
            Pload_slack[i, t] = LpVariable(name, lowBound=0, upBound=None)

        # apply the load availability
        Pload_slack *= numerical.electric.state_load
        load_power *= numerical.electric.state_load

        # generation at the buses (might contain LPVars and numbers)
        load_at_the_buses = self.Cproduct(csc_matrix(numerical.electric.C_bus_load), load_power)
        load_slack_at_the_buses = self.Cproduct(csc_matrix(numerical.electric.C_bus_load), Pload_slack)

        ################################################################################################################
        # merge all power values variables
        ################################################################################################################
        power_at_the_buses = generation_at_the_buses - load_at_the_buses  # per unit power at the buses

        ################################################################################################################
        # Create the hydro nodes' variables (reservoirs + hydro plants)!
        ################################################################################################################

        n_hydro_nodes = len(numerical.water.nodes)

        # declare the water level arrays
        hydro_water = np.empty((n_hydro_nodes, nt), dtype=object)
        hydro_slack_p = np.empty((n_hydro_nodes, nt), dtype=object)
        hydro_slack_n = np.empty((n_hydro_nodes, nt), dtype=object)

        # set the initial water state
        # hydro_water[:, 0] = numerical.water.water_state

        # fill in the subsequent states with LP variables
        for i, t in product(range(n_hydro_nodes), range(nt)):
            name = 'HydroWater_' + str(i) + '_' + str(t)
            hydro_water[i, t] = LpVariable(name,
                                           lowBound=numerical.water.water_min[i],
                                           upBound=numerical.water.water_max[i])
            name = 'HydroSlackP_' + str(i) + '_' + str(t)
            hydro_slack_p[i, t] = LpVariable(name, lowBound=0, upBound=None)
            name = 'HydroSlackN_' + str(i) + '_' + str(t)
            hydro_slack_n[i, t] = LpVariable(name, lowBound=0, upBound=None)

        ################################################################################################################
        # Create the price device variables
        ################################################################################################################

        # create the price devices' power variables
        Pprice = np.empty((n_price, nt), dtype=object)
        for i, t in product(range(n_price), range(nt)):  # i: generator index, t: time step
            name = 'PricePower_' + str(i) + '_' + str(t)
            Pprice[i, t] = LpVariable(name,
                                      lowBound=numerical.electric.Price_device_pmin[i, t] / Sbase,
                                      upBound=numerical.electric.Price_device_pmax[i, t] / Sbase)

        # apply the generation availability
        Pprice *= numerical.electric.state_price

        # generation at the buses (might contain LPVars and numbers)
        price_power_at_the_buses = self.Cproduct(csc_matrix(numerical.electric.C_bus_price), Pprice)

        ################################################################################################################
        # Create the voltage variables
        ################################################################################################################
        theta = np.empty((nt, n_bus), dtype=object)
        for t, i in product(range(nt), range(n_bus)):
            name = 'Theta ' + str(i) + '_t' + str(t)
            theta[t, i] = LpVariable(name, -3, 3)

        ################################################################################################################
        # Create the node power balance variables
        ################################################################################################################
        node_power = np.zeros((nt, n_bus), dtype=object)
        node_power_balance = np.zeros((nt, n_bus), dtype=object)

        ################################################################################################################
        # Create the flow variables
        ################################################################################################################
        flow_ij = np.empty((nt, n_br), dtype=object)
        flow_ji = np.empty((nt, n_br), dtype=object)
        flow_ij_slack_p = np.empty((nt, n_br), dtype=object)
        flow_ji_slack_p = np.empty((nt, n_br), dtype=object)
        flow_ij_slack_n = np.empty((nt, n_br), dtype=object)
        flow_ji_slack_n = np.empty((nt, n_br), dtype=object)
        branch_rates = numerical.electric.br_rates / Sbase
        for t, i in product(range(nt), range(n_br)):
            suffix = str(i) + '_t' + str(t)
            br_rate = branch_rates[t, i]
            flow_ij[t, i] = LpVariable("Fij" + suffix, -br_rate, br_rate)
            flow_ji[t, i] = LpVariable("Fji" + suffix, -br_rate, br_rate)
            flow_ij_slack_p[t, i] = LpVariable("Fij_slack_p_" + suffix, lowBound=0)
            flow_ji_slack_p[t, i] = LpVariable("Fji_slack_p_" + suffix, lowBound=0)
            flow_ij_slack_n[t, i] = LpVariable("Fij_slack_n_" + suffix, lowBound=0)
            flow_ji_slack_n[t, i] = LpVariable("Fji_slack_n_" + suffix, lowBound=0)

        ################################################################################################################
        # Add the objective function
        ################################################################################################################

        if n_gen > 0:

            # Generation costs: the units are MW * €/MWh (we could think of this as €)
            fobj += lpSum(lpSum((generator_power * numerical.electric.cost_gen)[:, t_min:t_max]))

            if self.options.use_ramps:
                fobj += lpSum(lpSum(ramp_up_slack[:, t_min:t_max]))
                fobj += lpSum(lpSum(ramp_down_slack[:, t_min:t_max]))

        if n_load > 0:
            fobj += lpSum(lpSum(Pload_slack[:, t_min:t_max]))

        if n_price > 0:
            fobj += lpSum(lpSum((Pprice * numerical.electric.Price_device_values)[:, t_min:t_max]))

        if self.options.use_frequency_regulation:
            fobj += lpSum(pr_slack_pos[t_min:t_max]) + lpSum(pr_slack_neg[t_min:t_max])
            fobj += lpSum(sr_slack_pos[t_min:t_max]) + lpSum(sr_slack_neg[t_min:t_max])
            fobj += lpSum(tr_slack_pos[t_min:t_max]) + lpSum(tr_slack_neg[t_min:t_max])

        if self.options.use_transmission_grid:
            fobj += lpSum(flow_ij_slack_p[t_min:t_max, :]) + lpSum(flow_ij_slack_n[t_min:t_max, :])
            fobj += lpSum(flow_ji_slack_p[t_min:t_max, :]) + lpSum(flow_ji_slack_n[t_min:t_max, :])

        if n_elec_hydro > 0:
            fobj += lpSum(lpSum(hydro_slack_p[:, t_min:t_max]))
            fobj += lpSum(lpSum(hydro_slack_n[:, t_min:t_max]))

        # add the objection function to the problem
        prob += fobj

        # For every time step ...
        for t in range(t_min, t_max):

            if t > t_min:

                # compute the time increment in hours
                dt = time[t] - time[t - 1]

                ########################################################################################################
                # Ramp restrictions on the generators
                ########################################################################################################
                if self.options.use_ramps:
                    for i in range(n_gen):
                        suffix = str(i) + '_t' + str(t)
                        r_up = (generator_power[i, t] <= generator_power[i, t - 1] + numerical.electric.gen_ramp_up[i] * dt + ramp_up_slack[i, t])
                        r_down = (generator_power[i, t] >= generator_power[i, t - 1] - numerical.electric.gen_ramp_down[i] * dt - ramp_down_slack[i, t])
                        prob.add(r_up, name='Rup_' + suffix)
                        prob.add(r_down, name='Rdw_' + suffix)

                else:
                    pass  # no ramp constraints

                ########################################################################################################
                # Hydro capacity constraints
                ########################################################################################################
                # hydro_water_per_node: MW * h * (m3/MWh) = m3
                hydro_water_per_node = np.zeros(len(numerical.water.nodes), dtype=object)

                # water "used" by the hydro plants themselves
                hydro_water_per_node[numerical.water.hydro_plant_idx] = generator_power[hydro_elec_idx, t - 1] * dt * numerical.electric.hydro_production_rate

                # water at the sending sides of the river sections
                sections_water = hydro_water_per_node[numerical.water.F]

                # water increment at each node due to other's water flow
                water_delta = self.Cproduct(numerical.water.C_node_branch, sections_water)

                # add the reservoir nodal inflows: m3/h * h = m3
                water_delta += numerical.water.nodal_inflows[t, :] * dt

                for i in range(n_hydro_nodes):  # i: hydro index, k: index in the generators array

                    # perform the water balance
                    w_res = (hydro_water[i, t] == hydro_water[i, t - 1] + water_delta[i] + hydro_slack_p[i, t] - hydro_slack_n[i, t])

                    suffix = str(i) + '_t' + str(t)
                    prob += LpConstraint(w_res, name='Water_balance_' + suffix)

            else:
                pass  # first time step

                for i in range(n_hydro_nodes):  # i: hydro index, k: index in the generators array

                    # perform the water balance
                    w_res = (hydro_water[i, t] == numerical.water.water_state[i])

                    suffix = str(i) + '_t' + str(t)
                    prob += LpConstraint(w_res, name='Water_balance_' + suffix)

            ############################################################################################################
            # Electric power balance (linear power flow or simple power summation)
            ############################################################################################################
            if self.options.use_transmission_grid:
                # linear power flow with losses

                if len(numerical.electric.islands[t]) == 1:
                    self.add_transmission_grid(t=t,
                                               prob=prob,
                                               F=numerical.electric.islands[t][0].F,
                                               T=numerical.electric.islands[t][0].T,
                                               Ybus=numerical.electric.islands[t][0].Ybus,
                                               pqpv=numerical.electric.islands[t][0].pqpv,
                                               slack=numerical.electric.islands[t][0].slack,
                                               theta=theta,
                                               node_power=node_power,
                                               node_power_balance=node_power_balance,
                                               P_bus=power_at_the_buses,
                                               load_slack_at_the_buses=load_slack_at_the_buses,
                                               price_power_at_the_buses=price_power_at_the_buses,
                                               branch_rates=branch_rates,
                                               Fij=flow_ij,
                                               Fji=flow_ji,
                                               Fij_slack_p=flow_ij_slack_p,
                                               Fji_slack_p=flow_ji_slack_p,
                                               Fij_slack_n=flow_ij_slack_n,
                                               Fji_slack_n=flow_ji_slack_n)
                else:

                    for island in numerical.electric.islands[t]:

                        self.add_transmission_grid(t=t,
                                                   prob=prob,
                                                   F=island.F,
                                                   T=island.T,
                                                   Ybus=island.Ybus,
                                                   pqpv=island.pqpv,
                                                   slack=island.slack,
                                                   theta=theta[island.bus_idx],
                                                   node_power=node_power[island.bus_idx],
                                                   node_power_balance=node_power_balance[island.bus_idx],
                                                   P_bus=power_at_the_buses[island.bus_idx],
                                                   load_slack_at_the_buses=load_slack_at_the_buses[island.bus_idx],
                                                   price_power_at_the_buses=price_power_at_the_buses[island.bus_idx],
                                                   branch_rates=branch_rates[island.br_idx],
                                                   Fij=flow_ij[island.br_idx],
                                                   Fji=flow_ji[island.br_idx],
                                                   Fij_slack_p=flow_ij_slack_p[island.br_idx],
                                                   Fji_slack_p=flow_ji_slack_p[island.br_idx],
                                                   Fij_slack_n=flow_ij_slack_n[island.br_idx],
                                                   Fji_slack_n=flow_ji_slack_n[island.br_idx] )

            else:
                # simple power balance restriction
                self.add_power_balance(t=t,
                                       prob=prob,
                                       node_power=node_power,
                                       P_bus=power_at_the_buses,
                                       load_slack_at_the_buses=load_slack_at_the_buses,
                                       price_power_at_the_buses=price_power_at_the_buses)

            ############################################################################################################
            # Electric reserves balance
            ############################################################################################################
            if self.options.use_frequency_regulation:

                pr_gen = lpSum(pr_generator_power[:, t])
                sr_gen = lpSum(sr_generator_power[:, t])
                tr_gen = lpSum(tr_generator_power[:, t])

                prob.add(pr_gen + pr_slack_pos[t] - pr_slack_neg[t] == pr_power[t], name='C_pr_' + str(t))
                prob.add(sr_gen + sr_slack_pos[t] - sr_slack_neg[t] == sr_power[t], name='C_sr_' + str(t))
                prob.add(tr_gen + tr_slack_pos[t] - tr_slack_neg[t] == tr_power[t], name='C_tr_' + str(t))

                # Electric reserves balance per generator
                for i in range(n_gen):
                    band = generator_power[i, t] + pr_generator_power[i, t] + sr_generator_power[i, t] + tr_generator_power[i, t]
                    prob.add(band <= gen_max[i], name='band_balance_' + str(i) + '_' + str(t))

        ################################################################################################################
        # Solve
        ################################################################################################################
        prob.writeLP('short_term_pulp.lp')
        prob.solve()  # solve with CBC
        #        prob.solve(CPLEX())

        # The status of the solution is printed to the screen
        print("Status:", LpStatus[prob.status])

        # The optimised objective function value is printed to the screen
        print("Cost =", value(prob.objective), '€')

        ################################################################################################################
        # Gather bus based results
        ################################################################################################################
        self.results.bus_names = bus_names
        self.results.voltage_angles = np.zeros((nt, n_bus))
        self.results.node_power = np.zeros((nt, n_bus))
        self.results.node_dual_price = np.zeros((nt, n_bus))

        for t, i in product(range(t_min, t_max), range(n_bus)):

            self.results.voltage_angles[t, i] = theta[t, i].value()

            if hasattr(node_power[t, i], 'value'):
                self.results.node_power[t, i] = node_power[t, i].value() * Sbase
                self.results.node_dual_price[t, i] = -node_power_balance[t, i].pi
            else:
                self.results.node_power[t, i] = node_power[t, i] * Sbase

        self.results.voltage_modules = np.ones((nt, n_bus), dtype=float)

        ################################################################################################################
        # Gather Branch based results
        ################################################################################################################
        self.results.branch_names = branch_names
        self.results.loading = np.zeros((nt, n_br))
        self.results.branch_power = np.zeros((nt, n_br))
        self.results.branch_power_overload = np.zeros((nt, n_br))

        # Compute the total losses: The computed slack power includes the losses in this model
        total_losses = self.results.node_power.sum(axis=1)

        # normalized impedance vector to sum 1 and spare the losses accordingly
        br_z_norm = numerical.electric.br_impedance / numerical.electric.br_impedance.sum()

        for t, i in product(range(t_min, t_max), range(n_br)):

            if self.options.use_transmission_grid:
                self.results.branch_power[t, i] = np.abs(flow_ji[t, i].value()) * Sbase
                self.results.branch_power_overload[t, i] = (flow_ij_slack_p[t, i].value()
                                                            + flow_ij_slack_n[t, i].value()
                                                            + flow_ji_slack_p[t, i].value()
                                                            + flow_ji_slack_n[t, i].value()) * Sbase
                self.results.loading[t, i] = self.results.branch_power[t, i] / Sbase / branch_rates[t, i]

                # these are already in MW since the power is in MW
                self.results.losses[t, i] = abs(total_losses[t] * br_z_norm[i])

        ################################################################################################################
        # Gather generator based results
        ################################################################################################################
        self.results.generator_names = numerical.electric.gen_names
        self.results.gen_power = np.zeros((nt, n_gen))
        self.results.gen_ramp_slack = np.zeros((nt, n_gen), dtype=float)
        self.results.gen_indices_by_type = numerical.electric.gen_indices_by_type
        for t, i in product(range(t_min, t_max), range(n_gen)):
            if hasattr(generator_power[i, t], 'value'):
                self.results.gen_power[t, i] = generator_power[i, t].value() * Sbase
            else:
                self.results.gen_power[t, i] = generator_power[i, t] * Sbase

            if ramp_up_slack[i, t].value() is not None:
                self.results.gen_ramp_slack[t, i] = (ramp_up_slack[i, t].value() - ramp_down_slack[i, t].value()) * Sbase

            if pr_generator_power[i, t].value() is not None:
                self.results.gen_pr[t, i] = pr_generator_power[i, t].value() * Sbase
                self.results.gen_sr[t, i] = sr_generator_power[i, t].value() * Sbase
                self.results.gen_tr[t, i] = tr_generator_power[i, t].value() * Sbase

        ################################################################################################################
        # Price devices' results
        ################################################################################################################

        self.results.price_power = np.zeros((nt, n_price), dtype=float)
        self.results.price_names = numerical.electric.price_devices_names
        for t, i in product(range(t_min, t_max), range(n_price)):
            self.results.price_power[t, i] = Pprice[i, t].value() * Sbase

        ################################################################################################################
        # Gather hydro based results
        ################################################################################################################
        self.results.hydro_names = np.array(numerical.water.node_names)
        self.results.hydro_water = np.zeros((nt, n_hydro_nodes))
        self.results.hydro_water_slack = np.zeros((nt, n_hydro_nodes))
        for t, i in product(range(t_min, t_max), range(n_hydro_nodes)):

            # hydro_water
            if hasattr(hydro_water[i, t], 'value'):
                self.results.hydro_water[t, i] = hydro_water[i, t].value()
                self.results.hydro_water_slack[t, i] = hydro_slack_p[i, t].value() - hydro_slack_n[i, t].value()

        ################################################################################################################
        # Gather load based results
        ################################################################################################################
        self.results.load_names = numerical.electric.load_names
        self.results.load_power = np.zeros((nt, n_load))
        self.results.load_curtailed_power = np.zeros((nt, n_load))
        for t, i in product(range(t_min, t_max), range(n_load)):
            self.results.load_power[t, i] = load_power[i, t] * Sbase
            if Pload_slack[i, t] != 0:
                self.results.load_curtailed_power[t, i] = Pload_slack[i, t].value()

        self.results.load_pr = pr_power * Sbase
        self.results.load_sr = sr_power * Sbase
        self.results.load_tr = tr_power * Sbase

        # link the new result arrays to the internal dictionary
        self.results.link_results()

        self.success = True
        return self.results

    def dual_prices_df(self):
        """

        Get the stored restrictions dual prices

        DUAL PRICE DEFINITION:

        The dual prices are some of the most interesting values in the solution to a linear program.
        A dual price is reported for each constraint. The dual price is only positive when a constraint is binding.

        The dual price gives the improvement in the objective function if the constraint is relaxed by one unit.

        In the case of a less-than-or-equal constraint, such as a resource constraint, the dual price gives the value
        of having one more unit of the resource represented by that constraint. In the case of a greater-than-or-equal
        constraint, such as a minimum production level constraint, the dual price gives the cost of meeting the last
        unit of the minimum production target.

        The units of the dual prices are the units of the objective function divided by the units of the constraint.
        Knowing the units of the dual prices can be useful when you are trying to interpret what the dual prices mean.

        :return: pandas DataFrame
        """
        T = len(self.time)
        data = np.zeros((T, self.nbus))

        # the units are €/MWh
        for t in range(T):
            for i in range(self.nbus):
                data[t, i] = self.node_constraint[t][i].pi  # '.pi' is the dual value of the constraint

        cols = [node.name for node in self.nodes]

        return pd.DataFrame(data, index=self.time, columns=cols)

    def print(self, t):
        """
        Print the problem
        """
        self.results.print(t=t)

