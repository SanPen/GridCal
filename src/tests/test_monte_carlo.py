# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import os

import numpy as np

from GridCalEngine.api import *


def test_monte_carlo():
    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')
    print('Reading...')
    main_circuit = FileOpen(fname).open()
    pf_options = PowerFlowOptions(SolverType.NR, verbose=False,
                                  initialize_with_existing_solution=False,
                                  multi_core=False, dispatch_storage=True,
                                  control_q=ReactivePowerControlMode.NoControl,
                                  control_p=True)

    ####################################################################################################################
    # Monte Carlo
    ####################################################################################################################
    print('Running MC...')
    mc_sim = StochasticPowerFlowDriver(main_circuit,
                                       pf_options,
                                       mc_tol=1e-5,
                                       sampling_points=1000)
    mc_sim.run()


if __name__ == '__main__':
    test_monte_carlo()
