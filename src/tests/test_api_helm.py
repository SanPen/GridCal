# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import numpy as np

from VeraGridEngine.IO.file_handler import FileOpen
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions, PowerFlowDriver


def test_api_helm():
    """

    :return:
    """
    np.set_printoptions(precision=4)
    fname = os.path.join('data', 'grids', 'IEEE 30 Bus with storage.xlsx')
    grid = FileOpen(fname).open()

    print('\n\n', grid.name)

    # print('Ybus:\n', grid.circuits[0].power_flow_input.Ybus.todense())
    options = PowerFlowOptions(SolverType.HELM, verbose=False, tolerance=1e-9)
    power_flow = PowerFlowDriver(grid, options)
    power_flow.run()


if __name__ == '__main__':
    test_api_helm()
