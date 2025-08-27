# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import numba as nb
from scipy.sparse import lil_matrix
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.basic_structures import Vec, IntVec, StrVec, IntMat
from VeraGridEngine.Simulations.InvestmentsEvaluation.Problems.black_box_problem_template import BlackBoxProblemTemplate
from VeraGridEngine.Simulations.Reliability.reliability import reliability_simulation
from VeraGridEngine.Simulations.OPF.simple_dispatch_ts import GreedyDispatchInputs, greedy_dispatch2


@nb.njit(cache=True)
def correct_x(x, lb, ub):
    """
    Correct x in place to the given boundaries
    :param x:
    :param lb:
    :param ub:
    :return:
    """
    for i in range(len(x)):
        if x[i] < lb[i]:
            x[i] = lb[i]
        elif x[i] > ub[i]:
            x[i] = ub[i]


@nb.njit(cache=True)
def apply_actives_mask(original_active: IntMat, mask_indices: IntVec, mask: IntVec, years_starts_indices: IntVec):
    """

    :param original_active:
    :param mask_indices:
    :param mask: x applied to generators or batteries (goes from 0 to N-years + 1)
    :param years_starts_indices: array saying in which profile index starts each year
    :return:
    """
    active = original_active.copy()
    for i in mask_indices:
        if mask[i] == 0:
            active[:, i] = 0
        else:
            start = years_starts_indices[int(mask[i]) - 1]
            active[:start, i] = 0  # deactivate until start
            active[start:, i] = 1  # activate from start onwards

    return active


def determine_starting_index_of_every_year(index) -> IntVec:
    """
    Find the index where each different year starts
    :param index:
    :return:
    """
    indices = list()
    year_prev = index[0].year
    indices.append(0)
    for i, entry in enumerate(index):
        if entry.year != year_prev:
            year_prev = entry.year
            indices.append(i)

    return np.array(indices)


