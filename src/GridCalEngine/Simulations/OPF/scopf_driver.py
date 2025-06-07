# scopf_driver.py
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import List, Dict
from dataclasses import dataclass

from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import LinearMultiContingencies
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.OPF.scopf_results import SCOPFResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from GridCalEngine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCalEngine.enumerations import SimulationTypes, EngineType, SolverType, AcOpfMode
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at

from GridCalEngine.Simulations.SCOPF_GNN.NumericalMethods.scopf import (run_nonlinear_MP_opf, run_nonlinear_SP_scopf)


# @dataclass
# class SCOPFResult:
#     Pg: np.ndarray  # Base‐case generator outputs
#     contingency_outputs: List[Dict]  # One dict per branch and per contingency
#     converged: bool


class SCOPFDriver(TimeSeriesDriverTemplate):
    name = 'Security-constrained optimal power flow'
    tpe = SimulationTypes.SCOPF_run

    def __init__(self,
                 grid: MultiCircuit,
                 pf_options: PowerFlowOptions,
                 scopf_options: OptimalPowerFlowOptions,
                 engine: EngineType = EngineType.GridCal):
        super().__init__(grid=grid,
                         time_indices=None,
                         clustering_results=None,
                         engine=engine,
                         check_time_series=False)

        self.scopf_options = scopf_options
        self.pf_options = pf_options
        # Will hold the final SCOPFResult
        self.results: SCOPFResults = None

    def run(self) -> SCOPFResults:
        import numpy as np
        import time
        from GridCalEngine.Simulations.SCOPF_GNN.NumericalMethods.scopf import (
            run_nonlinear_MP_opf, run_nonlinear_SP_scopf
        )

        self.scopf_options.acopf_mode = AcOpfMode.ACOPFslacks

        print(self.scopf_options.acopf_mode)

        time_start = time.time()
        grid = self.grid
        pf_options = self.pf_options
        opf_slack_options = self.scopf_options

        # Monitor branch loading
        for line in grid.lines:
            line.monitor_loading = True
        for tr in grid.transformers2w:
            tr.monitor_loading = True

        nc = compile_numerical_circuit_at(grid, t_idx=None)

        # Run base OPF
        acopf_results = run_nonlinear_MP_opf(nc=nc,
                                             pf_options=pf_options,
                                             opf_options=opf_slack_options,
                                             pf_init=True,
                                             load_shedding=False)

        Pg_perturbed = acopf_results.Pg

        linear_multiple_contingencies = LinearMultiContingencies(grid, grid.get_contingency_groups())
        prob_cont = 0
        max_iter = 15
        tolerance = 1e-6

        n_con_groups = len(linear_multiple_contingencies.contingency_groups_used)
        n_con_all = n_con_groups * 100
        v_slacks = np.zeros(n_con_all)
        f_slacks = np.zeros(n_con_all)
        W_k_vec = np.zeros(n_con_all)
        Z_k_vec = np.zeros((n_con_all, nc.generator_data.nelm))
        u_j_vec = np.zeros((n_con_all, nc.generator_data.nelm))

        contingency_outputs = []

        for klm in range(max_iter):
            viols = 0
            W_k_local = np.zeros(n_con_groups)
            br_lists = grid.get_branch_lists()
            all_branches = [br for group in br_lists for br in group]

            for ic, contingency_group in enumerate(linear_multiple_contingencies.contingency_groups_used):
                contingencies = linear_multiple_contingencies.contingency_group_dict[contingency_group.idtag]

                if contingencies is None:
                    break

                nc.set_con_or_ra_status(contingencies)

                for cont in contingencies:
                    try:
                        br_idx = next(i for i, br in enumerate(all_branches) if br.name == cont.name)
                        nc.passive_branch_data.active[br_idx] = False

                        islands = nc.split_into_islands()
                        island = max(islands, key=lambda isl: isl.nbus) if len(islands) > 1 else islands[0]

                        indices = island.get_simulation_indices()
                        if len(indices.vd) > 0:
                            slack_sol_cont = run_nonlinear_SP_scopf(
                                nc=island,
                                pf_options=pf_options,
                                opf_options=opf_slack_options,
                                pf_init=False,
                                mp_results=acopf_results,
                                load_shedding=False,
                            )

                            v_slack = max(np.maximum(slack_sol_cont.sl_vmax, slack_sol_cont.sl_vmin))
                            f_slack = max(np.maximum(slack_sol_cont.sl_sf, slack_sol_cont.sl_st))
                            v_slacks[ic] = v_slack
                            f_slacks[ic] = f_slack
                            W_k_local[ic] = slack_sol_cont.W_k

                            if slack_sol_cont.W_k > tolerance:
                                W_k_vec[prob_cont] = slack_sol_cont.W_k
                                Z_k_vec[prob_cont, island.generator_data.original_idx] = slack_sol_cont.Z_k
                                u_j_vec[prob_cont, island.generator_data.original_idx] = slack_sol_cont.u_j
                                prob_cont += 1
                                viols += 1

                            contingency_outputs.append({
                                "contingency_index": int(ic),
                                "W_k": float(slack_sol_cont.W_k),
                                "Z_k": slack_sol_cont.Z_k.tolist(),
                                "u_j": slack_sol_cont.u_j.tolist(),
                                "Pg": acopf_results.Pg.tolist(),
                                "R": [line.R for line in grid.lines],
                                "X": [line.X for line in grid.lines],
                                "B": [line.B for line in grid.lines],
                                "active": [bool(nc.passive_branch_data.active[grid.lines.index(line)]) for line in
                                           grid.lines]
                            })

                        nc.passive_branch_data.active[br_idx] = True

                    except StopIteration:
                        continue

                nc.set_con_or_ra_status(contingencies, revert=True)

            if viols > 0:
                W_k_vec_used = W_k_vec[:prob_cont]
                Z_k_vec_used = Z_k_vec[:prob_cont, :]
                u_j_vec_used = u_j_vec[:prob_cont, :]

            acopf_results = run_nonlinear_MP_opf(nc=nc,
                                                 pf_options=pf_options,
                                                 opf_options=opf_slack_options,
                                                 pf_init=False,
                                                 W_k_vec=W_k_vec_used,
                                                 Z_k_vec=Z_k_vec_used,
                                                 u_j_vec=u_j_vec_used,
                                                 load_shedding=False)

            if viols == 0:
                break

        time_end = time.time()
        print(f"SCOPF completed in {time_end - time_start:.2f} seconds")

        from GridCalEngine.Simulations.OPF.scopf_results import SCOPFResults


        self.results = SCOPFResults(
            bus_names=np.array([bus.name for bus in self.grid.buses]),
            generator_names=np.array([gen.name for gen in self.grid.generators]),
            branch_names=np.array([line.name for line in self.grid.lines]),
            Pg=acopf_results.Pg,
            contingency_outputs=contingency_outputs,
            converged=(viols == 0)
        )

        return self.results
