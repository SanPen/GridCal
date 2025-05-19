# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import numpy as np

from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.DataStructures.numerical_circuit import build_branches_C_coo_3
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Simulations.OPF.simple_dispatch_ts import GreedyDispatchInputs, greedy_dispatch
from GridCalEngine.Simulations.Reliability.reliability import reliability_simulation


class ReliabilityStudy(DriverTemplate):

    def __init__(self, grid: MultiCircuit, pf_options: PowerFlowOptions,
                 n_sim: int = 1000000):
        """
        ContinuationPowerFlowDriver constructor
        :param grid: NumericalCircuit instance
        :param pf_options: power flow options instance
        :param n_sim: Number of Monte-Carlo simulations
        """
        DriverTemplate.__init__(self, grid=grid)

        # voltage stability options
        self.pf_options = pf_options

        self.n_sim = n_sim

        self.lole_evolution = np.zeros(n_sim)
        self.lole = np.zeros(n_sim)

        self.greedy_dispatch_inputs = GreedyDispatchInputs(grid=grid,
                                                           time_indices=None,
                                                           logger=self.logger)

        self.__cancel__ = False

    def progress_callback(self, lmbda: float):
        """
        Send progress report
        :param lmbda: lambda value
        :return: None
        """
        self.report_text('Running voltage collapse lambda:' + "{0:.2f}".format(lmbda) + '...')

    def run(self):
        """
        run the voltage collapse simulation
        @return:
        """
        self.tic()

        horizon = self.grid.get_time_number()

        n_gen = self.grid.get_generators_number()

        gen_pmax = np.empty((horizon, n_gen), dtype=float)
        gen_mttf = np.zeros(n_gen)
        gen_mttr = np.zeros(n_gen)
        for k, gen in enumerate(self.grid.generators):
            gen_mttf[k] = gen.mttf
            gen_mttr[k] = gen.mttr
            if gen.enabled_dispatch:
                gen_pmax[:, k] = gen.Snom * gen.active_prof.toarray()
            else:
                gen_pmax[:, k] = gen.P_prof.toarray() * gen.active_prof.toarray()

        # nc = compile_numerical_circuit_at(circuit=self.grid, t_idx=None)
        #
        # i, j, data, n_elm = build_branches_C_coo_3(
        #     bus_active=nc.bus_data.active,
        #     F1=nc.passive_branch_data.F, T1=nc.passive_branch_data.T, active1=nc.passive_branch_data.active,
        #     F2=nc.vsc_data.F, T2=nc.vsc_data.T, active2=nc.vsc_data.active,
        #     F3=nc.hvdc_data.F, T3=nc.hvdc_data.T, active3=nc.hvdc_data.active,
        # )

        # C = sp.coo_matrix((data, (i, j)), shape=(n_elm, nc.bus_data.nbus), dtype=int)
        # A = (C.T @ C).tocsc()

        self.lole = reliability_simulation(
            n_sim=self.n_sim,
            load_profile=self.greedy_dispatch_inputs.load_profile,

            gen_profile=self.greedy_dispatch_inputs.gen_profile,
            gen_p_max=gen_pmax,
            gen_p_min=self.greedy_dispatch_inputs.gen_p_min,
            gen_dispatchable=self.greedy_dispatch_inputs.gen_dispatchable,
            gen_active=self.greedy_dispatch_inputs.gen_active,
            gen_cost=self.greedy_dispatch_inputs.gen_cost,
            gen_mttf=gen_mttf,
            gen_mttr=gen_mttr,

            batt_active=self.greedy_dispatch_inputs.batt_active,
            batt_p_max_charge=self.greedy_dispatch_inputs.batt_p_max_charge,
            batt_p_max_discharge=self.greedy_dispatch_inputs.batt_p_max_discharge,
            batt_energy_max=self.greedy_dispatch_inputs.batt_energy_max,
            batt_eff_charge=self.greedy_dispatch_inputs.batt_eff_charge,
            batt_eff_discharge=self.greedy_dispatch_inputs.batt_eff_discharge,
            batt_soc0=self.greedy_dispatch_inputs.batt_soc0,
            batt_soc_min=self.greedy_dispatch_inputs.batt_soc_min,
            dt=self.greedy_dispatch_inputs.dt,
            force_charge_if_low=True,
            tol=1e-6
        )

        self.lole_evolution = np.cumsum(self.lole) / (np.arange(len(self.lole)) + 1)
        print(f"LOLE: {self.lole.mean()} MWh/year")

        # fig = plt.figure(1)
        # ax1 = fig.add_subplot(211)
        # ax1.plot(worst_gen.sum(axis=1), label='Generation capacity')
        # ax1.plot(load_p.sum(axis=1), label='Load')
        # ax1.set_title("Worst situation")
        # ax1.set_ylabel("MWh")
        # ax1.set_xlabel("Hour of the year")
        # ax1.legend()
        #
        # ax2 = fig.add_subplot(212)
        # ax2.plot(lole_evolution, label='LOLE')
        # ax2.set_title("LOLE evolution")
        # ax2.set_ylabel("MWh")
        # ax2.set_xlabel("Simulation number")
        # ax2.legend()
        #
        # fig.tight_layout()

        self.toc()

    def cancel(self):
        self.__cancel__ = True


if __name__ == '__main__':
    import GridCalEngine.api as gce
    from matplotlib import pyplot as plt

    fname = "/home/santi/Documentos/Git/eRoots/tonga_planning/model_conversion_and_validation/Tongatapu/models/Tongatapu_v4_2024_ts.gridcal"

    grid_ = gce.open_file(fname)
    options_ = PowerFlowOptions()
    problem = ReliabilityStudy(grid=grid_, pf_options=options_, n_sim=1000)
    problem.run()

    plt.plot(problem.lole_evolution)
    plt.show()
