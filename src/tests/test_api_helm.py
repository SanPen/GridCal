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

from GridCal.Engine.IO.file_handler import FileOpen
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import SolverType
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions, PowerFlowDriver
from tests.print_power_flow_results import print_power_flow_results


def test_api_helm():
    np.set_printoptions(precision=4)
    fname = os.path.join('..', '..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')
    grid = FileOpen(fname).open()

    print('\n\n', grid.name)

    # print('Ybus:\n', grid.circuits[0].power_flow_input.Ybus.todense())
    options = PowerFlowOptions(SolverType.HELM, verbose=False, tolerance=1e-9)
    power_flow = PowerFlowDriver(grid, options)
    power_flow.run()

    print_power_flow_results(power_flow)


if __name__ == '__main__':
    test_api_helm()
