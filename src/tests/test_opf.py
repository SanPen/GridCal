# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import os

import numpy as np

from GridCalEngine.api import *


def test_opf():
    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')
    print('Reading...')
    main_circuit = FileOpen(fname).open()
    print('Running OPF...', '')
    opf_options = OptimalPowerFlowOptions(verbose=0,
                                          solver=SolverType.LINEAR_OPF)
    opf = OptimalPowerFlowDriver(grid=main_circuit, options=opf_options)
    opf.run()


if __name__ == '__main__':
    test_opf()
