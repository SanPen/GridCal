# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List
import numpy as np
import numba as nb
from scipy.sparse import lil_matrix
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.basic_structures import Vec, IntVec, StrVec, IntMat, Mat
from GridCalEngine.Simulations.InvestmentsEvaluation.Problems.black_box_problem_template import BlackBoxProblemTemplate
from GridCalEngine.Simulations.Reliability.reliability import reliability_simulation
from GridCalEngine.Simulations.OPF.simple_dispatch_ts import GreedyDispatchInputs, greedy_dispatch


@nb.njit(cache=True)
def apply_actives_mask(original_active: IntMat, mask_indices: IntVec, mask: IntVec):
    active = original_active.copy()
    for i in mask_indices:
        active[:, i] = mask[i]
    return active


class AdequacyInvestmentProblem(BlackBoxProblemTemplate):

    def __init__(self,
                 grid: MultiCircuit,
                 n_monte_carlo_sim=10000,
                 use_monte_carlo: bool = True,
                 save_file: bool = True):
        """

        :param grid:
        :param n_monte_carlo_sim:
        :param use_monte_carlo:
        :param save_file:
        """
        super().__init__(grid=grid, plot_x_idx=1, plot_y_idx=2)

        # options object
        self.n_monte_carlo_sim = n_monte_carlo_sim
        self.use_monte_carlo = use_monte_carlo
        self.save_file = save_file

        self.x_dim = len(self.grid.investments_groups)

        if self.save_file:
            self.output_f = open("adequacy_output.csv", "w")
        else:
            self.output_f = None

        # --------------------------------------------------------------------------------------------------------------
        # gather problem structures
        # --------------------------------------------------------------------------------------------------------------

        self.greedy_dispatch_inputs = GreedyDispatchInputs(grid=self.grid,
                                                           time_indices=None,
                                                           logger=self.logger)

        nc = compile_numerical_circuit_at(self.grid, t_idx=None)
        self.gen_mttf = nc.generator_data.mttf
        self.gen_mttr = nc.generator_data.mttr
        self.gen_capex = nc.generator_data.capex * nc.generator_data.snom  # CAPEX in $
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

        self.branches_cost = np.array([e.Cost for e in grid.get_branches_wo_hvdc()], dtype=float)

    def n_objectives(self) -> int:
        """
        Number of objectives (size of f)
        :return:
        """
        return 3

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
        return np.array(["LOLE", "CAPEX", "Electricity cost"])

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
        gen_mask = self.dim2gen @ x
        batt_mask = self.dim2batt @ x

        invested_gen_idx = np.where(gen_mask == 1)[0]
        capex = np.sum(self.gen_capex[invested_gen_idx])

        gen_active = apply_actives_mask(original_active=self.greedy_dispatch_inputs.gen_active,
                                        mask_indices=self.inv_gen_idx,
                                        mask=gen_mask)

        batt_active = apply_actives_mask(original_active=self.greedy_dispatch_inputs.batt_active,
                                         mask_indices=self.inv_batt_idx,
                                         mask=batt_mask)

        # batt_pmax = self.greedy_dispatch_inputs.batt_p_max_charge.copy()
        # batt_pmax[:, self.inv_batt_idx] *= batt_mask[self.inv_batt_idx]
        # invested_batt_idx = np.where(batt_mask == 1)[0]
        # capex += np.sum(self.batt_capex[invested_batt_idx])

        if self.use_monte_carlo:

            lole_array, total_cost_arr = reliability_simulation(
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
                batt_soc0=self.greedy_dispatch_inputs.batt_soc0,
                batt_soc_min=self.greedy_dispatch_inputs.batt_soc_min,
                dt=self.greedy_dispatch_inputs.dt,
                force_charge_if_low=True
            )
            lole = np.cumsum(lole_array / (self.n_monte_carlo_sim - 1))[-1]
            total_cost = np.cumsum(total_cost_arr / (self.n_monte_carlo_sim - 1))[-1]
        else:

            (gen_dispatch, batt_dispatch,
             batt_energy, total_cost,
             load_not_supplied, load_shedding) = greedy_dispatch(
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
                batt_soc0=self.greedy_dispatch_inputs.batt_soc0,
                batt_soc_min=self.greedy_dispatch_inputs.batt_soc_min,
                dt=self.greedy_dispatch_inputs.dt,
                force_charge_if_low=True
            )
            lole = np.sum(load_not_supplied)

        print(f"n_inv: {sum(x)}, lole: {lole}, capex: {capex}")

        if self.output_f is not None:
            # write header
            self.output_f.write(f"{sum(x)},{lole},{capex}" + ",".join([f"{xi}" for xi in x]) + "\n")

        return np.array([lole, capex, total_cost])
