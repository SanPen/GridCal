# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.OPF.ac_opf_worker import run_nonlinear_opf
from VeraGridEngine.Simulations.OPF.Formulations.linear_opf_ts import run_linear_opf_ts
from VeraGridEngine.enumerations import AcOpfMode
import numpy as np


def test_linear_vs_nonlinear_ncap():
    """
    IEEE14
    """
    cwd = os.getcwd()

    # Go back two directories
    fname = os.path.join('data', 'grids', 'IEEE 14 zip costs.gridcal')

    grid = gce.FileOpen(fname).open()

    # Nonlinear OPF
    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF,
                                              ips_tolerance=1e-8,
                                              ips_iterations=50,
                                              verbose=0,
                                              acopf_mode=AcOpfMode.ACOPFstd)

    res = run_nonlinear_opf(grid=grid,
                            opf_options=opf_options,
                            plot_error=False,
                            optimize_nodal_capacity=True,
                            nodal_capacity_sign=-1.0,
                            capacity_nodes_idx=np.array([10, 11]))

    res_nl = np.array([5.0114640, 1.693406])
    assert np.allclose(res.nodal_capacity, res_nl, rtol=1e-5)

    # Linear OPF
    res = run_linear_opf_ts(grid=grid,
                            optimize_nodal_capacity=True,
                            time_indices=None,
                            nodal_capacity_sign=-1.0,
                            capacity_nodes_idx=np.array([10, 11]))

    print('P nodal capacity: ', res.nodal_capacity_vars.P)
    print('P generators: ', res.gen_vars.p)
    print('P loads: ', res.load_vars.shedding)
    print('P slacks pos: ', res.branch_vars.flow_slacks_pos)
    print('P slacks neg: ', res.branch_vars.flow_slacks_neg)
    print('')

    # res_l = np.array([4.85736901, 1.52653874])  # old value...

    res_l = np.array([5.655194829207089, 1.634477969392556])

    assert np.allclose(res.nodal_capacity_vars.P, res_l, rtol=1e-5)


if __name__ == "__main__":
    test_linear_vs_nonlinear_ncap()