class AdequacyInvestmentProblem(BlackBoxProblemTemplate):

    def __init__(self,
                 grid: MultiCircuit,
                 n_monte_carlo_sim=10000,
                 use_monte_carlo: bool = True,
                 minimum_firm_share: float = 0.2,
                 use_firm_capacity_penalty: bool = True,
                 save_file: bool = True,
                 time_indices: IntVec | None = None):
        """

        :param grid:
        :param n_monte_carlo_sim:
        :param use_monte_carlo:
        :param minimum_firm_share: minimum share of firm capacity in p.u.
        :param use_firm_capacity_penalty: if to use the firm capacity penalty
        :param save_file:
        :param time_indices: array of time indices to use, if None all are used
        """
        super().__init__(grid=grid,
                         x_dim=len(grid.investments_groups),
                         plot_x_idx=1, plot_y_idx=2)

        # options object
        self.n_monte_carlo_sim = n_monte_carlo_sim
        self.use_monte_carlo = use_monte_carlo
        self.minimum_firm_share: float = minimum_firm_share
        self.use_firm_capacity_penalty: bool = use_firm_capacity_penalty
        self.save_file = save_file
        self.time_indices = time_indices

        if self.save_file:
            self.output_f = open("adequacy_output.csv", "w")
        else:
            self.output_f = None

        # --------------------------------------------------------------------------------------------------------------
        # gather problem structures
        # --------------------------------------------------------------------------------------------------------------

        self.greedy_dispatch_inputs = GreedyDispatchInputs(grid=self.grid,
                                                           time_indices=self.time_indices,
                                                           logger=self.logger)

        self.years_starts_indices = determine_starting_index_of_every_year(index=self.grid.time_profile)
        years = len(self.years_starts_indices)
        self.x_max *= years  # 0 is for not investing, any other number is for the year of entrance

        self.total_load = np.sum(self.greedy_dispatch_inputs.load_profile)

        self.inv_group_capex = self.grid.get_capex_by_investment_group()

        nc = compile_numerical_circuit_at(self.grid, t_idx=None)
        self.gen_mttf = nc.generator_data.mttf
        self.gen_mttr = nc.generator_data.mttr
        self.gen_capex = nc.generator_data.capex * nc.generator_data.snom  # CAPEX in $
        self.batt_capex = nc.battery_data.capex * nc.battery_data.snom
        self.dim = len(self.grid.investments_groups)

        if self.output_f is not None:
            # write header
            self.output_f.write("n_inv,LOLE(MWh),CAPEX(M$),"
                                + ",".join(self.grid.get_investment_groups_names()) + "\n")

        self.dt = self.grid.get_time_deltas_in_hours()
        gen_dict = {idtag: idx for idx, idtag in enumerate(nc.generator_data.idtag)}
        batt_dict = {idtag: idx for idx, idtag in enumerate(nc.battery_data.idtag)}
        inv_group_dict = self.grid.get_investment_by_groups_index_dict()

        self.dim2gen = lil_matrix((nc.generator_data.nelm, self.dim))
        self.dim2batt = lil_matrix((nc.battery_data.nelm, self.dim))
        self.inv_gen_idx = list()
        self.inv_batt_idx = list()

        for inv_group_idx, invs in inv_group_dict.items():
            for investment in invs:
                gen_idx = gen_dict.get(investment.device_idtag, None)
                if gen_idx is not None:
                    self.dim2gen[gen_idx, inv_group_idx] = 1
                    self.inv_gen_idx.append(gen_idx)

                else:
                    batt_idx = batt_dict.get(investment.device_idtag, None)
                    if batt_idx is not None:
                        self.dim2batt[batt_idx, inv_group_idx] = 1
                        self.inv_batt_idx.append(batt_idx)

        self.inv_gen_idx = np.array(self.inv_gen_idx)
        self.inv_batt_idx = np.array(self.inv_batt_idx)

        self.branches_cost = np.array([e.Cost for e in
                                       grid.get_branches(add_hvdc=False, add_vsc=False, add_switch=True)],
                                      dtype=float)

    def n_objectives(self) -> int:
        """
        Number of objectives (size of f)
        :return:
        """
        if self.use_firm_capacity_penalty:
            return 5
        else:
            return 4

    def n_vars(self) -> int:
        """
        Number of variables (size of x)
        :return:
        """
        return self.x_dim

    def get_objectives_names(self) -> StrVec:
        """
        Get a list of names for the elements of f
        :return:
        """
        if self.use_firm_capacity_penalty:
            return np.array(["LOLE",
                             "CAPEX",
                             "Unitary electricity cost",
                             "Curtailment",
                             "Firm capacity penalty"])
        else:
            return np.array(["LOLE",
                             "CAPEX",
                             "Unitary electricity cost",
                             "Curtailment"])

    def get_vars_names(self) -> StrVec:
        """
        Get a list of names for the elements of x
        :return:
        """
        return np.array([e.name for e in self.grid.investments_groups])

    def objective_function(self, x: Vec | IntVec) -> Vec:
        """
        Evaluate x and return f(x)
        :param x: array of variable values
        :return: array of objectives
        """
        # correct x
        correct_x(x=x, lb=self.x_min, ub=self.x_max)

        x_bin = x.astype(bool).astype(float)
        gen_mask = self.dim2gen @ x
        batt_mask = self.dim2batt @ x

        # compute the firm capacity
        if self.use_firm_capacity_penalty:
            # a generator is "firm" if it is dispatchable
            P_firm = np.sum(self.greedy_dispatch_inputs.gen_dispatchable
                            * gen_mask
                            * self.greedy_dispatch_inputs.gen_p_max)

            P_total = np.sum(gen_mask * self.greedy_dispatch_inputs.gen_p_max)
            if P_total > 0:
                firm_share = P_firm / P_total

                if firm_share < self.minimum_firm_share:
                    # the penalty is the difference scaled by 1000
                    firm_capacity_penalty = (self.minimum_firm_share - firm_share) * 1000.0
                else:
                    firm_capacity_penalty = 0.0
            else:
                firm_capacity_penalty = 0.0
        else:
            firm_capacity_penalty = 0.0

            # get the active arrays of generators and batteries
        gen_active = apply_actives_mask(original_active=self.greedy_dispatch_inputs.gen_active,
                                        mask_indices=self.inv_gen_idx,
                                        mask=gen_mask,
                                        years_starts_indices=self.years_starts_indices)

        batt_active = apply_actives_mask(original_active=self.greedy_dispatch_inputs.batt_active,
                                         mask_indices=self.inv_batt_idx,
                                         mask=batt_mask,
                                         years_starts_indices=self.years_starts_indices)

        # batt_pmax = self.greedy_dispatch_inputs.batt_p_max_charge.copy()
        # batt_pmax[:, self.inv_batt_idx] *= batt_mask[self.inv_batt_idx]
        # invested_batt_idx = np.where(batt_mask == 1)[0]
        # capex += np.sum(self.batt_capex[invested_batt_idx])

        # compute the capex of the selected investment groups
        capex = np.sum(self.inv_group_capex * x_bin)

        if self.use_monte_carlo:

            lole_array, total_cost_arr, curtailment_arr = reliability_simulation(
                n_sim=self.n_monte_carlo_sim,
                load_profile=self.greedy_dispatch_inputs.load_profile,

                gen_profile=self.greedy_dispatch_inputs.gen_profile,
                gen_p_max=self.greedy_dispatch_inputs.gen_p_max,
                gen_p_min=self.greedy_dispatch_inputs.gen_p_min,
                gen_dispatchable=self.greedy_dispatch_inputs.gen_dispatchable,
                gen_active=gen_active,
                gen_cost=self.greedy_dispatch_inputs.gen_cost,
                gen_mttf=self.gen_mttf,
                gen_mttr=self.gen_mttr,

                batt_active=batt_active,
                batt_p_max_charge=self.greedy_dispatch_inputs.batt_p_max_charge,
                batt_p_max_discharge=self.greedy_dispatch_inputs.batt_p_max_discharge,
                batt_energy_max=self.greedy_dispatch_inputs.batt_energy_max,
                batt_eff_charge=self.greedy_dispatch_inputs.batt_eff_charge,
                batt_eff_discharge=self.greedy_dispatch_inputs.batt_eff_discharge,
                batt_cost=self.greedy_dispatch_inputs.batt_cost,
                batt_soc0=self.greedy_dispatch_inputs.batt_soc0,
                batt_soc_min=self.greedy_dispatch_inputs.batt_soc_min,
                dt=self.greedy_dispatch_inputs.dt,
                force_charge_if_low=True
            )
            lole = np.cumsum(lole_array / (self.n_monte_carlo_sim - 1))[-1]
            total_cost = np.cumsum(total_cost_arr / (self.n_monte_carlo_sim - 1))[-1]
            ndg_curtailment = np.cumsum(curtailment_arr / (self.n_monte_carlo_sim - 1))[-1]

        else:

            (gen_dispatch, batt_dispatch,
             batt_energy, total_cost,
             load_not_supplied, load_shedding,
             ndg_surplus_after_batt,
             ndg_curtailment_per_gen) = greedy_dispatch2(
                load_profile=self.greedy_dispatch_inputs.load_profile,
                gen_profile=self.greedy_dispatch_inputs.gen_profile,
                gen_p_max=self.greedy_dispatch_inputs.gen_p_max,
                gen_p_min=self.greedy_dispatch_inputs.gen_p_min,
                gen_dispatchable=self.greedy_dispatch_inputs.gen_dispatchable,
                gen_active=gen_active,
                gen_cost=self.greedy_dispatch_inputs.gen_cost,
                batt_active=batt_active,
                batt_p_max_charge=self.greedy_dispatch_inputs.batt_p_max_charge,
                batt_p_max_discharge=self.greedy_dispatch_inputs.batt_p_max_discharge,
                batt_energy_max=self.greedy_dispatch_inputs.batt_energy_max,
                batt_eff_charge=self.greedy_dispatch_inputs.batt_eff_charge,
                batt_eff_discharge=self.greedy_dispatch_inputs.batt_eff_discharge,
                batt_cost=self.greedy_dispatch_inputs.batt_cost,
                batt_soc0=self.greedy_dispatch_inputs.batt_soc0,
                batt_soc_min=self.greedy_dispatch_inputs.batt_soc_min,
                dt=self.greedy_dispatch_inputs.dt,
                force_charge_if_low=True
            )
            lole = np.sum(load_not_supplied)
            ndg_curtailment = np.sum(ndg_surplus_after_batt)

        if self.output_f is not None:
            # write header
            self.output_f.write(f"{sum(x)},{lole},{capex}" + ",".join([f"{xi}" for xi in x]) + "\n")

        unit_cost = total_cost / self.total_load

        print(f"n_inv: {sum(x)}, "
              f"lole: {lole}, "
              f"capex: {capex}, "
              f"e cost: {unit_cost}, "
              f"curtailment: {ndg_curtailment}, "
              f"firm penalty {firm_capacity_penalty}")

        if self.use_firm_capacity_penalty:
            return np.array([lole, capex, unit_cost, ndg_curtailment, firm_capacity_penalty])
        else:
            return np.array([lole, capex, unit_cost, ndg_curtailment])
