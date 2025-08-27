# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os

import numpy as np

from VeraGridEngine.api import *


def test_monte_carlo():
    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')
    print('Reading...')
    main_circuit = FileOpen(fname).open()
    pf_options = PowerFlowOptions(SolverType.NR, verbose=0, control_q=False)

    ####################################################################################################################
    # Monte Carlo
    ####################################################################################################################
    print('Running MC...')
    mc_sim = StochasticPowerFlowDriver(main_circuit, pf_options, mc_tol=1e-5, sampling_points=1000)
    mc_sim.run()


if __name__ == '__main__':
    test_monte_carlo()
