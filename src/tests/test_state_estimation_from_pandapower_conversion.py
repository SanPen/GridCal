# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
from GridCalEngine.IO.others.pandapower_parser import Panda2GridCal, PANDAPOWER_AVAILABLE
from GridCalEngine.Simulations.StateEstimation.state_stimation_driver import StateEstimation
import GridCalEngine as gce


def test_state_estimation_pandapower():
    if PANDAPOWER_AVAILABLE:
        import pandapower
        # tests/data/grids/state-estimation /small_grid_gb_hv_estimate_raw_expected.json
        fname = os.path.join("data", "grids", "state-estimation", "small_grid_gb_hv_estimate_raw_expected.json")
        net_wns = pandapower.from_json(fname)

        # pandapower.to_pickle(net_wns, "small_grid_gb_hv_estimate_raw_expected.p")

        g = Panda2GridCal(net_wns)
        grid = g.get_multicircuit()

        print()
        g.logger.print("PandaPower conversion logs")

        # gce.save_file(grid, 'small_grid_gb_hv_estimate_raw_expected.gridcal')

        pf_res = gce.power_flow(grid)
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


if __name__ == '__main__':
    test_state_estimation_pandapower()
