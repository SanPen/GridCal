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

from grid.CircuitOO import *
from multiprocessing import Pool

grid = MultiCircuit()
# fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_300BUS.xls'
# fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_118.xls'
# fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_57BUS.xls'
fname = 'IEEE_30BUS_profiles.xls'
# fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_14.xls'
# fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_39Bus(Islands).xls'
grid.load_file(fname)
grid.compile()

options = PowerFlowOptions(SolverType.NR, verbose=False, robust=False)

####################################################################################################################
# PowerFlow
####################################################################################################################
print('\n\n')
power_flow = PowerFlow(grid, options)
power_flow.run()

print('\n\n', grid.name)
print('\t|V|:', abs(grid.power_flow_results.voltage))
print('\t|Sbranch|:', abs(grid.power_flow_results.Sbranch))
print('\t|loading|:', abs(grid.power_flow_results.loading) * 100)
print('\terr:', grid.power_flow_results.error)
print('\tConv:', grid.power_flow_results.converged)


def caller0(i):  # function to create a copy of the grid and a power flow associated
    grd = grid.copy()
    grd.name = 'grid ' + str(i)
    grd.compile()
    return PowerFlow(grd, options)


def caller1(worker: PowerFlow):  # function to run the instance
    worker.run()
    return worker.grid


def run():
    pool = Pool()
    batch_size = 1000

    # create copies of the grid to run asynchronously
    print('cloning...')
    workers = pool.map(caller0, range(batch_size))

    # run asynchronous power flows on the created copies
    print('running...')
    grids = pool.map(caller1, workers)

    # display the collected results
    for grid_item in grids:
        print('\n\n' + grid_item.name)
        print('\t|V|:', abs(grid_item.power_flow_results.voltage))

if __name__ == '__main__':
    run()
