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

from GridCal.Engine import *


def test():
    fname = os.path.join('..', '..', 'Grids_and_profiles', 'grids', 'IEEE39.gridcal')
    print('Reading...')
    main_circuit = FileOpen(fname).open()
    options = PowerFlowOptions(SolverType.NR, verbose=False,
                               initialize_with_existing_solution=False,
                               multi_core=False, dispatch_storage=True,
                               control_q=ReactivePowerControlMode.NoControl,
                               control_p=True)

    ####################################################################################################################
    # Time Series
    ####################################################################################################################
    print('Running TS...', '')
    start = time.time()

    ts = TimeSeries(grid=main_circuit, options=options)
    ts.run()

    end = time.time()
    dt = end - start
    print('  total', dt, 's')

if __name__ == '__main__':
    import cProfile

    cProfile.runctx('test()', None, locals())