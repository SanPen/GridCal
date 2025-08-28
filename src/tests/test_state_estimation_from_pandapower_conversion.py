# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os

from VeraGridEngine import power_flow, SolverType
from VeraGridEngine.IO.file_handler import FileOpen
from VeraGridEngine.IO.others.pandapower_parser import Panda2VeraGrid, PANDAPOWER_AVAILABLE
from VeraGridEngine.Simulations.StateEstimation.state_stimation_driver import StateEstimation, StateEstimationOptions


def test_state_estimation_pandapower():
    if PANDAPOWER_AVAILABLE:
        import pandapower
        # tests/data/grids/state-estimation /small_grid_gb_hv_estimate_raw_expected.json
        #fname = os.path.join("src", "tests", "data", "grids", "state-estimation", "small_grid_gb_hv_estimate_raw_expected.json")
        fname = os.path.join("data", "grids", "state-estimation", "small_grid_gb_hv_estimate_raw_expected.json")
        net_wns = pandapower.from_json(fname)

        # pandapower.to_pickle(net_wns, "small_grid_gb_hv_estimate_raw_expected.p")

        g = Panda2VeraGrid(net_wns)
        grid = g.get_multicircuit()

        print()
        g.logger.print("PandaPower conversion logs")

        # gce.save_file(grid, 'small_grid_gb_hv_estimate_raw_expected.gridcal')

        pf_res = power_flow(grid)
        print(pf_res.get_bus_df())
        print(pf_res.get_branch_df())

        for solver in [SolverType.LU,SolverType.GN,SolverType.LM]:
            se_opt = StateEstimationOptions(
                prefer_correct=True,
                fixed_slack=True,
                solver=solver,
                verbose=2,
                run_observability_analyis=True
            )
            se = StateEstimation(circuit=grid, options=se_opt)
            se.run()

            se_res = se.results
            print(se_res.get_bus_df())
            print(se_res.get_branch_df())

            print(f"Converged: {se_res.converged}")
            print(f"Error: {se_res.error}")
            print(f"Iter: {se_res.iterations}")

            se.logger.print("SE Logger:")


def test_network_objects_consistency():
    if PANDAPOWER_AVAILABLE:
        import pandapower
        # tests/data/grids/state-estimation /small_grid_gb_hv_estimate_raw_expected.json
        # fname = os.path.join("src", "tests", "data", "grids", "state-estimation", "small_grid_gb_hv_estimate_raw_expected.json")
        fname_pp = os.path.join("data", "grids", "state-estimation", "without_pre_processing_and_meas.json")
        fname = os.path.join("data", "grids", "state-estimation", "20250605T1315Z_RT_SmallGridTestConfiguration_.zip")
        net_wns = pandapower.from_json(fname_pp)
        if "max_i_ka" not in net_wns.line:
            net_wns.line.loc[:, "max_i_ka"] = 10.

        # pandapower.to_pickle(net_wns, "small_grid_gb_hv_estimate_raw_expected.p")
        file_handler = FileOpen(fname)
        circuit_cim = file_handler.open()

        g = Panda2VeraGrid(net_wns)
        grid = g.get_multicircuit()

        print()
        g.logger.print("PandaPower conversion logs")

        ok, logger = circuit_cim.compare_circuits(grid)

        ok, logger_diff, diff_grid = circuit_cim.differentiate_circuits(grid)
        logger_diff.to_xlsx("grid diff.xlsx")
        # assert ok
        # gce.save_file(grid, 'small_grid_gb_hv_estimate_raw_expected.gridcal')

        pf_res = power_flow(grid)
        print(pf_res.get_bus_df())
        print(pf_res.get_branch_df())

        se = StateEstimation(circuit=grid)
        se.run()

        se_res = se.results
        print(se_res.get_bus_df())
        print(se_res.get_branch_df())

        print(f"Converged: {se_res.converged}")
        print(f"Error: {se_res.error}")
        print(f"Iter: {se_res.iterations}")

        se.logger.print("SE Logger:")

        pf_res_cim =power_flow(circuit_cim)
        print(pf_res_cim.get_bus_df())
        print(pf_res_cim.get_branch_df())

        se_cim = StateEstimation(circuit=circuit_cim)
        se_cim.run()

        se_res_cim = se_cim.results
        print(se_res_cim.get_bus_df())
        print(se_res_cim.get_branch_df())

        print(f"Converged: {se_res_cim.converged}")
        print(f"Error: {se_res_cim.error}")
        print(f"Iter: {se_res_cim.iterations}")


if __name__ == '__main__':
    test_state_estimation_pandapower()
    test_network_objects_consistency()
