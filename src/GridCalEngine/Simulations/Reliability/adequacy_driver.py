# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import numba as nb
from scipy.sparse import lil_matrix
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.Simulations.Reliability.adequacy_results import AdequacyResults
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Simulations.InvestmentsEvaluation.Methods.NSGA_3 import NSGA_3
from GridCalEngine.Simulations.Reliability.reliability import (reliability_simulation,
                                                               compute_loss_of_load_because_of_lack_of_generation)
from GridCalEngine.Simulations.OPF.simple_dispatch_ts import GreedyDispatchInputs, greedy_dispatch
from GridCalEngine.basic_structures import Vec, IntVec, IntMat


class AdequacyOptimizationOptions:

    def __init__(self,
                 n_ga_evaluations=1000,
                 n_monte_carlo_sim=10000,
                 use_monte_carlo: bool = True,
                 save_file: bool = True):
        self.max_ga_evaluations = n_ga_evaluations
        self.n_monte_carlo_sim = n_monte_carlo_sim
        self.use_monte_carlo = use_monte_carlo
        self.save_file = save_file


@nb.njit(cache=True)
def apply_actives_mask(original_active: IntMat, mask_indices: IntVec, mask: IntVec):
    active = original_active.copy()
    for i in mask_indices:
        active[:, i] = mask[i]
    return active


class AdequacyOptimizationDriver(DriverTemplate):

    def __init__(self, grid: MultiCircuit, options: AdequacyOptimizationOptions):
        """
        ContinuationPowerFlowDriver constructor
        @param circuit: NumericalCircuit instance
        @param pf_options: power flow options instance
        """
        DriverTemplate.__init__(self, grid=grid)

        # voltage stability options
        self.options = options

        self.results = AdequacyResults(investment_groups_names=grid.get_investment_groups_names(),
                                       max_eval=self.options.max_ga_evaluations)

        self.dim = 0  # to be extended

        if self.options.save_file:
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
        inv_group_dict = self.grid.get_investmenst_by_groups_index_dict()

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

        self.__cancel__ = False

    def progress_callback(self, lmbda: float):
        """
        Send progress report
        :param lmbda: lambda value
        :return: None
        """
        self.report_text('Running voltage collapse lambda:' + "{0:.2f}".format(lmbda) + '...')

    def objective_function(self, x: IntVec):
        """

        :param x: array of active investment groups
        :return:
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

        if self.options.use_monte_carlo:

            lole_array = reliability_simulation(
                n_sim=self.options.n_monte_carlo_sim,
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
            lole = lole_array[-1]

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

        self.results.add(
            capex=capex,
            opex=0,
            lole=lole,
            overload_score=0,
            voltage_score=0,
            financial=0,
            objective_function_sum=lole,
            combination=x
        )
        print(f"n_inv: {sum(x)}, lole: {lole}, capex: {capex}")

        if self.output_f is not None:
            # write header
            self.output_f.write(f"{sum(x)},{lole},{capex}" + ",".join([f"{xi}" for xi in x]) + "\n")

        return lole, capex

    def run(self):
        """
        run the voltage collapse simulation
        @return:
        """
        self.tic()

        # --------------------------------------------------------------------------------------------------------------
        # Run the NSGA 3
        # --------------------------------------------------------------------------------------------------------------
        pop_size = 20

        X, obj_values = NSGA_3(
            obj_func=self.objective_function,
            n_partitions=pop_size,
            n_var=self.dim,
            n_obj=2,
            max_evals=self.options.max_ga_evaluations,  # termination
            pop_size=pop_size,
            crossover_prob=0.8,
            mutation_probability=0.1,
            eta=30,
        )

        self.X = X
        self.obj_values = obj_values

        if self.output_f is not None:
            self.output_f.close()

        self.toc()

    def cancel(self):
        self.__cancel__ = True


if __name__ == '__main__':
    import GridCalEngine.api as gce

    fname = "/home/santi/Documentos/Git/eRoots/tonga_planning/model_conversion_and_validation/Tongatapu/models/Tongatapu_v4_2024_ts.gridcal"

    grid_ = gce.open_file(fname)
    options_ = AdequacyOptimizationOptions()
    problem = AdequacyOptimizationDriver(grid=grid_, options=options_)
    problem.run()

    print()
