# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import os
from multiprocessing import Pool

from GridCal.Engine.IO.file_handler import FileOpen
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import SolverType, multi_island_pf
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions, PowerFlowDriver


def test_api_multi_core_starmap():
    """
    Test the pool.starmap function together with GridCal
    """

    file_name = os.path.join('..', '..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')
    batch_size = 100
    grid = FileOpen(file_name).open()
    print('\n\n', grid.name)

    options = PowerFlowOptions(SolverType.NR, verbose=False)
    power_flow = PowerFlowDriver(grid, options)
    power_flow.run()

    # create instances of the of the power flow simulation given the grid
    print('running...')

    pool = Pool()
    results = pool.starmap(multi_island_pf, [(grid, options, 0)] * batch_size)


if __name__ == '__main__':

    test_api_multi_core_starmap()
